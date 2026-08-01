"""Acceptance tests for deterministic schema-v7 catalog composition."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from embed_context import (
    CatalogAmbiguousError,
    CatalogValidationError,
    load_catalog,
)


ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_PATH = ROOT / "catalog/semantic/catalog.json"
OPEN_PROFILE_PATH = ROOT / "catalog/profiles/open-v2.json"
LEGACY_PATH = ROOT / "catalog/catalog.json"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def renamed_profile(identifier: str) -> dict[str, Any]:
    serialized = json.dumps(read_json(OPEN_PROFILE_PATH))
    synthetic_table = f"{identifier.replace('-', '_')}_patients"
    result = json.loads(
        serialized.replace("open-v2", identifier).replace(
            "patients_anon", synthetic_table
        )
    )
    result["profile"]["label"] = f"Synthetic profile {identifier}"
    result["vocabularies"][f"{identifier}.pathology.severity"]["codes"][
        "0"
    ] = "Synthetic invasive grouping"
    return result


def empty_extension(
    identifier: str,
    *,
    dependencies: list[str] | None = None,
    target: str = "open-v2",
) -> dict[str, Any]:
    return {
        "$schema": "./extension.schema.json",
        "extension_schema_version": 1,
        "extension": {
            "id": identifier,
            "version": "0.1.0",
            "label": f"Synthetic extension {identifier}",
            "lifecycle_status": "work_in_progress",
        },
        "applies_to": {"profile": target},
        "requires": {
            "semantic_schema_version": 7,
            "profile_schema_version": 1,
            "extensions": dependencies or [],
        },
        "semantic_additions": {"concepts": {}},
        "qualifications": {},
        "feature_lineage": {},
        "sources": {},
        "contexts": {},
        "coverage": {},
        "vocabularies": {},
        "binding_additions": {
            "feature_bindings": [],
            "object_bindings": [],
            "tables": [],
            "relationship_bindings": [],
            "relationship_binding_paths": [],
        },
        "revisions": [],
    }


def representative_extension() -> dict[str, Any]:
    semantic = read_json(SEMANTIC_PATH)
    profile = read_json(OPEN_PROFILE_PATH)
    extension = empty_extension("project.alpha")

    project_concept = deepcopy(semantic["concepts"]["demographics.race"])
    project_concept.update(
        {
            "label": "Project-cleaned patient race",
            "definition": (
                "A project-owned reinterpretation of represented patient race."
            ),
            "search_terms": ["project cleaned race"],
            "evidence": ["inference"],
            "lifecycle_status": "work_in_progress",
        }
    )
    extension["semantic_additions"]["concepts"][
        "project.alpha.cleaned_race"
    ] = project_concept

    original_binding = next(
        item
        for item in profile["profile_binding"]["feature_bindings"]
        if item["concept"] == "demographics.race"
        and item["table"] == "patients_anon"
    )
    secondary = deepcopy(original_binding)
    secondary.update(
        {
            "id": "project.alpha.binding.secondary-race",
            "column": "cleaned_race",
            "role": "reference",
        }
    )
    replacement = deepcopy(original_binding)
    replacement.update(
        {
            "id": "project.alpha.binding.cleaned-race",
            "concept": "project.alpha.cleaned_race",
        }
    )
    extension["binding_additions"]["feature_bindings"] = [
        secondary,
        replacement,
    ]
    extension["feature_lineage"]["project.alpha.lineage.cleaned-race"] = {
        "id": "project.alpha.lineage.cleaned-race",
        "output_concept": "project.alpha.cleaned_race",
        "input_concepts": ["demographics.race"],
        "input_bindings": [original_binding["id"]],
        "summary": "Project-owned harmonization of represented race meaning.",
        "claim_refs": [],
        "known_limitations": [
            "Synthetic metadata does not validate a transformation pipeline."
        ],
        "lifecycle_status": "work_in_progress",
    }
    extension["revisions"] = [
        {
            "id": "project.alpha.revision.race-concept",
            "kind": "reinterprets_concept",
            "original_concept": "demographics.race",
            "replacement_concept": "project.alpha.cleaned_race",
            "semantic_difference": "The project uses a revised category meaning.",
            "reason": "Exercise an intentional project reinterpretation.",
            "claim_refs": [],
            "known_limitations": ["Synthetic acceptance metadata only."],
        },
        {
            "id": "project.alpha.revision.race-binding",
            "kind": "replaces_binding",
            "original_binding": original_binding["id"],
            "replacement_binding": replacement["id"],
            "reason": "Prefer the project interpretation at this occurrence.",
            "claim_refs": [],
            "known_limitations": ["Synthetic acceptance metadata only."],
            "original_remains_alternative": False,
        },
    ]
    return extension


class CatalogCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_semantic_only_and_legacy_transition_loads(self) -> None:
        semantic = load_catalog(SEMANTIC_PATH)
        self.assertEqual(semantic.schema_version, 7)
        self.assertEqual(semantic.profiles, ())
        feature = semantic.get_feature("pathology.severity")
        self.assertEqual(feature["bindings"], [])
        self.assertIsNone(feature["vocabulary"])
        self.assertEqual(feature["origin"]["contribution_class"], "portable")

        legacy = load_catalog(LEGACY_PATH)
        self.assertEqual(legacy.schema_version, 6)
        self.assertEqual(legacy.profiles, ("open-v2",))

    def test_default_open_v2_is_normalized_against_frozen_v6_fixture(self) -> None:
        split = load_catalog()
        legacy = load_catalog(LEGACY_PATH)

        split_summary = split.summary()
        legacy_summary = legacy.summary()
        inventory_keys = (
            "clinical_objects",
            "concepts",
            "semantic_relationships",
            "temporal_semantics",
            "aggregations",
            "guardrails",
            "coverage",
            "vocabularies",
            "sources",
            "contexts",
            "profile_bindings",
            "feature_bindings",
            "object_bindings",
            "tables",
            "relationship_bindings",
            "relationship_binding_paths",
        )
        self.assertEqual(
            {key: split_summary[key] for key in inventory_keys},
            {key: legacy_summary[key] for key in inventory_keys},
        )

        split_feature = split.get_feature(
            "pathology.severity", profile="open-v2", include_codes=True
        )
        legacy_feature = legacy.get_feature(
            "pathology.severity", include_codes=True
        )
        stable_feature_fields = (
            "label",
            "definition",
            "feature_kind",
            "domains",
            "objects",
            "search_terms",
            "caveats",
            "evidence",
            "temporal_semantics",
            "aggregations",
        )
        self.assertEqual(
            {key: split_feature["feature"][key] for key in stable_feature_fields},
            {key: legacy_feature["feature"][key] for key in stable_feature_fields},
        )
        self.assertEqual(
            split_feature["vocabulary"]["codes"],
            legacy_feature["vocabulary"]["codes"],
        )
        physical_fields = (
            "profile",
            "table",
            "column",
            "concept",
            "grain",
            "role",
            "physical_type",
            "nullable",
        )
        self.assertEqual(
            [
                {key: item[key] for key in physical_fields}
                for item in split_feature["bindings"]
            ],
            [
                {key: item[key] for key in physical_fields}
                for item in legacy_feature["bindings"]
            ],
        )
        self.assertEqual(split_feature["provenance"], legacy_feature["provenance"])

        for query in (
            "What does absent pathology mean?",
            "laterality null bilateral",
            "risk probability calibration",
            "pathology attribution to imaging findings",
        ):
            with self.subTest(query=query):
                split_matches = split.discover(
                    query, profile="open-v2", limit=8
                )["matches"]
                legacy_matches = legacy.discover(
                    query, profile="open-v2", limit=8
                )["matches"]
                split_ids = [
                    (item["kind"], item["identifier"])
                    for item in split_matches
                ]
                legacy_ids = [
                    (item["kind"], item["identifier"])
                    for item in legacy_matches
                ]
                self.assertEqual(split_ids[0], legacy_ids[0])
                self.assertEqual(set(split_ids), set(legacy_ids))

    def test_two_profiles_are_isolated_order_independent_and_ambiguous(self) -> None:
        open_profile = write_json(
            self.directory / "a/open.json", read_json(OPEN_PROFILE_PATH)
        )
        synthetic = write_json(
            self.directory / "b/synthetic.json",
            renamed_profile("synthetic-v1"),
        )
        first = load_catalog(
            SEMANTIC_PATH, profile_paths=[open_profile, synthetic]
        )
        second = load_catalog(
            SEMANTIC_PATH, profile_paths=[synthetic, open_profile]
        )
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.profiles, ("open-v2", "synthetic-v1"))
        with self.assertRaises(CatalogAmbiguousError):
            first.get_feature("pathology.severity")
        selected = first.get_feature(
            "pathology.severity", profile="synthetic-v1", include_codes=True
        )
        self.assertTrue(
            all(item["profile"] == "synthetic-v1" for item in selected["bindings"])
        )
        self.assertIn("codes", selected["vocabulary"])
        self.assertEqual(
            selected["vocabulary"]["codes"]["0"],
            "Synthetic invasive grouping",
        )
        identity = first.get_feature(
            "identity.patient_identifier", profile="synthetic-v1"
        )
        self.assertTrue(
            any(
                item["table"] == "synthetic_v1_patients"
                for item in identity["bindings"]
            )
        )

        invalid = renamed_profile("synthetic-bad")
        first_qualification = next(iter(invalid["qualifications"].values()))
        first_qualification["claim_refs"] = [
            "open-v2.pathology-procedure-context#severity-meaning"
        ]
        invalid_path = write_json(self.directory / "bad.json", invalid)
        with self.assertRaisesRegex(
            CatalogValidationError, "module dependency closure"
        ):
            load_catalog(
                SEMANTIC_PATH,
                profile_paths=[OPEN_PROFILE_PATH, invalid_path],
            )

    def test_extensions_compose_dependencies_lineage_and_typed_revisions(self) -> None:
        alpha = representative_extension()
        beta = empty_extension("project.beta", dependencies=["project.alpha"])
        beta["qualifications"]["project.beta.qualification.cleaned-race"] = {
            "id": "project.beta.qualification.cleaned-race",
            "subject": {"kind": "concept", "id": "project.alpha.cleaned_race"},
            "applicability": "interpretation_limit",
            "summary": "Dependent project review remains in progress.",
            "claim_refs": [],
            "caveats": ["Synthetic acceptance metadata only."],
        }
        alpha_path = write_json(self.directory / "alpha.json", alpha)
        beta_path = write_json(self.directory / "beta.json", beta)

        catalog = load_catalog(
            SEMANTIC_PATH,
            profile_paths=[OPEN_PROFILE_PATH],
            extension_paths=[beta_path, alpha_path],
        )
        reverse = load_catalog(
            SEMANTIC_PATH,
            profile_paths=[OPEN_PROFILE_PATH],
            extension_paths=[alpha_path, beta_path],
        )
        self.assertEqual(catalog.fingerprint, reverse.fingerprint)
        self.assertEqual(
            [item["id"] for item in catalog.configuration["extensions"]],
            ["project.alpha", "project.beta"],
        )

        original = catalog.get_feature("demographics.race", profile="open-v2")
        self.assertEqual(
            original["effective_view"]["replacement_id"],
            "project.alpha.cleaned_race",
        )
        original_binding = next(
            item
            for item in original["bindings"]
            if item.get("effective_view", {}).get("superseded_in_view")
        )
        self.assertTrue(original_binding["effective_view"]["superseded_in_view"])

        replacement = catalog.get_feature(
            "project.alpha.cleaned_race", profile="open-v2"
        )
        self.assertEqual(replacement["origin"]["module_id"], "project.alpha")
        self.assertEqual(
            replacement["origin"]["lifecycle_status"], "work_in_progress"
        )
        self.assertTrue(replacement["feature_lineage"])
        self.assertTrue(
            replacement["bindings"][0]["effective_view"]["preferred_in_view"]
        )
        self.assertEqual(
            {item["origin"]["module_id"] for item in replacement["qualifications"]},
            {"project.beta"},
        )

        direct_original = catalog.get_feature(original_binding["id"])
        direct_replacement = catalog.get_feature(
            "project.alpha.binding.cleaned-race"
        )
        self.assertEqual(direct_original["binding"]["id"], original_binding["id"])
        self.assertEqual(
            direct_replacement["binding"]["id"],
            "project.alpha.binding.cleaned-race",
        )
        discovered = catalog.discover("project cleaned race", limit=5)
        project_match = next(
            item
            for item in discovered["matches"]
            if item["identifier"] == "project.alpha.cleaned_race"
        )
        self.assertEqual(project_match["origin"]["module_id"], "project.alpha")

    def test_extension_dependency_failures_are_structured(self) -> None:
        missing = empty_extension("project.missing", dependencies=["project.absent"])
        missing_path = write_json(self.directory / "missing.json", missing)
        with self.assertRaisesRegex(CatalogValidationError, "missing extension"):
            load_catalog(
                SEMANTIC_PATH,
                profile_paths=[OPEN_PROFILE_PATH],
                extension_paths=[missing_path],
            )

        one = empty_extension("project.one", dependencies=["project.two"])
        two = empty_extension("project.two", dependencies=["project.one"])
        one_path = write_json(self.directory / "one.json", one)
        two_path = write_json(self.directory / "two.json", two)
        with self.assertRaisesRegex(CatalogValidationError, "acyclic"):
            load_catalog(
                SEMANTIC_PATH,
                profile_paths=[OPEN_PROFILE_PATH],
                extension_paths=[one_path, two_path],
            )

        target = empty_extension("project.target", target="synthetic-v1")
        target_path = write_json(self.directory / "target.json", target)
        with self.assertRaisesRegex(CatalogValidationError, "unloaded profile"):
            load_catalog(
                SEMANTIC_PATH,
                profile_paths=[OPEN_PROFILE_PATH],
                extension_paths=[target_path],
            )

        namespace = empty_extension("project.namespace")
        namespace["qualifications"]["wrong.identifier"] = {
            "id": "wrong.identifier",
            "subject": {"kind": "concept", "id": "demographics.race"},
            "applicability": "supported",
            "summary": "Invalid namespace contribution.",
            "claim_refs": [],
            "caveats": [],
        }
        namespace_path = write_json(self.directory / "namespace.json", namespace)
        with self.assertRaisesRegex(CatalogValidationError, "namespace"):
            load_catalog(
                SEMANTIC_PATH,
                profile_paths=[OPEN_PROFILE_PATH],
                extension_paths=[namespace_path],
            )

        cycle = empty_extension("project.cycle")
        source_concept = deepcopy(
            read_json(SEMANTIC_PATH)["concepts"]["demographics.race"]
        )
        source_concept["lifecycle_status"] = "work_in_progress"
        cycle["semantic_additions"]["concepts"] = {
            "project.cycle.one": deepcopy(source_concept),
            "project.cycle.two": deepcopy(source_concept),
        }
        cycle["revisions"] = [
            {
                "id": "project.cycle.revision.one",
                "kind": "reinterprets_concept",
                "original_concept": "project.cycle.one",
                "replacement_concept": "project.cycle.two",
                "semantic_difference": "Synthetic first revision.",
                "reason": "Exercise revision-cycle rejection.",
                "claim_refs": [],
                "known_limitations": [],
            },
            {
                "id": "project.cycle.revision.two",
                "kind": "reinterprets_concept",
                "original_concept": "project.cycle.two",
                "replacement_concept": "project.cycle.one",
                "semantic_difference": "Synthetic second revision.",
                "reason": "Exercise revision-cycle rejection.",
                "claim_refs": [],
                "known_limitations": [],
            },
        ]
        cycle_path = write_json(self.directory / "revision-cycle.json", cycle)
        with self.assertRaisesRegex(CatalogValidationError, "revision graph"):
            load_catalog(
                SEMANTIC_PATH,
                profile_paths=[OPEN_PROFILE_PATH],
                extension_paths=[cycle_path],
            )


if __name__ == "__main__":
    unittest.main()
