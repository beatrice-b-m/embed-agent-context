"""Focused checks for the schema-v8 semantic and profile contracts."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_PATH = ROOT / "catalog" / "semantic" / "catalog.json"
SEMANTIC_SCHEMA_PATH = ROOT / "catalog" / "semantic" / "catalog.schema.json"
PROFILE_PATH = ROOT / "catalog" / "profiles" / "open-v2.json"
PROFILE_SCHEMA_PATH = ROOT / "catalog" / "profiles" / "profile.schema.json"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class CatalogSchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.semantic = read_json(SEMANTIC_PATH)
        cls.profile = read_json(PROFILE_PATH)
        cls.semantic_schema = read_json(SEMANTIC_SCHEMA_PATH)
        cls.profile_schema = read_json(PROFILE_SCHEMA_PATH)
        Draft202012Validator.check_schema(cls.semantic_schema)
        Draft202012Validator.check_schema(cls.profile_schema)
        cls.semantic_validator = Draft202012Validator(cls.semantic_schema)
        cls.profile_validator = Draft202012Validator(cls.profile_schema)

    def test_canonical_modules_validate(self) -> None:
        self.semantic_validator.validate(self.semantic)
        self.profile_validator.validate(self.profile)

    def test_nonblank_semantic_strings_reject_surrounding_whitespace(self) -> None:
        for value in (" Leading", "Trailing ", "Trailing\n"):
            with self.subTest(value=value):
                semantic = deepcopy(self.semantic)
                semantic["clinical_objects"]["patient"]["label"] = value
                with self.assertRaises(ValidationError):
                    self.semantic_validator.validate(semantic)

    def test_vocabulary_codes_are_nonempty_and_trimmed(self) -> None:
        empty = deepcopy(self.profile)
        vocabulary = next(iter(empty["vocabularies"].values()))
        vocabulary["codes"] = {}
        with self.assertRaises(ValidationError):
            self.profile_validator.validate(empty)

        whitespace = deepcopy(self.profile)
        vocabulary = next(iter(whitespace["vocabularies"].values()))
        vocabulary["codes"][" invalid"] = "Whitespace-prefixed code"
        with self.assertRaises(ValidationError):
            self.profile_validator.validate(whitespace)

    def test_unordered_comma_delimited_vocabulary_parsing_is_controlled(
        self,
    ) -> None:
        profile = deepcopy(self.profile)
        vocabulary = next(iter(profile["vocabularies"].values()))
        vocabulary["parsing"] = "comma_delimited_unordered"
        self.profile_validator.validate(profile)

        vocabulary["parsing"] = "comma_delimited"
        with self.assertRaises(ValidationError):
            self.profile_validator.validate(profile)

    def test_observed_source_evidence_is_release_neutral(self) -> None:
        semantic = deepcopy(self.semantic)
        semantic_concept = next(iter(semantic["concepts"].values()))
        semantic_concept["evidence"] = ["observed_source_values"]
        self.semantic_validator.validate(semantic)
        semantic_concept["evidence"] = ["observed_v2_values"]
        with self.assertRaises(ValidationError):
            self.semantic_validator.validate(semantic)

        profile = deepcopy(self.profile)
        profile_vocabulary = next(iter(profile["vocabularies"].values()))
        profile_vocabulary["evidence"] = ["observed_source_values"]
        self.profile_validator.validate(profile)
        profile_vocabulary["evidence"] = ["observed_v2_values"]
        with self.assertRaises(ValidationError):
            self.profile_validator.validate(profile)

    def test_optional_semantic_collections_may_be_empty(self) -> None:
        semantic = deepcopy(self.semantic)
        for concept in semantic["concepts"].values():
            concept["temporal_semantics"] = []
            concept["aggregations"] = []
        for collection in (
            "semantic_relationships",
            "temporal_semantics",
            "aggregations",
            "guardrails",
            "coverage",
        ):
            semantic[collection] = {}
        self.semantic_validator.validate(semantic)

    def test_mapping_notes_and_nested_metadata_are_closed(self) -> None:
        notes = deepcopy(self.profile)
        notes["profile_binding"]["feature_bindings"][0]["notes"] = []
        with self.assertRaises(ValidationError):
            self.profile_validator.validate(notes)

        column = deepcopy(self.profile)
        column["profile_binding"]["tables"][0]["columns"][0][
            "unexpected"
        ] = True
        with self.assertRaises(ValidationError):
            self.profile_validator.validate(column)

        identity = deepcopy(self.profile)
        object_mapping = next(
            item
            for item in identity["profile_binding"]["object_bindings"]
            if "instance_identity" in item
        )
        object_mapping["instance_identity"]["unexpected"] = True
        with self.assertRaises(ValidationError):
            self.profile_validator.validate(identity)

    def test_physical_columns_own_type_and_nullability(self) -> None:
        profile = deepcopy(self.profile)
        table = profile["profile_binding"]["tables"][0]
        column = table["columns"][0]
        self.assertEqual(set(column), {"name", "physical_type", "nullable"})

        missing = deepcopy(profile)
        del missing["profile_binding"]["tables"][0]["columns"][0][
            "physical_type"
        ]
        with self.assertRaises(ValidationError):
            self.profile_validator.validate(missing)

        mapping = profile["profile_binding"]["feature_bindings"][0]
        for old_field in ("grain", "role", "physical_type", "nullable"):
            mapping[old_field] = "legacy"
            with self.assertRaises(ValidationError):
                self.profile_validator.validate(profile)
            del mapping[old_field]

    def test_mapping_status_is_controlled_and_occurrences_are_many_to_many(self) -> None:
        profile = deepcopy(self.profile)
        mappings = profile["profile_binding"]["feature_bindings"]
        duplicate_occurrence = deepcopy(mappings[0])
        duplicate_occurrence["id"] = "open-v2.binding.feature.alternative-meaning"
        duplicate_occurrence["concept"] = mappings[1]["concept"]
        duplicate_occurrence["status"] = "ambiguous"
        mappings.append(duplicate_occurrence)
        self.profile_validator.validate(profile)

        duplicate_occurrence["status"] = "canonical"
        with self.assertRaises(ValidationError):
            self.profile_validator.validate(profile)

    def test_mapping_qualifiers_are_generic_scalar_metadata(self) -> None:
        profile = deepcopy(self.profile)
        mapping = profile["profile_binding"]["feature_bindings"][0]
        mapping["qualifiers"] = {
            "slot": 1,
            "method": "source-defined",
            "reviewed": False,
        }
        self.profile_validator.validate(profile)

        mapping["qualifiers"] = {"nested": {"not": "descriptive scalar"}}
        with self.assertRaises(ValidationError):
            self.profile_validator.validate(profile)

    def test_object_mapping_axes_are_independent_and_co_location_is_not_authored(
        self,
    ) -> None:
        profile = deepcopy(self.profile)
        mapping = profile["profile_binding"]["object_bindings"][0]
        mapping.update(
            {
                "completeness": "partial",
                "authority": "reference",
                "derivation": "projected",
            }
        )
        self.profile_validator.validate(profile)

        mapping["representation"] = "co_located"
        with self.assertRaises(ValidationError):
            self.profile_validator.validate(profile)

    def test_contribution_availability_is_closed(self) -> None:
        profile = deepcopy(self.profile)
        concept = deepcopy(next(iter(self.semantic["concepts"].values())))
        concept["availability"] = {
            "scope": "profiles",
            "profiles": ["open-v2"],
        }
        profile["contributions"]["concepts"]["open-v2.example"] = concept
        self.profile_validator.validate(profile)

        concept["availability"]["unexpected"] = True
        with self.assertRaises(ValidationError):
            self.profile_validator.validate(profile)


if __name__ == "__main__":
    unittest.main()
