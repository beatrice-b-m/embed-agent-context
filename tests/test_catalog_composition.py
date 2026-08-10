"""Acceptance tests for semantic-v8/profile-v2 catalog composition."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from embed_context import CatalogAmbiguousError, CatalogValidationError, load_catalog
from embed_context.catalog import _resolve_catalog


ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_PATH = ROOT / "catalog/semantic/catalog.json"
PROFILE_PATH = ROOT / "catalog/profiles/open-v2.json"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def write_json(path: Path, value: dict[str, Any]) -> Path:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def empty_extension(identifier: str = "project.alpha") -> dict[str, Any]:
    return {
        "$schema": "./extension.schema.json",
        "extension_schema_version": 2,
        "extension": {
            "id": identifier,
            "version": "0.1.0",
            "label": "Synthetic project extension",
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


class CatalogCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def load_profile(
        self,
        profile: dict[str, Any],
        *,
        semantic: dict[str, Any] | None = None,
        extensions: list[dict[str, Any]] | None = None,
    ):
        semantic_path = write_json(
            self.directory / "semantic.json", semantic or read_json(SEMANTIC_PATH)
        )
        profile_path = write_json(self.directory / "profile.json", profile)
        extension_paths = [
            write_json(self.directory / f"extension-{index}.json", value)
            for index, value in enumerate(extensions or ())
        ]
        return load_catalog(
            semantic_path,
            profile_paths=[profile_path],
            extension_paths=extension_paths,
            include_default_profiles=False,
        )

    def test_default_and_semantic_only_catalogs_use_v8(self) -> None:
        catalog = load_catalog()
        self.assertEqual(catalog.schema_version, 8)
        self.assertEqual(catalog.configuration["semantic_schema_version"], 8)
        self.assertEqual(catalog.configuration["profile_schema_versions"], {"open-v2": 2})
        self.assertTrue(catalog.profile_tables[0].columns)
        summary = catalog.summary()
        self.assertNotIn("binding_grains", summary)
        self.assertEqual(
            summary["physical_columns"],
            sum(len(table.columns) for table in catalog.profile_tables),
        )
        self.assertEqual(summary["feature_mappings"], len(catalog.feature_bindings))
        self.assertEqual(
            summary["mapping_statuses"],
            ["direct", "derived", "conditional", "ambiguous", "unresolved"],
        )
        self.assertEqual(
            summary["observed_mapping_statuses"],
            sorted({binding.status for binding in catalog.feature_bindings}),
        )
        self.assertEqual(
            summary["table_grains"],
            sorted({table.grain for table in catalog.profile_tables if table.grain}),
        )

        semantic_only = load_catalog(SEMANTIC_PATH)
        self.assertEqual(semantic_only.schema_version, 8)
        self.assertEqual(semantic_only.profiles, ())

    def test_legacy_catalog_and_outdated_modules_are_fatal(self) -> None:
        legacy_path = write_json(
            self.directory / "legacy-v6.json",
            {"$schema": "./catalog.schema.json", "schema_version": 6},
        )
        with self.assertRaisesRegex(CatalogValidationError, "no longer supported"):
            load_catalog(legacy_path)

        semantic = read_json(SEMANTIC_PATH)
        semantic["semantic_schema_version"] = 7
        with self.assertRaises(CatalogValidationError):
            load_catalog(write_json(self.directory / "semantic-v7.json", semantic))

        profile = read_json(PROFILE_PATH)
        profile["profile_schema_version"] = 1
        with self.assertRaises(CatalogValidationError):
            self.load_profile(profile)

        extension = empty_extension()
        extension["extension_schema_version"] = 1
        with self.assertRaises(CatalogValidationError):
            self.load_profile(read_json(PROFILE_PATH), extensions=[extension])

    def test_profile_can_contribute_every_semantic_registry(self) -> None:
        semantic = read_json(SEMANTIC_PATH)
        profile = read_json(PROFILE_PATH)
        examples = {
            collection: next(
                iter(
                    semantic[collection].values()
                    or profile["contributions"][collection].values()
                )
            )
            for collection in (
                "clinical_objects",
                "concepts",
                "semantic_relationships",
                "temporal_semantics",
                "aggregations",
                "guardrails",
                "coverage",
            )
        }
        for collection, raw in examples.items():
            record = deepcopy(raw)
            record["availability"] = {"scope": "profiles", "profiles": ["open-v2"]}
            profile["contributions"][collection][f"profile.test.{collection}"] = record

        catalog = self.load_profile(profile, semantic=semantic)
        for collection in examples:
            kind = {
                "clinical_objects": "clinical_object",
                "concepts": "concept",
                "semantic_relationships": "semantic_relationship",
                "temporal_semantics": "temporal_semantic",
                "aggregations": "aggregation",
                "guardrails": "guardrail",
                "coverage": "coverage",
            }[collection]
            origin = catalog.origins[f"{kind}:profile.test.{collection}"]
            self.assertEqual(origin.availability_profiles, ("open-v2",))

    def test_explicit_portable_and_invalid_profile_availability(self) -> None:
        profile = read_json(PROFILE_PATH)
        concept = deepcopy(read_json(SEMANTIC_PATH)["concepts"]["demographics.race"])
        concept["availability"] = {"scope": "portable"}
        profile["contributions"]["concepts"]["profile.test.portable"] = concept
        catalog = self.load_profile(profile)
        self.assertEqual(
            catalog.origins["concept:profile.test.portable"].availability_profiles, ()
        )

        concept["availability"] = {"scope": "profiles", "profiles": ["missing"]}
        with self.assertRaisesRegex(CatalogValidationError, "unloaded profiles"):
            self.load_profile(profile)

    def test_many_to_many_mappings_are_keyed_by_id_and_surface_ambiguity(self) -> None:
        profile = read_json(PROFILE_PATH)
        semantic = read_json(SEMANTIC_PATH)
        concept = deepcopy(semantic["concepts"]["demographics.race"])
        profile["contributions"]["concepts"]["profile.test.alternate_race"] = concept
        original = next(
            item
            for item in profile["profile_binding"]["feature_bindings"]
            if item["concept"] == "demographics.race"
        )
        alternate = deepcopy(original)
        alternate.update(
            {
                "id": "profile.test.alternate-race-mapping",
                "concept": "profile.test.alternate_race",
                "status": "ambiguous",
            }
        )
        profile["profile_binding"]["feature_bindings"].append(alternate)
        catalog = self.load_profile(profile, semantic=semantic)

        self.assertEqual(
            catalog.get_feature(alternate["id"])["binding"]["concept"],
            "profile.test.alternate_race",
        )
        occurrence = f"open-v2:{alternate['table']}.{alternate['column']}"
        with self.assertRaisesRegex(CatalogAmbiguousError, "mapping ID"):
            catalog.get_feature(occurrence)

    def test_table_inventory_allows_unmapped_columns(self) -> None:
        profile = read_json(PROFILE_PATH)
        table = profile["profile_binding"]["tables"][0]
        table["columns"].append(
            {"name": "uncataloged_internal_field", "physical_type": "string", "nullable": True}
        )
        catalog = self.load_profile(profile)
        result = catalog.get_profile_table("open-v2", table["table"])
        self.assertIn(
            "uncataloged_internal_field",
            {item["name"] for item in result["table"]["columns"]},
        )
        self.assertNotIn(
            "uncataloged_internal_field",
            {item["column"] for item in result["feature_bindings"]},
        )

    def test_mapping_qualifiers_are_generic_scalar_metadata(self) -> None:
        profile = read_json(PROFILE_PATH)
        mapping = profile["profile_binding"]["feature_bindings"][0]
        mapping["qualifiers"] = {
            "slot": 1,
            "transform": "normalized",
            "reviewed": False,
            "threshold": 0.5,
        }
        catalog = self.load_profile(profile)
        self.assertEqual(
            catalog.get_feature(mapping["id"])["binding"]["qualifiers"],
            mapping["qualifiers"],
        )

    def test_co_location_is_derived_from_object_mappings(self) -> None:
        catalog = load_catalog()
        grouped: dict[tuple[str, str], list[Any]] = {}
        for binding in catalog.object_bindings:
            grouped.setdefault((binding.profile, binding.table), []).append(binding)
        bindings = next(values for values in grouped.values() if len(values) > 1)
        result = catalog._object_binding_result(bindings[0])
        self.assertEqual(
            result["co_located_objects"],
            sorted({item.object for item in bindings[1:]}),
        )

    def test_extension_uses_same_contribution_and_mapping_model(self) -> None:
        profile = read_json(PROFILE_PATH)
        semantic = read_json(SEMANTIC_PATH)
        extension = empty_extension()
        concept = deepcopy(semantic["concepts"]["demographics.race"])
        extension["contributions"]["concepts"]["project.alpha.race"] = concept
        original = next(
            item for item in profile["profile_binding"]["feature_bindings"]
            if item["concept"] == "demographics.race"
        )
        mapping = deepcopy(original)
        mapping.update(
            {"id": "project.alpha.race-mapping", "concept": "project.alpha.race", "status": "conditional"}
        )
        extension["profile_binding"]["feature_bindings"].append(mapping)
        extension["feature_lineage"]["project.alpha.race-lineage"] = {
            "id": "project.alpha.race-lineage",
            "output_concept": "project.alpha.race",
            "input_concepts": ["demographics.race"],
            "input_bindings": [original["id"]],
            "summary": "Synthetic derivation for composition testing.",
            "claim_refs": [],
            "known_limitations": ["Synthetic metadata only."],
            "lifecycle_status": "work_in_progress",
        }
        catalog = self.load_profile(profile, semantic=semantic, extensions=[extension])
        result = catalog.get_feature("project.alpha.race", profile="open-v2")
        self.assertEqual(result["bindings"][0]["status"], "conditional")
        self.assertEqual(
            result["feature_lineage"][0]["id"], "project.alpha.race-lineage"
        )

    def test_resolver_retains_immutable_authored_snapshots(self) -> None:
        resolved = _resolve_catalog()
        self.assertEqual([item.kind for item in resolved.documents], ["manifest", "semantic", "profile"])
        self.assertTrue(all(item.source_digest.startswith("sha256:") for item in resolved.documents))


if __name__ == "__main__":
    unittest.main()
