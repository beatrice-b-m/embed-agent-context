"""Authored source indexing and mutation contracts."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from pathlib import Path

from embed_context_curator.documents import (
    build_source_index,
    canonical_json_bytes,
    creation_location,
    mutable_copy,
    record_at,
)


class CuratorDocumentTests(unittest.TestCase):
    def test_map_and_id_addressed_array_entries_keep_authored_pointers(self) -> None:
        mapping = {
            "profile_schema_version": 2,
            "profile": {"id": "profile-a"},
            "contributions": {
                "clinical_objects": {}, "concepts": {},
                "semantic_relationships": {}, "temporal_semantics": {},
                "aggregations": {}, "guardrails": {},
                "coverage": {"profile-a.coverage": {"summary": "Gap"}},
            },
            "qualifications": {"profile-a.q": {"id": "profile-a.q", "summary": "Q"}},
            "sources": {}, "contexts": {}, "vocabularies": {},
            "profile_binding": {
                "feature_bindings": [{"id": "profile-a.binding", "concept": "x"}],
                "object_bindings": [],
                "tables": [{
                    "id": "profile-a.table", "table": "table_a",
                    "columns": [{"name": "value", "physical_type": "string", "nullable": True}],
                }],
                "relationship_bindings": [],
                "relationship_binding_paths": [],
            },
        }
        document = SimpleNamespace(
            kind="profile", locator_kind="explicit", source_path=Path("/tmp/profile.json"),
            mapping=mapping, module_id="profile-a", target_profile="profile-a",
        )
        entries = build_source_index([document], document.source_path)
        qualification = next(item for item in entries if item.kind == "qualification")
        binding = next(item for item in entries if item.kind == "feature_binding")
        coverage = next(item for item in entries if item.kind == "coverage")
        column = next(item for item in entries if item.kind == "physical_column")
        self.assertEqual(qualification.json_pointer, "/qualifications/profile-a.q")
        self.assertEqual(binding.json_pointer, "/profile_binding/feature_bindings/0")
        self.assertEqual(record_at(mapping, binding)["concept"], "x")
        self.assertEqual(coverage.json_pointer, "/contributions/coverage/profile-a.coverage")
        self.assertEqual(column.identifier, "profile-a.table::value")
        self.assertEqual(column.json_pointer, "/profile_binding/tables/0/columns/0")
        self.assertEqual(record_at(mapping, column)["physical_type"], "string")
        self.assertTrue(binding.editable)

    def test_canonical_serialization_is_stable_and_lossless(self) -> None:
        value = {"z": [1, {"nested": True}], "a": "é"}
        copied = mutable_copy(value)
        self.assertEqual(copied, value)
        self.assertEqual(canonical_json_bytes(copied), b'{\n  "z": [\n    1,\n    {\n      "nested": true\n    }\n  ],\n  "a": "\xc3\xa9"\n}\n')

    def test_creation_locations_preserve_layer_ownership(self) -> None:
        self.assertEqual(creation_location("semantic", "feature"), (("concepts",), "map"))
        self.assertEqual(creation_location("profile", "feature"), (("contributions", "concepts"), "map"))
        self.assertEqual(creation_location("extension", "clinical_object"), (("contributions", "clinical_objects"), "map"))
        self.assertEqual(creation_location("profile", "table"), (("profile_binding", "tables"), "array"))
        with self.assertRaises(ValueError):
            creation_location("extension", "revision")


if __name__ == "__main__":
    unittest.main()
