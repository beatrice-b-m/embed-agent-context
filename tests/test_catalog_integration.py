"""Acceptance contracts for the checked-in schema-v5 semantic catalog."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from embed_context import load_catalog


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "catalog" / "catalog.json"


class ClinicalSemanticCatalogAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.catalog = load_catalog(CATALOG_PATH)

    def test_v5_models_the_clinical_graph_without_analysis_patterns(self) -> None:
        self.assertEqual(self.catalog.schema_version, 5)
        self.assertNotIn("analysis_pattern_statuses", self.raw)
        self.assertNotIn("analysis_patterns", self.raw)
        self.assertFalse(hasattr(self.catalog, "analysis_patterns"))
        self.assertFalse(hasattr(self.catalog, "get_analysis_pattern"))
        for legacy_name in (
            "bindings",
            "tables",
            "relationships",
            "get_table",
            "get_relationship",
            "search_relationships",
        ):
            with self.subTest(legacy_api=legacy_name):
                self.assertFalse(hasattr(self.catalog, legacy_name))

        expected_objects = {
            "patient",
            "breast_imaging_episode",
            "imaging_exam",
            "breast_side",
            "imaging_finding",
            "imaging_interpretation",
            "procedure",
            "pathology_observation",
            "pathology_diagnosis",
        }
        self.assertLessEqual(expected_objects, set(self.catalog.clinical_objects))

        expected_edges = {
            "clinical.patient-imaging-episode": (
                "patient",
                "breast_imaging_episode",
            ),
            "clinical.episode-exam": (
                "breast_imaging_episode",
                "imaging_exam",
            ),
            "clinical.exam-side": ("imaging_exam", "breast_side"),
            "clinical.exam-finding": ("imaging_exam", "imaging_finding"),
            "clinical.finding-interpretation": (
                "imaging_finding",
                "imaging_interpretation",
            ),
            "clinical.interpretation-procedure": (
                "imaging_interpretation",
                "procedure",
            ),
            "clinical.procedure-pathology-observation": (
                "procedure",
                "pathology_observation",
            ),
            "clinical.pathology-observation-diagnosis": (
                "pathology_observation",
                "pathology_diagnosis",
            ),
        }
        for identifier, endpoints in expected_edges.items():
            with self.subTest(relationship=identifier):
                relationship = self.catalog.get_semantic_relationship(
                    identifier
                )["semantic_relationship"]
                self.assertEqual(
                    (
                        relationship["source_object"],
                        relationship["target_object"],
                    ),
                    endpoints,
                )

    def test_exact_getters_resolve_navigation_and_claim_provenance(self) -> None:
        result = self.catalog.get_clinical_object("pathology_diagnosis")

        self.assertIn("pathology.severity", result["related"]["features"])
        self.assertIn(
            "clinical.pathology-observation-diagnosis",
            result["related"]["semantic_relationships"],
        )
        self.assertIn(
            "time.pathology-report-documentation",
            result["related"]["temporal_semantics"],
        )
        self.assertIn(
            "aggregation.pathology-severity-to-patient",
            result["related"]["aggregations"],
        )
        self.assertEqual(
            result["provenance"]["claims"][0]["id"],
            "open-v2.pathology-procedure-context#severity-meaning",
        )
        self.assertEqual(
            result["provenance"]["claims"][0]["status"], "verified"
        )
        self.assertIn(
            "open-v2.maintainer-clarification-2026-07-29",
            result["provenance"]["sources"],
        )
        self.assertEqual(
            result["provenance"]["contexts"][0]["profiles"], ["open-v2"]
        )

        context = self.catalog.get_context(
            "open-v2.pathology-procedure-context"
        )
        self.assertEqual(context["kind"], "context")
        self.assertTrue(context["context"]["claims"])
        self.assertTrue(context["provenance"]["sources"])

    def test_pathology_states_and_nulls_remain_clinically_distinct(self) -> None:
        result = self.catalog.get_feature(
            "pathology.severity", include_codes=True
        )
        self.assertEqual(
            result["vocabulary"]["codes"],
            {
                "0": "Invasive breast cancer",
                "1": "In-situ breast cancer",
                "2": "High-risk lesion",
                "3": "Borderline lesion",
                "4": "Benign finding",
                "5": "Non-breast cancer",
            },
        )
        self.assertNotIn("6", result["vocabulary"]["codes"])
        self.assertEqual(
            result["feature"]["missing_states"][0]["id"],
            "unattached_pathology",
        )
        missing_text = json.dumps(
            result["feature"]["missing_states"][0]
        ).casefold()
        self.assertIn("not a diagnosis category or negative outcome", missing_text)
        self.assertIn(
            "time.downstream-availability",
            result["related"]["temporal_semantics"],
        )

        for aggregate_feature in (
            "breast_side.pathology_severity_aggregate",
            "exam.pathology_severity_aggregate",
        ):
            with self.subTest(feature=aggregate_feature):
                feature = self.catalog.get_feature(aggregate_feature)["feature"]
                self.assertEqual(
                    feature["missing_states"][0]["id"],
                    "unattached_pathology",
                )

        non_breast = self.catalog.get_guardrail(
            "guardrail.non-breast-cancer-not-no-malignancy"
        )["guardrail"]
        self.assertIn("not be interpreted as benign", non_breast["statement"])

    def test_attribution_is_optional_many_to_many_and_not_a_join_recipe(
        self,
    ) -> None:
        result = self.catalog.get_semantic_relationship(
            "clinical.finding-pathology-observation"
        )
        relationship = result["semantic_relationship"]

        self.assertEqual(
            relationship["cardinality"],
            {
                "targets_per_source": "zero_or_more",
                "sources_per_target": "zero_or_more",
            },
        )
        self.assertEqual(
            relationship["optionality"],
            {"source": "optional", "target": "optional"},
        )
        self.assertIn(
            "many-to-many",
            " ".join(relationship["attribution_limitations"]),
        )
        self.assertIn(
            "time.downstream-availability",
            relationship["temporal_semantics"],
        )
        self.assertIn(
            "coverage.open-v2.finding-pathology-attribution",
            result["related"]["coverage"],
        )

        binding = result["related"]["relationship_bindings"][0]
        self.assertEqual(binding["source"]["completeness"], "optional")
        self.assertEqual(
            binding["source"]["columns"], ["acc_anon", "side", "numfind"]
        )
        self.assertEqual(
            binding["target"]["columns"], ["acc_anon", "side", "numfind"]
        )
        self.assertIn("multiply rows", " ".join(binding["join_hazards"]))

    def test_timestamps_preserve_event_documentation_and_availability_meaning(
        self,
    ) -> None:
        expected = {
            "time.exam-event": ("event_time", ["exam.study_date"]),
            "time.procedure-event": (
                "event_time",
                ["pathology.procedure_date"],
            ),
            "time.specimen-collection": ("event_time", []),
            "time.pathology-report-documentation": (
                "documentation_time",
                ["pathology.report_date"],
            ),
            "time.downstream-availability": ("availability_time", []),
        }
        for identifier, (kind, feature_refs) in expected.items():
            with self.subTest(temporal_semantic=identifier):
                temporal = self.catalog.get_temporal_semantic(identifier)[
                    "temporal_semantic"
                ]
                self.assertEqual(temporal["kind"], kind)
                self.assertEqual(temporal["feature_refs"], feature_refs)

        report_time = self.catalog.get_temporal_semantic(
            "time.pathology-report-documentation"
        )["temporal_semantic"]
        self.assertIn(
            "not designated as a universal diagnosis date",
            " ".join(report_time["caveats"]),
        )
        timestamp_guardrail = self.catalog.get_guardrail(
            "guardrail.timestamps-answer-different-questions"
        )["guardrail"]
        self.assertIn("rather than treated as interchangeable", timestamp_guardrail["statement"])

        for feature_id, absent_event in (
            ("pathology.procedure_date", "procedure did not occur"),
            ("pathology.report_date", "pathology report or diagnosis did not exist"),
        ):
            with self.subTest(feature=feature_id):
                state = self.catalog.get_feature(feature_id)["feature"][
                    "missing_states"
                ][0]
                self.assertEqual(state["representation"], "null")
                self.assertIn(absent_event, state["meaning"])

        for coverage_id in (
            "coverage.open-v2.specimen-time",
            "coverage.open-v2.downstream-availability-time",
        ):
            with self.subTest(coverage=coverage_id):
                coverage = self.catalog.get_coverage(coverage_id)["coverage"]
                self.assertEqual(coverage["status"], "unsupported")
                self.assertEqual(coverage["profiles"], ["open-v2"])

    def test_aggregation_and_profile_support_are_explicit(self) -> None:
        for suffix, target, result_feature in (
            ("side", "breast_side", "breast_side.pathology_severity_aggregate"),
            ("exam", "imaging_exam", "exam.pathology_severity_aggregate"),
        ):
            with self.subTest(level=suffix):
                identifier = f"aggregation.pathology-severity-to-{suffix}"
                result = self.catalog.get_aggregation(identifier)
                aggregation = result["aggregation"]
                self.assertEqual(aggregation["status"], "provided")
                self.assertEqual(aggregation["target_object"], target)
                self.assertEqual(aggregation["result_concept"], result_feature)
                self.assertIn("minimum", aggregation["method"].casefold())
                self.assertIn(
                    f"coverage.open-v2.pathology-severity-to-{suffix}",
                    result["related"]["coverage"],
                )
                coverage = self.catalog.get_coverage(
                    f"coverage.open-v2.pathology-severity-to-{suffix}"
                )["coverage"]
                self.assertEqual(coverage["status"], "supported")
                self.assertEqual(coverage["profiles"], ["open-v2"])

        finding = self.catalog.get_aggregation(
            "aggregation.pathology-severity-to-finding"
        )["aggregation"]
        self.assertEqual(finding["status"], "unresolved")
        self.assertIsNone(finding["result_concept"])
        self.assertIn(
            "clinical.finding-pathology-observation",
            finding["semantic_relationships"],
        )

        patient = self.catalog.get_aggregation(
            "aggregation.pathology-severity-to-patient"
        )["aggregation"]
        self.assertEqual(patient["status"], "analyst_defined")
        self.assertIsNone(patient["result_concept"])
        patient_coverage = self.catalog.get_coverage(
            "coverage.open-v2.patient-pathology-aggregate"
        )["coverage"]
        self.assertEqual(patient_coverage["status"], "unsupported")

    def test_reusable_guardrails_replace_task_specific_recipes(self) -> None:
        expected = {
            "guardrail.null-pathology-not-negative",
            "guardrail.assessment-not-pathology",
            "guardrail.downstream-temporal-leakage",
            "guardrail.explicit-attribution-policy",
            "guardrail.explicit-grain-aggregation",
            "guardrail.timestamps-answer-different-questions",
            "guardrail.inverse-severity-ordering",
            "guardrail.attached-pathology-selection",
            "guardrail.non-breast-cancer-not-no-malignancy",
            "guardrail.colocation-not-coavailability",
            "guardrail.incomplete-outcome-capture",
        }
        self.assertLessEqual(expected, set(self.catalog.guardrails))

        workflow_fields = {
            "alternatives",
            "required_decisions",
            "prohibited_shortcuts",
        }
        for identifier, guardrail in self.raw["guardrails"].items():
            with self.subTest(guardrail=identifier):
                self.assertTrue(workflow_fields.isdisjoint(guardrail))

    def test_clinical_discovery_finds_outcomes_attribution_and_profile_gaps(
        self,
    ) -> None:
        outcome = self.catalog.discover(
            "How is breast cancer represented and when is it known?",
            limit=100,
        )
        outcome_ids = {item["identifier"] for item in outcome["matches"]}
        self.assertIn("pathology_diagnosis", outcome_ids)
        self.assertIn("pathology.severity", outcome_ids)
        severity_match = next(
            item
            for item in outcome["matches"]
            if item["identifier"] == "pathology.severity"
        )
        self.assertTrue(severity_match["match_reasons"])
        self.assertIn(
            "time.downstream-availability",
            severity_match["entity"]["temporal_semantics"],
        )

        attribution = self.catalog.discover(
            "pathology linked to imaging finding", limit=100
        )
        relationship_match = next(
            item
            for item in attribution["matches"]
            if item["identifier"]
            == "clinical.finding-pathology-observation"
        )
        self.assertEqual(relationship_match["kind"], "semantic_relationship")
        self.assertTrue(relationship_match["match_reasons"])

        specimen = self.catalog.discover(
            "specimen date",
            profile="open-v2",
            kinds=["temporal_semantic", "coverage"],
        )
        specimen_ids = {item["identifier"] for item in specimen["matches"]}
        self.assertIn("time.specimen-collection", specimen_ids)
        self.assertIn("coverage.open-v2.specimen-time", specimen_ids)
        self.assertIn(
            "unsupported_in_profile",
            {item["category"] for item in specimen["diagnostics"]},
        )

    def test_discovery_diagnostics_distinguish_failure_modes(self) -> None:
        filtered = self.catalog.discover(
            "missing specimen timestamp", kinds=["aggregation"]
        )
        self.assertIn(
            "filters_excluded_matches",
            {item["category"] for item in filtered["diagnostics"]},
        )

        vocabulary = self.catalog.discover(
            "pathology severity frobnicate", limit=5
        )
        self.assertIn(
            "vocabulary_mismatch",
            {item["category"] for item in vocabulary["diagnostics"]},
        )
        self.assertIn("frobnicate", vocabulary["unmatched_terms"])

        absent = self.catalog.discover("xylophonic reticulocyte")
        self.assertEqual(absent["matches"], [])
        self.assertIn(
            "no_catalog_coverage",
            {item["category"] for item in absent["diagnostics"]},
        )

        unknown = self.catalog.discover(
            "pathology", profile="missing-profile", kinds=["imaginary"]
        )
        self.assertEqual(unknown["matches"], [])
        self.assertEqual(unknown["diagnostics"][0]["category"], "unknown_filter")

    def test_physical_bindings_are_secondary_and_projections_are_explicit(
        self,
    ) -> None:
        self.assertTrue(
            {"bindings", "tables", "relationships"}.isdisjoint(self.raw)
        )
        profile = self.raw["profile_bindings"]["open-v2"]
        self.assertEqual(
            set(profile),
            {
                "feature_bindings",
                "object_bindings",
                "tables",
                "relationship_bindings",
            },
        )

        combined = self.catalog.get_profile_table("open-v2", "combined_anon")
        self.assertEqual(combined["kind"], "profile_table")
        self.assertEqual(combined["identifier"], "open-v2:combined_anon")
        projected_objects = {
            item["object"]
            for item in combined["object_bindings"]
            if item["representation"] == "projection"
        }
        self.assertLessEqual(
            {
                "patient",
                "imaging_exam",
                "imaging_finding",
                "imaging_interpretation",
                "procedure",
                "pathology_observation",
                "pathology_diagnosis",
            },
            projected_objects,
        )

    def test_physical_aliases_are_profile_scoped_discovery_metadata(self) -> None:
        physical_names = {
            value.casefold()
            for profile in self.raw["profile_bindings"].values()
            for binding in profile["feature_bindings"]
            for value in (binding["table"], binding["column"])
        }
        for identifier, concept in self.raw["concepts"].items():
            with self.subTest(concept=identifier):
                self.assertTrue(
                    physical_names.isdisjoint(
                        term.casefold() for term in concept["search_terms"]
                    )
                )

        portable = self.catalog.discover(
            "procdate_anon", kinds=["feature"]
        )
        self.assertEqual(portable["matches"], [])

        bound = self.catalog.discover(
            "procdate_anon", profile="open-v2", kinds=["feature"]
        )
        self.assertEqual(bound["matches"][0]["identifier"], "pathology.procedure_date")
        self.assertIn(
            "binding.column",
            {
                reason["field"]
                for reason in bound["matches"][0]["match_reasons"]
            },
        )
        self.assertEqual(
            bound["matches"][0]["implementation_bindings"]["profile"],
            "open-v2",
        )
        object_match = self.catalog.discover(
            "imaging finding",
            profile="open-v2",
            kinds=["clinical_object"],
        )["matches"][0]
        object_bindings = object_match["implementation_bindings"][
            "object_bindings"
        ]
        self.assertTrue(object_bindings)
        self.assertTrue(
            all(binding["provenance"]["claims"] for binding in object_bindings)
        )

    def test_repository_source_locators_exist_and_are_not_self_citing(
        self,
    ) -> None:
        repository_sources = {
            identifier: source
            for identifier, source in self.raw["sources"].items()
            if source["locator_kind"] == "repository_path"
        }
        self.assertTrue(repository_sources)
        for identifier, source in repository_sources.items():
            with self.subTest(source=identifier):
                locator = Path(source["locator"])
                self.assertFalse(locator.is_absolute())
                self.assertNotEqual(locator, Path("catalog/catalog.json"))
                self.assertTrue((REPO_ROOT / locator).is_file())


if __name__ == "__main__":
    unittest.main()
