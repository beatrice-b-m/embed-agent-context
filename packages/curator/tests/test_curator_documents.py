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
            "profile_schema_version": 1,
            "profile": {"id": "profile-a"},
            "qualifications": {"profile-a.q": {"id": "profile-a.q", "summary": "Q"}},
            "sources": {}, "contexts": {}, "coverage": {}, "vocabularies": {},
            "profile_binding": {
                "feature_bindings": [{"id": "profile-a.binding", "concept": "x"}],
                "object_bindings": [], "tables": [], "relationship_bindings": [],
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
        self.assertEqual(qualification.json_pointer, "/qualifications/profile-a.q")
        self.assertEqual(binding.json_pointer, "/profile_binding/feature_bindings/0")
        self.assertEqual(record_at(mapping, binding)["concept"], "x")
        self.assertTrue(binding.editable)

    def test_canonical_serialization_is_stable_and_lossless(self) -> None:
        value = {"z": [1, {"nested": True}], "a": "é"}
        copied = mutable_copy(value)
        self.assertEqual(copied, value)
        self.assertEqual(canonical_json_bytes(copied), b'{\n  "z": [\n    1,\n    {\n      "nested": true\n    }\n  ],\n  "a": "\xc3\xa9"\n}\n')

    def test_creation_locations_preserve_layer_ownership(self) -> None:
        self.assertEqual(creation_location("semantic", "feature"), (("concepts",), "map"))
        self.assertEqual(creation_location("profile", "table"), (("profile_binding", "tables"), "array"))
        self.assertEqual(creation_location("extension", "revision"), (("revisions",), "array"))
        with self.assertRaises(ValueError):
            creation_location("profile", "feature")


if __name__ == "__main__":
    unittest.main()
