"""Unit tests for schema-v8 loading, validation, and semantic discovery."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from embed_context import (
    AGGREGATION_STATUSES,
    COVERAGE_STATUSES,
    DISCOVERY_KINDS,
    RELATIONSHIP_BINDING_KINDS,
    SEMANTIC_RELATIONSHIP_KINDS,
    TEMPORAL_KINDS,
    Catalog,
    CatalogAmbiguousError,
    CatalogLoadError,
    CatalogNotFoundError,
    CatalogValidationError,
    load_catalog,
)
from embed_context.catalog import GUARDRAIL_CATEGORIES, GUARDRAIL_PRIORITIES
from tests.catalog_fixture import cloned_catalog, synthetic_catalog


class CatalogLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def load(self, data: dict | None = None) -> Catalog:
        return Catalog.from_mapping(
            synthetic_catalog() if data is None else data
        )

    def assert_invalid(self, data: dict, message: str) -> None:
        with self.assertRaisesRegex(CatalogValidationError, message):
            Catalog.from_mapping(data)

    def test_loads_and_freezes_two_profile_catalog(self) -> None:
        catalog = self.load()

        self.assertEqual(catalog.schema_version, 8)
        self.assertEqual(catalog.profiles, ("profile-a", "profile-b"))
        self.assertEqual(len(catalog.clinical_objects), 3)
        self.assertEqual(len(catalog.concepts), 4)
        self.assertEqual(len(catalog.feature_bindings), 8)
        self.assertEqual(len(catalog.object_bindings), 6)
        self.assertEqual(len(catalog.relationship_bindings), 2)
        self.assertEqual(len(catalog.relationship_binding_paths), 1)
        self.assertNotIn("analysis_patterns", catalog.summary())
        self.assertFalse(hasattr(catalog, "grains"))
        with self.assertRaises(TypeError):
            catalog.concepts["new"] = catalog.concepts["exam.study_date"]
        with self.assertRaises(FrozenInstanceError):
            catalog.feature_bindings[0].profile = "changed"
        with self.assertRaises(AttributeError):
            catalog._schema_version = 8

    def test_summary_exposes_v8_facets_and_derived_grains(self) -> None:
        summary = self.load().summary()

        self.assertNotIn("binding_grains", summary)
        self.assertEqual(
            summary["semantic_relationship_kinds"],
            list(SEMANTIC_RELATIONSHIP_KINDS),
        )
        self.assertEqual(summary["temporal_kinds"], list(TEMPORAL_KINDS))
        self.assertEqual(
            summary["aggregation_statuses"], list(AGGREGATION_STATUSES)
        )
        self.assertEqual(
            summary["coverage_statuses"], list(COVERAGE_STATUSES)
        )
        self.assertEqual(
            summary["relationship_binding_kinds"],
            sorted(RELATIONSHIP_BINDING_KINDS),
        )
        self.assertEqual(
            summary["guardrail_categories"], list(GUARDRAIL_CATEGORIES)
        )
        self.assertEqual(
            summary["guardrail_priorities"], list(GUARDRAIL_PRIORITIES)
        )
        self.assertEqual(summary["discovery_kinds"], list(DISCOVERY_KINDS))
        self.assertEqual(summary["profile_bindings"], 2)

    def test_wrong_schema_version_and_schema_reference_are_rejected(self) -> None:
        for version in (6, 7, 9):
            with self.subTest(version=version):
                data = cloned_catalog()
                data["schema_version"] = version
                self.assert_invalid(
                    data,
                    "unsupported catalog schema_version.*expected integer 8",
                )

        data = cloned_catalog()
        data["$schema"] = "catalog-v6.schema.json"
        self.assert_invalid(data, r"\$\.\$schema must equal")

    def test_unknown_and_missing_top_level_fields_are_rejected(self) -> None:
        data = cloned_catalog()
        data["analysis_patterns"] = {}
        self.assert_invalid(data, "unexpected fields: analysis_patterns")

        data = cloned_catalog()
        del data["guardrails"]
        self.assert_invalid(data, "missing required fields: guardrails")

    def test_controlled_arrays_must_match_schema_order_exactly(self) -> None:
        data = cloned_catalog()
        data["temporal_kinds"].reverse()
        self.assert_invalid(
            data, r"\$\.temporal_kinds must equal.*controlled values"
        )

    def test_declared_profiles_and_binding_layer_keys_must_agree(self) -> None:
        data = cloned_catalog()
        data["profiles"] = ["profile-a"]

        self.assert_invalid(
            data, r"\$\.profiles and \$\.profile_bindings keys must agree"
        )

    def test_malformed_json_duplicate_keys_and_nonfinite_numbers_are_rejected(
        self,
    ) -> None:
        duplicate_path = self.directory / "duplicate.json"
        duplicate_path.write_text(
            '{"schema_version": 8, "schema_version": 8}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            CatalogValidationError, "duplicate JSON object key"
        ):
            load_catalog(duplicate_path)

        nonfinite_path = self.directory / "nan.json"
        nonfinite_path.write_text('{"value": NaN}', encoding="utf-8")
        with self.assertRaisesRegex(
            CatalogValidationError, "non-standard JSON number"
        ):
            load_catalog(nonfinite_path)

    def test_io_and_decode_failures_are_safe_catalog_errors(self) -> None:
        with self.assertRaises(CatalogLoadError):
            load_catalog(self.directory / "missing.json")

        bad_path = self.directory / "bad.json"
        bad_path.write_text("{", encoding="utf-8")
        with self.assertRaises(CatalogLoadError):
            load_catalog(bad_path)

    def test_nontechnical_feature_requires_a_clinical_object(self) -> None:
        data = cloned_catalog()
        data["concepts"]["exam.study_date"]["objects"] = []

        self.assert_invalid(data, "objects must not be empty for nontechnical")

    def test_feature_object_vocabulary_and_extension_refs_must_resolve(self) -> None:
        mutations = (
            ("objects", ["unknown_object"], "unknown clinical objects"),
            ("vocabulary", "unknown.vocabulary", "unknown vocabulary"),
            (
                "temporal_semantics",
                ["unknown.time"],
                "unknown temporal semantics",
            ),
            ("aggregations", ["unknown.rollup"], "unknown aggregations"),
        )
        for field, value, message in mutations:
            with self.subTest(field=field):
                data = cloned_catalog()
                data["concepts"]["exam.study_date"][field] = value
                self.assert_invalid(data, message)

    def test_missing_state_ids_are_unique_and_claim_refs_resolve(self) -> None:
        data = cloned_catalog()
        state = data["concepts"]["pathology.severity"]["missing_states"][0]
        data["concepts"]["pathology.severity"]["missing_states"].append(
            dict(state)
        )
        self.assert_invalid(data, "missing_states contains duplicate IDs")

        data = cloned_catalog()
        data["concepts"]["pathology.severity"]["missing_states"][0][
            "claim_refs"
        ] = ["missing.context#claim"]
        self.assert_invalid(data, "references unknown claims")

    def test_semantic_relationship_objects_and_hierarchy_are_validated(self) -> None:
        data = cloned_catalog()
        data["semantic_relationships"]["patient.has_exam"][
            "target_object"
        ] = "unknown"
        self.assert_invalid(data, "unknown clinical object")

        data = cloned_catalog()
        data["semantic_relationships"]["exam.has_patient"] = {
            **data["semantic_relationships"]["patient.has_exam"],
            "label": "Exam has patient",
            "source_object": "imaging_exam",
            "target_object": "patient",
        }
        self.assert_invalid(data, "semantic hierarchy must be acyclic")

        data = cloned_catalog()
        data["semantic_relationships"]["patient.has_exam"][
            "temporal_semantics"
        ] = ["unknown.time"]
        self.assert_invalid(data, "unknown temporal semantics")

    def test_temporal_refs_resolve_and_relative_to_is_acyclic(self) -> None:
        data = cloned_catalog()
        data["temporal_semantics"]["exam.event_time"]["relative_to"] = [
            "unknown.time"
        ]
        self.assert_invalid(data, "unknown relative_to IDs")

        data = cloned_catalog()
        data["temporal_semantics"]["exam.event_time"]["relative_to"] = [
            "specimen.collection_time"
        ]
        data["temporal_semantics"]["specimen.collection_time"][
            "relative_to"
        ] = ["exam.event_time"]
        self.assert_invalid(data, "temporal relative_to must be acyclic")

        data = cloned_catalog()
        data["temporal_semantics"]["specimen.collection_time"][
            "feature_refs"
        ] = ["exam.study_date"]
        self.assert_invalid(
            data, "feature_refs do not belong to any referenced temporal object"
        )

    def test_unbound_temporal_semantic_requires_explicit_coverage(self) -> None:
        data = cloned_catalog()
        del data["coverage"]["specimen-time.profile-support"]

        self.assert_invalid(
            data, "has no feature_refs.*unsupported or unresolved coverage"
        )

        data = cloned_catalog()
        data["coverage"]["specimen-time.profile-support"][
            "status"
        ] = "not_cataloged"
        self.assert_invalid(
            data, "has no feature_refs.*unsupported or unresolved coverage"
        )

        data = cloned_catalog()
        data["coverage"]["specimen-time.profile-support"]["profiles"] = [
            "profile-a"
        ]
        self.assert_invalid(
            data,
            "lacks unsupported or unresolved coverage for profiles: profile-b",
        )

    def test_aggregation_status_controls_result_feature(self) -> None:
        data = cloned_catalog()
        data["aggregations"]["pathology.severity-to-exam"][
            "result_concept"
        ] = None
        self.assert_invalid(data, "provided aggregation.*requires result_concept")

        data = cloned_catalog()
        data["aggregations"]["pathology.severity-to-patient"][
            "result_concept"
        ] = "pathology.severity"
        self.assert_invalid(
            data, "analyst_defined aggregation.*must not select"
        )

        data = cloned_catalog()
        data["aggregations"]["pathology.severity-to-exam"][
            "result_concept"
        ] = "identity.patient_identifier"
        self.assert_invalid(data, "does not belong to target_object")

        data = cloned_catalog()
        data["aggregations"]["pathology.severity-to-exam"][
            "source_concept"
        ] = "identity.patient_identifier"
        self.assert_invalid(data, "does not belong to source_object")

        data = cloned_catalog()
        data["aggregations"]["pathology.severity-to-exam"][
            "semantic_relationships"
        ] = ["unknown.relationship"]
        self.assert_invalid(data, "unknown semantic relationships")

    def test_guardrail_links_and_source_backed_claims_are_required(self) -> None:
        data = cloned_catalog()
        guardrail = data["guardrails"]["pathology.null-is-not-negative"]
        for field in (
            "objects",
            "concepts",
            "semantic_relationships",
            "temporal_semantics",
            "aggregations",
            "coverage",
        ):
            guardrail[field] = []
        self.assert_invalid(data, "reference at least one semantic entity")

        data = cloned_catalog()
        data["guardrails"]["pathology.null-is-not-negative"][
            "claim_refs"
        ] = []
        self.assert_invalid(data, "claim_refs must contain at least 1")

    def test_profile_specific_scope_requires_profiles_and_compatible_claims(
        self,
    ) -> None:
        data = cloned_catalog()
        record = data["coverage"]["specimen-time.profile-support"]
        record["profiles"] = []
        self.assert_invalid(data, "profiles must not be empty")

        data = cloned_catalog()
        record = data["coverage"]["specimen-time.profile-support"]
        record["scope"] = "embed_general"
        record["profiles"] = []
        record["claim_refs"] = ["profiles.synthetic#severity-binding"]
        self.assert_invalid(data, "claim.*incompatible scope")

    def test_coverage_subjects_resolve_and_supported_features_are_bound(
        self,
    ) -> None:
        data = cloned_catalog()
        data["coverage"]["pathology-severity.profile-support"][
            "subject"
        ] = "unknown.feature"
        self.assert_invalid(data, "references unknown concept subject")

        data = cloned_catalog()
        for binding in data["profile_bindings"]["profile-b"][
            "feature_bindings"
        ]:
            if binding["concept"] == "pathology.severity":
                binding["concept"] = "technical.row_index"
        self.assert_invalid(data, "supported coverage.*no feature binding")

    def test_physical_inventory_allows_unmapped_columns_and_keys_use_inventory(
        self,
    ) -> None:
        catalog = Catalog.from_mapping(cloned_catalog())
        table = catalog.get_profile_table("profile-a", "clinical_a")
        self.assertIn(
            "unmapped_note",
            {column["name"] for column in table["table"]["columns"]},
        )
        self.assertNotIn(
            "unmapped_note",
            {binding.column for binding in catalog.feature_bindings},
        )

        data = cloned_catalog()
        data["profile_bindings"]["profile-a"]["tables"][0]["keys"][0][
            "columns"
        ] = ["unbound_column"]
        self.assert_invalid(data, "references unknown columns: unbound_column")

    def test_mapping_concept_status_and_generic_qualifiers_are_validated(self) -> None:
        data = cloned_catalog()
        data["profile_bindings"]["profile-a"]["feature_bindings"][0][
            "concept"
        ] = "unknown.feature"
        self.assert_invalid(data, "references unknown concept")

        data = cloned_catalog()
        data["profile_bindings"]["profile-a"]["feature_bindings"][0][
            "status"
        ] = "canonical"
        self.assert_invalid(data, "status has unknown value")

        data = cloned_catalog()
        data["profile_bindings"]["profile-a"]["feature_bindings"][0][
            "qualifiers"
        ] = {"nested": {"not": "scalar"}}
        self.assert_invalid(data, "must be a scalar descriptive value")

    def test_observed_source_evidence_is_release_neutral(self) -> None:
        data = cloned_catalog()
        data["concepts"]["pathology.severity"]["evidence"] = [
            "observed_source_values"
        ]
        Catalog.from_mapping(data)

        data["concepts"]["pathology.severity"]["evidence"] = [
            "observed_v2_values"
        ]
        self.assert_invalid(data, "unknown evidence values")

    def test_object_binding_can_be_table_level_but_must_resolve(self) -> None:
        data = cloned_catalog()
        data["profile_bindings"]["profile-a"]["object_bindings"][0][
            "columns"
        ] = []
        Catalog.from_mapping(data)

        data = cloned_catalog()
        data["profile_bindings"]["profile-a"]["object_bindings"][0][
            "object"
        ] = "unknown.object"
        self.assert_invalid(data, "unknown clinical object")

    def test_object_axes_are_independent_and_co_location_is_derived(self) -> None:
        catalog = Catalog.from_mapping(cloned_catalog())
        result = catalog.get_clinical_object("patient")
        profile_a = next(
            item
            for item in result["related"]["object_bindings"]
            if item["profile"] == "profile-a"
        )
        self.assertEqual(profile_a["completeness"], "complete")
        self.assertEqual(profile_a["authority"], "preferred")
        self.assertEqual(profile_a["derivation"], "source")
        self.assertEqual(
            profile_a["co_located_objects"],
            ["imaging_exam", "pathology_diagnosis"],
        )

    def test_binding_claims_must_apply_to_the_containing_profile(self) -> None:
        data = cloned_catalog()
        context = data["contexts"]["profiles.profile-b-only"] = dict(
            data["contexts"]["profiles.synthetic"]
        )
        context["profiles"] = ["profile-b"]
        context["related_tables"] = [
            table
            for table in context["related_tables"]
            if table["profile"] == "profile-b"
        ]
        data["profile_bindings"]["profile-a"]["object_bindings"][0][
            "claim_refs"
        ] = ["profiles.profile-b-only#severity-binding"]
        self.assert_invalid(data, "claim.*outside selected profiles")

        data = cloned_catalog()
        context = data["contexts"]["profiles.profile-a-only"] = dict(
            data["contexts"]["profiles.synthetic"]
        )
        context["profiles"] = ["profile-a"]
        context["related_tables"] = [
            table
            for table in context["related_tables"]
            if table["profile"] == "profile-a"
        ]
        context["related_relationships"] = []
        data["profile_bindings"]["profile-b"]["relationship_bindings"][0][
            "claim_refs"
        ] = ["profiles.profile-a-only#severity-binding"]
        self.assert_invalid(data, "claim.*outside selected profiles")

    def test_occurrence_interpretations_are_structured_and_scoped(self) -> None:
        catalog = Catalog.from_mapping(cloned_catalog())
        interpretation = catalog.profile_bindings[
            "profile-a"
        ].feature_bindings[2].occurrence_interpretations[0]
        self.assertEqual(interpretation.representation, "null")
        self.assertEqual(interpretation.status, "verified")

        data = cloned_catalog()
        interpretations = data["profile_bindings"]["profile-a"][
            "feature_bindings"
        ][2]["occurrence_interpretations"]
        interpretations.append(dict(interpretations[0]))
        self.assert_invalid(data, "duplicate representations")

        data = cloned_catalog()
        data["profile_bindings"]["profile-a"]["feature_bindings"][2][
            "occurrence_interpretations"
        ][0]["claim_refs"] = ["missing.context#claim"]
        self.assert_invalid(data, "references unknown claims")

    def test_instance_identity_columns_exceptions_and_claims_are_validated(
        self,
    ) -> None:
        catalog = Catalog.from_mapping(cloned_catalog())
        identity = catalog.profile_bindings["profile-b"].object_bindings[
            0
        ].instance_identity
        self.assertIsNotNone(identity)
        assert identity is not None
        self.assertEqual(identity.columns, ("pid",))
        self.assertTrue(identity.longitudinal_identity)

        data = cloned_catalog()
        data["profile_bindings"]["profile-b"]["object_bindings"][0][
            "instance_identity"
        ]["columns"] = ["unknown_column"]
        self.assert_invalid(data, "columns outside the object binding")

        data = cloned_catalog()
        identity_data = data["profile_bindings"]["profile-b"][
            "object_bindings"
        ][0]["instance_identity"]
        identity_data["reserved_exceptions"] = [
            {
                "column": "exam_id",
                "representation": "-9",
                "meaning": "Synthetic record.",
                "claim_refs": ["profiles.synthetic#severity-binding"],
                "caveats": [],
            }
        ]
        self.assert_invalid(data, "non-identity column")

        data = cloned_catalog()
        identity_data = data["profile_bindings"]["profile-b"][
            "object_bindings"
        ][0]["instance_identity"]
        identity_data["reserved_exceptions"] = [
            {
                "column": "pid",
                "representation": "-9",
                "meaning": "Synthetic record.",
                "claim_refs": ["missing.context#claim"],
                "caveats": [],
            }
        ]
        self.assert_invalid(data, "references unknown claims")

    def test_relationship_binding_paths_resolve_and_require_adjacency(
        self,
    ) -> None:
        catalog = Catalog.from_mapping(cloned_catalog())
        path = catalog.relationship_binding_paths[0]
        self.assertEqual(path.semantic_relationship, "patient.has_exam")
        self.assertEqual(
            path.relationship_bindings, ("profile-b.exams.patient",)
        )

        data = cloned_catalog()
        data["profile_bindings"]["profile-b"][
            "relationship_binding_paths"
        ][0]["semantic_relationship"] = "unknown.relationship"
        self.assert_invalid(data, "unknown semantic relationship")

        data = cloned_catalog()
        data["profile_bindings"]["profile-b"][
            "relationship_binding_paths"
        ][0]["relationship_bindings"] = ["profile-a.unknown"]
        self.assert_invalid(
            data, "unknown relationship bindings in profile"
        )

        data = cloned_catalog()
        profile = data["profile_bindings"]["profile-b"]
        second = {
            **profile["relationship_bindings"][0],
            "id": "profile-b.patients.self",
            "kind": "reference",
            "semantic_relationships": [],
            "source": {
                "table": "patients_b",
                "columns": ["pid"],
                "completeness": "required",
            },
            "target": {"table": "patients_b", "columns": ["pid"]},
            "cardinality": {
                "targets_per_source": "exactly_one",
                "sources_per_target": "zero_or_more",
            },
        }
        profile["relationship_bindings"].append(second)
        profile["relationship_binding_paths"][0][
            "relationship_bindings"
        ].append("profile-b.patients.self")
        Catalog.from_mapping(data)

        second["source"] = {
            "table": "exams_b",
            "columns": ["pid"],
            "completeness": "required",
        }
        self.assert_invalid(data, "non-adjacent steps")

    def test_same_table_relationships_are_valid_navigation(self) -> None:
        catalog = Catalog.from_mapping(cloned_catalog())
        relationship = catalog.get_relationship_binding(
            "profile-a.patient-exam-colocated"
        )
        self.assertEqual(
            relationship["relationship_binding"]["source"]["table"],
            "clinical_a",
        )
        self.assertEqual(
            relationship["relationship_binding"]["target"]["table"],
            "clinical_a",
        )

    def test_relationship_binding_semantics_columns_types_and_keys_are_validated(
        self,
    ) -> None:
        data = cloned_catalog()
        relationship = data["profile_bindings"]["profile-b"][
            "relationship_bindings"
        ][0]
        relationship["semantic_relationships"] = ["unknown.relationship"]
        self.assert_invalid(data, "unknown semantic relationships")

        data = cloned_catalog()
        relationship = data["profile_bindings"]["profile-b"][
            "relationship_bindings"
        ][0]
        relationship["source"]["columns"] = ["exam_date"]
        self.assert_invalid(data, "incompatible physical types")

        data = cloned_catalog()
        relationship = data["profile_bindings"]["profile-b"][
            "relationship_bindings"
        ][0]
        relationship["cardinality"]["targets_per_source"] = "exactly_one"
        relationship["source"]["completeness"] = "optional"
        data["profile_bindings"]["profile-b"]["tables"][1]["keys"][1][
            "completeness"
        ] = "unknown"
        self.assert_invalid(data, "source completeness must be required")

    def test_many_to_many_occurrences_are_allowed_but_ids_are_unique(self) -> None:
        data = cloned_catalog()
        binding = dict(
            data["profile_bindings"]["profile-a"]["feature_bindings"][0]
        )
        binding["concept"] = "technical.row_index"
        binding["id"] = "profile-a.feature.patient-id-alternative"
        binding["status"] = "ambiguous"
        data["profile_bindings"]["profile-a"]["feature_bindings"].append(
            binding
        )
        catalog = Catalog.from_mapping(data)
        same_occurrence = [
            item
            for item in catalog.feature_bindings
            if item.profile == "profile-a"
            and item.table == "clinical_a"
            and item.column == "person_id"
        ]
        self.assertEqual(len(same_occurrence), 2)
        self.assertEqual(
            {item.status for item in same_occurrence}, {"direct", "ambiguous"}
        )

        binding["id"] = "profile-a.feature.patient-id"
        self.assert_invalid(data, "duplicate or missing feature mapping ID")

        data = cloned_catalog()
        relationship = dict(
            data["profile_bindings"]["profile-b"][
                "relationship_bindings"
            ][0]
        )
        data["profile_bindings"]["profile-b"][
            "relationship_bindings"
        ].append(relationship)
        self.assert_invalid(data, "duplicate relationship binding ID")


class CatalogQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = Catalog.from_mapping(synthetic_catalog())

    def test_exact_object_getter_computes_navigation_and_provenance(self) -> None:
        result = self.catalog.get_clinical_object("imaging_exam")

        self.assertEqual(result["kind"], "clinical_object")
        self.assertIn("exam.study_date", result["related"]["features"])
        self.assertIn(
            "patient.has_exam",
            result["related"]["semantic_relationships"],
        )
        self.assertEqual(
            result["provenance"]["claims"][0]["id"],
            "embed.semantic#exam-meaning",
        )
        self.assertIn(
            "embed.semantic-source", result["provenance"]["sources"]
        )
        for binding in result["related"]["object_bindings"]:
            self.assertEqual(
                binding["provenance"]["claims"][0]["id"],
                "profiles.synthetic#severity-binding",
            )
            self.assertIn(
                "profiles.synthetic-schema",
                binding["provenance"]["sources"],
            )

    def test_feature_getter_resolves_concept_and_profile_physical_names(
        self,
    ) -> None:
        semantic = self.catalog.get_feature(
            "pathology.severity", include_codes=True, profile="profile-a"
        )
        physical = self.catalog.get_feature(
            "profile-a:clinical_a.severity_code"
        )

        self.assertEqual(semantic["kind"], "feature")
        self.assertEqual(len(semantic["bindings"]), 1)
        self.assertEqual(
            semantic["vocabulary"]["codes"]["0"],
            "Invasive breast cancer",
        )
        self.assertIn(
            "pathology.severity-to-patient",
            semantic["related"]["aggregations"],
        )
        self.assertEqual(physical["kind"], "feature_binding")
        self.assertEqual(
            physical["feature"]["id"], "pathology.severity"
        )

    def test_unqualified_physical_name_can_resolve_or_be_ambiguous(self) -> None:
        result = self.catalog.get_feature("clinical_a.study_when")
        self.assertEqual(result["feature"]["id"], "exam.study_date")

        data = cloned_catalog()
        duplicate = dict(
            data["profile_bindings"]["profile-a"]["feature_bindings"][1]
        )
        duplicate["id"] = "profile-b.feature.ambiguous-study-date"
        duplicate["concept"] = "pathology.severity"
        duplicate["status"] = "ambiguous"
        data["profile_bindings"]["profile-b"]["feature_bindings"].append(
            duplicate
        )
        data["profile_bindings"]["profile-b"]["tables"].append(
            {
                "id": "profile-b.table.clinical-a",
                "table": "clinical_a",
                "grain": "wide_row",
                "columns": [
                    {
                        "name": "study_when",
                        "physical_type": "timestamp[ns]",
                        "nullable": True,
                    }
                ],
                "keys": [],
                "caveats": [],
            }
        )
        catalog = Catalog.from_mapping(data)
        with self.assertRaisesRegex(CatalogAmbiguousError, "ambiguous"):
            catalog.get_feature("clinical_a.study_when")

    def test_semantic_exact_getters_include_related_and_provenance(self) -> None:
        relationship = self.catalog.get_semantic_relationship(
            "patient.has_exam"
        )
        temporal = self.catalog.get_temporal_semantic(
            "specimen.collection_time"
        )
        aggregation = self.catalog.get_aggregation(
            "pathology.severity-to-patient"
        )
        guardrail = self.catalog.get_guardrail(
            "pathology.null-is-not-negative"
        )
        coverage = self.catalog.get_coverage(
            "specimen-time.profile-support"
        )

        self.assertIn(
            "profile-b.exams.patient",
            [
                item["id"]
                for item in relationship["related"][
                    "relationship_bindings"
                ]
            ],
        )
        self.assertIn(
            "profile-b.patient-exam-path",
            [
                item["id"]
                for item in relationship["related"][
                    "relationship_binding_paths"
                ]
            ],
        )
        self.assertEqual(temporal["temporal_semantic"]["feature_refs"], [])
        self.assertIn(
            "specimen-time.profile-support",
            temporal["related"]["coverage"],
        )
        self.assertEqual(aggregation["aggregation"]["status"], "analyst_defined")
        self.assertIn(
            "pathology.severity", guardrail["related"]["features"]
        )
        self.assertEqual(
            coverage["related"]["subject"]["identifier"],
            "specimen.collection_time",
        )

    def test_exact_getters_return_six_derived_constraint_groups(self) -> None:
        results = (
            self.catalog.get_clinical_object("imaging_exam"),
            self.catalog.get_feature("pathology.severity", profile="profile-a"),
            self.catalog.get_semantic_relationship("patient.has_exam"),
            self.catalog.get_temporal_semantic("exam.event_time"),
            self.catalog.get_aggregation(
                "pathology.severity-to-patient"
            ),
            self.catalog.get_guardrail(
                "pathology.null-is-not-negative"
            ),
            self.catalog.get_coverage("specimen-time.profile-support"),
            self.catalog.get_context("embed.semantic"),
            self.catalog.get_profile_table("profile-b", "exams_b"),
            self.catalog.get_relationship_binding(
                "profile-b.exams.patient"
            ),
        )
        expected = {
            "supported_facts",
            "unresolved_claims",
            "unsupported_substitutions",
            "analyst_choices_required",
            "high_priority_guardrails",
            "relevant_contexts",
        }
        for result in results:
            with self.subTest(kind=result["kind"]):
                self.assertEqual(set(result["constraints"]), expected)

        feature = results[1]
        self.assertIn(
            "pathology.severity-to-patient",
            {
                item["id"]
                for item in feature["constraints"][
                    "analyst_choices_required"
                ]
            },
        )
        self.assertIn(
            "pathology.null-is-not-negative",
            {
                item["id"]
                for item in feature["constraints"][
                    "high_priority_guardrails"
                ]
            },
        )
        self.assertIn(
            "profiles.synthetic",
            {
                item["id"]
                for item in feature["constraints"]["relevant_contexts"]
            },
        )
        self.assertIn(
            "profiles.synthetic",
            feature["related"]["contexts"],
        )

    def test_reverse_linked_unresolved_claims_are_prominent(self) -> None:
        data = cloned_catalog()
        data["contexts"]["profiles.synthetic"]["claims"].append(
            {
                "id": "unresolved-interpretation",
                "statement": "A reverse-linked interpretation is unresolved.",
                "status": "unresolved",
                "sources": ["profiles.synthetic-schema"],
                "caveats": [],
            }
        )
        catalog = Catalog.from_mapping(data)

        result = catalog.get_feature("pathology.severity", profile="profile-a")

        self.assertIn(
            "profiles.synthetic#unresolved-interpretation",
            {
                item["id"]
                for item in result["constraints"]["unresolved_claims"]
            },
        )
        self.assertNotIn(
            "embed.semantic#patient-meaning",
            {
                item["id"]
                for item in result["constraints"]["supported_facts"]
            },
        )
        self.assertIn(
            "embed.semantic",
            {
                item["id"]
                for item in result["constraints"]["relevant_contexts"]
            },
        )

    def test_object_constraints_only_promote_explicit_claim_evidence(
        self,
    ) -> None:
        data = cloned_catalog()
        data["contexts"]["profiles.synthetic"]["claims"].append(
            {
                "id": "feature-only-uncertainty",
                "statement": (
                    "An uncertainty linked through an owned feature is "
                    "not object evidence."
                ),
                "status": "unresolved",
                "sources": ["profiles.synthetic-schema"],
                "caveats": [],
            }
        )
        catalog = Catalog.from_mapping(data)

        object_result = catalog.get_clinical_object("imaging_exam")
        feature_result = catalog.get_feature("exam.study_date", profile="profile-a")

        self.assertNotIn(
            "profiles.synthetic#feature-only-uncertainty",
            {
                item["id"]
                for item in object_result["constraints"][
                    "unresolved_claims"
                ]
            },
        )
        self.assertIn(
            "profiles.synthetic#severity-binding",
            {
                item["id"]
                for item in object_result["constraints"]["supported_facts"]
            },
        )
        self.assertIn(
            "profiles.synthetic",
            {
                item["id"]
                for item in object_result["constraints"][
                    "relevant_contexts"
                ]
            },
        )
        self.assertIn(
            "profiles.synthetic#feature-only-uncertainty",
            {
                item["id"]
                for item in feature_result["constraints"][
                    "unresolved_claims"
                ]
            },
        )

    def test_imaging_finding_constraints_exclude_report_addendum_claim(
        self,
    ) -> None:
        result = load_catalog().get_clinical_object("imaging_finding")
        constraints = result["constraints"]

        self.assertNotIn(
            "open-v2.report-context#addendum-link",
            {
                item["id"]
                for item in constraints["unresolved_claims"]
            },
        )
        self.assertIn(
            "open-v2.multimodal-finding-context#descriptor-families",
            {
                item["id"]
                for item in constraints["supported_facts"]
            },
        )
        self.assertIn(
            "aggregation.pathology-severity-to-finding",
            {
                item["id"]
                for item in constraints["analyst_choices_required"]
            },
        )
        self.assertIn(
            "open-v2.report-context",
            {
                item["id"] for item in constraints["relevant_contexts"]
            },
        )
        self.assertIn(
            "open-v2.multimodal-finding-context#synthetic-contralateral-finding",
            {
                item["id"]
                for item in result["provenance"]["claims"]
            },
        )

    def test_feature_inherits_coverage_linked_by_applicable_guardrail(
        self,
    ) -> None:
        data = cloned_catalog()
        data["guardrails"]["pathology.null-is-not-negative"][
            "coverage"
        ] = ["specimen-time.profile-support"]
        catalog = Catalog.from_mapping(data)

        result = catalog.get_feature("pathology.severity", profile="profile-a")

        self.assertIn(
            "specimen-time.profile-support",
            result["related"]["coverage"],
        )
        self.assertIn(
            "specimen-time.profile-support",
            {
                item["id"]
                for item in result["constraints"]["unresolved_claims"]
            },
        )

    def test_profiled_relationship_discovery_includes_composed_paths(
        self,
    ) -> None:
        result = self.catalog.discover(
            "patient exam",
            profile="profile-b",
            kinds=["semantic_relationship"],
            limit=10,
        )
        relationship = next(
            item
            for item in result["matches"]
            if item["identifier"] == "patient.has_exam"
        )

        self.assertEqual(
            [
                item["id"]
                for item in relationship["implementation_bindings"][
                    "relationship_binding_paths"
                ]
            ],
            ["profile-b.patient-exam-path"],
        )

    def test_temporal_prohibitions_surface_as_unsupported_substitutions(
        self,
    ) -> None:
        data = cloned_catalog()
        guardrail = data["guardrails"][
            "temporal.no-universal-diagnosis-date"
        ]
        guardrail["category"] = "prohibition"
        guardrail["statement"] = (
            "Do not use a report timestamp as a fallback or proxy."
        )
        catalog = Catalog.from_mapping(data)

        result = catalog.get_temporal_semantic("exam.event_time")

        self.assertIn(
            "temporal.no-universal-diagnosis-date",
            {
                item["id"]
                for item in result["constraints"][
                    "unsupported_substitutions"
                ]
            },
        )

    def test_context_getter_resolves_claim_sources_and_navigation(self) -> None:
        result = self.catalog.get_context("profiles.synthetic")

        self.assertEqual(result["kind"], "context")
        self.assertEqual(
            result["context"]["claims"][0]["id"],
            "severity-binding",
        )
        self.assertIn(
            "pathology.severity",
            result["related"]["features"],
        )
        self.assertIn(
            "profile-b:exams_b",
            result["related"]["profile_tables"],
        )
        self.assertIn(
            "profile-b.exams.patient",
            result["related"]["relationship_bindings"],
        )
        self.assertEqual(
            result["provenance"]["claims"][0]["id"],
            "profiles.synthetic#severity-binding",
        )
        self.assertIn(
            "profiles.synthetic-schema",
            result["provenance"]["sources"],
        )

    def test_unknown_exact_entities_raise_not_found(self) -> None:
        methods = (
            self.catalog.get_clinical_object,
            self.catalog.get_feature,
            self.catalog.get_semantic_relationship,
            self.catalog.get_temporal_semantic,
            self.catalog.get_aggregation,
            self.catalog.get_guardrail,
            self.catalog.get_coverage,
            self.catalog.get_context,
            self.catalog.get_relationship_binding,
        )
        for method in methods:
            with self.subTest(method=method.__name__):
                with self.assertRaises(CatalogNotFoundError):
                    method("unknown.identifier")

    def test_code_lookup_accepts_feature_and_physical_binding(
        self,
    ) -> None:
        for identifier, profile in (
            ("pathology.severity", "profile-a"),
            ("profile-b:exams_b.path_group", None),
        ):
            with self.subTest(identifier=identifier):
                result = self.catalog.lookup_code(
                    identifier, "0", profile=profile
                )
                self.assertEqual(
                    result["meaning"], "Invasive breast cancer"
                )
                self.assertEqual(result["vocabulary"], "pathology.severity")

        with self.assertRaises(CatalogNotFoundError):
            self.catalog.lookup_code(
                "pathology.severity", "99", profile="profile-a"
            )

    def test_profile_table_surfaces_secondary_binding_layer(self) -> None:
        result = self.catalog.get_profile_table("profile-b", "exams_b")

        self.assertEqual(result["kind"], "profile_table")
        self.assertEqual(len(result["feature_bindings"]), 4)
        self.assertEqual(len(result["object_bindings"]), 2)
        for binding in result["object_bindings"]:
            self.assertEqual(
                binding["provenance"]["contexts"][0]["profiles"],
                ["profile-a", "profile-b"],
            )
        self.assertEqual(
            len(result["relationship_bindings"]["outgoing"]), 1
        )
        self.assertEqual(
            self.catalog.get_profile_table("profile-b", "exams_b"), result
        )

    def test_relationship_binding_get_and_search(self) -> None:
        exact = self.catalog.get_relationship_binding(
            "profile-b.exams.patient"
        )
        searched = self.catalog.search_relationship_bindings(
            profile="profile-b",
            table="patients_b",
            semantic_relationship="patient.has_exam",
        )

        self.assertEqual(exact["kind"], "relationship_binding")
        self.assertEqual(
            exact["semantic_relationships"][0]["id"], "patient.has_exam"
        )
        self.assertEqual(
            [
                item["id"]
                for item in exact["relationship_binding_paths"]
            ],
            ["profile-b.patient-exam-path"],
        )
        self.assertEqual(searched["count"], 1)
        self.assertEqual(
            searched["matches"][0]["id"], "profile-b.exams.patient"
        )
        self.assertEqual(searched["path_count"], 1)
        self.assertEqual(searched["path_total"], 1)
        self.assertEqual(
            searched["relationship_binding_paths"][0]["id"],
            "profile-b.patient-exam-path",
        )

    def test_relationship_search_returns_composed_semantic_paths(
        self,
    ) -> None:
        data = cloned_catalog()
        relationship = dict(
            data["semantic_relationships"]["patient.has_exam"]
        )
        relationship.update(
            {
                "label": "Patient has represented pathology",
                "kind": "association",
                "target_object": "pathology_diagnosis",
            }
        )
        data["semantic_relationships"][
            "patient.has_pathology"
        ] = relationship
        data["profile_bindings"]["profile-b"][
            "relationship_binding_paths"
        ][0]["semantic_relationship"] = "patient.has_pathology"
        catalog = Catalog.from_mapping(data)

        result = catalog.search_relationship_bindings(
            profile="profile-b",
            source_table="exams_b",
            target_table="patients_b",
            semantic_relationship="patient.has_pathology",
        )

        self.assertEqual(result["count"], 0)
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["path_count"], 1)
        self.assertEqual(result["path_total"], 1)
        self.assertEqual(
            result["relationship_binding_paths"][0][
                "relationship_bindings"
            ],
            ["profile-b.exams.patient"],
        )

        by_table = catalog.search_relationship_bindings(
            table="patients_b",
            semantic_relationship="patient.has_pathology",
        )
        self.assertEqual(by_table["path_count"], 1)

        edge_kind_only = catalog.search_relationship_bindings(
            kind="hierarchy",
            semantic_relationship="patient.has_pathology",
        )
        self.assertEqual(edge_kind_only["path_count"], 0)

    def test_relationship_search_validates_filters_and_limit(self) -> None:
        calls = (
            {"profile": "missing"},
            {"kind": "unknown"},
            {"semantic_relationship": "unknown"},
            {"table": "bad:table"},
            {"limit": 0},
        )
        for kwargs in calls:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(CatalogValidationError):
                    self.catalog.search_relationship_bindings(**kwargs)

    def test_discover_indexes_unbound_semantics_and_explains_matches(self) -> None:
        result = self.catalog.discover(
            "specimen date", kinds=["temporal_semantic"]
        )

        self.assertEqual(
            result["matches"][0]["identifier"],
            "specimen.collection_time",
        )
        self.assertTrue(result["matches"][0]["match_reasons"])
        self.assertTrue(
            result["matches"][0]["match_reasons"][0]["terms"]
        )
        self.assertEqual(
            result["matches"][0]["entity"]["feature_refs"], []
        )

    def test_discover_indexes_physical_aliases_only_for_selected_profile(
        self,
    ) -> None:
        unprofiled = self.catalog.discover(
            "clinical_a", kinds=["feature"]
        )
        selected = self.catalog.discover(
            "clinical_a", profile="profile-a", kinds=["feature"]
        )

        self.assertFalse(
            any(
                reason["field"].startswith("binding.")
                for match in unprofiled["matches"]
                for reason in match["match_reasons"]
            )
        )
        self.assertTrue(selected["matches"])
        self.assertTrue(
            any(
                reason["field"] == "binding.table"
                for match in selected["matches"]
                for reason in match["match_reasons"]
            )
        )

    def test_profile_column_exact_match_outranks_table_noise(self) -> None:
        data = cloned_catalog()
        profile = data["profile_bindings"]["profile-a"]
        profile["feature_bindings"][1]["column"] = "procdate_anon"
        profile["object_bindings"][1]["columns"] = ["procdate_anon"]
        profile["tables"][0]["columns"][1]["name"] = "procdate_anon"
        profile["tables"][0]["keys"][0]["columns"] = [
            "person_id",
            "procdate_anon",
        ]
        catalog = Catalog.from_mapping(data)

        unprofiled = catalog.discover(
            "procdate_anon", kinds=["feature"]
        )
        selected = catalog.discover(
            "procdate_anon",
            profile="profile-a",
            kinds=["feature"],
        )

        self.assertEqual(unprofiled["matches"], [])
        self.assertEqual(
            selected["matches"][0]["identifier"], "exam.study_date"
        )
        self.assertEqual(
            selected["matches"][0]["match_reasons"],
            [
                {
                    "field": "binding.column",
                    "terms": ["procdate"],
                    "matched_terms": ["procdate"],
                    "phrase_match": True,
                }
            ],
        )
    def test_discover_accepts_clinical_language_not_stable_ids(self) -> None:
        result = self.catalog.discover(
            "cancer diagnosis pathology result"
        )

        identifiers = {item["identifier"] for item in result["matches"]}
        self.assertIn("pathology_diagnosis", identifiers)
        self.assertIn("pathology.severity", identifiers)

    def test_discover_profile_reports_explicit_unsupported_coverage(self) -> None:
        result = self.catalog.discover(
            "specimen collection",
            profile="profile-a",
            kinds=["temporal_semantic"],
        )

        self.assertEqual(result["count"], 1)
        self.assertIn(
            "unsupported_in_profile",
            {item["category"] for item in result["diagnostics"]},
        )

    def test_discovery_distinguishes_filters_vocabulary_and_missing_coverage(
        self,
    ) -> None:
        filtered = self.catalog.discover(
            "specimen collection", kinds=["feature"]
        )
        self.assertIn(
            "filters_excluded_matches",
            {item["category"] for item in filtered["diagnostics"]},
        )

        vocabulary = self.catalog.discover("pathology severity frobnicate")
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

    def test_discovery_unknown_filters_are_diagnostic_not_false_absence(
        self,
    ) -> None:
        result = self.catalog.discover(
            "pathology", profile="unknown", kinds=["imaginary"]
        )

        self.assertEqual(result["matches"], [])
        self.assertEqual(
            result["diagnostics"][0]["category"], "unknown_filter"
        )
        self.assertNotIn(
            "no_catalog_coverage",
            {item["category"] for item in result["diagnostics"]},
        )

    def test_discovery_requires_terms_or_filters_and_valid_limit(self) -> None:
        with self.assertRaises(CatalogValidationError):
            self.catalog.discover("the and for")
        with self.assertRaises(CatalogValidationError):
            self.catalog.discover("pathology", limit=True)
        with self.assertRaises(CatalogValidationError):
            self.catalog.discover(123)  # type: ignore[arg-type]

        result = self.catalog.discover(
            "", kinds=["clinical_object"], limit=2
        )
        self.assertEqual(result["count"], 2)

    def test_discovery_order_and_limits_are_deterministic(self) -> None:
        first = self.catalog.discover("pathology", limit=3)
        second = self.catalog.discover("pathology", limit=3)

        self.assertEqual(first, second)
        self.assertEqual(first["count"], 3)
        self.assertGreater(first["total"], first["count"])

    def test_discovery_intent_bonuses_are_transparently_explained(
        self,
    ) -> None:
        queries = {
            "nearest prior exam": "longitudinal",
            "fallback coalesce proxy date": "temporal_fallback",
            "calibration probability risk": "probability_calibration",
            "one row per finding key": "finding_identity",
            "laterality side null": "laterality_role",
            "represented binary cancer endpoint": (
                "represented_binary_endpoint"
            ),
        }
        for query, intent in queries.items():
            with self.subTest(intent=intent):
                result = self.catalog.discover(query, limit=10)
                reasons = [
                    reason
                    for match in result["matches"]
                    for reason in match["match_reasons"]
                    if reason.get("intent") == intent
                ]
                self.assertTrue(reasons)
                self.assertTrue(
                    all(
                        reason["field"] == "query_intent"
                        and reason["semantic_cues"]
                        and reason["score_bonus"] > 0
                        for reason in reasons
                    )
                )

    def test_discovery_reserves_limited_safety_results_and_respects_kinds(
        self,
    ) -> None:
        data = cloned_catalog()
        guardrail = data["guardrails"][
            "temporal.no-universal-diagnosis-date"
        ]
        guardrail["category"] = "prohibition"
        guardrail["priority"] = "critical"
        guardrail["search_terms"].extend(["fallback", "coalesce", "proxy"])
        catalog = Catalog.from_mapping(data)

        result = catalog.discover(
            "procedure report exam fallback coalesce proxy date",
            limit=2,
        )
        self.assertEqual(result["count"], 2)
        self.assertIn(
            "temporal.no-universal-diagnosis-date",
            {match["identifier"] for match in result["matches"]},
        )
        self.assertLessEqual(
            sum(
                match["kind"] in {"guardrail", "coverage"}
                for match in result["matches"]
            ),
            1,
        )

        feature_only = catalog.discover(
            "procedure report exam fallback coalesce proxy date",
            kinds=["feature"],
            limit=2,
        )
        self.assertTrue(feature_only["matches"])
        self.assertEqual(
            {match["kind"] for match in feature_only["matches"]},
            {"feature"},
        )


if __name__ == "__main__":
    unittest.main()
