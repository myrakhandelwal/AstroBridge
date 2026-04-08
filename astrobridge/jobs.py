"""Asynchronous job manager for long-running query workloads."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class JobRecord(BaseModel):
    """Status and result payload for one background job."""

    job_id: str
    status: str = Field(..., description="queued|running|completed|failed")
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class JobManager:
    """Run orchestrator requests asynchronously and track lifecycle state."""

    def __init__(self) -> None:
        self._jobs: Dict[str, JobRecord] = {}

    async def submit_query(self, request: Any, orchestrator: Any) -> str:
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = JobRecord(
            job_id=job_id,
            status="queued",
            created_at=datetime.utcnow(),
        )
        asyncio.create_task(self._run_query(job_id, request, orchestrator))
        return job_id

    async def _run_query(self, job_id: str, request: Any, orchestrator: Any) -> None:
        record = self._jobs[job_id]
        record.status = "running"
        record.started_at = datetime.utcnow()

        try:
            response = await orchestrator.execute_query(request)
            record.status = "completed"
            record.result = response.model_dump()
        except Exception as exc:  # pragma: no cover - defensive catch
            record.status = "failed"
            record.error = str(exc)
        finally:
            record.finished_at = datetime.utcnow()

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self._jobs.get(job_id)

    def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        record = self._jobs.get(job_id)
        if record is None:
            return None
        return record.result
