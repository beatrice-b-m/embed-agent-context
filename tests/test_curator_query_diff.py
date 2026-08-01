"""Focused tests for deterministic draft discovery comparison."""

from __future__ import annotations

import unittest

from embed_context import load_catalog
from embed_context.curator.query_diff import (
    compare_discovery_results,
    run_discovery_comparison,
)


def match(identifier: str, score: int, **values: object) -> dict[str, object]:
    return {
        "kind": "feature",
        "identifier": identifier,
        "score": score,
        "match_reasons": values.pop("match_reasons", []),
        "profile_coverage": values.pop("profile_coverage", []),
        "qualifications": values.pop("qualifications", []),
        "active_revisions": values.pop("active_revisions", []),
        "implementation_bindings": values.pop(
            "implementation_bindings", {}
        ),
        **values,
    }


class CuratorQueryDiffTests(unittest.TestCase):
    def test_compare_reports_add_remove_rank_score_and_metadata_changes(self) -> None:
        baseline = {
            "count": 2,
            "matches": [
                match(
                    "alpha",
                    20,
                    match_reasons=[{"field": "label", "terms": ["alpha"]}],
                    qualifications=[{"id": "q.old"}],
                    implementation_bindings={
                        "profile": "open-v2",
                        "feature_bindings": [{"id": "binding.old"}],
                    },
                ),
                match("removed", 10),
            ],
            "diagnostics": [{"category": "old"}],
        }
        draft = {
            "count": 2,
            "matches": [
                match("added", 30),
                match(
                    "alpha",
                    25,
                    match_reasons=[{"field": "definition", "terms": ["alpha"]}],
                    qualifications=[{"id": "q.new"}],
                    active_revisions=[{"id": "revision.new"}],
                    implementation_bindings={
                        "profile": "open-v2",
                        "feature_bindings": [{"id": "binding.new"}],
                    },
                ),
            ],
            "diagnostics": [],
        }

        result = compare_discovery_results(baseline, draft)
        changes = {item["identifier"]: item for item in result["changes"]}

        self.assertEqual(changes["added"]["status"], "added")
        self.assertEqual(changes["removed"]["status"], "removed")
        changed = changes["alpha"]
        self.assertEqual(changed["rank"]["delta"], 1)
        self.assertEqual(changed["score"]["delta"], 5)
        self.assertIn("match_reasons", changed)
        self.assertIn("qualifications", changed)
        self.assertIn("active_revisions", changed)
        self.assertEqual(
            changed["implementation_binding_inventory"]["draft"][
                "feature_bindings"
            ],
            ["binding.new"],
        )
        self.assertTrue(result["diagnostics_changed"])
        self.assertEqual(
            [item["identifier"] for item in result["changes"]],
            ["added", "alpha", "removed"],
        )

    def test_equal_results_have_no_changes(self) -> None:
        result = {
            "count": 1,
            "matches": [match("same", 5)],
            "diagnostics": [],
        }

        comparison = compare_discovery_results(result, result)

        self.assertEqual(comparison["changed_count"], 0)
        self.assertEqual(comparison["unchanged_count"], 1)
        self.assertIsNone(comparison["diagnostics"])

    def test_run_uses_real_catalog_discovery_and_labels_revision(self) -> None:
        catalog = load_catalog()

        result = run_discovery_comparison(
            catalog,
            catalog,
            query="pathology severity",
            profile="open-v2",
            limit=3,
            draft_revision=7,
        )

        self.assertEqual(result["draft_revision"], 7)
        self.assertTrue(result["comparison"]["available"])
        self.assertEqual(result["comparison"]["changed_count"], 0)
        self.assertEqual(result["baseline"], result["draft"])

    def test_missing_valid_draft_keeps_baseline_available(self) -> None:
        result = run_discovery_comparison(
            load_catalog(), query="pathology", limit=1, draft_revision=4
        )

        self.assertIsNotNone(result["baseline"])
        self.assertIsNone(result["draft"])
        self.assertEqual(
            result["comparison"],
            {"available": False, "reason": "no_valid_draft"},
        )
        self.assertEqual(result["draft_revision"], 4)

    def test_duplicate_match_keys_are_rejected(self) -> None:
        duplicate = {
            "matches": [match("same", 2), match("same", 1)],
            "diagnostics": [],
        }
        with self.assertRaisesRegex(ValueError, "duplicate"):
            compare_discovery_results(duplicate, {"matches": []})


if __name__ == "__main__":
    unittest.main()
