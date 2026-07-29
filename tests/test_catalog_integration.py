"""Integration contracts for the checked-in structured catalog."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from embed_context import load_catalog
from embed_context.catalog import (
    BINDING_PARAMETER_KEYS,
    DOMAINS,
    EVIDENCE_VALUES,
    FEATURE_KINDS,
    GRAINS,
    ROLES,
    VOCABULARY_COMPLETENESS,
    VOCABULARY_PARSING,
    _BINDING_KEYS,
    _BINDING_REQUIRED_KEYS,
    _CONCEPT_KEYS,
    _CONCEPT_REQUIRED_KEYS,
    _VOCABULARY_KEYS,
    _VOCABULARY_REQUIRED_KEYS,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class CheckedInCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_catalog()

    def test_every_concept_and_binding_resolves_exactly(self) -> None:
        for concept_id in self.catalog.concepts:
            with self.subTest(concept=concept_id):
                result = self.catalog.get_feature(concept_id)
                self.assertEqual(result["concept"]["id"], concept_id)

        for binding in self.catalog.bindings:
            with self.subTest(binding=binding.qualified_identifier):
                result = self.catalog.get_feature(binding.qualified_identifier)
                self.assertEqual(result["binding"]["concept"], binding.concept)

    def test_domain_only_search_returns_each_matching_concept_once(self) -> None:
        for domain in (
            "pathology",
            "demographics",
            "social_determinants_of_health",
        ):
            with self.subTest(domain=domain):
                expected = {
                    concept_id
                    for concept_id, concept in self.catalog.concepts.items()
                    if domain in concept.domains
                }
                result = self.catalog.search_features("", domain=domain)
                identifiers = [
                    match["identifier"] for match in result["matches"]
                ]
                self.assertEqual(set(identifiers), expected)
                self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_shared_accession_and_pathology_slots_are_normalized(self) -> None:
        accession = self.catalog.get_feature("exam.accession_identifier")
        self.assertTrue(accession["bindings"])
        self.assertEqual(
            {binding["column"] for binding in accession["bindings"]},
            {"acc_anon"},
        )

        pathology_slots = [
            binding
            for binding in self.catalog.bindings
            if binding.column.startswith("path")
            and binding.column.removeprefix("path").isdigit()
        ]
        self.assertTrue(pathology_slots)
        self.assertEqual(
            {binding.concept for binding in pathology_slots},
            {"pathology.diagnosis_code_slot"},
        )
        for binding in pathology_slots:
            self.assertEqual(
                dict(binding.parameters)["slot"],
                int(binding.column.removeprefix("path")),
            )

    def test_code_lookup_returns_plain_structured_meaning(self) -> None:
        result = self.catalog.lookup_code("imaging.assessment", "N")
        self.assertEqual(result["meaning"], "Negative")
        self.assertEqual(result["concept"], "imaging.assessment")

        for vocabulary in self.catalog.vocabularies.values():
            for _, meaning in vocabulary.codes:
                self.assertNotIn("**", meaning)
                self.assertNotIn("`", meaning)

    def test_requirement_level_text_queries(self) -> None:
        accession = self.catalog.search_features("ACCAnon")
        self.assertEqual(accession["total"], 1)
        self.assertEqual(
            accession["matches"][0]["identifier"],
            "exam.accession_identifier",
        )

        demographic = self.catalog.search_features("demographic features")
        self.assertGreater(demographic["total"], 0)
        self.assertTrue(
            all(
                "demographics" in match["domains"]
                for match in demographic["matches"]
            )
        )

        masses = self.catalog.search_features("breast masses")
        mass_identifiers = {
            match["identifier"] for match in masses["matches"]
        }
        self.assertTrue(mass_identifiers)
        self.assertNotIn("breast.side", mass_identifiers)
        self.assertTrue(
            any("mass" in identifier for identifier in mass_identifiers)
        )

    def test_pathology_severity_aggregate_caveats_distinguish_coded_field(self) -> None:
        for concept_id in (
            "breast_side.pathology_severity_aggregate",
            "exam.pathology_severity_aggregate",
        ):
            with self.subTest(concept=concept_id):
                caveats = self.catalog.concepts[concept_id].caveats
                self.assertTrue(
                    any("finding-level coded severity field" in item for item in caveats)
                )
                self.assertTrue(
                    all("finding-level presence flag" not in item for item in caveats)
                )

    def test_schema_facets_match_the_dependency_free_core(self) -> None:
        schema = json.loads(
            (REPO_ROOT / "catalog/catalog.schema.json").read_text(
                encoding="utf-8"
            )
        )
        properties = schema["properties"]
        self.assertEqual(properties["grains"]["const"], list(GRAINS))
        self.assertEqual(
            properties["feature_kinds"]["const"], list(FEATURE_KINDS)
        )
        self.assertEqual(properties["domains"]["const"], list(DOMAINS))
        definitions = schema["$defs"]
        self.assertEqual(
            set(definitions["evidence"]["enum"]), EVIDENCE_VALUES
        )
        self.assertEqual(
            set(definitions["binding"]["properties"]["role"]["enum"]),
            ROLES,
        )
        self.assertEqual(
            set(
                definitions["binding"]["properties"]["parameters"][
                    "properties"
                ]
            ),
            BINDING_PARAMETER_KEYS,
        )
        self.assertEqual(
            set(
                definitions["vocabulary"]["properties"]["completeness"][
                    "enum"
                ]
            ),
            VOCABULARY_COMPLETENESS,
        )
        self.assertEqual(
            set(
                definitions["vocabulary"]["properties"]["parsing"]["enum"]
            ),
            VOCABULARY_PARSING,
        )
        for definition, allowed, required in (
            ("concept", _CONCEPT_KEYS, _CONCEPT_REQUIRED_KEYS),
            ("binding", _BINDING_KEYS, _BINDING_REQUIRED_KEYS),
            (
                "vocabulary",
                _VOCABULARY_KEYS,
                _VOCABULARY_REQUIRED_KEYS,
            ),
        ):
            with self.subTest(definition=definition):
                self.assertEqual(
                    set(definitions[definition]["properties"]), allowed
                )
                self.assertEqual(
                    set(definitions[definition]["required"]), required
                )


if __name__ == "__main__":
    unittest.main()
