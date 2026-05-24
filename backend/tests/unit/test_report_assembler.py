"""
Tests for the deterministic report assembler.
Verifies that known findings produce expected markdown structure.
"""
import pytest

from app.services.claude_analyzer import (
    EnrichmentFinding,
    ExecutiveSummary,
    QualityFinding,
)
from app.services.relationship_inferer import InferredRelationship
from app.services.report_assembler import ReportAssembler


def _quality(
    code: str,
    severity: str,
    fix_risk: str,
    sql_fix: str | None = None,
    investigation_query: str | None = None,
) -> QualityFinding:
    return QualityFinding(
        code=code,
        table="orders",
        column="status",
        severity=severity,
        fix_risk=fix_risk,
        description=f"Test finding {code}",
        evidence={"null_pct": 0.23},
        sql_fix=sql_fix,
        investigation_query=investigation_query,
    )


@pytest.mark.unit
class TestReportAssembler:
    def _assemble(self, quality=None, enrichment=None, relationships=None):
        assembler = ReportAssembler()
        return assembler.assemble(
            summary=ExecutiveSummary(
                health_score=72,
                summary="Test summary.",
                critical_count=0,
                high_count=1,
                medium_count=2,
                low_count=0,
            ),
            quality_findings=quality or [],
            enrichment_findings=enrichment or [],
            relationships=relationships or [],
            source_name="test_db",
            source_type="postgres",
        )

    def test_header_present(self):
        md = self._assemble()
        assert "DataProbe Report" in md
        assert "test_db" in md

    def test_health_score_present(self):
        md = self._assemble()
        assert "72" in md
        assert "Health Score" in md

    def test_severity_icons_in_findings(self):
        findings = [
            _quality("NULL_EXCESS", "critical", "green", "UPDATE orders SET status='ok' WHERE 1=1"),
            _quality("TYPE_MISMATCH", "high", "yellow"),
            _quality("CARDINALITY", "medium", "red", investigation_query="SELECT * FROM orders LIMIT 10"),
        ]
        md = self._assemble(quality=findings)
        assert "🔴" in md   # critical icon
        assert "🟠" in md   # high icon
        assert "🟡" in md   # medium icon

    def test_sql_fix_in_code_block(self):
        findings = [_quality("NULL_EXCESS", "high", "green", sql_fix="UPDATE orders SET status='ok'")]
        md = self._assemble(quality=findings)
        assert "```sql" in md
        assert "UPDATE orders" in md

    def test_red_finding_no_runnable_fix(self):
        findings = [_quality("DEDUP", "high", "red", sql_fix=None, investigation_query="SELECT id FROM orders GROUP BY id HAVING COUNT(*) > 1")]
        md = self._assemble(quality=findings)
        assert "Advisory" in md
        assert "Investigation Query" in md

    def test_runbook_phases_present(self):
        findings = [
            _quality("A", "high", "green", sql_fix="UPDATE orders SET x=1"),
            _quality("B", "medium", "yellow", sql_fix="UPDATE orders SET y=2"),
            _quality("C", "low", "red", investigation_query="SELECT * FROM orders LIMIT 10"),
        ]
        md = self._assemble(quality=findings)
        assert "Phase 1" in md
        assert "Phase 2" in md
        assert "Phase 3" in md

    def test_no_findings_graceful(self):
        md = self._assemble()
        assert "No quality issues detected" in md
        assert "No enrichment opportunities" in md

    def test_relationships_section(self):
        rels = [
            InferredRelationship(
                from_table="orders",
                from_column="user_id",
                to_table="users",
                to_column="id",
                confidence=1.0,
                evidence=["declared_fk"],
                is_declared=True,
            )
        ]
        md = self._assemble(relationships=rels)
        assert "Relationship Map" in md
        assert "orders" in md
        assert "user_id" in md
