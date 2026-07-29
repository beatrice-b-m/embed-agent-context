"""Contract tests for the schema-v5 clinical-semantic CLI."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from typing import Any
from unittest.mock import patch

from embed_context.cli import _format_text, build_parser, main


class FakeCatalog:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def summary(self) -> dict[str, Any]:
        self.calls.append(("summary", {}))
        return {
            "schema_version": 5,
            "profiles": ["open-v2"],
            "binding_grains": ["patient", "exam", "imaging_finding"],
            "feature_kinds": ["date", "coded"],
            "domains": ["exam", "pathology"],
            "semantic_relationship_kinds": ["hierarchy", "attribution"],
            "temporal_kinds": ["event_time", "documentation_time"],
            "aggregation_statuses": ["provided", "unresolved"],
            "coverage_statuses": ["supported", "unsupported"],
            "relationship_binding_kinds": ["hierarchy", "projection"],
            "clinical_objects": 3,
            "concepts": 4,
            "semantic_relationships": 2,
            "temporal_semantics": 2,
            "aggregations": 1,
            "guardrails": 2,
            "coverage": 1,
            "vocabularies": 1,
            "sources": 1,
            "contexts": 1,
            "profile_bindings": 1,
            "feature_bindings": 3,
            "tables": 2,
            "relationship_bindings": 1,
        }

    def discover(
        self,
        query: str,
        *,
        profile: str | None = None,
        kinds: tuple[str, ...] | None = None,
        domain: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        arguments = {
            "query": query,
            "profile": profile,
            "kinds": kinds,
            "domain": domain,
            "limit": limit,
        }
        self.calls.append(("discover", arguments))
        filters = {
            "profile": profile,
            "kinds": list(kinds) if kinds else None,
            "domain": domain,
        }
        if query == "unrepresented specimen":
            return {
                "query": query,
                "filters": filters,
                "count": 0,
                "total": 0,
                "matches": [],
                "diagnostics": {
                    "no_catalog_coverage": True,
                    "unsupported_in_profile": ["open-v2"],
                },
            }
        return {
            "query": query,
            "filters": filters,
            "count": 1,
            "total": 2,
            "matches": [
                {
                    "kind": "guardrail",
                    "identifier": "pathology.null-not-negative",
                    "score": 14,
                    "label": "Absent pathology is not negative",
                    "entity": {
                        "id": "pathology.null-not-negative",
                        "statement": "Missing attachment is not benign.",
                    },
                    "match_reasons": [
                        {"field": "search_terms", "terms": ["pathology"]},
                        {"field": "statement", "terms": ["negative"]},
                    ],
                    "matched_terms": ["negative", "pathology"],
                    "unmatched_terms": ["outcome"],
                }
            ],
            "diagnostics": {
                "filters_excluded_matches": 1,
                "unknown_filter_or_vocabulary_value": [],
                "unsupported_in_profile": [],
                "no_catalog_coverage": False,
            },
        }

    def get_clinical_object(self, identifier: str) -> dict[str, Any]:
        return self._exact(
            "get_clinical_object",
            identifier,
            "clinical_object",
            {
                "id": identifier,
                "label": "Imaging finding",
                "definition": "A localized imaging observation.",
                "grain": "imaging_finding",
            },
        )

    def get_feature(
        self,
        identifier: str,
        *,
        include_codes: bool = False,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "get_feature",
                {"identifier": identifier, "include_codes": include_codes},
            )
        )
        result: dict[str, Any] = {
            "kind": "feature",
            "identifier": identifier,
            "feature": {
                "id": identifier,
                "label": "Pathology severity",
                "definition": "An inverse ordered diagnosis group.",
                "kind": "coded",
            },
            "bindings": [{"profile": "open-v2"}],
            "vocabulary": {
                "id": "pathology-severity",
                "completeness": "complete",
                "parsing": "atomic",
            },
        }
        if include_codes:
            result["vocabulary"]["codes"] = {
                "0": "Invasive breast cancer",
                "5": "Non-breast cancer",
            }
        return result

    def get_semantic_relationship(self, identifier: str) -> dict[str, Any]:
        return self._exact(
            "get_semantic_relationship",
            identifier,
            "semantic_relationship",
            {
                "id": identifier,
                "label": "Finding attributed to pathology",
                "kind": "attribution",
                "source_object": "imaging_finding",
                "target_object": "pathology_observation",
                "cardinality": {
                    "targets_per_source": "zero_or_more",
                    "sources_per_target": "zero_or_more",
                },
                "optionality": {
                    "source": "optional",
                    "target": "optional",
                },
                "attribution": "optional_many_to_many",
                "attribution_limitations": [
                    "Attribution may be absent or many-to-many."
                ],
                "temporal_qualification": (
                    "A downstream link does not make pathology available "
                    "at imaging time."
                ),
            },
        )

    def get_temporal_semantic(self, identifier: str) -> dict[str, Any]:
        return self._exact(
            "get_temporal_semantic",
            identifier,
            "temporal_semantic",
            {
                "id": identifier,
                "label": "Pathology report date",
                "meaning": "Documentation time, not a universal diagnosis date.",
                "kind": "documentation_time",
                "objects": ["pathology_observation"],
                "feature_refs": ["pathology.report_date"],
                "relative_to": ["time.procedure-event"],
            },
        )

    def get_aggregation(self, identifier: str) -> dict[str, Any]:
        return self._exact(
            "get_aggregation",
            identifier,
            "aggregation",
            {
                "id": identifier,
                "label": "Exam severity",
                "description": "Minimum code reflects maximum severity.",
                "status": "provided",
                "source_object": "pathology_observation",
                "target_object": "imaging_exam",
                "source_concept": "pathology.severity",
                "result_concept": "pathology.exam_severity",
                "method": "minimum represented numeric code",
                "ordering": "inverse severity",
            },
        )

    def get_guardrail(self, identifier: str) -> dict[str, Any]:
        if identifier == "missing.guardrail":
            raise ValueError("guardrail was not found")
        return self._exact(
            "get_guardrail",
            identifier,
            "guardrail",
            {
                "id": identifier,
                "label": "Null is not negative",
                "statement": "Absent attached pathology is not a benign outcome.",
                "rationale": "Attachment and follow-up may be incomplete.",
            },
        )

    def get_coverage(self, identifier: str) -> dict[str, Any]:
        return self._exact(
            "get_coverage",
            identifier,
            "coverage",
            {
                "id": identifier,
                "label": "Specimen collection time",
                "description": "Not represented by a supported open-v2 feature.",
                "status": "unsupported",
            },
        )

    def lookup_code(
        self,
        feature_or_vocabulary: str,
        code: str,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "lookup_code",
                {
                    "feature_or_vocabulary": feature_or_vocabulary,
                    "code": code,
                },
            )
        )
        return {
            "vocabulary": "pathology-severity",
            "code": code,
            "meaning": "Invasive breast cancer",
        }

    def get_profile_table(self, profile: str, table: str) -> dict[str, Any]:
        self.calls.append(
            ("get_profile_table", {"profile": profile, "table": table})
        )
        return {
            "kind": "profile_table",
            "identifier": f"{profile}:{table}",
            "table": {
                "id": table,
                "label": table,
                "grain": "exam",
                "keys": [
                    {
                        "id": "exam.accession",
                        "columns": ["acc_anon"],
                        "kind": "natural",
                        "uniqueness": "unique",
                        "completeness": "complete",
                    }
                ],
            },
            "relationship_bindings": {
                "outgoing": [{"id": "exam.patient"}],
                "incoming": [],
            },
        }

    def get_relationship_binding(self, identifier: str) -> dict[str, Any]:
        self.calls.append(
            ("get_relationship_binding", {"identifier": identifier})
        )
        return {
            "kind": "relationship_binding",
            "identifier": identifier,
            "relationship_binding": self._relationship_binding(identifier),
        }

    def search_relationship_bindings(
        self,
        *,
        profile: str | None = None,
        table: str | None = None,
        source_table: str | None = None,
        target_table: str | None = None,
        kind: str | None = None,
        semantic_relationship: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        arguments = {
            "profile": profile,
            "table": table,
            "source_table": source_table,
            "target_table": target_table,
            "kind": kind,
            "semantic_relationship": semantic_relationship,
            "limit": limit,
        }
        self.calls.append(("search_relationship_bindings", arguments))
        return {
            "filters": {
                key: value for key, value in arguments.items() if key != "limit"
            },
            "count": 1,
            "total": 1,
            "matches": [self._relationship_binding("exam.patient")],
        }

    def _exact(
        self,
        method: str,
        identifier: str,
        entity_key: str,
        entity: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append((method, {"identifier": identifier}))
        return {
            "kind": entity_key,
            "identifier": identifier,
            entity_key: entity,
        }

    @staticmethod
    def _relationship_binding(identifier: str) -> dict[str, Any]:
        return {
            "id": identifier,
            "profile": "open-v2",
            "kind": "hierarchy",
            "source": {"table": "exam_level_anon", "columns": ["empi_anon"]},
            "target": {"table": "clinical_data_anon", "columns": ["empi_anon"]},
            "cardinality": {
                "targets_per_source": "one",
                "sources_per_target": "zero_or_more",
            },
            "join_hazards": ["Patient identifiers are profile-scoped."],
        }


class CatalogCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = FakeCatalog()

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("embed_context.cli.load_catalog", return_value=self.catalog),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            status = main(arguments)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_validate_json_uses_stable_envelope_and_v5_inventory(self) -> None:
        status, stdout, stderr = self.run_cli(
            "--format",
            "json",
            "validate",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        envelope = json.loads(stdout)
        self.assertEqual(envelope["ok"], True)
        self.assertEqual(envelope["command"], "validate")
        self.assertEqual(envelope["data"]["schema_version"], 5)
        self.assertEqual(envelope["data"]["clinical_objects"], 3)
        self.assertEqual(envelope["data"]["relationship_bindings"], 1)

    def test_validate_text_exposes_semantic_and_binding_facets(self) -> None:
        status, stdout, stderr = self.run_cli("validate")

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertIn("3 clinical objects", stdout)
        self.assertIn("2 semantic relationships", stdout)
        self.assertIn("1 relationship bindings", stdout)
        self.assertIn("temporal kinds: event_time, documentation_time", stdout)

    def test_discover_passes_clinical_filters_and_explains_matches(self) -> None:
        status, stdout, stderr = self.run_cli(
            "discover",
            "negative pathology outcome",
            "--profile",
            "open-v2",
            "--kind",
            "guardrail",
            "--kind",
            "coverage",
            "--domain",
            "pathology",
            "--limit",
            "1",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            self.catalog.calls[-1],
            (
                "discover",
                {
                    "query": "negative pathology outcome",
                    "profile": "open-v2",
                    "kinds": ("guardrail", "coverage"),
                    "domain": "pathology",
                    "limit": 1,
                },
            ),
        )
        self.assertIn(
            "pathology.null-not-negative [guardrail] — "
            "Absent pathology is not negative",
            stdout,
        )
        self.assertIn("matched by search_terms: pathology", stdout)
        self.assertIn("unmatched terms: outcome", stdout)
        self.assertIn("diagnostics:", stdout)
        self.assertIn("filters excluded matches: 1", stdout)

    def test_discover_json_preserves_diagnostics(self) -> None:
        status, stdout, stderr = self.run_cli(
            "--format",
            "json",
            "discover",
            "unrepresented specimen",
            "--profile",
            "open-v2",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        data = json.loads(stdout)["data"]
        self.assertEqual(data["matches"], [])
        self.assertTrue(data["diagnostics"]["no_catalog_coverage"])
        self.assertEqual(
            data["diagnostics"]["unsupported_in_profile"],
            ["open-v2"],
        )

    def test_discover_allows_a_filter_without_free_text(self) -> None:
        status, stdout, stderr = self.run_cli(
            "--format",
            "json",
            "discover",
            "--kind",
            "guardrail",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            self.catalog.calls[-1],
            (
                "discover",
                {
                    "query": "",
                    "profile": None,
                    "kinds": ("guardrail",),
                    "domain": None,
                    "limit": 50,
                },
            ),
        )
        self.assertEqual(json.loads(stdout)["data"]["count"], 1)

    def test_exact_semantic_commands_dispatch_to_distinct_getters(self) -> None:
        cases = (
            ("object", "imaging_finding", "get_clinical_object"),
            ("semantic-relationship", "finding.pathology", "get_semantic_relationship"),
            ("temporal", "pathology.report_date", "get_temporal_semantic"),
            ("aggregation", "pathology.exam_severity", "get_aggregation"),
            ("guardrail", "pathology.null-not-negative", "get_guardrail"),
            ("coverage", "pathology.specimen_time", "get_coverage"),
        )
        for command, identifier, expected_method in cases:
            with self.subTest(command=command):
                self.catalog.calls.clear()
                status, stdout, stderr = self.run_cli(command, identifier)
                self.assertEqual(status, 0)
                self.assertEqual(stderr, "")
                self.assertEqual(
                    self.catalog.calls,
                    [(expected_method, {"identifier": identifier})],
                )
                self.assertIn(identifier, stdout)

    def test_feature_includes_codes_only_when_requested(self) -> None:
        status, stdout, stderr = self.run_cli(
            "feature",
            "pathology.severity",
            "--include-codes",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            self.catalog.calls[-1],
            (
                "get_feature",
                {
                    "identifier": "pathology.severity",
                    "include_codes": True,
                },
            ),
        )
        self.assertIn("codes:", stdout)
        self.assertIn("0 — Invasive breast cancer", stdout)

    def test_text_semantic_getters_expose_choices_and_limitations(self) -> None:
        _, relationship, _ = self.run_cli(
            "semantic-relationship",
            "clinical.finding-pathology-observation",
        )
        self.assertIn("targets_per_source=zero_or_more", relationship)
        self.assertIn("optionality: source=optional; target=optional", relationship)
        self.assertIn("attribution: optional_many_to_many", relationship)
        self.assertIn("temporal qualification:", relationship)
        self.assertIn("many-to-many", relationship)

        _, temporal, _ = self.run_cli(
            "temporal",
            "time.pathology-report-documentation",
        )
        self.assertIn("documentation_time", temporal)
        self.assertIn("features: pathology.report_date", temporal)
        self.assertIn("relative to: time.procedure-event", temporal)

        _, aggregation, _ = self.run_cli(
            "aggregation",
            "aggregation.pathology-severity-to-exam",
        )
        self.assertIn(
            "grain transition: pathology_observation → imaging_exam",
            aggregation,
        )
        self.assertIn("method: minimum represented numeric code", aggregation)
        self.assertIn("ordering: inverse severity", aggregation)

        _, guardrail, _ = self.run_cli(
            "guardrail",
            "guardrail.null-pathology-not-negative",
        )
        self.assertIn("Absent attached pathology is not a benign outcome", guardrail)
        self.assertIn(
            "rationale: Attachment and follow-up may be incomplete",
            guardrail,
        )

    def test_code_preserves_exact_code_string(self) -> None:
        status, stdout, stderr = self.run_cli(
            "code",
            "pathology-severity",
            "MiXeD,Value",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            self.catalog.calls[-1],
            (
                "lookup_code",
                {
                    "feature_or_vocabulary": "pathology-severity",
                    "code": "MiXeD,Value",
                },
            ),
        )
        self.assertIn("MiXeD,Value", stdout)

    def test_profile_table_is_explicitly_a_binding_surface(self) -> None:
        status, stdout, stderr = self.run_cli(
            "profile-table",
            "open-v2",
            "exam_level_anon",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertIn("open-v2:exam_level_anon", stdout)
        self.assertIn("exam.accession — acc_anon", stdout)
        self.assertIn("relationship bindings: 1 outgoing, 0 incoming", stdout)

    def test_relationship_binding_commands_preserve_physical_filters(self) -> None:
        status, stdout, stderr = self.run_cli(
            "relationship-binding",
            "exam.patient",
        )
        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertIn(
            "exam_level_anon(empi_anon) → clinical_data_anon(empi_anon)",
            stdout,
        )
        self.assertIn("hazards:", stdout)

        self.catalog.calls.clear()
        status, stdout, stderr = self.run_cli(
            "--format",
            "json",
            "relationship-bindings",
            "--profile",
            "open-v2",
            "--table",
            "exam_level_anon",
            "--source-table",
            "exam_level_anon",
            "--target-table",
            "clinical_data_anon",
            "--kind",
            "hierarchy",
            "--semantic-relationship",
            "clinical.exam-patient",
            "--limit",
            "2",
        )
        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            self.catalog.calls,
            [
                (
                    "search_relationship_bindings",
                    {
                        "profile": "open-v2",
                        "table": "exam_level_anon",
                        "source_table": "exam_level_anon",
                        "target_table": "clinical_data_anon",
                        "kind": "hierarchy",
                        "semantic_relationship": "clinical.exam-patient",
                        "limit": 2,
                    },
                )
            ],
        )
        self.assertEqual(json.loads(stdout)["data"]["count"], 1)

    def test_legacy_and_ambiguous_commands_are_removed(self) -> None:
        parser = build_parser()
        for command in (
            "search",
            "table",
            "relationship",
            "relationships",
            "context",
            "contexts",
            "pattern",
            "patterns",
            "get",
        ):
            with self.subTest(command=command), self.assertRaises(SystemExit):
                with redirect_stderr(io.StringIO()):
                    parser.parse_args([command, "anything"])

    def test_json_error_is_machine_readable(self) -> None:
        status, stdout, stderr = self.run_cli(
            "--format",
            "json",
            "guardrail",
            "missing.guardrail",
        )

        self.assertEqual(status, 2)
        self.assertEqual(stderr, "")
        envelope = json.loads(stdout)
        self.assertEqual(envelope["ok"], False)
        self.assertEqual(envelope["command"], "guardrail")
        self.assertEqual(envelope["error"]["type"], "value")
        self.assertIn("was not found", envelope["error"]["message"])

    def test_text_formatters_tolerate_minimal_documented_envelopes(self) -> None:
        self.assertEqual(
            _format_text(
                "coverage",
                {
                    "kind": "coverage",
                    "identifier": "coverage.minimal",
                    "coverage": {
                        "id": "coverage.minimal",
                        "label": "Minimal coverage",
                    },
                },
            ),
            "coverage.minimal — Minimal coverage",
        )
        self.assertEqual(
            _format_text(
                "relationship-bindings",
                {"count": 0, "total": 0, "matches": []},
            ),
            "No relationship bindings.",
        )

    def test_text_exact_getter_surfaces_navigation_and_provenance(self) -> None:
        rendered = _format_text(
            "guardrail",
            {
                "kind": "guardrail",
                "identifier": "pathology.null-not-negative",
                "guardrail": {
                    "id": "pathology.null-not-negative",
                    "label": "Null is not negative",
                },
                "related": {
                    "features": ["pathology.severity"],
                    "clinical_objects": [{"id": "pathology_observation"}],
                },
                "provenance": {
                    "claims": [{"id": "null-semantics"}],
                    "sources": {"open-v2.schema": {"title": "Schema"}},
                },
            },
        )

        self.assertIn("related:", rendered)
        self.assertIn("features: pathology.severity", rendered)
        self.assertIn("clinical_objects: pathology_observation", rendered)
        self.assertIn("provenance:", rendered)
        self.assertIn("claims: null-semantics", rendered)
        self.assertIn("sources: open-v2.schema", rendered)

    def test_text_discovery_renders_structured_diagnostic_categories(self) -> None:
        rendered = _format_text(
            "discover",
            {
                "count": 0,
                "total": 0,
                "matches": [],
                "diagnostics": [
                    {
                        "category": "no_catalog_coverage",
                        "message": (
                            "No indexed entity covers these terms; this does "
                            "not establish absence from EMBED."
                        ),
                    }
                ],
            },
        )

        self.assertIn("diagnostics:", rendered)
        self.assertIn(
            "no catalog coverage: No indexed entity covers these terms",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
