"""
Security-critical tests for the SQL allowlist guard.
Every test here is a boundary case that must pass.
"""
import pytest

from app.utils.sql_guard import assert_read_only_sql


@pytest.mark.unit
class TestReadOnlyGuard:
    def test_select_passes(self):
        assert_read_only_sql("SELECT * FROM users")

    def test_select_with_where_passes(self):
        assert_read_only_sql("SELECT id, email FROM users WHERE id = '1' LIMIT 100")

    def test_select_count_passes(self):
        assert_read_only_sql("SELECT COUNT(*) FROM orders")

    def test_information_schema_passes(self):
        assert_read_only_sql(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'users'"
        )

    def test_insert_blocked(self):
        with pytest.raises(ValueError, match="Non-read"):
            assert_read_only_sql("INSERT INTO users (email) VALUES ('x@x.com')")

    def test_update_blocked(self):
        with pytest.raises(ValueError, match="Non-read"):
            assert_read_only_sql("UPDATE users SET email = 'x' WHERE id = '1'")

    def test_delete_blocked(self):
        with pytest.raises(ValueError, match="Non-read"):
            assert_read_only_sql("DELETE FROM users WHERE id = '1'")

    def test_drop_blocked(self):
        with pytest.raises(ValueError, match="Non-read"):
            assert_read_only_sql("DROP TABLE users")

    def test_create_blocked(self):
        with pytest.raises(ValueError, match="Non-read"):
            assert_read_only_sql("CREATE TABLE evil (id int)")

    def test_truncate_blocked(self):
        with pytest.raises(ValueError, match="Non-read"):
            assert_read_only_sql("TRUNCATE TABLE users")

    def test_pg_shadow_blocked(self):
        with pytest.raises(ValueError, match="blocked"):
            assert_read_only_sql("SELECT * FROM pg_shadow")

    def test_pg_authid_blocked(self):
        with pytest.raises(ValueError, match="blocked"):
            assert_read_only_sql("SELECT * FROM pg_authid")

    def test_empty_sql_rejected(self):
        with pytest.raises(ValueError, match="Empty"):
            assert_read_only_sql("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValueError, match="Empty"):
            assert_read_only_sql("   ")

    def test_multiple_statements_with_dml_blocked(self):
        with pytest.raises(ValueError, match="Non-read"):
            assert_read_only_sql("SELECT 1; DROP TABLE users;")
