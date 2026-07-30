"""Parity checks for the standalone JSON Schema and runtime validator."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from embed_context import Catalog, CatalogValidationError
from tests.catalog_fixture import synthetic_catalog


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPOSITORY_ROOT / "catalog" / "catalog.schema.json"
CATALOG_PATH = REPOSITORY_ROOT / "catalog" / "catalog.json"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class CatalogSchemaParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = _read_json(SCHEMA_PATH)
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def assert_invalid_in_both(self, data: dict[str, Any]) -> None:
        with self.assertRaises(ValidationError):
            self.validator.validate(data)
        with self.assertRaises(CatalogValidationError):
            Catalog.from_mapping(data)

    def test_canonical_and_synthetic_catalogs_validate(self) -> None:
        for name, data in (
            ("canonical", _read_json(CATALOG_PATH)),
            ("synthetic", synthetic_catalog()),
        ):
            with self.subTest(catalog=name):
                self.validator.validate(data)
                Catalog.from_mapping(data)

    def test_nonblank_strings_reject_surrounding_whitespace(self) -> None:
        for value in (" Leading", "Trailing ", "Trailing\n"):
            with self.subTest(value=value):
                data = synthetic_catalog()
                data["clinical_objects"]["patient"]["label"] = value
                self.assert_invalid_in_both(data)

    def test_vocabulary_codes_are_nonempty_and_trimmed(self) -> None:
        empty = synthetic_catalog()
        empty["vocabularies"]["pathology.severity"]["codes"] = {}
        self.assert_invalid_in_both(empty)

        whitespace_key = synthetic_catalog()
        whitespace_key["vocabularies"]["pathology.severity"]["codes"][
            " 6"
        ] = "Whitespace-prefixed code"
        self.assert_invalid_in_both(whitespace_key)

    def test_optional_semantic_collections_may_be_empty(self) -> None:
        data = synthetic_catalog()
        for concept in data["concepts"].values():
            concept["temporal_semantics"] = []
            concept["aggregations"] = []
        for profile in data["profile_bindings"].values():
            for relationship in profile["relationship_bindings"]:
                relationship["semantic_relationships"] = []
            profile["relationship_binding_paths"] = []
        for collection in (
            "semantic_relationships",
            "temporal_semantics",
            "aggregations",
            "guardrails",
            "coverage",
        ):
            data[collection] = {}

        self.validator.validate(data)
        Catalog.from_mapping(data)

    def test_feature_binding_notes_are_nonempty_when_present(self) -> None:
        data = synthetic_catalog()
        data["profile_bindings"]["profile-a"]["feature_bindings"][0][
            "notes"
        ] = []
        self.assert_invalid_in_both(data)

    def test_v6_binding_metadata_shapes_are_closed(self) -> None:
        mutations = []

        occurrence = synthetic_catalog()
        occurrence["profile_bindings"]["profile-a"]["feature_bindings"][2][
            "occurrence_interpretations"
        ][0]["unexpected"] = True
        mutations.append(occurrence)

        identity = synthetic_catalog()
        identity["profile_bindings"]["profile-b"]["object_bindings"][0][
            "instance_identity"
        ]["unexpected"] = True
        mutations.append(identity)

        path = synthetic_catalog()
        path["profile_bindings"]["profile-b"][
            "relationship_binding_paths"
        ][0]["unexpected"] = True
        mutations.append(path)

        for data in mutations:
            with self.subTest():
                self.assert_invalid_in_both(data)

    def test_v6_controlled_values_are_enforced(self) -> None:
        guardrail = synthetic_catalog()
        guardrail["guardrails"]["pathology.null-is-not-negative"][
            "priority"
        ] = "urgent"
        self.assert_invalid_in_both(guardrail)

        interpretation = synthetic_catalog()
        interpretation["profile_bindings"]["profile-a"][
            "feature_bindings"
        ][2]["occurrence_interpretations"][0]["status"] = "assumed"
        self.assert_invalid_in_both(interpretation)

        identity = synthetic_catalog()
        identity["profile_bindings"]["profile-b"]["object_bindings"][0][
            "instance_identity"
        ]["rows_per_instance"] = "many"
        self.assert_invalid_in_both(identity)

    def test_every_profile_has_at_least_one_feature_binding(self) -> None:
        data = synthetic_catalog()
        data["profile_bindings"]["profile-a"]["feature_bindings"] = []
        self.assert_invalid_in_both(data)

    def test_slot_parameters_are_reserved_for_diagnosis_slot_bindings(
        self,
    ) -> None:
        unrelated = synthetic_catalog()
        unrelated["profile_bindings"]["profile-a"]["feature_bindings"][0][
            "parameters"
        ] = {"slot": 1}
        self.assert_invalid_in_both(unrelated)

        missing_slot = _read_json(CATALOG_PATH)
        binding = next(
            item
            for item in missing_slot["profile_bindings"]["open-v2"][
                "feature_bindings"
            ]
            if item["concept"] == "pathology.diagnosis_code_slot"
        )
        del binding["parameters"]
        self.assert_invalid_in_both(missing_slot)

    def test_canonical_slot_parameters_are_positive_integers(self) -> None:
        data = _read_json(CATALOG_PATH)
        bindings = [
            item
            for item in data["profile_bindings"]["open-v2"][
                "feature_bindings"
            ]
            if item["concept"] == "pathology.diagnosis_code_slot"
        ]

        self.assertEqual(len(bindings), 20)
        self.assertTrue(
            all(
                isinstance(item["parameters"]["slot"], int)
                and not isinstance(item["parameters"]["slot"], bool)
                and item["parameters"]["slot"] > 0
                for item in bindings
            )
        )
        self.validator.validate(deepcopy(data))
        Catalog.from_mapping(data)


if __name__ == "__main__":
    unittest.main()
