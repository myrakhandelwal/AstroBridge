"""Asynchronous job manager for long-running query workloads."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from astrobridge.state_store import connect_sqlite, resolve_state_db_path

logger = logging.getLogger(__name__)


class JobRecord(BaseModel):
    """Status and result payload for one background job."""

    job_id: str
    status: str = Field(..., description="queued|running|completed|failed")
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[dict[str, Any]] = None


class JobManager:
    """Run orchestrator requests asynchronously and track lifecycle state."""

    def __init__(self, db_path: Optional[str] = None, persist: bool = True) -> None:
        self.persist = persist
        self._jobs: dict[str, JobRecord] = {}
        self._tasks: set[asyncio.Task] = set()  # Track active tasks
        self._lock = threading.Lock()

        if self.persist:
            self._db_path = resolve_state_db_path(db_path)
            self._init_db()
        else:
            self._db_path = None

    def _connect(self) -> sqlite3.Connection:
        if self._db_path is None:
            raise RuntimeError("Persistence is disabled")
        return connect_sqlite(self._db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    error TEXT,
                    result_json TEXT
                )
                """
            )
            conn.commit()

    @staticmethod
    def _record_to_tuple(record: JobRecord) -> tuple:
        return (
            record.job_id,
            record.status,
            record.created_at.isoformat(),
            record.started_at.isoformat() if record.started_at else None,
            record.finished_at.isoformat() if record.finished_at else None,
            record.error,
            json.dumps(record.result) if record.result is not None else None,
        )

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=(datetime.fromisoformat(row["started_at"]) if row["started_at"] else None),
            finished_at=(datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None),
            error=row["error"],
            result=json.loads(row["result_json"]) if row["result_json"] else None,
        )

    def _save_record(self, record: JobRecord) -> None:
        if not self.persist:
            return
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                    INSERT INTO jobs (
                        job_id,
                        status,
                        created_at,
                        started_at,
                        finished_at,
                        error,
                        result_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_id) DO UPDATE SET
                        status=excluded.status,
                        started_at=excluded.started_at,
                        finished_at=excluded.finished_at,
                        error=excluded.error,
                        result_json=excluded.result_json
                    """,
                self._record_to_tuple(record),
            )
            conn.commit()

    async def submit_query(self, request: Any, orchestrator: Any) -> str:
        job_id = str(uuid.uuid4())
        record = JobRecord(
            job_id=job_id,
            status="queued",
            created_at=datetime.utcnow(),
        )
        self._jobs[job_id] = record
        self._save_record(record)
        
        # Create task and store reference for tracking
        task = asyncio.create_task(self._run_query(job_id, request, orchestrator))
        self._tasks.add(task)
        
        # Add callback to handle task completion and cleanup
        def _task_done_callback(t: asyncio.Task) -> None:
            self._tasks.discard(t)
            if t.cancelled():
                logger.info("Query job %s was cancelled", job_id)
            elif t.exception() is not None:
                logger.error(
                    "Query job %s raised an exception: %s",
                    job_id,
                    t.exception(),
                    exc_info=t.exception(),
                )
        
        task.add_done_callback(_task_done_callback)
        return job_id

    async def _run_query(self, job_id: str, request: Any, orchestrator: Any) -> None:
        record = self._jobs[job_id]
        record.status = "running"
        record.started_at = datetime.utcnow()
        self._save_record(record)

        try:
            response = await orchestrator.execute_query(request)
            record.status = "completed"
            record.result = response.model_dump()
        except Exception as exc:  # pragma: no cover - defensive catch
            record.status = "failed"
            record.error = str(exc)
        finally:
            record.finished_at = datetime.utcnow()
            self._save_record(record)

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        record = self._jobs.get(job_id)
        if record is not None:
            return record

        if not self.persist:
            return None

        with self._lock, self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                    SELECT job_id, status, created_at, started_at, finished_at, error, result_json
                    FROM jobs
                    WHERE job_id = ?
                    """,
                (job_id,),
            ).fetchone()

        if row is None:
            return None
        record = self._record_from_row(row)
        self._jobs[job_id] = record
        return record

    def get_result(self, job_id: str) -> Optional[dict[str, Any]]:
        record = self._jobs.get(job_id)
        if record is None:
            return None
        return record.result
