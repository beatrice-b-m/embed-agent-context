"""Standalone schema and artifact checks for the schema-v8 catalog set."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def walk_claim_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "claim_refs":
                refs.extend(nested)
            else:
                refs.extend(walk_claim_refs(nested))
    elif isinstance(value, list):
        for nested in value:
            refs.extend(walk_claim_refs(nested))
    return refs


class CatalogSetSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.documents = {
            "manifest": (
                read_json(CATALOG / "catalog-set.schema.json"),
                read_json(CATALOG / "catalog-set.json"),
            ),
            "semantic": (
                read_json(CATALOG / "semantic" / "catalog.schema.json"),
                read_json(CATALOG / "semantic" / "catalog.json"),
            ),
            "profile": (
                read_json(CATALOG / "profiles" / "profile.schema.json"),
                read_json(CATALOG / "profiles" / "open-v2.json"),
            ),
        }
        cls.extension_schema = read_json(
            CATALOG / "extensions" / "extension.schema.json"
        )

    def test_standalone_schemas_and_canonical_documents_validate(self) -> None:
        for name, (schema, document) in self.documents.items():
            with self.subTest(document=name):
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(document)
        Draft202012Validator.check_schema(self.extension_schema)

    def test_all_document_shapes_are_closed(self) -> None:
        for name, (schema, document) in self.documents.items():
            with self.subTest(document=name):
                mutated = deepcopy(document)
                mutated["unexpected"] = True
                with self.assertRaises(ValidationError):
                    Draft202012Validator(schema).validate(mutated)

    def test_manifest_uses_only_closed_explicit_resource_locators(self) -> None:
        schema, document = self.documents["manifest"]
        validator = Draft202012Validator(schema)

        file_manifest = deepcopy(document)
        file_manifest["semantic_catalog"] = {
            "kind": "file",
            "path": "../shared/semantic/catalog.json",
        }
        validator.validate(file_manifest)

        for locator in (
            {"kind": "bundled", "path": "semantic/catalog.json"},
            {"kind": "file", "path": "catalog.json", "resource": "x"},
            {"kind": "environment", "name": "CATALOG"},
        ):
            with self.subTest(locator=locator):
                invalid = deepcopy(document)
                invalid["semantic_catalog"] = locator
                with self.assertRaises(ValidationError):
                    validator.validate(invalid)

    def test_semantic_artifact_is_profile_independent(self) -> None:
        semantic = self.documents["semantic"][1]
        self.assertEqual(semantic["semantic_schema_version"], 8)
        self.assertEqual(semantic["coverage"], {})
        self.assertEqual(semantic["vocabularies"], {})
        self.assertNotIn("profiles", semantic)
        self.assertNotIn("profile_bindings", semantic)
        self.assertFalse(
            any(ref.startswith("open-v2.") for ref in walk_claim_refs(semantic))
        )
        for concept in semantic["concepts"].values():
            self.assertNotIn("vocabulary", concept)

    def test_open_v2_module_owns_release_specific_content(self) -> None:
        profile = self.documents["profile"][1]
        self.assertEqual(profile["profile"]["id"], "open-v2")
        self.assertEqual(profile["profile_schema_version"], 2)
        self.assertEqual(profile["requires"]["semantic_schema_version"], 8)
        self.assertTrue(profile["sources"])
        self.assertTrue(profile["contexts"])
        self.assertTrue(profile["contributions"]["coverage"])
        self.assertTrue(profile["qualifications"])
        self.assertTrue(profile["vocabularies"])
        self.assertTrue(
            all(
                value["scope"] == "profile_specific"
                for value in profile["sources"].values()
            )
        )
        self.assertTrue(
            all(
                value["scope"] == "profile_specific"
                for value in profile["contexts"].values()
            )
        )

    def test_internal_v2_profile_combines_magview_and_v1c_image_bindings(
        self,
    ) -> None:
        profile_schema = self.documents["profile"][0]
        manifest_schema = self.documents["manifest"][0]
        internal_profile = read_json(CATALOG / "profiles" / "internal-v2.json")
        internal_manifest = read_json(CATALOG / "internal-v2-catalog-set.json")

        Draft202012Validator(profile_schema).validate(internal_profile)
        Draft202012Validator(manifest_schema).validate(internal_manifest)
        self.assertEqual(internal_profile["profile"]["id"], "internal-v2")
        self.assertIn(
            "region_of_interest",
            internal_profile["contributions"]["clinical_objects"],
        )
        self.assertIn(
            "clinical.image-region-of-interest",
            internal_profile["contributions"]["semantic_relationships"],
        )
        binding = internal_profile["profile_binding"]
        self.assertEqual(
            [table["table"] for table in binding["tables"]],
            ["magview_all_cohorts_PACS_v2_anon", "metadata_all_cohorts_v1c"],
        )
        tables = {table["table"]: table for table in binding["tables"]}
        self.assertEqual(
            len(tables["magview_all_cohorts_PACS_v2_anon"]["columns"]), 152
        )
        metadata = tables["metadata_all_cohorts_v1c"]
        self.assertEqual(len(metadata["columns"]), 166)
        self.assertEqual(
            len({column["name"] for column in metadata["columns"]}), 166
        )
        self.assertTrue(all(column["nullable"] for column in metadata["columns"]))
        self.assertEqual(
            {column["physical_type"] for column in metadata["columns"]},
            {"string", "double", "int64"},
        )
        self.assertTrue(binding["feature_bindings"])
        self.assertTrue(binding["object_bindings"])
        self.assertTrue(binding["relationship_bindings"])
        image_side = {
            item["object"]: item
            for item in binding["object_bindings"]
            if item["object"] in {"image", "region_of_interest"}
        }
        self.assertEqual(set(image_side), {"image", "region_of_interest"})
        self.assertTrue(
            all(
                item["table"] == "metadata_all_cohorts_v1c"
                for item in image_side.values()
            )
        )
        self.assertEqual(
            image_side["image"]["instance_identity"]["columns"],
            ["anon_dicom_path"],
        )
        self.assertEqual(
            image_side["image"]["instance_identity"]["rows_per_instance"],
            "exactly_one",
        )
        self.assertNotIn("instance_identity", image_side["region_of_interest"])
        self.assertTrue(
            any(
                "clinical.image-region-of-interest"
                in item["semantic_relationships"]
                for item in binding["relationship_bindings"]
            )
        )
        exam_image = next(
            item
            for item in binding["relationship_bindings"]
            if item["id"] == "internal-v2.binding.relationship.exam-image"
        )
        self.assertEqual(
            exam_image["source"]["table"], "magview_all_cohorts_PACS_v2_anon"
        )
        self.assertEqual(
            exam_image["target"]["table"], "metadata_all_cohorts_v1c"
        )
        self.assertEqual(
            exam_image["cardinality"],
            {
                "targets_per_source": "zero_or_more",
                "sources_per_target": "zero_or_more",
            },
        )
        roi_coverage = internal_profile["contributions"]["coverage"][
            "coverage.internal-v2.roi-physical-binding"
        ]
        self.assertEqual(roi_coverage["status"], "supported")
        self.assertNotIn(
            "not_cataloged",
            {
                record["status"]
                for record in internal_profile["contributions"][
                    "coverage"
                ].values()
            },
        )
        self.assertIn(
            "6",
            internal_profile["vocabularies"][
                "internal-v2.pathology.severity"
            ]["codes"],
        )
        pathology_claims = {
            claim["id"]: claim
            for claim in internal_profile["contexts"][
                "internal-v2.magview-pathology-context"
            ]["claims"]
        }
        self.assertEqual(
            pathology_claims["path-severity-five-six-disagreement"]["status"],
            "reconciled",
        )
        self.assertEqual(
            internal_profile["vocabularies"][
                "internal-v2.pathology.severity"
            ]["codes"]["6"],
            "Invalid source value with no expected meaning",
        )
        patient = next(
            item
            for item in binding["object_bindings"]
            if item["object"] == "patient"
        )
        self.assertTrue(patient["instance_identity"]["longitudinal_identity"])
        finding = next(
            item
            for item in binding["object_bindings"]
            if item["object"] == "imaging_finding"
        )
        self.assertEqual(
            finding["instance_identity"]["columns"],
            ["acc_anon", "numfind"],
        )
        procedure = next(
            item
            for item in binding["object_bindings"]
            if item["object"] == "procedure"
        )
        self.assertEqual(
            procedure["instance_identity"]["columns"],
            ["empi_anon", "procdate_anon", "type", "bside"],
        )
        self.assertEqual(
            procedure["instance_identity"]["rows_per_instance"],
            "one_or_more",
        )
        feature_by_column = {
            item["column"]: item for item in binding["feature_bindings"]
        }
        side_meanings = {
            item["representation"]: item
            for item in feature_by_column["side"]["occurrence_interpretations"]
        }
        self.assertEqual(set(side_meanings), {"B", "null"})
        self.assertTrue(
            all(item["status"] == "verified" for item in side_meanings.values())
        )
        self.assertTrue(
            all(
                "both the left and right" in item["meaning"]
                for item in side_meanings.values()
            )
        )
        finding_number = feature_by_column["numfind"]
        synthetic = finding_number["occurrence_interpretations"][0]
        self.assertEqual(synthetic["representation"], "-9")
        self.assertEqual(synthetic["status"], "verified")
        self.assertIn("Synthetic contralateral", synthetic["meaning"])
        self.assertEqual(
            internal_profile["vocabularies"][
                "internal-v2.mri.other_finding"
            ]["parsing"],
            "comma_delimited_unordered",
        )
        self.assertNotIn(
            "C,G",
            internal_profile["vocabularies"][
                "internal-v2.mri.other_finding"
            ]["codes"],
        )
        self.assertIn(
            "internal-v2.v1c-metadata-context#parsed-dicom-element-semantics",
            internal_profile["contributions"]["concepts"][
                "internal-v2.image.compression_force"
            ]["claim_refs"],
        )
        specimen = next(
            item
            for item in binding["object_bindings"]
            if item["object"] == "pathology_specimen"
        )
        self.assertEqual(specimen["completeness"], "unknown")
        self.assertNotIn("instance_identity", specimen)

        all_ids = [
            record["id"]
            for collection in (
                "feature_bindings",
                "object_bindings",
                "tables",
                "relationship_bindings",
                "relationship_binding_paths",
            )
            for record in binding[collection]
        ]
        self.assertTrue(
            all(identifier.startswith("internal-v2.") for identifier in all_ids)
        )
        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_physical_inventory_is_independent_from_semantic_mappings(self) -> None:
        profiles = {
            "open-v2": self.documents["profile"][1],
            "internal-v2": read_json(CATALOG / "profiles" / "internal-v2.json"),
        }
        for profile_id, profile in profiles.items():
            with self.subTest(profile=profile_id):
                tables = {
                    table["table"]: {
                        column["name"]: column for column in table["columns"]
                    }
                    for table in profile["profile_binding"]["tables"]
                }
                self.assertTrue(tables)
                for mapping in profile["profile_binding"]["feature_bindings"]:
                    self.assertIn(mapping["column"], tables[mapping["table"]])
                    self.assertNotIn("physical_type", mapping)
                    self.assertNotIn("nullable", mapping)
                    self.assertNotIn("grain", mapping)
                    self.assertNotIn("role", mapping)
                    self.assertIn(
                        mapping["status"],
                        {
                            "direct",
                            "derived",
                            "conditional",
                            "ambiguous",
                            "unresolved",
                        },
                    )

    def test_binding_and_qualification_ids_are_authored_and_unique(self) -> None:
        profile = self.documents["profile"][1]
        binding = profile["profile_binding"]
        all_ids: list[str] = []
        for collection in (
            "feature_bindings",
            "object_bindings",
            "tables",
            "relationship_bindings",
            "relationship_binding_paths",
        ):
            identifiers = [record["id"] for record in binding[collection]]
            self.assertTrue(all(value.startswith("open-v2.") for value in identifiers))
            self.assertEqual(len(identifiers), len(set(identifiers)))
            all_ids.extend(identifiers)
        self.assertEqual(len(all_ids), len(set(all_ids)))

        qualifications = profile["qualifications"]
        self.assertEqual(
            set(qualifications), {record["id"] for record in qualifications.values()}
        )
        self.assertTrue(
            all(value.startswith("open-v2.") for value in qualifications)
        )

    def test_qualification_subjects_resolve_in_semantic_catalog(self) -> None:
        semantic = self.documents["semantic"][1]
        profile = self.documents["profile"][1]
        collection_for_kind = {
            "clinical_object": "clinical_objects",
            "concept": "concepts",
            "semantic_relationship": "semantic_relationships",
            "temporal_semantic": "temporal_semantics",
            "aggregation": "aggregations",
            "guardrail": "guardrails",
        }
        for qualification in profile["qualifications"].values():
            subject = qualification["subject"]
            self.assertIn(
                subject["id"],
                {
                    **semantic[collection_for_kind[subject["kind"]]],
                    **profile["contributions"][collection_for_kind[subject["kind"]]],
                },
            )
            self.assertTrue(qualification["claim_refs"])

    def test_profile_vocabularies_are_selected_on_feature_bindings(self) -> None:
        semantic = self.documents["semantic"][1]
        profile = self.documents["profile"][1]
        selected = {
            item["vocabulary"]
            for item in profile["profile_binding"]["feature_bindings"]
            if "vocabulary" in item
        }
        self.assertEqual(selected, set(profile["vocabularies"]))
        self.assertTrue(
            all(item["concept"] in {
                    **semantic["concepts"],
                    **profile["contributions"]["concepts"],
                }
                for item in profile["profile_binding"]["feature_bindings"])
        )

    def test_empty_extension_validates_and_old_revision_fields_are_rejected(self) -> None:
        extension = {
            "$schema": "./extension.schema.json",
            "extension_schema_version": 2,
            "extension": {
                "id": "project.example",
                "version": "0.1.0",
                "label": "Example project extension",
                "lifecycle_status": "work_in_progress",
            },
            "applies_to": {"profile": "open-v2"},
            "requires": {
                "semantic_schema_version": 8,
                "profile_schema_version": 2,
                "extensions": [],
            },
            "contributions": {
                "clinical_objects": {},
                "concepts": {},
                "semantic_relationships": {},
                "temporal_semantics": {},
                "aggregations": {},
                "guardrails": {},
                "coverage": {},
            },
            "qualifications": {},
            "feature_lineage": {},
            "sources": {},
            "contexts": {},
            "vocabularies": {},
            "profile_binding": {
                "feature_bindings": [],
                "object_bindings": [],
                "tables": [],
                "relationship_bindings": [],
                "relationship_binding_paths": [],
            },
        }
        validator = Draft202012Validator(self.extension_schema)
        validator.validate(extension)

        with_source_observation = deepcopy(extension)
        with_source_observation["contributions"]["concepts"][
            "project.example.observed_feature"
        ] = {
            "label": "Observed feature",
            "definition": "An example feature observed in a source artifact.",
            "feature_kind": "categorical",
            "domains": ["technical"],
            "search_terms": ["observed feature"],
            "caveats": [],
            "evidence": ["observed_source_values"],
            "objects": ["image"],
        }
        validator.validate(with_source_observation)

        with_source_observation["contributions"]["concepts"][
            "project.example.observed_feature"
        ]["evidence"] = ["observed_v2_values"]
        with self.assertRaises(ValidationError):
            validator.validate(with_source_observation)

        invalid = deepcopy(extension)
        invalid["revisions"] = []
        with self.assertRaises(ValidationError):
            validator.validate(invalid)


if __name__ == "__main__":
    unittest.main()
