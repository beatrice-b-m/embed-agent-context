"""Acceptance contracts for the checked-in clinical-semantic catalog."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from embed_context import load_catalog


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "catalog" / "catalog-set.json"
SEMANTIC_PATH = REPO_ROOT / "catalog" / "semantic" / "catalog.json"
PROFILE_PATH = REPO_ROOT / "catalog" / "profiles" / "open-v2.json"
INTERNAL_MANIFEST_PATH = REPO_ROOT / "catalog" / "internal-v2-catalog-set.json"


class ClinicalSemanticCatalogAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(SEMANTIC_PATH.read_text(encoding="utf-8"))
        cls.profile_raw = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))[
            "profile_binding"
        ]
        cls.catalog = load_catalog(CATALOG_PATH)

    def test_v8_models_the_clinical_graph_without_analysis_patterns(self) -> None:
        self.assertEqual(self.catalog.schema_version, 8)
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

    def test_internal_v2_profiles_magview_and_v1c_image_metadata(
        self,
    ) -> None:
        internal = load_catalog(INTERNAL_MANIFEST_PATH)
        self.assertNotIn("region_of_interest", self.catalog.clinical_objects)
        self.assertIn("image", self.catalog.clinical_objects)
        self.assertIn("image", internal.clinical_objects)
        self.assertIn("region_of_interest", internal.clinical_objects)
        self.assertIn(
            "clinical.image-region-of-interest",
            internal.semantic_relationships,
        )
        roi = internal.discover(
            "region of interest attached to image",
            profile="internal-v2",
            limit=10,
        )
        self.assertIn(
            "region_of_interest",
            {item["identifier"] for item in roi["matches"]},
        )
        binding = internal.profile_bindings["internal-v2"]
        self.assertEqual(
            {table.table for table in binding.tables},
            {"magview_all_cohorts_PACS_v2_anon", "metadata_all_cohorts_v1c"},
        )
        expected_bound_objects = {
            "patient",
            "breast_imaging_episode",
            "imaging_exam",
            "breast_side",
            "imaging_finding",
            "imaging_interpretation",
            "procedure",
            "pathology_specimen",
            "pathology_observation",
            "pathology_diagnosis",
            "image",
            "region_of_interest",
        }
        self.assertLessEqual(
            expected_bound_objects,
            {item.object for item in binding.object_bindings},
        )
        self.assertEqual(
            {
                item.table
                for item in binding.object_bindings
                if item.object in {"image", "region_of_interest"}
            },
            {"metadata_all_cohorts_v1c"},
        )
        self.assertTrue(binding.relationship_bindings)
        self.assertTrue(
            any(
                item.source.table == "magview_all_cohorts_PACS_v2_anon"
                and item.target.table == "magview_all_cohorts_PACS_v2_anon"
                for item in binding.relationship_bindings
            )
        )
        self.assertTrue(
            any(
                "clinical.image-region-of-interest"
                in item.semantic_relationships
                for item in binding.relationship_bindings
            )
        )
        severity = [
            item
            for item in binding.feature_bindings
            if item.column == "path_severity"
        ]
        self.assertTrue(severity)
        self.assertEqual(
            {item.concept for item in severity}, {"pathology.severity"}
        )
        self.assertEqual(severity[0].status, "derived")
        self.assertTrue(
            {
                "breast_side.pathology_severity_aggregate",
                "exam.pathology_severity_aggregate",
            }.isdisjoint(item.concept for item in binding.feature_bindings)
        )
        episode = next(
            item
            for item in binding.object_bindings
            if item.object == "breast_imaging_episode"
        )
        self.assertEqual(episode.authority, "reference")
        patient = next(
            item for item in binding.object_bindings if item.object == "patient"
        )
        self.assertTrue(patient.instance_identity.longitudinal_identity)
        finding = next(
            item
            for item in binding.object_bindings
            if item.object == "imaging_finding"
        )
        self.assertEqual(
            finding.instance_identity.columns,
            ("acc_anon", "numfind"),
        )
        specimen = next(
            item
            for item in binding.object_bindings
            if item.object == "pathology_specimen"
        )
        self.assertEqual(specimen.completeness, "unknown")
        self.assertEqual(specimen.authority, "unspecified")
        self.assertIsNone(specimen.instance_identity)
        statuses_by_column = {
            item.column: item.status for item in binding.feature_bindings
        }
        self.assertEqual(statuses_by_column["studydate_anon"], "direct")
        self.assertEqual(statuses_by_column["procdate_anon"], "direct")
        self.assertEqual(statuses_by_column["pdate_anon"], "ambiguous")
        self.assertEqual(
            statuses_by_column["cancer_outcome_registry_id"],
            "conditional",
        )
        roi_relationship = internal.semantic_relationships[
            "clinical.image-region-of-interest"
        ]
        self.assertEqual(
            roi_relationship.sources_per_target,
            "exactly_one",
        )

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

    def test_internal_v2_binds_v1c_image_metadata_and_roi_collections(
        self,
    ) -> None:
        internal = load_catalog(INTERNAL_MANIFEST_PATH)
        binding = internal.profile_bindings["internal-v2"]
        metadata = next(
            table
            for table in binding.tables
            if table.table == "metadata_all_cohorts_v1c"
        )

        # Complete physical inventory, conservatively typed and nullable.
        self.assertEqual(len(metadata.columns), 166)
        self.assertEqual(
            {column.physical_type for column in metadata.columns},
            {"string", "double", "int64"},
        )
        self.assertTrue(all(column.nullable for column in metadata.columns))
        self.assertIn("image", metadata.grain)
        self.assertIn(
            "one row per region of interest",
            " ".join(metadata.caveats),
        )

        # Image grain and the absence of an unjustified instance identity.
        image = next(
            item
            for item in binding.object_bindings
            if item.object == "image"
        )
        self.assertEqual(image.table, "metadata_all_cohorts_v1c")
        self.assertEqual(image.completeness, "partial")
        self.assertEqual(image.authority, "preferred")
        self.assertEqual(image.derivation, "source")
        self.assertIsNone(image.instance_identity)
        self.assertEqual(
            internal.coverage["coverage.internal-v2.v1c-image-instance-identity"]
            .status,
            "unresolved",
        )
        locator_key = next(
            key
            for key in metadata.keys
            if key.columns == ("anon_dicom_path",)
        )
        self.assertEqual(locator_key.kind, "technical")
        self.assertEqual(locator_key.uniqueness, "unique")
        self.assertEqual(locator_key.completeness, "incomplete")
        self.assertIn(
            "intended to be defined for every extracted image row",
            " ".join(locator_key.caveats),
        )

        # Co-located patient, exam, and image-derived side projections.
        by_object = {
            item.object: item
            for item in binding.object_bindings
            if item.table == "metadata_all_cohorts_v1c"
        }
        self.assertEqual(by_object["patient"].columns, ("empi_anon",))
        self.assertTrue(
            by_object["patient"].instance_identity.longitudinal_identity
        )
        self.assertEqual(
            by_object["imaging_exam"].instance_identity.columns,
            ("acc_anon",),
        )
        self.assertFalse(
            by_object["imaging_exam"].instance_identity.longitudinal_identity
        )
        self.assertIn(
            "one distinct exam across EMBED",
            " ".join(by_object["imaging_exam"].caveats),
        )
        self.assertEqual(
            by_object["breast_side"].columns,
            ("acc_anon", "ImageLateralityFinal"),
        )
        self.assertEqual(by_object["breast_side"].derivation, "derived")
        self.assertIsNone(by_object["breast_side"].instance_identity)

        # Cross-table exam-to-image route, explicitly incomplete from V2.
        exam_image = next(
            item
            for item in binding.relationship_bindings
            if item.id == "internal-v2.binding.relationship.exam-image"
        )
        self.assertEqual(
            (exam_image.source.table, exam_image.target.table),
            ("magview_all_cohorts_PACS_v2_anon", "metadata_all_cohorts_v1c"),
        )
        self.assertEqual(exam_image.source.columns, ("acc_anon",))
        self.assertEqual(exam_image.target.columns, ("acc_anon",))
        self.assertEqual(exam_image.targets_per_source, "zero_or_more")
        self.assertEqual(exam_image.sources_per_target, "zero_or_more")
        self.assertIn("clinical.exam-image", exam_image.semantic_relationships)
        caveats = " ".join(exam_image.caveats)
        self.assertIn("incomplete relative to internal clinical V2", caveats)
        self.assertIn("no matching V1c image row", caveats)
        self.assertIn("not evidence that the exam had no images", caveats)
        self.assertIn("inner join", caveats)
        hazards = " ".join(exam_image.join_hazards)
        self.assertIn("consistency check", hazards)
        self.assertIn("source defect", hazards)
        qualification = internal.qualifications[
            "internal-v2.qualification.semantic_relationship."
            "clinical.exam-image"
        ]
        self.assertEqual(qualification.applicability, "supported")

        # Image metadata concepts resolve and keep DICOM, derived, and
        # enrichment meanings separate.
        statuses = {
            item.column: item.status
            for item in binding.feature_bindings
            if item.table == "metadata_all_cohorts_v1c"
        }
        self.assertEqual(statuses["Modality"], "direct")
        self.assertEqual(statuses["ImageType"], "direct")
        self.assertEqual(statuses["FinalImageType"], "derived")
        self.assertEqual(statuses["ImageLaterality"], "direct")
        self.assertEqual(statuses["LateralityDeriveFlag"], "ambiguous")
        self.assertEqual(statuses["category"], "unresolved")
        self.assertEqual(statuses["has_pix_array"], "unresolved")
        self.assertEqual(statuses["anon_dicom_path"], "direct")
        self.assertEqual(statuses["png_path"], "conditional")
        concepts_by_column = {
            item.column: item.concept
            for item in binding.feature_bindings
            if item.table == "metadata_all_cohorts_v1c"
        }
        self.assertEqual(
            concepts_by_column["empi_anon"], "identity.patient_identifier"
        )
        self.assertEqual(
            concepts_by_column["acc_anon"], "exam.accession_identifier"
        )
        for concept in set(concepts_by_column.values()):
            with self.subTest(concept=concept):
                self.assertIn(concept, internal.concepts)
        self.assertEqual(
            internal.concepts["internal-v2.image.dicom_file_locator"]
            .feature_kind,
            "technical",
        )
        self.assertEqual(
            internal.concepts["internal-v2.image.dicom_file_locator"].objects,
            (),
        )
        modality_codes = dict(
            internal.vocabularies[
                "internal-v2.vocabulary.image.source_modality"
            ].codes
        ).keys()
        image_type_codes = dict(
            internal.vocabularies[
                "internal-v2.vocabulary.image.derived_image_type"
            ].codes
        ).keys()
        self.assertTrue({"2D", "3D", "cview"} <= set(image_type_codes))
        self.assertTrue(set(modality_codes).isdisjoint(image_type_codes))
        self.assertEqual(
            set(
                dict(
                    internal.vocabularies[
                        "internal-v2.vocabulary.image.derived_laterality"
                    ].codes
                )
            ),
            {"L", "R"},
        )
        burned_in = internal.concepts[
            "internal-v2.image.burned_in_annotation_flag"
        ]
        self.assertIn("sufficient burned-in annotation", burned_in.definition)
        self.assertEqual(
            set(
                dict(
                    internal.vocabularies[
                        "internal-v2.vocabulary.image.burned_in_annotation"
                    ].codes
                )
            ),
            {"YES", "NO"},
        )
        self.assertEqual(
            {state.id for state in burned_in.missing_states},
            {"absent-attribute"},
        )

        # ROI collections are bound without inventing a row-per-ROI identity.
        roi = next(
            item
            for item in binding.object_bindings
            if item.object == "region_of_interest"
        )
        self.assertEqual(roi.table, "metadata_all_cohorts_v1c")
        self.assertEqual(roi.derivation, "derived")
        self.assertIsNone(roi.instance_identity)
        self.assertEqual(
            set(roi.columns),
            {"num_ROI", "ROI_coords", "ROI_frames", "ROI_depth_derived"},
        )
        roi_caveats = " ".join(roi.caveats)
        self.assertIn("zero or more regions", roi_caveats)
        self.assertIn("row-per-region representation", roi_caveats)
        self.assertEqual(statuses["num_ROI"], "derived")
        self.assertEqual(statuses["ROI_coords"], "ambiguous")
        self.assertEqual(statuses["ROI_frames"], "derived")
        self.assertEqual(statuses["ROI_depth_derived"], "derived")
        roi_route = next(
            item
            for item in binding.relationship_bindings
            if item.id
            == "internal-v2.binding.relationship.image-region-of-interest"
        )
        self.assertEqual(roi_route.source.table, roi_route.target.table)
        self.assertEqual(roi_route.targets_per_source, "zero_or_more")
        self.assertEqual(roi_route.sources_per_target, "exactly_one")
        self.assertIn(
            "intended to be defined for every extracted image row",
            " ".join(roi_route.caveats),
        )
        self.assertEqual(
            internal.coverage["coverage.internal-v2.roi-physical-binding"]
            .status,
            "supported",
        )
        self.assertEqual(
            internal.coverage[
                "coverage.internal-v2.v1c-roi-coordinate-geometry"
            ].status,
            "unresolved",
        )
        self.assertNotIn(
            "not_cataloged",
            {
                record.status
                for record in internal.coverage.values()
                if "roi" in record.subject or "roi" in str(record.subject_kind)
            },
        )

        # No future ultrasound or MRI extraction is represented.
        self.assertEqual(
            internal.coverage[
                "coverage.internal-v2.v1c-image-modality-coverage"
            ].status,
            "unresolved",
        )
        self.assertNotIn("MRI", modality_codes)
        metadata_columns = {column.name for column in metadata.columns}
        self.assertTrue(
            all(
                "ultrasound" not in name.lower() and "mri" not in name.lower()
                for name in metadata_columns
            )
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
        self.assertEqual(timestamp_guardrail["category"], "prohibition")
        self.assertEqual(timestamp_guardrail["priority"], "critical")
        self.assertIn("Do not coalesce", timestamp_guardrail["statement"])
        self.assertIn(
            "remains missing", timestamp_guardrail["rationale"]
        )

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
                feature_text = json.dumps(
                    self.catalog.get_feature(feature_id)["feature"]
                )
                self.assertIn("Do not coalesce", feature_text)
                self.assertIn("separately named endpoint", feature_text)

        for coverage_id in (
            "coverage.open-v2.specimen-time",
            "coverage.open-v2.downstream-availability-time",
        ):
            with self.subTest(coverage=coverage_id):
                coverage = self.catalog.get_coverage(coverage_id)["coverage"]
                self.assertEqual(coverage["status"], "unsupported")
                self.assertEqual(coverage["profiles"], ["open-v2"])
        downstream = self.catalog.get_coverage(
            "coverage.open-v2.downstream-availability-time"
        )["coverage"]
        self.assertNotIn(
            "analysis-specific justification", json.dumps(downstream)
        )
        self.assertIn("Do not coalesce", json.dumps(downstream))

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
        self.assertEqual(finding["status"], "analyst_defined")
        self.assertIsNone(finding["result_concept"])
        self.assertIn(
            "clinical.finding-pathology-observation",
            finding["semantic_relationships"],
        )
        self.assertIn("earliest linked outcome", finding["method"])
        self.assertIn("estimand dependence", finding["ordering"])

        patient = self.catalog.get_aggregation(
            "aggregation.pathology-severity-to-patient"
        )["aggregation"]
        self.assertEqual(patient["status"], "analyst_defined")
        self.assertIsNone(patient["result_concept"])
        patient_coverage = self.catalog.get_coverage(
            "coverage.open-v2.patient-pathology-aggregate"
        )["coverage"]
        self.assertEqual(patient_coverage["status"], "unsupported")

    def test_longitudinal_search_traverses_candidate_exam_to_patient(
        self,
    ) -> None:
        patient_exam = self.catalog.get_semantic_relationship(
            "clinical.patient-exam"
        )["semantic_relationship"]
        patient_pathology = self.catalog.get_semantic_relationship(
            "clinical.patient-pathology-observation"
        )["semantic_relationship"]
        self.assertIn("patient timeline", json.dumps(patient_exam))
        self.assertIn(
            "pathology accession to candidate exam to patient",
            json.dumps(patient_pathology),
        )
        self.assertIn(
            "not necessarily the index exam accession",
            json.dumps(patient_pathology),
        )

        guardrail = self.catalog.get_guardrail(
            "guardrail.longitudinal-search-is-patient-scoped"
        )["guardrail"]
        self.assertEqual(guardrail["category"], "prohibition")
        self.assertEqual(guardrail["priority"], "critical")
        self.assertIn("do not restrict", guardrail["statement"])
        self.assertLessEqual(
            {
                "clinical.patient-exam",
                "clinical.patient-pathology-observation",
            },
            set(guardrail["semantic_relationships"]),
        )

        binding = next(
            item
            for item in self.profile_raw["relationship_bindings"]
            if item["id"] == "open-v2.pathology_findings_anon.exam"
        )
        binding_text = json.dumps(binding)
        self.assertIn("candidate exam", binding_text)
        self.assertIn("Do not equate pathology acc_anon", binding_text)
        self.assertNotIn(
            "clinical.patient-pathology-observation",
            binding["semantic_relationships"],
        )
        path = self.profile_raw["relationship_binding_paths"][0]
        self.assertEqual(
            path["semantic_relationship"],
            "clinical.patient-pathology-observation",
        )
        self.assertEqual(
            path["relationship_bindings"],
            [
                "open-v2.pathology_findings_anon.exam",
                "open-v2.exam_level_anon.patient",
            ],
        )

    def test_finding_number_distinguishes_clinical_identity_from_rows(
        self,
    ) -> None:
        finding_number = self.catalog.get_feature("imaging.finding_number")[
            "feature"
        ]
        finding_text = json.dumps(finding_number)
        self.assertIn("(acc_anon, numfind)", finding_text)
        self.assertIn("-9", finding_text)
        self.assertIn("multiple physical rows", finding_text)
        self.assertIn("not a persistent lesion identifier", finding_text)
        self.assertNotIn(
            "other nonpositive values remain unresolved", finding_text
        )
        finding_bindings = [
            item
            for item in self.profile_raw["object_bindings"]
            if item["object"] == "imaging_finding"
        ]
        self.assertEqual(len(finding_bindings), 2)
        for binding in finding_bindings:
            with self.subTest(table=binding["table"]):
                identity = binding["instance_identity"]
                self.assertEqual(
                    identity["columns"], ["acc_anon", "numfind"]
                )
                self.assertEqual(identity["rows_per_instance"], "one_or_more")
                self.assertFalse(identity["longitudinal_identity"])
                self.assertEqual(
                    identity["reserved_exceptions"][0]["representation"],
                    "-9",
                )

    def test_laterality_null_meaning_is_binding_specific(self) -> None:
        bindings = {
            (item["table"], item["column"]): item
            for item in self.profile_raw["feature_bindings"]
            if item["column"] in {"side", "bside"}
        }
        finding = bindings[("imaging_findings_anon", "side")][
            "occurrence_interpretations"
        ][0]
        pathology_finding = bindings[("pathology_findings_anon", "side")][
            "occurrence_interpretations"
        ][0]
        biopsy = bindings[("pathology_findings_anon", "bside")][
            "occurrence_interpretations"
        ][0]
        side_record = bindings[("side_level_anon", "side")][
            "occurrence_interpretations"
        ][0]
        wide_side = bindings[("combined_anon", "side")][
            "occurrence_interpretations"
        ][0]
        wide_biopsy = bindings[("combined_anon", "bside")][
            "occurrence_interpretations"
        ][0]

        self.assertIn("bilateral", finding["meaning"])
        self.assertIn("bilateral", pathology_finding["meaning"])
        self.assertIn("not bilateral", biopsy["meaning"])
        self.assertIn("breast-side record", side_record["meaning"])
        self.assertEqual(wide_side["status"], "unresolved")
        self.assertEqual(wide_biopsy["status"], "unresolved")
        biopsy_concept = self.catalog.get_feature("pathology.biopsy_side")[
            "feature"
        ]
        self.assertIn(
            "occurrence- and profile-specific",
            " ".join(biopsy_concept["caveats"]),
        )
        self.assertNotIn(
            "not documented",
            " ".join(biopsy_concept["caveats"]),
        )

    def test_risk_probability_metrics_remain_unresolved(self) -> None:
        guardrail = self.catalog.get_guardrail(
            "guardrail.risk-probability-readiness"
        )["guardrail"]
        guardrail_text = json.dumps(guardrail)
        self.assertEqual(guardrail["priority"], "critical")
        self.assertIn("Brier score", guardrail_text)
        self.assertIn("model version", guardrail_text)
        self.assertIn("Association or ranking", guardrail_text)

        coverage = self.catalog.get_coverage(
            "coverage.open-v2.risk-probability-calibration-readiness"
        )["coverage"]
        self.assertEqual(coverage["status"], "unresolved")
        self.assertEqual(coverage["profiles"], ["open-v2"])
        self.assertIn("physically represented", coverage["summary"])
        self.assertIn("not mark", json.dumps(coverage))

        nci = self.catalog.get_feature("risk.nci_five_year")
        self.assertIn(
            "guardrail.risk-probability-readiness",
            nci["related"]["guardrails"],
        )
        nci_binding = next(
            item
            for item in self.profile_raw["feature_bindings"]
            if item["concept"] == "risk.nci_five_year"
        )
        self.assertEqual(
            {
                item["representation"]
                for item in nci_binding["occurrence_interpretations"]
            },
            {"-35", "-2", "100"},
        )
        self.assertTrue(
            all(
                item["status"] == "unresolved"
                for item in nci_binding["occurrence_interpretations"]
            )
        )

        risk_outputs = {
            identifier
            for identifier, concept in self.raw["concepts"].items()
            if concept["feature_kind"] == "model_output"
            and "risk" in concept["domains"]
        }
        self.assertEqual(
            set(guardrail["concepts"]),
            risk_outputs,
        )
        risk_context = self.catalog.get_context("open-v2.risk-context")[
            "context"
        ]
        self.assertEqual(
            set(risk_context["related_concepts"]),
            risk_outputs,
        )
        bindings_by_concept = {
            item["concept"]: item
            for item in self.profile_raw["feature_bindings"]
            if item["concept"] in risk_outputs
        }
        self.assertEqual(set(bindings_by_concept), risk_outputs)
        for identifier in sorted(risk_outputs):
            with self.subTest(risk_output=identifier):
                feature = self.catalog.get_feature(identifier)
                self.assertIn(
                    "guardrail.risk-probability-readiness",
                    feature["related"]["guardrails"],
                )
                self.assertIn(
                    "open-v2.risk-context",
                    feature["related"]["contexts"],
                )
                interpretations = bindings_by_concept[identifier][
                    "occurrence_interpretations"
                ]
                self.assertTrue(interpretations)
                self.assertTrue(
                    all(
                        item["status"] == "unresolved"
                        and "open-v2.risk-context#risk-semantics"
                        in item["claim_refs"]
                        and "not validated as a probability-like prediction"
                        in item["meaning"]
                        for item in interpretations
                    )
                )

    def test_represented_endpoints_and_policy_choices_are_not_failures(
        self,
    ) -> None:
        endpoint = self.catalog.get_guardrail(
            "guardrail.incomplete-outcome-capture"
        )["guardrail"]
        endpoint_text = json.dumps(endpoint)
        self.assertIn("no represented biopsy or cancer event", endpoint_text)
        self.assertIn("never biopsied", endpoint_text)
        self.assertIn("observation proxies", endpoint_text)

        selection = self.catalog.get_guardrail(
            "guardrail.attached-pathology-selection"
        )["guardrail"]
        self.assertIn("not inherently invalid", selection["rationale"])
        self.assertIn("pathology-observed estimand", selection["statement"])

        choices = self.catalog.get_guardrail(
            "guardrail.longitudinal-boundaries-are-analyst-choices"
        )["guardrail"]
        self.assertEqual(choices["category"], "analyst_choice")
        self.assertIn("same-day", choices["statement"])
        self.assertIn("episodes", choices["statement"])
        self.assertIn("equally near", choices["statement"])

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
            "guardrail.longitudinal-search-is-patient-scoped",
            "guardrail.longitudinal-boundaries-are-analyst-choices",
            "guardrail.risk-probability-readiness",
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
                self.assertIn(
                    guardrail["category"],
                    {"prohibition", "analyst_choice", "interpretation_limit"},
                )
                self.assertIn(
                    guardrail["priority"],
                    {"critical", "high", "standard"},
                )

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

    def test_review_prompts_discover_the_applicable_constraints(self) -> None:
        cases = (
            (
                "most recent prior cancer",
                "guardrail.longitudinal-search-is-patient-scoped",
            ),
            (
                "procedure report exam fallback coalesce",
                "guardrail.timestamps-answer-different-questions",
            ),
            (
                "risk probability calibration Brier score",
                "guardrail.risk-probability-readiness",
            ),
            (
                "represented binary cancer endpoint",
                "guardrail.incomplete-outcome-capture",
            ),
        )
        for query, expected in cases:
            with self.subTest(query=query):
                result = self.catalog.discover(
                    query,
                    profile="open-v2",
                    limit=20,
                )
                self.assertIn(
                    expected,
                    {item["identifier"] for item in result["matches"]},
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
        profile = self.profile_raw
        self.assertEqual(
            set(profile),
            {
                "feature_bindings",
                "object_bindings",
                "tables",
                "relationship_bindings",
                "relationship_binding_paths",
            },
        )

        combined = self.catalog.get_profile_table("open-v2", "combined_anon")
        self.assertEqual(combined["kind"], "profile_table")
        self.assertEqual(combined["identifier"], "open-v2:combined_anon")
        projected_objects = {
            item["object"]
            for item in combined["object_bindings"]
            if item.get("derivation") == "projected"
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
            for binding in self.profile_raw["feature_bindings"]
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
            for identifier, source in {
                **self.raw["sources"],
                **json.loads(PROFILE_PATH.read_text(encoding="utf-8"))["sources"],
            }.items()
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
