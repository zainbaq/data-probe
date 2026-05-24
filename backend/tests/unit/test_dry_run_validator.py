"""
Dry-run validator tests using DuckDB in-memory (FileAdapter path).
Verifies green→yellow downgrade on failure.
"""
import pytest

from app.services.adapters.file import FileAdapter
from app.services.claude_analyzer import QualityFinding
from app.services.dry_run_validator import DryRunValidator


def _make_finding(
    fix_risk: str,
    sql_fix: str | None,
    code: str = "TEST",
) -> QualityFinding:
    return QualityFinding(
        code=code,
        table="main_data",
        column="val",
        severity="medium",
        fix_risk=fix_risk,
        description="Test finding",
        evidence={},
        sql_fix=sql_fix,
        investigation_query=None,
    )


@pytest.fixture
def csv_adapter(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("id,val\n1,foo\n2,bar\n3,\n")
    return FileAdapter(str(csv_file))


@pytest.mark.unit
@pytest.mark.asyncio
class TestDryRunValidator:
    async def test_green_valid_sql_passes(self, csv_adapter):
        finding = _make_finding("green", "UPDATE main_data SET val = 'baz' WHERE val IS NULL")
        validator = DryRunValidator()
        results = await validator.validate_quality(csv_adapter, [finding])
        f = results[0]
        assert f.dry_run_result is not None
        assert f.dry_run_result["passed"] is True
        # Green finding keeps its fix after passing
        assert f.sql_fix is not None
        await csv_adapter.close()

    async def test_green_invalid_sql_downgraded_to_yellow(self, csv_adapter):
        finding = _make_finding(
            "green",
            "UPDATE nonexistent_table SET x = 1",  # table doesn't exist
        )
        validator = DryRunValidator()
        results = await validator.validate_quality(csv_adapter, [finding])
        f = results[0]
        # Should be downgraded to yellow and sql_fix cleared
        assert f.fix_risk == "yellow"
        assert f.sql_fix is None
        await csv_adapter.close()

    async def test_yellow_invalid_sql_cleared(self, csv_adapter):
        finding = _make_finding(
            "yellow",
            "UPDATE nonexistent_table SET x = 1",
        )
        validator = DryRunValidator()
        results = await validator.validate_quality(csv_adapter, [finding])
        f = results[0]
        # Yellow stays yellow but sql_fix is cleared
        assert f.fix_risk == "yellow"
        assert f.sql_fix is None
        await csv_adapter.close()

    async def test_red_finding_skipped(self, csv_adapter):
        finding = _make_finding("red", None)
        finding.investigation_query = "SELECT * FROM main_data"
        validator = DryRunValidator()
        results = await validator.validate_quality(csv_adapter, [finding])
        f = results[0]
        # Red findings are never validated, pass through unchanged
        assert f.fix_risk == "red"
        assert f.sql_fix is None
        assert f.dry_run_result is None
        await csv_adapter.close()
