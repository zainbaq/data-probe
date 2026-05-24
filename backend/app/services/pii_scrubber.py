"""
PII scrubber — Presidio wrapper.

Scrubs column top_values before any value reaches the LLM or the report UI.
The scrubber is initialized once per worker process (expensive spaCy model load).
"""
from __future__ import annotations

import copy
import logging
from typing import Any

from app.logging import log_json
from app.services.profiler import ColumnProfile

logger = logging.getLogger(__name__)

_REDACT_TEMPLATE = "[REDACTED:{entity_type}]"


class PIIScrubber:
    def __init__(self) -> None:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        from presidio_anonymizer.entities import OperatorConfig

        self._analyzer = AnalyzerEngine()
        self._anonymizer = AnonymizerEngine()
        self._operator_config = {
            "DEFAULT": OperatorConfig(
                "replace",
                {"new_value": _REDACT_TEMPLATE.format(entity_type="PII")},
            )
        }
        log_json(logger, "pii_scrubber_initialized")

    def scrub_value(self, value: str) -> str:
        if not value or not value.strip():
            return value
        try:
            results = self._analyzer.analyze(text=value, language="en")
            if not results:
                return value

            from presidio_anonymizer.entities import OperatorConfig

            # Build per-entity-type operator configs for accurate redaction labels
            operators = {
                r.entity_type: OperatorConfig(
                    "replace",
                    {"new_value": _REDACT_TEMPLATE.format(entity_type=r.entity_type)},
                )
                for r in results
            }
            anonymized = self._anonymizer.anonymize(
                text=value, analyzer_results=results, operators=operators
            )
            return anonymized.text
        except Exception as e:
            log_json(logger, "pii_scrub_error", error=str(e), value_len=len(value))
            # On uncertainty, redact aggressively
            return _REDACT_TEMPLATE.format(entity_type="UNKNOWN")

    def scrub_profiles(
        self, profiles: dict[str, list[ColumnProfile]]
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Return a deep-copy of the profiles with top_values scrubbed.
        Original ColumnProfile objects are not modified.
        Returns the profiles as dicts (ready for JSON serialization).
        """
        scrubbed: dict[str, list[dict[str, Any]]] = {}

        for table, col_profiles in profiles.items():
            scrubbed[table] = []
            for cp in col_profiles:
                cp_dict = cp.to_dict()
                scrubbed_top = []
                for tv in cp_dict.get("top_values", []):
                    raw_val = tv.get("value")
                    if raw_val is not None:
                        cleaned = self.scrub_value(str(raw_val))
                        scrubbed_top.append({**tv, "value": cleaned})
                    else:
                        scrubbed_top.append(tv)
                cp_dict["top_values"] = scrubbed_top
                scrubbed[table].append(cp_dict)

        return scrubbed
