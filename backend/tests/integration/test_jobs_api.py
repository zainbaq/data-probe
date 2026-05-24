"""
Integration tests for the jobs API.
Arq enqueue is mocked — we test job creation, not job execution.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.dependencies import get_current_user
from app.main import app
from app.models import Job, JobStatus, SourceConnection, SourceType, User


def _make_user():
    return User(
        id="u1",
        clerk_user_id="clerk-u1",
        email="test@test.com",
        created_at=datetime.now(timezone.utc),
    )


def _make_source(user_id: str):
    return SourceConnection(
        id="src1",
        user_id=user_id,
        name="Test CSV",
        source_type=SourceType.CSV,
        file_path="/tmp/test.csv",
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.integration
@pytest.mark.asyncio
class TestJobsAPI:
    async def test_create_job_enqueues_task(self, client, db):
        user = _make_user()
        source = _make_source(user.id)
        db.add(user)
        db.add(source)
        await db.commit()

        app.dependency_overrides[get_current_user] = lambda: user

        with patch("app.api.v1.jobs.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_pool.enqueue_job = AsyncMock()
            mock_pool.aclose = AsyncMock()
            mock_create_pool.return_value = mock_pool

            resp = await client.post(
                "/api/v1/jobs",
                json={"source_connection_id": "src1"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "queued"
        assert data["source_connection_id"] == "src1"
        mock_pool.enqueue_job.assert_awaited_once()

        app.dependency_overrides.clear()

    async def test_create_job_wrong_source_returns_404(self, client, db):
        user = _make_user()
        db.add(user)
        await db.commit()

        app.dependency_overrides[get_current_user] = lambda: user

        resp = await client.post(
            "/api/v1/jobs",
            json={"source_connection_id": "nonexistent"},
        )
        assert resp.status_code == 404

        app.dependency_overrides.clear()
