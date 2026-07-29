"""Integration contracts for the checked-in structured catalog."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from embed_context import load_catalog
from embed_context.catalog import (
    BINDING_PARAMETER_KEYS,
    CARDINALITY_VALUES,
    CLAIM_STATUSES,
    CONTEXT_KINDS,
    CONTEXT_SCOPES,
    DOMAINS,
    ENDPOINT_COMPLETENESS,
    EVIDENCE_VALUES,
    FEATURE_KINDS,
    GRAINS,
    KEY_COMPLETENESS,
    KEY_KINDS,
    KEY_UNIQUENESS,
    RELATIONSHIP_KINDS,
    ROLES,
    SOURCE_KINDS,
    SOURCE_LOCATOR_KINDS,
    VOCABULARY_COMPLETENESS,
    VOCABULARY_PARSING,
    _BINDING_KEYS,
    _BINDING_REQUIRED_KEYS,
    _CONCEPT_KEYS,
    _CONCEPT_REQUIRED_KEYS,
    _CLINICAL_CONTEXT_KEYS,
    _CONTEXT_CLAIM_KEYS,
    _CONTEXT_SOURCE_KEYS,
    _CONTEXT_TABLE_REFERENCE_KEYS,
    _VOCABULARY_KEYS,
    _VOCABULARY_REQUIRED_KEYS,
    _WORKFLOW_STEP_KEYS,
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

    def test_every_table_and_relationship_resolves_exactly(self) -> None:
        for table in self.catalog.tables:
            with self.subTest(table=table.identifier):
                result = self.catalog.get_table(table.profile, table.table)
                self.assertEqual(result["identifier"], table.identifier)

        for relationship in self.catalog.relationships:
            with self.subTest(relationship=relationship.id):
                result = self.catalog.get_relationship(relationship.id)
                self.assertEqual(result["identifier"], relationship.id)

    def test_open_v2_relationship_inventory_is_complete(self) -> None:
        expected = {
            "open-v2.combined_anon.exam_projection",
            "open-v2.combined_anon.imaging_index_projection",
            "open-v2.combined_anon.linked_exam",
            "open-v2.combined_anon.pathology_index_projection",
            "open-v2.combined_anon.patient_projection",
            "open-v2.combined_anon.side_projection",
            "open-v2.exam_level_anon.patient",
            "open-v2.imaging_findings_anon.exam",
            "open-v2.imaging_findings_anon.linked_exam",
            "open-v2.imaging_findings_anon.side",
            "open-v2.pathology_findings_anon.exam",
            "open-v2.pathology_findings_anon.imaging_finding",
            "open-v2.pathology_findings_anon.side",
            "open-v2.reports_anon.exam",
            "open-v2.reports_anon.patient",
            "open-v2.risk_anon.exam",
            "open-v2.risk_anon.patient",
            "open-v2.side_level_anon.exam",
        }
        actual = {
            relationship.id
            for relationship in self.catalog.relationships
            if relationship.profile == "open-v2"
        }
        self.assertEqual(actual, expected)

    def test_unreliable_natural_keys_and_wide_hazards_remain_explicit(self) -> None:
        by_table = {table.table: table for table in self.catalog.tables}
        for table_name in (
            "imaging_findings_anon",
            "pathology_findings_anon",
            "reports_anon",
        ):
            with self.subTest(table=table_name):
                natural_keys = [
                    key
                    for key in by_table[table_name].keys
                    if key.kind == "natural"
                ]
                self.assertTrue(natural_keys)
                self.assertTrue(
                    all(
                        key.uniqueness != "unique"
                        for key in natural_keys
                    )
                )

        wide_relationships = self.catalog.search_relationships(
            table="combined_anon"
        )["matches"]
        self.assertTrue(wide_relationships)
        self.assertTrue(
            all(item["join_hazards"] for item in wide_relationships)
        )

        for relationship_id in (
            "open-v2.combined_anon.linked_exam",
            "open-v2.imaging_findings_anon.linked_exam",
        ):
            with self.subTest(relationship=relationship_id):
                linked = self.catalog.get_relationship(relationship_id)[
                    "relationship"
                ]
                self.assertEqual(
                    linked["source"]["completeness"], "optional"
                )
                self.assertEqual(
                    linked["cardinality"]["targets_per_source"], "zero_or_one"
                )
                self.assertTrue(linked["join_hazards"])


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
        self.assertEqual(
            properties["context_kinds"]["const"], list(CONTEXT_KINDS)
        )
        self.assertEqual(
            properties["context_scopes"]["const"], list(CONTEXT_SCOPES)
        )
        self.assertEqual(
            properties["source_kinds"]["const"], list(SOURCE_KINDS)
        )
        self.assertEqual(
            properties["source_locator_kinds"]["const"],
            list(SOURCE_LOCATOR_KINDS),
        )
        self.assertEqual(
            properties["claim_statuses"]["const"], list(CLAIM_STATUSES)
        )
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
        self.assertEqual(
            set(definitions["key"]["properties"]["kind"]["enum"]),
            KEY_KINDS,
        )
        self.assertEqual(
            set(definitions["key"]["properties"]["uniqueness"]["enum"]),
            KEY_UNIQUENESS,
        )
        self.assertEqual(
            set(definitions["key"]["properties"]["completeness"]["enum"]),
            KEY_COMPLETENESS,
        )
        self.assertEqual(
            set(definitions["relationship"]["properties"]["kind"]["enum"]),
            RELATIONSHIP_KINDS,
        )
        self.assertEqual(
            set(
                definitions["source_endpoint"]["properties"][
                    "completeness"
                ]["enum"]
            ),
            ENDPOINT_COMPLETENESS,
        )
        self.assertEqual(
            set(definitions["cardinality_value"]["enum"]),
            CARDINALITY_VALUES,
        )
        self.assertEqual(
            set(definitions["context_source"]["properties"]),
            _CONTEXT_SOURCE_KEYS,
        )
        self.assertEqual(
            set(definitions["clinical_context"]["properties"]),
            _CLINICAL_CONTEXT_KEYS,
        )
        self.assertEqual(
            set(definitions["context_claim"]["properties"]),
            _CONTEXT_CLAIM_KEYS,
        )
        self.assertEqual(
            set(definitions["context_table_reference"]["properties"]),
            _CONTEXT_TABLE_REFERENCE_KEYS,
        )
        self.assertEqual(
            set(definitions["workflow_step"]["properties"]),
            _WORKFLOW_STEP_KEYS,
        )
        for definition in (
            "context_source",
            "clinical_context",
            "context_claim",
            "context_table_reference",
            "workflow_step",
        ):
            with self.subTest(definition=definition):
                self.assertEqual(
                    set(definitions[definition]["required"]),
                    set(definitions[definition]["properties"]),
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

    def test_phase_two_schema_strings_match_core_validation(self) -> None:
        schema = json.loads(
            (REPO_ROOT / "catalog/catalog.schema.json").read_text(
                encoding="utf-8"
            )
        )
        definitions = schema["$defs"]
        identifier_schemas = (
            definitions["key"]["properties"]["id"],
            definitions["table"]["properties"]["profile"],
            definitions["relationship"]["properties"]["id"],
            definitions["relationship"]["properties"]["profile"],
        )
        for identifier_schema in identifier_schemas:
            pattern = identifier_schema["pattern"]
            with self.subTest(pattern=pattern):
                self.assertIsNotNone(re.search(pattern, "open-v2.valid_id"))
                for invalid in ("open-v2.valid_id\n", "Open-v2", " "):
                    self.assertIsNone(re.search(pattern, invalid))

        nonblank_schemas = (
            definitions["key"]["properties"]["caveats"]["items"],
            definitions["table"]["properties"]["caveats"]["items"],
            definitions["relationship"]["properties"]["caveats"]["items"],
            definitions["relationship"]["properties"]["join_hazards"]["items"],
        )
        for string_schema in nonblank_schemas:
            pattern = string_schema["pattern"]
            with self.subTest(pattern=pattern):
                self.assertIsNotNone(re.search(pattern, "Documented caveat."))
                self.assertIsNone(re.search(pattern, " \t\n"))


if __name__ == "__main__":
    unittest.main()
