"""Tests for stable JSON envelopes and concise CLI text."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from embed_context.cli import main
from tests.catalog_fixture import synthetic_catalog, write_catalog


class CatalogCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        data = synthetic_catalog()
        data["relationships"].append(
            {
                "id": "wide.tissue-density-projection",
                "profile": "open-v2",
                "kind": "projection",
                "source": {
                    "table": "combined_anon",
                    "columns": ["tissueden"],
                    "completeness": "unknown",
                },
                "target": {
                    "table": "exam_level_anon",
                    "columns": ["tissueden"],
                },
                "cardinality": {
                    "targets_per_source": "unknown",
                    "sources_per_target": "unknown",
                },
                "evidence": ["release_schema"],
                "caveats": ["Projection equality is not established."],
                "join_hazards": [
                    "Do not use the wide projection as an authoritative join."
                ],
            }
        )
        self.catalog_path = write_catalog(
            Path(self.temporary.name) / "catalog.json",
            data,
        )

    def run_cli(self, *arguments: str):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(
                ["--catalog", str(self.catalog_path), *arguments]
            )
        return status, stdout.getvalue(), stderr.getvalue()

    def test_validate_json_uses_stable_envelope(self) -> None:
        status, stdout, stderr = self.run_cli(
            "--format", "json", "validate"
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        envelope = json.loads(stdout)
        self.assertEqual(envelope["ok"], True)
        self.assertEqual(envelope["command"], "validate")
        self.assertEqual(
            envelope["data"],
            {
                "schema_version": 3,
                "profiles": ["open-v2"],
                "grains": [
                    "patient",
                    "exam",
                    "breast_side",
                    "imaging_finding",
                    "pathology_finding",
                    "report",
                    "risk_assessment",
                    "wide_row",
                ],
                "feature_kinds": [
                    "identifier",
                    "date",
                    "categorical",
                    "coded",
                    "flag",
                    "numeric",
                    "text",
                    "aggregate",
                    "model_output",
                    "technical",
                ],
                "domains": [
                    "identity",
                    "demographics",
                    "social_determinants_of_health",
                    "exam",
                    "breast_side",
                    "imaging",
                    "mammography",
                    "ultrasound",
                    "mri",
                    "pathology",
                    "procedure",
                    "report",
                    "risk",
                    "temporal",
                    "workflow",
                    "technical",
                ],
                "context_kinds": [
                    "clinical_workflow",
                    "data_representation",
                    "interpretation_guardrail",
                    "known_issue",
                ],
                "context_scopes": [
                    "general_clinical",
                    "embed_general",
                    "profile_specific",
                ],
                "source_kinds": [
                    "maintainer_confirmed",
                    "release_schema",
                    "release_legend",
                    "supporting_internal",
                    "public_documentation",
                ],
                "source_locator_kinds": [
                    "url",
                    "repository_path",
                    "logical_artifact",
                ],
                "claim_statuses": [
                    "verified",
                    "reconciled",
                    "unverified",
                    "unresolved",
                    "contradicted",
                ],
                "concepts": 2,
                "bindings": 3,
                "vocabularies": 1,
                "tables": 2,
                "relationships": 1,
                "sources": 1,
                "contexts": 1,
            },
        )

    def test_validate_text_includes_structural_and_context_counts(self) -> None:
        status, stdout, stderr = self.run_cli("validate")

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertIn("2 tables, 1 relationship", stdout)
        self.assertIn("1 source, 1 context", stdout)

    def test_get_text_is_concise(self) -> None:
        status, stdout, stderr = self.run_cli(
            "get", "exam_level_anon.tissueden"
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertIn(
            "exam_level_anon.tissueden — Breast tissue density", stdout
        )
        self.assertIn("open-v2 · exam · int8 · canonical", stdout)
        self.assertNotIn('"ok"', stdout)

    def test_get_text_includes_codes_only_when_requested(self) -> None:
        status, stdout, stderr = self.run_cli(
            "get", "exam_level_anon.tissueden", "--include-codes"
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertIn("codes:\n", stdout)
        self.assertIn("  2 — Scattered fibroglandular densities", stdout)

    def test_search_help_lists_controlled_filters(self) -> None:
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as raised, redirect_stdout(stdout):
            main(["search", "--help"])

        self.assertEqual(raised.exception.code, 0)
        help_text = stdout.getvalue()
        self.assertIn("social_determinants_of_health", help_text)
        self.assertIn("pathology_finding", help_text)
        self.assertIn("model_output", help_text)

    def test_search_json_passes_filters_and_limit(self) -> None:
        status, stdout, _ = self.run_cli(
            "--format",
            "json",
            "search",
            "density",
            "--table",
            "exam_level_anon",
            "--domain",
            "mammography",
            "--limit",
            "1",
        )

        self.assertEqual(status, 0)
        data = json.loads(stdout)["data"]
        self.assertEqual(data["count"], 1)
        self.assertEqual(
            data["matches"][0]["identifier"],
            "exam.tissue_density",
        )
        self.assertEqual(
            data["matches"][0]["bindings"][0]["identifier"],
            "exam_level_anon.tissueden",
        )

    def test_code_text_preserves_exact_code(self) -> None:
        status, stdout, stderr = self.run_cli(
            "code", "exam.tissue_density", "2"
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            stdout,
            "exam.tissue_density 2 — Scattered fibroglandular densities\n",
        )

    def test_table_json_returns_core_result(self) -> None:
        status, stdout, stderr = self.run_cli(
            "--format",
            "json",
            "table",
            "open-v2",
            "exam_level_anon",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        envelope = json.loads(stdout)
        self.assertEqual(envelope["command"], "table")
        data = envelope["data"]
        self.assertEqual(data["kind"], "table")
        self.assertEqual(data["identifier"], "open-v2:exam_level_anon")
        self.assertEqual(data["table"]["keys"][0]["id"], "exam.accession")
        self.assertEqual(
            [item["id"] for item in data["relationships"]["incoming"]],
            ["wide.tissue-density-projection"],
        )

    def test_table_text_summarizes_keys_and_relationships(self) -> None:
        status, stdout, stderr = self.run_cli(
            "table", "open-v2", "exam_level_anon"
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertIn("open-v2:exam_level_anon — exam table", stdout)
        self.assertIn(
            "exam.accession — acc_anon (natural; unique; complete)",
            stdout,
        )
        self.assertIn("relationships: 0 outgoing, 1 incoming", stdout)

    def test_relationship_json_returns_core_result(self) -> None:
        status, stdout, stderr = self.run_cli(
            "--format",
            "json",
            "relationship",
            "wide.tissue-density-projection",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        envelope = json.loads(stdout)
        self.assertEqual(envelope["command"], "relationship")
        self.assertEqual(envelope["data"]["kind"], "relationship")
        self.assertEqual(
            envelope["data"]["relationship"]["source"]["table"],
            "combined_anon",
        )

    def test_relationship_text_preserves_direction_and_hazards(self) -> None:
        status, stdout, stderr = self.run_cli(
            "relationship", "wide.tissue-density-projection"
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertIn("wide.tissue-density-projection — projection", stdout)
        self.assertIn(
            "combined_anon(tissueden) → exam_level_anon(tissueden)",
            stdout,
        )
        self.assertIn("unknown target(s) per source", stdout)
        self.assertIn("hazards:", stdout)

    def test_relationships_help_lists_directional_and_kind_filters(self) -> None:
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as raised, redirect_stdout(stdout):
            main(["relationships", "--help"])

        self.assertEqual(raised.exception.code, 0)
        help_text = stdout.getvalue()
        self.assertIn("--source-table", help_text)
        self.assertIn("--target-table", help_text)
        self.assertIn("hierarchy", help_text)
        self.assertIn("projection", help_text)
        self.assertIn("reference", help_text)

    def test_relationships_json_passes_filters_and_limit(self) -> None:
        status, stdout, stderr = self.run_cli(
            "--format",
            "json",
            "relationships",
            "--profile",
            "open-v2",
            "--table",
            "combined_anon",
            "--source-table",
            "combined_anon",
            "--target-table",
            "exam_level_anon",
            "--kind",
            "projection",
            "--limit",
            "1",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        data = json.loads(stdout)["data"]
        self.assertEqual(
            data["filters"],
            {
                "profile": "open-v2",
                "table": "combined_anon",
                "source_table": "combined_anon",
                "target_table": "exam_level_anon",
                "kind": "projection",
            },
        )
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["total"], 1)
        self.assertEqual(
            data["matches"][0]["id"],
            "wide.tissue-density-projection",
        )

    def test_relationships_text_handles_matches_and_empty_results(self) -> None:
        status, stdout, stderr = self.run_cli("relationships")

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertIn("wide.tissue-density-projection — projection", stdout)

        status, stdout, stderr = self.run_cli(
            "relationships", "--table", "missing_table"
        )
        self.assertEqual(status, 0)
        self.assertEqual(stdout, "No relationships.\n")
        self.assertEqual(stderr, "")

    def test_relationship_errors_use_existing_error_envelopes(self) -> None:
        status, stdout, stderr = self.run_cli(
            "--format",
            "json",
            "relationship",
            "missing.relationship",
        )

        self.assertEqual(status, 2)
        self.assertEqual(stderr, "")
        envelope = json.loads(stdout)
        self.assertEqual(envelope["command"], "relationship")
        self.assertEqual(envelope["error"]["type"], "not_found")

    def test_context_json_returns_exact_core_result(self) -> None:
        status, stdout, stderr = self.run_cli(
            "--format",
            "json",
            "context",
            "open-v2.density-interpretation",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        envelope = json.loads(stdout)
        self.assertEqual(envelope["command"], "context")
        self.assertEqual(envelope["data"]["kind"], "context")
        self.assertEqual(
            envelope["data"]["context"]["claims"][0]["id"],
            "coded-feature",
        )
        self.assertEqual(
            list(envelope["data"]["sources"]),
            ["open-v2.release-schema"],
        )

    def test_context_text_includes_claim_status_and_source(self) -> None:
        status, stdout, stderr = self.run_cli(
            "context",
            "open-v2.density-interpretation",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertIn(
            "open-v2.density-interpretation — "
            "Density interpretation boundary",
            stdout,
        )
        self.assertIn(
            "profile_specific · interpretation_guardrail · open-v2",
            stdout,
        )
        self.assertIn(
            "[verified] coded-feature — The synthetic density field",
            stdout,
        )
        self.assertIn(
            "open-v2.release-schema — Synthetic open-v2 release schema",
            stdout,
        )

    def test_contexts_help_lists_controlled_and_reference_filters(self) -> None:
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as raised, redirect_stdout(stdout):
            main(["contexts", "--help"])

        self.assertEqual(raised.exception.code, 0)
        help_text = stdout.getvalue()
        self.assertIn("clinical_workflow", help_text)
        self.assertIn("profile_specific", help_text)
        self.assertIn("contradicted", help_text)
        self.assertIn("--concept", help_text)
        self.assertIn("--relationship", help_text)
        self.assertIn("--source", help_text)

    def test_contexts_json_passes_all_filters_and_limit(self) -> None:
        status, stdout, stderr = self.run_cli(
            "--format",
            "json",
            "contexts",
            "density",
            "--kind",
            "interpretation_guardrail",
            "--scope",
            "profile_specific",
            "--profile",
            "open-v2",
            "--domain",
            "mammography",
            "--concept",
            "exam.tissue_density",
            "--table",
            "exam_level_anon",
            "--status",
            "verified",
            "--source",
            "open-v2.release-schema",
            "--limit",
            "1",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        data = json.loads(stdout)["data"]
        self.assertEqual(
            data["filters"],
            {
                "kind": "interpretation_guardrail",
                "scope": "profile_specific",
                "profile": "open-v2",
                "domain": "mammography",
                "concept": "exam.tissue_density",
                "table": "exam_level_anon",
                "relationship": None,
                "status": "verified",
                "source": "open-v2.release-schema",
            },
        )
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["total"], 1)
        self.assertEqual(
            data["matches"][0]["identifier"],
            "open-v2.density-interpretation",
        )
        self.assertEqual(
            [claim["id"] for claim in data["matches"][0]["matching_claims"]],
            ["coded-feature"],
        )

    def test_contexts_json_passes_relationship_filter(self) -> None:
        data = synthetic_catalog()
        data["relationships"].append(
            {
                "id": "wide.tissue-density-projection",
                "profile": "open-v2",
                "kind": "projection",
                "source": {
                    "table": "combined_anon",
                    "columns": ["tissueden"],
                    "completeness": "unknown",
                },
                "target": {
                    "table": "exam_level_anon",
                    "columns": ["tissueden"],
                },
                "cardinality": {
                    "targets_per_source": "unknown",
                    "sources_per_target": "unknown",
                },
                "evidence": ["release_schema"],
                "caveats": [],
                "join_hazards": [],
            }
        )
        data["contexts"][
            "open-v2.density-interpretation"
        ]["related_relationships"] = ["wide.tissue-density-projection"]
        relationship_catalog = write_catalog(
            Path(self.temporary.name) / "relationship-context.json",
            data,
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(
                [
                    "--catalog",
                    str(relationship_catalog),
                    "--format",
                    "json",
                    "contexts",
                    "--relationship",
                    "wide.tissue-density-projection",
                ]
            )

        self.assertEqual(status, 0)
        self.assertEqual(stderr.getvalue(), "")
        result = json.loads(stdout.getvalue())["data"]
        self.assertEqual(result["count"], 1)
        self.assertEqual(
            result["filters"]["relationship"],
            "wide.tissue-density-projection",
        )

    def test_contexts_text_handles_matches_and_empty_results(self) -> None:
        status, stdout, stderr = self.run_cli(
            "contexts",
            "--status",
            "verified",
        )

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        self.assertIn(
            "open-v2.density-interpretation — "
            "Density interpretation boundary",
            stdout,
        )
        self.assertIn(
            "[verified] coded-feature — The synthetic density field",
            stdout,
        )

        status, stdout, stderr = self.run_cli(
            "contexts",
            "pathology",
        )
        self.assertEqual(status, 0)
        self.assertEqual(stdout, "No contexts.\n")
        self.assertEqual(stderr, "")

    def test_context_errors_use_existing_error_envelopes(self) -> None:
        status, stdout, stderr = self.run_cli(
            "--format",
            "json",
            "context",
            "missing.context",
        )

        self.assertEqual(status, 2)
        self.assertEqual(stderr, "")
        envelope = json.loads(stdout)
        self.assertEqual(envelope["command"], "context")
        self.assertEqual(envelope["error"]["type"], "not_found")

    def test_contexts_require_query_or_filter(self) -> None:
        status, stdout, stderr = self.run_cli("contexts")

        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn(
            "provide a query or at least one context search filter",
            stderr,
        )

    def test_json_error_is_machine_readable(self) -> None:
        status, stdout, stderr = self.run_cli(
            "--format", "json", "get", "missing.feature"
        )

        self.assertEqual(status, 2)
        self.assertEqual(stderr, "")
        envelope = json.loads(stdout)
        self.assertEqual(envelope["ok"], False)
        self.assertEqual(envelope["command"], "get")
        self.assertEqual(envelope["error"]["type"], "not_found")
        self.assertIn("was not found", envelope["error"]["message"])

    def test_text_error_goes_to_stderr(self) -> None:
        status, stdout, stderr = self.run_cli("search")

        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("provide a query", stderr)


if __name__ == "__main__":
    unittest.main()
