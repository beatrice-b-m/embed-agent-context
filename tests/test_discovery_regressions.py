"""Regression coverage for the reviewed clinical-first discovery prompts."""

from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence
from typing import Any

from embed_context import load_catalog


class DiscoveryReviewRegressionTests(unittest.TestCase):
    """Keep safety-relevant semantics prominent without fixing score values."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_catalog()

    def discover_ids(self, query: str, *, window: int = 8) -> list[str]:
        result = self.catalog.discover(
            query,
            profile="open-v2",
            limit=window,
        )
        return [match["identifier"] for match in result["matches"]]

    def assert_in_window(
        self,
        identifier: str,
        identifiers: Sequence[str],
        *,
        window: int,
    ) -> None:
        self.assertIn(
            identifier,
            identifiers[:window],
            f"{identifier!r} was not in the top {window}: {identifiers}",
        )

    def assert_before_if_present(
        self,
        preferred: str,
        misleading: str,
        identifiers: Sequence[str],
    ) -> None:
        self.assertIn(
            preferred,
            identifiers,
            f"{preferred!r} was absent from results: {identifiers}",
        )
        if misleading in identifiers:
            self.assertLess(
                identifiers.index(preferred),
                identifiers.index(misleading),
                f"{preferred!r} should precede {misleading!r}: {identifiers}",
            )

    @staticmethod
    def constraint_ids(result: Mapping[str, Any], category: str) -> set[str]:
        constraints = result.get("constraints", {})
        entries = constraints.get(category, ()) if isinstance(
            constraints, Mapping
        ) else ()
        return {
            str(entry.get("id", entry.get("identifier")))
            for entry in entries
            if isinstance(entry, Mapping)
            and (entry.get("id") or entry.get("identifier"))
        }

    def test_nearest_subsequent_ipsilateral_cancer_is_patient_scoped(
        self,
    ) -> None:
        identifiers = self.discover_ids(
            "nearest subsequent ipsilateral cancer",
        )

        self.assert_in_window(
            "guardrail.longitudinal-search-is-patient-scoped",
            identifiers,
            window=5,
        )
        self.assert_in_window(
            "clinical.patient-pathology-observation",
            identifiers,
            window=8,
        )
        self.assert_before_if_present(
            "guardrail.longitudinal-search-is-patient-scoped",
            "clinical.exam-pathology-observation",
            identifiers,
        )

        relationship = self.catalog.get_semantic_relationship(
            "clinical.patient-pathology-observation"
        )
        paths = relationship["related"]["relationship_binding_paths"]
        self.assertTrue(paths)
        self.assertTrue(
            any(len(path["relationship_bindings"]) >= 2 for path in paths)
        )
        self.assertIn(
            "guardrail.longitudinal-search-is-patient-scoped",
            self.constraint_ids(
                relationship,
                "high_priority_guardrails",
            ),
        )

    def test_most_recent_prior_cancer_outranks_same_accession_semantics(
        self,
    ) -> None:
        identifiers = self.discover_ids("most recent prior cancer")

        self.assert_in_window(
            "guardrail.longitudinal-search-is-patient-scoped",
            identifiers,
            window=5,
        )
        self.assert_in_window(
            "clinical.patient-pathology-observation",
            identifiers,
            window=8,
        )
        self.assert_before_if_present(
            "guardrail.longitudinal-search-is-patient-scoped",
            "aggregation.pathology-severity-to-exam",
            identifiers,
        )

    def test_procedure_report_exam_fallback_surfaces_non_substitution(
        self,
    ) -> None:
        identifiers = self.discover_ids(
            "procedure report exam fallback coalesce",
        )

        self.assert_in_window(
            "guardrail.timestamps-answer-different-questions",
            identifiers,
            window=4,
        )
        self.assert_in_window(
            "coverage.open-v2.downstream-availability-time",
            identifiers,
            window=8,
        )
        for misleading in (
            "time.exam-event",
            "time.procedure-event",
            "time.pathology-report-documentation",
        ):
            self.assert_before_if_present(
                "guardrail.timestamps-answer-different-questions",
                misleading,
                identifiers,
            )

        temporal = self.catalog.get_temporal_semantic(
            "time.pathology-report-documentation"
        )
        self.assertIn(
            "guardrail.timestamps-answer-different-questions",
            self.constraint_ids(temporal, "unsupported_substitutions"),
        )

    def test_risk_probability_calibration_surfaces_unresolved_readiness(
        self,
    ) -> None:
        identifiers = self.discover_ids(
            "risk probability calibration Brier score",
        )

        self.assert_in_window(
            "guardrail.risk-probability-readiness",
            identifiers,
            window=4,
        )
        self.assert_in_window(
            "coverage.open-v2.risk-probability-calibration-readiness",
            identifiers,
            window=6,
        )
        self.assert_before_if_present(
            "guardrail.risk-probability-readiness",
            "risk.ibis_ten_year",
            identifiers,
        )

        feature = self.catalog.get_feature("risk.ibis_ten_year")
        self.assertIn(
            "coverage.open-v2.risk-probability-calibration-readiness",
            feature["related"]["coverage"],
        )
        self.assertIn(
            "coverage.open-v2.risk-probability-calibration-readiness",
            self.constraint_ids(feature, "unresolved_claims"),
        )
        self.assertIn(
            "guardrail.risk-probability-readiness",
            self.constraint_ids(feature, "high_priority_guardrails"),
        )
        self.assertIn(
            "open-v2.risk-context",
            self.constraint_ids(feature, "relevant_contexts"),
        )
        coverage = self.catalog.get_coverage(
            "coverage.open-v2.risk-probability-calibration-readiness"
        )
        self.assertIn(
            "coverage.open-v2.risk-probability-calibration-readiness",
            self.constraint_ids(coverage, "unresolved_claims"),
        )

    def test_one_row_per_finding_surfaces_bounded_clinical_identity(
        self,
    ) -> None:
        identifiers = self.discover_ids("one row per finding finding key")

        self.assert_in_window(
            "imaging.finding_number",
            identifiers,
            window=4,
        )
        self.assert_before_if_present(
            "imaging.finding_number",
            "technical.pandas_index",
            identifiers,
        )

        finding = self.catalog.get_clinical_object("imaging_finding")
        bindings = finding["related"]["object_bindings"]
        identities = [
            binding["instance_identity"]
            for binding in bindings
            if binding.get("instance_identity")
        ]
        self.assertTrue(identities)
        self.assertTrue(
            any(
                identity["columns"] == ["acc_anon", "numfind"]
                and identity["rows_per_instance"] == "one_or_more"
                and identity["longitudinal_identity"] is False
                for identity in identities
            )
        )
        self.assertTrue(
            any(
                any(
                    exception["representation"] == "-9"
                    for exception in identity["reserved_exceptions"]
                )
                for identity in identities
            )
        )

    def test_laterality_null_side_and_bside_remain_role_specific(
        self,
    ) -> None:
        identifiers = self.discover_ids("laterality null side bside")

        self.assert_in_window("breast.side", identifiers, window=6)
        self.assert_in_window(
            "pathology.biopsy_side",
            identifiers,
            window=6,
        )
        self.assert_in_window(
            "clinical.side-finding",
            identifiers,
            window=8,
        )

        finding_side = self.catalog.get_feature(
            "open-v2:imaging_findings_anon.side"
        )
        biopsy_side = self.catalog.get_feature(
            "open-v2:pathology_findings_anon.bside"
        )
        finding_meanings = {
            item["meaning"]
            for item in finding_side["binding"]["occurrence_interpretations"]
            if item["representation"] == "null"
        }
        biopsy_meanings = {
            item["meaning"]
            for item in biopsy_side["binding"]["occurrence_interpretations"]
            if item["representation"] == "null"
        }
        self.assertTrue(
            any("bilateral" in item.lower() for item in finding_meanings)
        )
        self.assertTrue(
            any("unknown" in item.lower() for item in biopsy_meanings)
        )
        self.assertFalse(
            any(
                item.lower().strip() == "bilateral"
                for item in biopsy_meanings
            )
        )

    def test_finding_pathology_severity_aggregate_requires_policy(
        self,
    ) -> None:
        identifiers = self.discover_ids(
            "finding pathology severity aggregate",
        )

        self.assert_in_window(
            "aggregation.pathology-severity-to-finding",
            identifiers,
            window=4,
        )
        self.assert_in_window(
            "guardrail.explicit-attribution-policy",
            identifiers,
            window=8,
        )
        for misleading in (
            "aggregation.pathology-severity-to-side",
            "aggregation.pathology-severity-to-exam",
        ):
            self.assert_before_if_present(
                "aggregation.pathology-severity-to-finding",
                misleading,
                identifiers,
            )

        aggregation = self.catalog.get_aggregation(
            "aggregation.pathology-severity-to-finding"
        )
        self.assertEqual(
            aggregation["aggregation"]["status"],
            "analyst_defined",
        )
        self.assertIn(
            "aggregation.pathology-severity-to-finding",
            self.constraint_ids(
                aggregation,
                "analyst_choices_required",
            ),
        )

    def test_represented_binary_cancer_endpoint_preserves_claim_boundary(
        self,
    ) -> None:
        identifiers = self.discover_ids(
            "represented binary cancer endpoint",
        )

        self.assert_in_window(
            "guardrail.incomplete-outcome-capture",
            identifiers,
            window=4,
        )
        self.assert_in_window(
            "coverage.open-v2.outcome-capture",
            identifiers,
            window=8,
        )
        self.assert_before_if_present(
            "guardrail.incomplete-outcome-capture",
            "pathology.severity",
            identifiers,
        )

        guardrail = self.catalog.get_guardrail(
            "guardrail.incomplete-outcome-capture"
        )
        self.assertEqual(
            guardrail["guardrail"]["category"],
            "interpretation_limit",
        )
        self.assertIn(
            "guardrail.incomplete-outcome-capture",
            self.constraint_ids(
                guardrail,
                "high_priority_guardrails",
            ),
        )
        statement = guardrail["guardrail"]["statement"].lower()
        self.assertIn("no represented", statement)
        self.assertIn("cancer-free", statement)


if __name__ == "__main__":
    unittest.main()
