"""Load, validate, and query the count-free EMBED feature catalog.

The core deliberately uses only the Python standard library. It does not read
clinical tables, import PyArrow, or depend on any protocol adapter.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


SCHEMA_REFERENCE = "./catalog.schema.json"
SCHEMA_VERSION = 2
GRAINS = (
    "patient",
    "exam",
    "breast_side",
    "imaging_finding",
    "pathology_finding",
    "report",
    "risk_assessment",
    "wide_row",
)
FEATURE_KINDS = (
    "identifier",
    "date",
    "categorical",
    "coded",
    "flag",
    "numeric",
    "text",
    "aggregate",
    "model_output",
    "technical",
)
DOMAINS = (
    "identity",
    "demographics",
    "social_determinants_of_health",
    "exam",
    "breast_side",
    "imaging",
    "mammography",
    "ultrasound",
    "mri",
    "pathology",
    "procedure",
    "report",
    "risk",
    "temporal",
    "workflow",
    "technical",
)
EVIDENCE_VALUES = frozenset(
    {
        "release_schema",
        "release_legend",
        "observed_v2_values",
        "cross_table_check",
        "maintainer_confirmed",
        "inference",
        "unresolved",
    }
)
ROLES = frozenset({"canonical", "reference", "wide_projection", "technical"})
VOCABULARY_COMPLETENESS = frozenset({"unknown", "open", "closed"})
VOCABULARY_PARSING = frozenset(
    {"atomic", "comma_composed_undocumented", "shared_slot_dictionary"}
)
KEY_KINDS = frozenset({"natural", "technical"})
KEY_UNIQUENESS = frozenset({"unique", "not_unique", "unknown"})
KEY_COMPLETENESS = frozenset({"complete", "incomplete", "unknown"})
RELATIONSHIP_KINDS = frozenset({"hierarchy", "reference", "projection"})
ENDPOINT_COMPLETENESS = frozenset({"required", "optional", "unknown"})
CARDINALITY_VALUES = frozenset(
    {"exactly_one", "zero_or_one", "one_or_more", "zero_or_more", "unknown"}
)

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_SEARCH_STOPWORDS = frozenset(
    {
        "a",
        "all",
        "an",
        "and",
        "everything",
        "feature",
        "features",
        "find",
        "for",
        "in",
        "of",
        "on",
        "or",
        "relevant",
        "show",
        "the",
        "to",
        "with",
    }
)
_TOP_LEVEL_KEYS = frozenset(
    {
        "$schema",
        "schema_version",
        "profiles",
        "grains",
        "feature_kinds",
        "domains",
        "concepts",
        "bindings",
        "vocabularies",
        "tables",
        "relationships",
    }
)
_CONCEPT_KEYS = frozenset(
    {
        "label",
        "definition",
        "feature_kind",
        "domains",
        "search_terms",
        "caveats",
        "evidence",
        "vocabulary",
    }
)
_CONCEPT_REQUIRED_KEYS = _CONCEPT_KEYS - {"vocabulary"}
_BINDING_KEYS = frozenset(
    {
        "profile",
        "table",
        "column",
        "concept",
        "grain",
        "role",
        "physical_type",
        "nullable",
        "parameters",
        "notes",
    }
)
_BINDING_REQUIRED_KEYS = _BINDING_KEYS - {"parameters", "notes"}
BINDING_PARAMETER_KEYS = frozenset({"slot"})
_VOCABULARY_KEYS = frozenset(
    {"label", "completeness", "parsing", "evidence", "caveats", "codes"}
)
_VOCABULARY_REQUIRED_KEYS = _VOCABULARY_KEYS - {"caveats"}
_TABLE_KEYS = frozenset({"profile", "table", "grain", "keys", "caveats"})
_KEY_KEYS = frozenset(
    {
        "id",
        "columns",
        "kind",
        "uniqueness",
        "completeness",
        "evidence",
        "caveats",
    }
)
_RELATIONSHIP_KEYS = frozenset(
    {
        "id",
        "profile",
        "kind",
        "source",
        "target",
        "cardinality",
        "evidence",
        "caveats",
        "join_hazards",
    }
)
_SOURCE_ENDPOINT_KEYS = frozenset({"table", "columns", "completeness"})
_TARGET_ENDPOINT_KEYS = frozenset({"table", "columns"})
_CARDINALITY_KEYS = frozenset(
    {"targets_per_source", "sources_per_target"}
)

class CatalogError(Exception):
    """Base class for catalog failures safe to present to a caller."""


class CatalogLoadError(CatalogError):
    """The catalog could not be read or decoded."""


class CatalogValidationError(CatalogError):
    """The decoded catalog violates the supported schema or references."""


class CatalogNotFoundError(CatalogError):
    """An exact feature, vocabulary, or code lookup failed."""


class CatalogAmbiguousError(CatalogError):
    """An unqualified physical identifier resolves to different concepts."""


@dataclass(frozen=True, slots=True)
class Concept:
    """One reusable semantic concept."""

    id: str
    label: str
    definition: str
    feature_kind: str
    domains: tuple[str, ...]
    search_terms: tuple[str, ...]
    caveats: tuple[str, ...]
    evidence: tuple[str, ...]
    vocabulary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "definition": self.definition,
            "feature_kind": self.feature_kind,
            "domains": list(self.domains),
            "search_terms": list(self.search_terms),
            "caveats": list(self.caveats),
            "evidence": list(self.evidence),
        }
        if self.vocabulary is not None:
            result["vocabulary"] = self.vocabulary
        return result


@dataclass(frozen=True, slots=True)
class Binding:
    """One physical table-column occurrence bound to a concept."""

    profile: str
    table: str
    column: str
    concept: str
    grain: str
    role: str
    physical_type: str
    nullable: bool
    parameters: tuple[tuple[str, int], ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def identifier(self) -> str:
        return f"{self.table}.{self.column}"

    @property
    def qualified_identifier(self) -> str:
        return f"{self.profile}:{self.identifier}"

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "identifier": self.identifier,
            "qualified_identifier": self.qualified_identifier,
            "profile": self.profile,
            "table": self.table,
            "column": self.column,
            "concept": self.concept,
            "grain": self.grain,
            "role": self.role,
            "physical_type": self.physical_type,
            "nullable": self.nullable,
        }
        if self.parameters:
            result["parameters"] = dict(self.parameters)
        if self.notes:
            result["notes"] = list(self.notes)
        return result


@dataclass(frozen=True, slots=True)
class Vocabulary:
    """A code-to-meaning map and its interpretation boundary."""

    id: str
    label: str
    completeness: str
    parsing: str
    evidence: tuple[str, ...]
    codes: tuple[tuple[str, str], ...]
    caveats: tuple[str, ...] = ()

    def to_dict(self, *, include_codes: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "completeness": self.completeness,
            "parsing": self.parsing,
            "evidence": list(self.evidence),
            "caveats": list(self.caveats),
        }
        if include_codes:
            result["codes"] = dict(self.codes)
        return result


@dataclass(frozen=True, slots=True)
class KeyCandidate:
    """A documented candidate key or explicitly non-key column tuple."""

    id: str
    columns: tuple[str, ...]
    kind: str
    uniqueness: str
    completeness: str
    evidence: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "columns": list(self.columns),
            "kind": self.kind,
            "uniqueness": self.uniqueness,
            "completeness": self.completeness,
            "evidence": list(self.evidence),
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class TableSpec:
    """One profile-specific table grain and its documented key candidates."""

    profile: str
    table: str
    grain: str
    keys: tuple[KeyCandidate, ...]
    caveats: tuple[str, ...]

    @property
    def identifier(self) -> str:
        return f"{self.profile}:{self.table}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "identifier": self.identifier,
            "profile": self.profile,
            "table": self.table,
            "grain": self.grain,
            "keys": [key.to_dict() for key in self.keys],
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class RelationshipEndpoint:
    """One ordered physical-column endpoint in a table relationship."""

    table: str
    columns: tuple[str, ...]
    completeness: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "table": self.table,
            "columns": list(self.columns),
        }
        if self.completeness is not None:
            result["completeness"] = self.completeness
        return result


@dataclass(frozen=True, slots=True)
class Relationship:
    """A count-free, profile-scoped linkage claim between physical tables."""

    id: str
    profile: str
    kind: str
    source: RelationshipEndpoint
    target: RelationshipEndpoint
    targets_per_source: str
    sources_per_target: str
    evidence: tuple[str, ...]
    caveats: tuple[str, ...]
    join_hazards: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "profile": self.profile,
            "kind": self.kind,
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "cardinality": {
                "targets_per_source": self.targets_per_source,
                "sources_per_target": self.sources_per_target,
            },
            "evidence": list(self.evidence),
            "caveats": list(self.caveats),
            "join_hazards": list(self.join_hazards),
        }


@dataclass(frozen=True, slots=True)
class _BindingSearchDocument:
    binding: Binding
    identifier_text: str
    auxiliary_text: str
    all_tokens: frozenset[str]


@dataclass(frozen=True, slots=True)
class _ConceptSearchDocument:
    concept: Concept
    vocabulary: Vocabulary | None
    concept_id_text: str
    label_text: str
    search_terms_text: str
    definition_text: str
    bindings: tuple[_BindingSearchDocument, ...]


class Catalog:
    """Validated immutable catalog with deterministic lookup indexes."""

    __slots__ = (
        "_schema_version",
        "_profiles",
        "_concepts",
        "_bindings",
        "_vocabularies",
        "_tables",
        "_relationships",
        "_tables_by_qualified",
        "_relationships_by_id",
        "_by_physical",
        "_by_qualified",
        "_bindings_by_concept",
        "_search_documents",
        "_sealed",
    )

    def __init__(
        self,
        *,
        schema_version: int,
        profiles: tuple[str, ...],
        concepts: Mapping[str, Concept],
        bindings: tuple[Binding, ...],
        vocabularies: Mapping[str, Vocabulary],
        tables: tuple[TableSpec, ...],
        relationships: tuple[Relationship, ...],
    ) -> None:
        object.__setattr__(self, "_schema_version", schema_version)
        object.__setattr__(self, "_profiles", profiles)
        object.__setattr__(
            self, "_concepts", MappingProxyType(dict(sorted(concepts.items())))
        )
        object.__setattr__(self, "_bindings", bindings)
        object.__setattr__(
            self,
            "_vocabularies",
            MappingProxyType(dict(sorted(vocabularies.items()))),
        )
        object.__setattr__(self, "_tables", tables)
        object.__setattr__(self, "_relationships", relationships)
        object.__setattr__(
            self,
            "_tables_by_qualified",
            MappingProxyType({table.identifier: table for table in tables}),
        )
        object.__setattr__(
            self,
            "_relationships_by_id",
            MappingProxyType(
                {relationship.id: relationship for relationship in relationships}
            ),
        )

        physical_groups: defaultdict[str, list[Binding]] = defaultdict(list)
        by_qualified: dict[str, Binding] = {}
        for binding in bindings:
            physical_groups[binding.identifier].append(binding)
            by_qualified[binding.qualified_identifier] = binding
        by_physical = {
            identifier: tuple(
                sorted(items, key=lambda item: item.qualified_identifier)
            )
            for identifier, items in sorted(physical_groups.items())
        }
        object.__setattr__(self, "_by_physical", MappingProxyType(by_physical))
        object.__setattr__(
            self, "_by_qualified", MappingProxyType(by_qualified)
        )

        grouped: defaultdict[str, list[Binding]] = defaultdict(list)
        for binding in bindings:
            grouped[binding.concept].append(binding)
        by_concept = {
            concept_id: tuple(
                sorted(items, key=lambda item: (item.profile, item.identifier))
            )
            for concept_id, items in sorted(grouped.items())
        }
        object.__setattr__(
            self, "_bindings_by_concept", MappingProxyType(by_concept)
        )
        object.__setattr__(self, "_search_documents", self._build_search_documents())
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("Catalog is immutable")
        object.__setattr__(self, name, value)

    @property
    def schema_version(self) -> int:
        return self._schema_version

    @property
    def profiles(self) -> tuple[str, ...]:
        return self._profiles

    @property
    def grains(self) -> tuple[str, ...]:
        return GRAINS

    @property
    def feature_kinds(self) -> tuple[str, ...]:
        return FEATURE_KINDS

    @property
    def domains(self) -> tuple[str, ...]:
        return DOMAINS

    @property
    def concepts(self) -> Mapping[str, Concept]:
        return self._concepts

    @property
    def bindings(self) -> tuple[Binding, ...]:
        return self._bindings

    @property
    def vocabularies(self) -> Mapping[str, Vocabulary]:
        return self._vocabularies

    @property
    def tables(self) -> tuple[TableSpec, ...]:
        return self._tables

    @property
    def relationships(self) -> tuple[Relationship, ...]:
        return self._relationships

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Catalog:
        """Validate an already-decoded mapping and freeze its contents."""

        data = _expect_mapping(value, "$")
        _require_exact_keys(data, _TOP_LEVEL_KEYS, _TOP_LEVEL_KEYS, "$")

        if data["$schema"] != SCHEMA_REFERENCE:
            raise CatalogValidationError(
                f"$.$schema must equal {SCHEMA_REFERENCE!r}"
            )
        if (
            not isinstance(data["schema_version"], int)
            or isinstance(data["schema_version"], bool)
            or data["schema_version"] != SCHEMA_VERSION
        ):
            raise CatalogValidationError(
                f"$.schema_version must equal integer {SCHEMA_VERSION}"
            )

        profiles = _string_array(
            data["profiles"], "$.profiles", minimum=1, identifier=True
        )
        _require_constant_array(data["grains"], GRAINS, "$.grains")
        _require_constant_array(
            data["feature_kinds"], FEATURE_KINDS, "$.feature_kinds"
        )
        _require_constant_array(data["domains"], DOMAINS, "$.domains")

        raw_concepts = _expect_mapping(data["concepts"], "$.concepts")
        if not raw_concepts:
            raise CatalogValidationError("$.concepts must not be empty")
        concepts: dict[str, Concept] = {}
        for concept_id, raw_concept in raw_concepts.items():
            _require_identifier(concept_id, f"$.concepts key {concept_id!r}")
            concepts[concept_id] = _parse_concept(concept_id, raw_concept)

        raw_vocabularies = _expect_mapping(
            data["vocabularies"], "$.vocabularies"
        )
        vocabularies: dict[str, Vocabulary] = {}
        for vocabulary_id, raw_vocabulary in raw_vocabularies.items():
            _require_identifier(
                vocabulary_id, f"$.vocabularies key {vocabulary_id!r}"
            )
            vocabularies[vocabulary_id] = _parse_vocabulary(
                vocabulary_id, raw_vocabulary
            )

        raw_bindings = _expect_list(data["bindings"], "$.bindings")
        if not raw_bindings:
            raise CatalogValidationError("$.bindings must not be empty")
        bindings = [
            _parse_binding(raw, index, frozenset(profiles))
            for index, raw in enumerate(raw_bindings)
        ]
        raw_tables = _expect_list(data["tables"], "$.tables")
        if not raw_tables:
            raise CatalogValidationError("$.tables must not be empty")
        tables = [
            _parse_table(raw, index, frozenset(profiles))
            for index, raw in enumerate(raw_tables)
        ]
        raw_relationships = _expect_list(
            data["relationships"], "$.relationships"
        )
        relationships = [
            _parse_relationship(raw, index, frozenset(profiles))
            for index, raw in enumerate(raw_relationships)
        ]

        for concept in concepts.values():
            if (
                concept.vocabulary is not None
                and concept.vocabulary not in vocabularies
            ):
                raise CatalogValidationError(
                    f"concept {concept.id!r} references unknown vocabulary "
                    f"{concept.vocabulary!r}"
                )
        mismatched_shared_ids = sorted(
            identifier
            for identifier in set(concepts) & set(vocabularies)
            if concepts[identifier].vocabulary != identifier
        )
        if mismatched_shared_ids:
            raise CatalogValidationError(
                "concept/vocabulary IDs may overlap only when each concept "
                "references the same-ID vocabulary: "
                + ", ".join(mismatched_shared_ids)
            )

        seen_qualified: set[str] = set()
        unqualified: set[str] = set()
        bound_profiles: set[str] = set()
        for binding in bindings:
            if binding.concept not in concepts:
                raise CatalogValidationError(
                    f"binding {binding.identifier!r} references unknown concept "
                    f"{binding.concept!r}"
                )
            if binding.qualified_identifier in seen_qualified:
                raise CatalogValidationError(
                    "duplicate physical binding "
                    f"{binding.qualified_identifier!r}"
                )
            seen_qualified.add(binding.qualified_identifier)
            unqualified.add(binding.identifier)
            bound_profiles.add(binding.profile)

        empty_profiles = sorted(set(profiles) - bound_profiles)
        if empty_profiles:
            raise CatalogValidationError(
                "catalog profiles have no physical bindings: "
                + ", ".join(empty_profiles)
            )

        collisions = sorted(set(concepts) & (seen_qualified | unqualified))
        if collisions:
            raise CatalogValidationError(
                "concept IDs collide with physical identifiers: "
                + ", ".join(collisions)
            )
        vocabulary_collisions = sorted(
            set(vocabularies) & (seen_qualified | unqualified)
        )
        if vocabulary_collisions:
            raise CatalogValidationError(
                "vocabulary IDs collide with physical identifiers: "
                + ", ".join(vocabulary_collisions)
            )

        bindings_by_table: defaultdict[
            tuple[str, str], dict[str, Binding]
        ] = defaultdict(dict)
        grains_by_table: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
        for binding in bindings:
            table_key = (binding.profile, binding.table)
            bindings_by_table[table_key][binding.column] = binding
            grains_by_table[table_key].add(binding.grain)

        table_specs: dict[tuple[str, str], TableSpec] = {}
        for table in tables:
            table_key = (table.profile, table.table)
            if table_key in table_specs:
                raise CatalogValidationError(
                    f"duplicate table specification {table.identifier!r}"
                )
            table_specs[table_key] = table
            columns = bindings_by_table.get(table_key)
            if columns is None:
                raise CatalogValidationError(
                    f"table specification {table.identifier!r} has no bindings"
                )
            binding_grains = grains_by_table[table_key]
            if binding_grains != {table.grain}:
                raise CatalogValidationError(
                    f"table specification {table.identifier!r} grain "
                    f"{table.grain!r} does not match binding grains "
                    f"{sorted(binding_grains)!r}"
                )
            seen_key_ids: set[str] = set()
            for key in table.keys:
                if key.id in seen_key_ids:
                    raise CatalogValidationError(
                        f"table {table.identifier!r} has duplicate key ID "
                        f"{key.id!r}"
                    )
                seen_key_ids.add(key.id)
                missing_columns = sorted(set(key.columns) - set(columns))
                if missing_columns:
                    raise CatalogValidationError(
                        f"table {table.identifier!r} key {key.id!r} references "
                        "unknown columns: " + ", ".join(missing_columns)
                    )

        missing_table_specs = sorted(set(bindings_by_table) - set(table_specs))
        if missing_table_specs:
            formatted = ", ".join(
                f"{profile}:{table}" for profile, table in missing_table_specs
            )
            raise CatalogValidationError(
                "physical tables have no table specification: " + formatted
            )

        relationship_ids: set[str] = set()
        for relationship in relationships:
            if relationship.id in relationship_ids:
                raise CatalogValidationError(
                    f"duplicate relationship ID {relationship.id!r}"
                )
            relationship_ids.add(relationship.id)
            _validate_relationship(
                relationship, bindings_by_table, table_specs
            )
        _validate_hierarchy_acyclic(relationships)

        ordered_bindings = tuple(
            sorted(
                bindings,
                key=lambda item: (
                    item.profile,
                    item.table,
                    item.column,
                    item.concept,
                ),
            )
        )
        return cls(
            schema_version=SCHEMA_VERSION,
            profiles=tuple(sorted(profiles)),
            concepts=concepts,
            bindings=ordered_bindings,
            vocabularies=vocabularies,
            tables=tuple(
                sorted(tables, key=lambda item: (item.profile, item.table))
            ),
            relationships=tuple(
                sorted(relationships, key=lambda item: item.id)
            ),
        )

    def summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profiles": list(self.profiles),
            "grains": list(self.grains),
            "feature_kinds": list(self.feature_kinds),
            "domains": list(self.domains),
            "concepts": len(self.concepts),
            "bindings": len(self.bindings),
            "vocabularies": len(self.vocabularies),
            "tables": len(self.tables),
            "relationships": len(self.relationships),
        }

    def get_table(self, profile: str, table: str) -> dict[str, Any]:
        """Get one profile-specific table and its incident relationships."""

        normalized_profile = _lookup_identifier(profile, "profile")
        normalized_table = _lookup_identifier(table, "table")
        identifier = f"{normalized_profile}:{normalized_table}"
        table_spec = self._tables_by_qualified.get(identifier)
        if table_spec is None:
            raise CatalogNotFoundError(f"table {identifier!r} was not found")

        outgoing = []
        incoming = []
        for relationship in self.relationships:
            if relationship.profile != normalized_profile:
                continue
            if relationship.source.table == normalized_table:
                outgoing.append(relationship.to_dict())
            if relationship.target.table == normalized_table:
                incoming.append(relationship.to_dict())
        return {
            "kind": "table",
            "identifier": identifier,
            "table": table_spec.to_dict(),
            "relationships": {
                "outgoing": outgoing,
                "incoming": incoming,
            },
        }

    def get_relationship(self, identifier: str) -> dict[str, Any]:
        """Get one relationship by its stable identifier."""

        normalized = _lookup_identifier(identifier, "identifier")
        relationship = self._relationships_by_id.get(normalized)
        if relationship is None:
            raise CatalogNotFoundError(
                f"relationship {normalized!r} was not found"
            )
        return {
            "kind": "relationship",
            "identifier": normalized,
            "relationship": relationship.to_dict(),
        }

    def search_relationships(
        self,
        *,
        profile: str | None = None,
        table: str | None = None,
        source_table: str | None = None,
        target_table: str | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Filter relationships by profile, endpoint table, and kind."""

        filters = {
            "profile": _optional_filter(profile, "profile"),
            "table": _optional_filter(table, "table"),
            "source_table": _optional_filter(source_table, "source_table"),
            "target_table": _optional_filter(target_table, "target_table"),
            "kind": _optional_filter(kind, "kind"),
        }
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 500
        ):
            raise CatalogValidationError("limit must be an integer from 1 to 500")
        controlled_filters = {
            "profile": self.profiles,
            "kind": RELATIONSHIP_KINDS,
        }
        for name, allowed in controlled_filters.items():
            if filters[name] is not None and filters[name] not in allowed:
                raise CatalogValidationError(
                    f"unknown {name} filter {filters[name]!r}"
                )

        matches = []
        for relationship in self.relationships:
            if (
                filters["profile"] is not None
                and relationship.profile != filters["profile"]
            ):
                continue
            if (
                filters["table"] is not None
                and filters["table"]
                not in (relationship.source.table, relationship.target.table)
            ):
                continue
            if (
                filters["source_table"] is not None
                and relationship.source.table != filters["source_table"]
            ):
                continue
            if (
                filters["target_table"] is not None
                and relationship.target.table != filters["target_table"]
            ):
                continue
            if (
                filters["kind"] is not None
                and relationship.kind != filters["kind"]
            ):
                continue
            matches.append(relationship)

        return {
            "filters": filters,
            "count": min(len(matches), limit),
            "total": len(matches),
            "matches": [
                relationship.to_dict() for relationship in matches[:limit]
            ],
        }

    def get_feature(
        self, identifier: str, include_codes: bool = False
    ) -> dict[str, Any]:
        """Get a concept ID, ``table.column``, or ``profile:table.column``."""

        normalized = _lookup_identifier(identifier, "identifier")
        concept = self._concepts.get(normalized)
        if concept is not None:
            vocabulary = self._vocabulary_for_concept(concept)
            return {
                "kind": "concept",
                "identifier": concept.id,
                "concept": concept.to_dict(),
                "bindings": [
                    binding.to_dict()
                    for binding in self._bindings_by_concept.get(concept.id, ())
                ],
                "vocabulary": (
                    vocabulary.to_dict(include_codes=include_codes)
                    if vocabulary is not None
                    else None
                ),
            }

        bindings = self._resolve_physical(normalized)
        concept = self._concepts[bindings[0].concept]
        vocabulary = self._vocabulary_for_concept(concept)
        result = {
            "kind": "binding" if len(bindings) == 1 else "binding_set",
            "identifier": normalized,
            "bindings": [binding.to_dict() for binding in bindings],
            "concept": concept.to_dict(),
            "vocabulary": (
                vocabulary.to_dict(include_codes=include_codes)
                if vocabulary is not None
                else None
            ),
        }
        if len(bindings) == 1:
            result["binding"] = bindings[0].to_dict()
        return result

    def lookup_code(
        self, feature_or_vocabulary: str, code: str
    ) -> dict[str, Any]:
        """Look up an exact code through a vocabulary, concept, or binding."""

        target = _lookup_identifier(
            feature_or_vocabulary, "feature_or_vocabulary"
        )
        if not isinstance(code, str) or code == "":
            raise CatalogValidationError("code must be a non-empty string")

        concept = self._concepts.get(target)
        concept_id: str | None = None
        if concept is not None:
            concept_id = concept.id
            vocabulary = self._vocabulary_for_concept(concept)
            if vocabulary is None:
                raise CatalogNotFoundError(
                    f"feature {target!r} has no vocabulary"
                )
        else:
            vocabulary = self._vocabularies.get(target)
            if vocabulary is None:
                bindings = self._resolve_physical(target)
                concept = self._concepts[bindings[0].concept]
                concept_id = concept.id
                vocabulary = self._vocabulary_for_concept(concept)
                if vocabulary is None:
                    raise CatalogNotFoundError(
                        f"feature {target!r} has no vocabulary"
                    )

        meanings = dict(vocabulary.codes)
        if code not in meanings:
            raise CatalogNotFoundError(
                f"code {code!r} was not found in vocabulary {vocabulary.id!r}"
            )
        return {
            "feature_or_vocabulary": target,
            "concept": concept_id,
            "vocabulary": vocabulary.id,
            "code": code,
            "meaning": meanings[code],
            "completeness": vocabulary.completeness,
            "parsing": vocabulary.parsing,
            "evidence": list(vocabulary.evidence),
            "caveats": list(vocabulary.caveats),
        }

    def search_features(
        self,
        query: str,
        *,
        profile: str | None = None,
        table: str | None = None,
        grain: str | None = None,
        domain: str | None = None,
        feature_kind: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Search concepts with deterministic weighted token matching."""

        if not isinstance(query, str):
            raise CatalogValidationError("query must be a string")
        query_text = query.strip().casefold()
        filters = {
            "profile": _optional_filter(profile, "profile"),
            "table": _optional_filter(table, "table"),
            "grain": _optional_filter(grain, "grain"),
            "domain": _optional_filter(domain, "domain"),
            "feature_kind": _optional_filter(feature_kind, "feature_kind"),
        }
        if not query_text and not any(filters.values()):
            raise CatalogValidationError(
                "provide a query or at least one search filter"
            )
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 500
        ):
            raise CatalogValidationError("limit must be an integer from 1 to 500")
        controlled_filters = {
            "profile": self.profiles,
            "grain": GRAINS,
            "domain": DOMAINS,
            "feature_kind": FEATURE_KINDS,
        }
        for name, allowed in controlled_filters.items():
            if filters[name] is not None and filters[name] not in allowed:
                raise CatalogValidationError(
                    f"unknown {name} filter {filters[name]!r}"
                )

        query_tokens = frozenset(
            token
            for token in _tokens(query_text)
            if token not in _SEARCH_STOPWORDS
        )
        if query_text and not query_tokens and not any(filters.values()):
            raise CatalogValidationError(
                "query must contain at least one meaningful token"
            )
        candidates = []
        has_complete_match = False
        for document in self._search_documents:
            concept = document.concept
            binding_matches: list[tuple[int, int, _BindingSearchDocument]] = []
            for binding_document in document.bindings:
                if not _matches_search_filters(
                    binding_document.binding, concept, filters
                ):
                    continue
                overlap = query_tokens & binding_document.all_tokens
                if query_tokens and not overlap:
                    continue
                score = _score_document(
                    document, binding_document, query_text, query_tokens
                )
                if query_tokens:
                    score += round(40 * len(overlap) / len(query_tokens))
                    has_complete_match |= len(overlap) == len(query_tokens)
                binding_matches.append((score, len(overlap), binding_document))

            if binding_matches:
                candidates.append((document, binding_matches))

        scored_concepts = []
        for document, entries in candidates:
            if query_tokens and has_complete_match:
                entries = [
                    entry for entry in entries if entry[1] == len(query_tokens)
                ]
                if not entries:
                    continue
            entries.sort(
                key=lambda item: (
                    -item[0],
                    item[2].binding.qualified_identifier,
                )
            )
            score = entries[0][0]
            binding_documents = tuple(
                sorted(
                    (entry[2] for entry in entries),
                    key=lambda item: item.binding.qualified_identifier,
                )
            )
            scored_concepts.append(
                (
                    score,
                    document.concept.id,
                    document,
                    binding_documents,
                )
            )
        scored_concepts.sort(key=lambda item: (-item[0], item[1]))
        matches = [
            _search_match(document, binding_documents, score)
            for score, _, document, binding_documents in scored_concepts[:limit]
        ]
        return {
            "query": query,
            "filters": filters,
            "count": len(matches),
            "total": len(scored_concepts),
            "matches": matches,
        }

    def _resolve_physical(self, identifier: str) -> tuple[Binding, ...]:
        if ":" in identifier:
            binding = self._by_qualified.get(identifier)
            if binding is None:
                raise CatalogNotFoundError(
                    f"feature {identifier!r} was not found"
                )
            return (binding,)

        bindings = self._by_physical.get(identifier)
        if not bindings:
            raise CatalogNotFoundError(
                f"feature or vocabulary {identifier!r} was not found"
            )
        concepts = {binding.concept for binding in bindings}
        if len(concepts) > 1:
            choices = ", ".join(
                binding.qualified_identifier for binding in bindings
            )
            raise CatalogAmbiguousError(
                f"feature {identifier!r} is ambiguous; use one of: {choices}"
            )
        return bindings

    def _vocabulary_for_concept(
        self, concept: Concept
    ) -> Vocabulary | None:
        if concept.vocabulary is None:
            return None
        return self._vocabularies[concept.vocabulary]

    def _build_search_documents(self) -> tuple[_ConceptSearchDocument, ...]:
        documents: list[_ConceptSearchDocument] = []
        for concept in self._concepts.values():
            bindings = self._bindings_by_concept.get(concept.id, ())
            if not bindings:
                continue
            vocabulary = self._vocabulary_for_concept(concept)
            concept_id_text = concept.id.casefold()
            label_text = concept.label.casefold()
            search_terms_text = " ".join(concept.search_terms).casefold()
            definition_text = concept.definition.casefold()
            binding_documents: list[_BindingSearchDocument] = []
            for binding in bindings:
                identifier_text = binding.identifier.casefold()
                auxiliary_parts = [
                    binding.profile,
                    binding.table,
                    binding.column,
                    binding.grain,
                    binding.role,
                    binding.physical_type,
                    concept.feature_kind,
                    *concept.domains,
                    *concept.caveats,
                    *concept.evidence,
                    *binding.notes,
                ]
                auxiliary_parts.extend(
                    compact
                    for compact in (
                        _compact_identifier(binding.identifier),
                        _compact_identifier(binding.column),
                        _compact_identifier(concept.id),
                        *(
                            _compact_identifier(term)
                            for term in concept.search_terms
                        ),
                    )
                    if compact
                )
                if vocabulary is not None:
                    auxiliary_parts.extend(
                        [
                            vocabulary.id,
                            vocabulary.label,
                            vocabulary.completeness,
                            vocabulary.parsing,
                            *vocabulary.caveats,
                            *(code for code, _ in vocabulary.codes),
                            *(meaning for _, meaning in vocabulary.codes),
                        ]
                    )
                auxiliary_text = " ".join(auxiliary_parts).casefold()
                all_text = " ".join(
                    (
                        identifier_text,
                        concept_id_text,
                        label_text,
                        search_terms_text,
                        definition_text,
                        auxiliary_text,
                    )
                )
                binding_documents.append(
                    _BindingSearchDocument(
                        binding=binding,
                        identifier_text=identifier_text,
                        auxiliary_text=auxiliary_text,
                        all_tokens=frozenset(_tokens(all_text)),
                    )
                )
            documents.append(
                _ConceptSearchDocument(
                    concept=concept,
                    vocabulary=vocabulary,
                    concept_id_text=concept_id_text,
                    label_text=label_text,
                    search_terms_text=search_terms_text,
                    definition_text=definition_text,
                    bindings=tuple(binding_documents),
                )
            )
        return tuple(documents)


def default_catalog_path() -> Path:
    """Return the repository-relative default catalog path."""

    return Path(__file__).resolve().parents[1] / "catalog" / "catalog.json"


def load_catalog(path: str | Path | None = None) -> Catalog:
    """Read and validate a catalog, rejecting duplicate JSON object keys."""

    catalog_path = default_catalog_path() if path is None else Path(path)
    try:
        text = catalog_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CatalogLoadError(
            f"could not read catalog {catalog_path}: {exc}"
        ) from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except CatalogValidationError:
        raise
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise CatalogLoadError(
            f"could not decode catalog {catalog_path}: {exc}"
        ) from exc
    if not isinstance(value, Mapping):
        raise CatalogValidationError("$ must be a JSON object")
    return Catalog.from_mapping(value)


def _object_without_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CatalogValidationError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise CatalogValidationError(f"non-standard JSON number {value!r} is forbidden")


def _parse_concept(concept_id: str, value: object) -> Concept:
    path = f"$.concepts.{concept_id}"
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data, _CONCEPT_REQUIRED_KEYS, _CONCEPT_KEYS, path
    )
    feature_kind = _nonempty_string(data["feature_kind"], f"{path}.feature_kind")
    if feature_kind not in FEATURE_KINDS:
        raise CatalogValidationError(
            f"{path}.feature_kind has unknown value {feature_kind!r}"
        )
    domains = _string_array(data["domains"], f"{path}.domains", minimum=1)
    for domain in domains:
        if domain not in DOMAINS:
            raise CatalogValidationError(
                f"{path}.domains contains unknown value {domain!r}"
            )
    vocabulary = data.get("vocabulary")
    if vocabulary is not None:
        vocabulary = _nonempty_string(vocabulary, f"{path}.vocabulary")
        _require_identifier(vocabulary, f"{path}.vocabulary")
    return Concept(
        id=concept_id,
        label=_nonempty_string(data["label"], f"{path}.label"),
        definition=_nonempty_string(data["definition"], f"{path}.definition"),
        feature_kind=feature_kind,
        domains=domains,
        search_terms=_string_array(
            data["search_terms"], f"{path}.search_terms", minimum=1
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
        evidence=_evidence_array(data["evidence"], f"{path}.evidence"),
        vocabulary=vocabulary,
    )


def _parse_binding(
    value: object, index: int, profiles: frozenset[str]
) -> Binding:
    path = f"$.bindings[{index}]"
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data, _BINDING_REQUIRED_KEYS, _BINDING_KEYS, path
    )
    profile = _nonempty_string(data["profile"], f"{path}.profile")
    _require_identifier(profile, f"{path}.profile")
    if profile not in profiles:
        raise CatalogValidationError(
            f"{path}.profile references unknown profile {profile!r}"
        )
    concept = _nonempty_string(data["concept"], f"{path}.concept")
    _require_identifier(concept, f"{path}.concept")
    grain = _nonempty_string(data["grain"], f"{path}.grain")
    if grain not in GRAINS:
        raise CatalogValidationError(
            f"{path}.grain has unknown value {grain!r}"
        )
    role = _nonempty_string(data["role"], f"{path}.role")
    if role not in ROLES:
        raise CatalogValidationError(
            f"{path}.role has unknown value {role!r}"
        )
    nullable = data["nullable"]
    if not isinstance(nullable, bool):
        raise CatalogValidationError(f"{path}.nullable must be a boolean")

    parameters: tuple[tuple[str, int], ...] = ()
    if "parameters" in data:
        raw_parameters = _expect_mapping(
            data["parameters"], f"{path}.parameters"
        )
        if not raw_parameters:
            raise CatalogValidationError(
                f"{path}.parameters must not be empty"
            )
        unsupported = sorted(set(raw_parameters) - BINDING_PARAMETER_KEYS)
        if unsupported:
            raise CatalogValidationError(
                f"{path}.parameters has unsupported fields: "
                + ", ".join(unsupported)
            )
        slot = raw_parameters["slot"]
        if (
            not isinstance(slot, int)
            or isinstance(slot, bool)
            or slot < 1
        ):
            raise CatalogValidationError(
                f"{path}.parameters.slot must be a positive integer"
            )
        parameters = (("slot", slot),)

    notes: tuple[str, ...] = ()
    if "notes" in data:
        notes = _string_array(data["notes"], f"{path}.notes", minimum=1)
    return Binding(
        profile=profile,
        table=_physical_component(data["table"], f"{path}.table"),
        column=_physical_component(data["column"], f"{path}.column"),
        concept=concept,
        grain=grain,
        role=role,
        physical_type=_nonempty_string(
            data["physical_type"], f"{path}.physical_type"
        ),
        nullable=nullable,
        parameters=parameters,
        notes=notes,
    )


def _parse_vocabulary(vocabulary_id: str, value: object) -> Vocabulary:
    path = f"$.vocabularies.{vocabulary_id}"
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data, _VOCABULARY_REQUIRED_KEYS, _VOCABULARY_KEYS, path
    )
    completeness = _nonempty_string(
        data["completeness"], f"{path}.completeness"
    )
    if completeness not in VOCABULARY_COMPLETENESS:
        raise CatalogValidationError(
            f"{path}.completeness has unknown value {completeness!r}"
        )
    parsing = _nonempty_string(data["parsing"], f"{path}.parsing")
    if parsing not in VOCABULARY_PARSING:
        raise CatalogValidationError(
            f"{path}.parsing has unknown value {parsing!r}"
        )
    raw_codes = _expect_mapping(data["codes"], f"{path}.codes")
    if not raw_codes:
        raise CatalogValidationError(f"{path}.codes must not be empty")
    codes: list[tuple[str, str]] = []
    for code, meaning in sorted(raw_codes.items()):
        if not isinstance(code, str) or code == "":
            raise CatalogValidationError(
                f"{path}.codes keys must be non-empty strings"
            )
        codes.append(
            (code, _nonempty_string(meaning, f"{path}.codes.{code}"))
        )
    caveats = (
        _string_array(data["caveats"], f"{path}.caveats")
        if "caveats" in data
        else ()
    )
    return Vocabulary(
        id=vocabulary_id,
        label=_nonempty_string(data["label"], f"{path}.label"),
        completeness=completeness,
        parsing=parsing,
        evidence=_evidence_array(data["evidence"], f"{path}.evidence"),
        codes=tuple(codes),
        caveats=caveats,
    )


def _parse_table(
    value: object, index: int, profiles: frozenset[str]
) -> TableSpec:
    path = f"$.tables[{index}]"
    data = _expect_mapping(value, path)
    _require_exact_keys(data, _TABLE_KEYS, _TABLE_KEYS, path)
    profile = _controlled_identifier(
        data["profile"], f"{path}.profile", profiles
    )
    grain = _controlled_string(data["grain"], f"{path}.grain", GRAINS)
    raw_keys = _expect_list(data["keys"], f"{path}.keys")
    keys = tuple(
        _parse_key(raw_key, f"{path}.keys[{key_index}]")
        for key_index, raw_key in enumerate(raw_keys)
    )
    return TableSpec(
        profile=profile,
        table=_physical_component(data["table"], f"{path}.table"),
        grain=grain,
        keys=keys,
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _parse_key(value: object, path: str) -> KeyCandidate:
    data = _expect_mapping(value, path)
    _require_exact_keys(data, _KEY_KEYS, _KEY_KEYS, path)
    key_id = _nonempty_string(data["id"], f"{path}.id")
    _require_identifier(key_id, f"{path}.id")
    return KeyCandidate(
        id=key_id,
        columns=_physical_component_array(
            data["columns"], f"{path}.columns"
        ),
        kind=_controlled_string(
            data["kind"], f"{path}.kind", KEY_KINDS
        ),
        uniqueness=_controlled_string(
            data["uniqueness"],
            f"{path}.uniqueness",
            KEY_UNIQUENESS,
        ),
        completeness=_controlled_string(
            data["completeness"],
            f"{path}.completeness",
            KEY_COMPLETENESS,
        ),
        evidence=_evidence_array(data["evidence"], f"{path}.evidence"),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _parse_relationship(
    value: object, index: int, profiles: frozenset[str]
) -> Relationship:
    path = f"$.relationships[{index}]"
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data, _RELATIONSHIP_KEYS, _RELATIONSHIP_KEYS, path
    )
    relationship_id = _nonempty_string(data["id"], f"{path}.id")
    _require_identifier(relationship_id, f"{path}.id")
    profile = _controlled_identifier(
        data["profile"], f"{path}.profile", profiles
    )
    cardinality = _expect_mapping(
        data["cardinality"], f"{path}.cardinality"
    )
    _require_exact_keys(
        cardinality,
        _CARDINALITY_KEYS,
        _CARDINALITY_KEYS,
        f"{path}.cardinality",
    )
    return Relationship(
        id=relationship_id,
        profile=profile,
        kind=_controlled_string(
            data["kind"], f"{path}.kind", RELATIONSHIP_KINDS
        ),
        source=_parse_source_endpoint(
            data["source"], f"{path}.source"
        ),
        target=_parse_target_endpoint(
            data["target"], f"{path}.target"
        ),
        targets_per_source=_controlled_string(
            cardinality["targets_per_source"],
            f"{path}.cardinality.targets_per_source",
            CARDINALITY_VALUES,
        ),
        sources_per_target=_controlled_string(
            cardinality["sources_per_target"],
            f"{path}.cardinality.sources_per_target",
            CARDINALITY_VALUES,
        ),
        evidence=_evidence_array(data["evidence"], f"{path}.evidence"),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
        join_hazards=_string_array(
            data["join_hazards"], f"{path}.join_hazards"
        ),
    )


def _parse_source_endpoint(
    value: object, path: str
) -> RelationshipEndpoint:
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data, _SOURCE_ENDPOINT_KEYS, _SOURCE_ENDPOINT_KEYS, path
    )
    return RelationshipEndpoint(
        table=_physical_component(data["table"], f"{path}.table"),
        columns=_physical_component_array(
            data["columns"], f"{path}.columns"
        ),
        completeness=_controlled_string(
            data["completeness"],
            f"{path}.completeness",
            ENDPOINT_COMPLETENESS,
        ),
    )


def _parse_target_endpoint(
    value: object, path: str
) -> RelationshipEndpoint:
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data, _TARGET_ENDPOINT_KEYS, _TARGET_ENDPOINT_KEYS, path
    )
    return RelationshipEndpoint(
        table=_physical_component(data["table"], f"{path}.table"),
        columns=_physical_component_array(
            data["columns"], f"{path}.columns"
        ),
    )


def _validate_relationship(
    relationship: Relationship,
    bindings_by_table: Mapping[tuple[str, str], Mapping[str, Binding]],
    table_specs: Mapping[tuple[str, str], TableSpec],
) -> None:
    source_key = (relationship.profile, relationship.source.table)
    target_key = (relationship.profile, relationship.target.table)
    source_columns = bindings_by_table.get(source_key)
    target_columns = bindings_by_table.get(target_key)
    if source_columns is None:
        raise CatalogValidationError(
            f"relationship {relationship.id!r} references unknown source "
            f"table {relationship.profile}:{relationship.source.table}"
        )
    if target_columns is None:
        raise CatalogValidationError(
            f"relationship {relationship.id!r} references unknown target "
            f"table {relationship.profile}:{relationship.target.table}"
        )
    if len(relationship.source.columns) != len(relationship.target.columns):
        raise CatalogValidationError(
            f"relationship {relationship.id!r} endpoint column tuples must "
            "have equal length"
        )
    for endpoint_name, columns, available in (
        ("source", relationship.source.columns, source_columns),
        ("target", relationship.target.columns, target_columns),
    ):
        missing = sorted(set(columns) - set(available))
        if missing:
            raise CatalogValidationError(
                f"relationship {relationship.id!r} {endpoint_name} references "
                "unknown columns: " + ", ".join(missing)
            )
    for source_column, target_column in zip(
        relationship.source.columns, relationship.target.columns, strict=True
    ):
        source_type = source_columns[source_column].physical_type
        target_type = target_columns[target_column].physical_type
        if source_type != target_type:
            raise CatalogValidationError(
                f"relationship {relationship.id!r} has incompatible physical "
                f"types for {source_column!r} and {target_column!r}: "
                f"{source_type!r} != {target_type!r}"
            )
    if relationship.targets_per_source in {"exactly_one", "zero_or_one"}:
        target = table_specs[target_key]
        if not any(
            key.columns == relationship.target.columns
            and key.uniqueness == "unique"
            for key in target.keys
        ):
            raise CatalogValidationError(
                f"relationship {relationship.id!r} claims at most one target "
                "but its target columns are not a documented unique key"
            )
    if relationship.sources_per_target in {"exactly_one", "zero_or_one"}:
        source = table_specs[source_key]
        if not any(
            key.columns == relationship.source.columns
            and key.uniqueness == "unique"
            for key in source.keys
        ):
            raise CatalogValidationError(
                f"relationship {relationship.id!r} claims at most one source "
                "but its source columns are not a documented unique key"
            )


def _validate_hierarchy_acyclic(
    relationships: Sequence[Relationship],
) -> None:
    graph: defaultdict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    nodes: set[tuple[str, str]] = set()
    for relationship in relationships:
        if relationship.kind != "hierarchy":
            continue
        source = (relationship.profile, relationship.source.table)
        target = (relationship.profile, relationship.target.table)
        graph[source].add(target)
        nodes.update((source, target))

    visiting: set[tuple[str, str]] = set()
    visited: set[tuple[str, str]] = set()

    def visit(node: tuple[str, str]) -> None:
        if node in visited:
            return
        if node in visiting:
            raise CatalogValidationError(
                "hierarchy relationships must be acyclic"
            )
        visiting.add(node)
        for target in graph.get(node, ()):
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(nodes):
        visit(node)


def _expect_mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CatalogValidationError(f"{path} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise CatalogValidationError(f"{path} object keys must be strings")
    return value


def _expect_list(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise CatalogValidationError(f"{path} must be an array")
    return value


def _require_exact_keys(
    data: Mapping[str, Any],
    required: frozenset[str],
    allowed: frozenset[str],
    path: str,
) -> None:
    actual = frozenset(data)
    missing = sorted(required - actual)
    unexpected = sorted(actual - allowed)
    if missing:
        raise CatalogValidationError(
            f"{path} is missing required fields: {', '.join(missing)}"
        )
    if unexpected:
        raise CatalogValidationError(
            f"{path} has unexpected fields: {', '.join(unexpected)}"
        )


def _nonempty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogValidationError(f"{path} must be a non-empty string")
    return value


def _physical_component(value: object, path: str) -> str:
    component = _nonempty_string(value, path)
    if component != component.strip():
        raise CatalogValidationError(
            f"{path} must not have surrounding whitespace"
        )
    if ":" in component:
        raise CatalogValidationError(
            f"{path} must not contain ':' because it separates profiles"
        )
    return component


def _physical_component_array(
    value: object, path: str
) -> tuple[str, ...]:
    items = _expect_list(value, path)
    if not items:
        raise CatalogValidationError(
            f"{path} must contain at least 1 item(s)"
        )
    parsed = tuple(
        _physical_component(item, f"{path}[{index}]")
        for index, item in enumerate(items)
    )
    if len(set(parsed)) != len(parsed):
        raise CatalogValidationError(f"{path} must contain unique values")
    return parsed


def _controlled_string(
    value: object, path: str, allowed: Sequence[str] | frozenset[str]
) -> str:
    parsed = _nonempty_string(value, path)
    if parsed not in allowed:
        raise CatalogValidationError(
            f"{path} has unknown value {parsed!r}"
        )
    return parsed


def _controlled_identifier(
    value: object, path: str, allowed: Sequence[str] | frozenset[str]
) -> str:
    parsed = _nonempty_string(value, path)
    _require_identifier(parsed, path)
    if parsed not in allowed:
        raise CatalogValidationError(
            f"{path} references unknown value {parsed!r}"
        )
    return parsed


def _string_array(
    value: object,
    path: str,
    *,
    minimum: int = 0,
    identifier: bool = False,
) -> tuple[str, ...]:
    items = _expect_list(value, path)
    if len(items) < minimum:
        raise CatalogValidationError(
            f"{path} must contain at least {minimum} item(s)"
        )
    parsed: list[str] = []
    for index, item in enumerate(items):
        string = _nonempty_string(item, f"{path}[{index}]")
        if identifier:
            _require_identifier(string, f"{path}[{index}]")
        parsed.append(string)
    if len(set(parsed)) != len(parsed):
        raise CatalogValidationError(f"{path} must contain unique values")
    return tuple(parsed)


def _evidence_array(value: object, path: str) -> tuple[str, ...]:
    evidence = _string_array(value, path, minimum=1)
    for item in evidence:
        if item not in EVIDENCE_VALUES:
            raise CatalogValidationError(
                f"{path} contains unknown evidence value {item!r}"
            )
    return evidence


def _require_constant_array(
    value: object, expected: Sequence[str], path: str
) -> None:
    if not isinstance(value, list) or tuple(value) != tuple(expected):
        raise CatalogValidationError(
            f"{path} must equal the catalog schema's controlled values"
        )


def _require_identifier(value: str, path: str) -> None:
    if _ID_PATTERN.fullmatch(value) is None:
        raise CatalogValidationError(
            f"{path} must match {_ID_PATTERN.pattern!r}"
        )


def _lookup_identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogValidationError(f"{name} must be a non-empty string")
    return value.strip()


def _optional_filter(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CatalogValidationError(
            f"{name} filter must be a non-empty string"
        )
    return value.strip()


def _matches_search_filters(
    binding: Binding,
    concept: Concept,
    filters: Mapping[str, str | None],
) -> bool:
    return (
        (filters["profile"] is None or binding.profile == filters["profile"])
        and (filters["table"] is None or binding.table == filters["table"])
        and (filters["grain"] is None or binding.grain == filters["grain"])
        and (
            filters["domain"] is None
            or filters["domain"] in concept.domains
        )
        and (
            filters["feature_kind"] is None
            or concept.feature_kind == filters["feature_kind"]
        )
    )


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(
        _normalize_token(token)
        for token in _TOKEN_PATTERN.findall(value.casefold())
    )


def _normalize_token(token: str) -> str:
    """Apply a deliberately small plural normalization for search."""

    if len(token) > 4 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 4 and token.endswith("sses"):
        return token[:-2]
    if (
        len(token) > 3
        and token.endswith("s")
        and not token.endswith(("ss", "us", "is"))
    ):
        return token[:-1]
    return token


def _compact_identifier(value: str) -> str:
    """Collapse identifier punctuation for aliases such as ACCAnon/acc_anon."""

    return re.sub(r"[\W_]+", "", value.casefold())


def _score_document(
    document: _ConceptSearchDocument,
    binding_document: _BindingSearchDocument,
    query_text: str,
    query_tokens: frozenset[str],
) -> int:
    if not query_text:
        return 0
    score = 0
    if query_text == binding_document.identifier_text:
        score += 1000
    if query_text == document.concept_id_text:
        score += 800
    fields = (
        (binding_document.identifier_text, 120),
        (document.concept_id_text, 100),
        (document.label_text, 80),
        (document.search_terms_text, 60),
        (document.definition_text, 30),
        (binding_document.auxiliary_text, 10),
    )
    for text, phrase_weight in fields:
        if query_text in text:
            score += phrase_weight
    token_fields = (
        (frozenset(_tokens(binding_document.identifier_text)), 24),
        (frozenset(_tokens(document.concept_id_text)), 20),
        (frozenset(_tokens(document.label_text)), 16),
        (frozenset(_tokens(document.search_terms_text)), 12),
        (frozenset(_tokens(document.definition_text)), 6),
        (frozenset(_tokens(binding_document.auxiliary_text)), 2),
    )
    for token in query_tokens:
        for field_tokens, token_weight in token_fields:
            if token in field_tokens:
                score += token_weight
    return score


def _search_match(
    document: _ConceptSearchDocument,
    binding_documents: tuple[_BindingSearchDocument, ...],
    score: int,
) -> dict[str, Any]:
    concept = document.concept
    vocabulary = document.vocabulary
    return {
        "score": score,
        "identifier": concept.id,
        "concept": concept.id,
        "label": concept.label,
        "definition": concept.definition,
        "feature_kind": concept.feature_kind,
        "domains": list(concept.domains),
        "evidence": list(concept.evidence),
        "caveats": list(concept.caveats),
        "bindings": [
            binding_document.binding.to_dict()
            for binding_document in binding_documents
        ],
        "vocabulary": (
            vocabulary.id if vocabulary is not None else None
        ),
    }
