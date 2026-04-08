"""Tests for persisted analytics and job state."""

from datetime import datetime

from astrobridge.analytics import AnalyticsEvent, AnalyticsStore
from astrobridge.jobs import JobManager, JobRecord


def test_analytics_persists_across_instances(tmp_path):
    db_path = tmp_path / "state.db"

    store1 = AnalyticsStore(db_path=str(db_path), persist=True)
    store1.clear()
    store1.record(
        AnalyticsEvent(
            event_type="query_executed",
            query_type="name",
            success=True,
            latency_ms=9.1,
            user_level="beginner",
        )
    )

    store2 = AnalyticsStore(db_path=str(db_path), persist=True)
    summary = store2.summary()

    assert summary["total_events"] == 1
    assert summary["event_type_counts"]["query_executed"] == 1
    assert summary["query_success_rate"] == 1.0


def test_job_manager_reads_persisted_job(tmp_path):
    db_path = tmp_path / "state.db"
    manager1 = JobManager(db_path=str(db_path), persist=True)

    record = JobRecord(
        job_id="job-123",
        status="completed",
        created_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        result={"status": "success", "query_type": "name"},
    )
    manager1._save_record(record)

    manager2 = JobManager(db_path=str(db_path), persist=True)
    loaded = manager2.get_job("job-123")

    assert loaded is not None
    assert loaded.status == "completed"
    assert loaded.result is not None
    assert loaded.result["query_type"] == "name"
