"""
Integration tests for the sources API.
Clerk token verification is mocked out.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.dependencies import get_current_user
from app.main import app
from app.models import User


def _mock_user() -> User:
    return User(id="user-1", clerk_user_id="clerk-1", email="test@test.com")


@pytest.mark.integration
@pytest.mark.asyncio
class TestSourcesAPI:
    async def test_list_sources_empty(self, client, db):
        app.dependency_overrides[get_current_user] = lambda: _mock_user()
        # Need to insert user first
        from app.models import User
        from datetime import datetime, timezone
        user = User(id="user-1", clerk_user_id="clerk-1", email="test@test.com",
                    created_at=datetime.now(timezone.utc))
        db.add(user)
        await db.commit()

        resp = await client.get("/api/v1/sources")
        assert resp.status_code == 200
        assert resp.json() == []
        app.dependency_overrides.clear()

    async def test_upload_file_source(self, client, db, tmp_path):
        from datetime import datetime, timezone
        user = User(id="user-1", clerk_user_id="clerk-1", email="test@test.com",
                    created_at=datetime.now(timezone.utc))
        db.add(user)
        await db.commit()
        app.dependency_overrides[get_current_user] = lambda: user

        # Create a minimal CSV in tmp_path but the upload dir may not exist
        import os
        from app.config import settings

        # Override upload dir to tmp
        with patch.object(settings, "upload_dir", str(tmp_path)):
            csv_content = b"id,name\n1,Alice\n2,Bob\n"
            resp = await client.post(
                "/api/v1/sources/upload",
                files={"file": ("test.csv", csv_content, "text/csv")},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["source_type"] == "csv"
        assert data["name"] == "test.csv"
        app.dependency_overrides.clear()
