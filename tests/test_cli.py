"""Tests for stable JSON envelopes and concise CLI text."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from embed_context.cli import main
from tests.catalog_fixture import write_catalog


class CatalogCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.catalog_path = write_catalog(
            Path(self.temporary.name) / "catalog.json"
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
                "schema_version": 1,
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
                "concepts": 2,
                "bindings": 3,
                "vocabularies": 1,
            },
        )

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
