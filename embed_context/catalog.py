"""Load, validate, and query the count-free EMBED clinical-semantic catalog.

The core uses only the Python standard library.  Portable clinical semantics
are kept separate from profile-specific tables, columns, and join bindings.
"""

from __future__ import annotations

import json
import hashlib
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import jsonschema


SCHEMA_REFERENCE = "./catalog.schema.json"
SCHEMA_VERSION = 6
SEMANTIC_SCHEMA_VERSION = 7

BINDING_GRAINS = (
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
CONTEXT_KINDS = (
    "clinical_workflow",
    "data_representation",
    "interpretation_guardrail",
    "known_issue",
)
CONTEXT_SCOPES = (
    "general_clinical",
    "embed_general",
    "profile_specific",
)
SOURCE_KINDS = (
    "maintainer_confirmed",
    "release_schema",
    "release_legend",
    "supporting_internal",
    "public_documentation",
)
SOURCE_LOCATOR_KINDS = ("url", "repository_path", "logical_artifact")
CLAIM_STATUSES = (
    "verified",
    "reconciled",
    "unverified",
    "unresolved",
    "contradicted",
)
SEMANTIC_RELATIONSHIP_KINDS = (
    "hierarchy",
    "association",
    "attribution",
    "documentation",
    "derivation",
)
TEMPORAL_KINDS = ("event_time", "documentation_time", "availability_time")
AGGREGATION_STATUSES = (
    "provided",
    "analyst_defined",
    "unsupported",
    "unresolved",
)
COVERAGE_STATUSES = ("supported", "unsupported", "unresolved", "not_cataloged")
GUARDRAIL_CATEGORIES = (
    "prohibition",
    "analyst_choice",
    "interpretation_limit",
)
GUARDRAIL_PRIORITIES = ("critical", "high", "standard")
DISCOVERY_KINDS = (
    "clinical_object",
    "feature",
    "semantic_relationship",
    "temporal_semantic",
    "aggregation",
    "guardrail",
    "coverage",
    "context",
)
RELATIONSHIP_BINDING_KINDS = frozenset(
    {"hierarchy", "reference", "projection"}
)
OBJECT_BINDING_REPRESENTATIONS = frozenset(
    {"canonical", "partial", "co_located", "projection", "reference"}
)
OPTIONALITY_VALUES = frozenset({"required", "optional", "unknown"})
CARDINALITY_VALUES = frozenset(
    {"exactly_one", "zero_or_one", "one_or_more", "zero_or_more", "unknown"}
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
ENDPOINT_COMPLETENESS = frozenset({"required", "optional", "unknown"})
COVERAGE_SUBJECT_KINDS = frozenset(
    {
        "clinical_object",
        "concept",
        "semantic_relationship",
        "temporal_semantic",
        "aggregation",
        "guardrail",
        "topic",
    }
)

BINDING_PARAMETER_KEYS = frozenset({"slot"})
_SLOT_PARAMETER_CONCEPT = "pathology.diagnosis_code_slot"

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_CLAIM_REF_PATTERN = re.compile(
    r"^(?P<context>[a-z][a-z0-9_.-]*)#(?P<claim>[a-z][a-z0-9_.-]*)$"
)
_SEARCH_STOPWORDS = frozenset(
    {
        "a",
        "all",
        "an",
        "and",
        "anon",
        "everything",
        "feature",
        "features",
        "find",
        "for",
        "how",
        "in",
        "is",
        "it",
        "known",
        "of",
        "on",
        "or",
        "relevant",
        "represented",
        "show",
        "the",
        "to",
        "with",
    }
)

_DISCOVERY_INTENT_AFFINITIES: Mapping[str, frozenset[str]] = {
    "longitudinal": frozenset(
        {
            "accession",
            "candidate",
            "exam",
            "history",
            "longitudinal",
            "nearest",
            "pathology",
            "patient",
            "prior",
            "subsequent",
            "timeline",
        }
    ),
    "temporal_fallback": frozenset(
        {
            "coalesce",
            "date",
            "fallback",
            "interchangeable",
            "missingness",
            "proxy",
            "report",
            "specimen",
            "substitute",
            "substitution",
            "temporal",
            "timestamp",
        }
    ),
    "probability_calibration": frozenset(
        {
            "brier",
            "calibration",
            "exceptional",
            "horizon",
            "model",
            "probability",
            "risk",
            "scale",
            "score",
            "unit",
            "version",
        }
    ),
    "finding_identity": frozenset(
        {
            "finding",
            "identity",
            "instance",
            "key",
            "longitudinal",
            "multiplicity",
            "numfind",
            "row",
            "synthetic",
        }
    ),
    "laterality_role": frozenset(
        {
            "bilateral",
            "bside",
            "laterality",
            "null",
            "procedure",
            "side",
            "unknown",
        }
    ),
    "represented_binary_endpoint": frozenset(
        {
            "binary",
            "biopsy",
            "cancer",
            "endpoint",
            "event",
            "outcome",
            "represented",
            "zero",
        }
    ),
    "finding_attribution_aggregation": frozenset(
        {
            "aggregate",
            "aggregation",
            "attribution",
            "finding",
            "multiplicity",
            "pathology",
            "policy",
            "severity",
        }
    ),
}

_TOP_LEVEL_KEYS = frozenset(
    {
        "$schema",
        "schema_version",
        "profiles",
        "binding_grains",
        "feature_kinds",
        "domains",
        "context_kinds",
        "context_scopes",
        "source_kinds",
        "source_locator_kinds",
        "claim_statuses",
        "semantic_relationship_kinds",
        "temporal_kinds",
        "aggregation_statuses",
        "coverage_statuses",
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
    }
)
_CLINICAL_OBJECT_KEYS = frozenset(
    {"label", "definition", "grain", "domains", "search_terms", "claim_refs", "caveats"}
)
_CONCEPT_KEYS = frozenset(
    {
        "label",
        "definition",
        "feature_kind",
        "domains",
        "objects",
        "search_terms",
        "caveats",
        "evidence",
        "vocabulary",
        "claim_refs",
        "missing_states",
        "temporal_semantics",
        "aggregations",
    }
)
_CONCEPT_REQUIRED_KEYS = frozenset(
    {
        "label",
        "definition",
        "feature_kind",
        "domains",
        "objects",
        "search_terms",
        "caveats",
        "evidence",
    }
)
_MISSING_STATE_KEYS = frozenset(
    {"id", "representation", "meaning", "claim_refs", "caveats"}
)
_SEMANTIC_RELATIONSHIP_KEYS = frozenset(
    {
        "label",
        "kind",
        "source_object",
        "target_object",
        "cardinality",
        "optionality",
        "attribution",
        "attribution_limitations",
        "temporal_qualification",
        "temporal_semantics",
        "domains",
        "search_terms",
        "claim_refs",
        "caveats",
    }
)
_CARDINALITY_KEYS = frozenset({"targets_per_source", "sources_per_target"})
_OPTIONALITY_KEYS = frozenset({"source", "target"})
_TEMPORAL_KEYS = frozenset(
    {
        "label",
        "kind",
        "meaning",
        "objects",
        "feature_refs",
        "relative_to",
        "domains",
        "search_terms",
        "claim_refs",
        "caveats",
    }
)
_AGGREGATION_KEYS = frozenset(
    {
        "label",
        "status",
        "source_object",
        "target_object",
        "source_concept",
        "result_concept",
        "semantic_relationships",
        "method",
        "ordering",
        "domains",
        "search_terms",
        "claim_refs",
        "caveats",
    }
)
_GUARDRAIL_KEYS = frozenset(
    {
        "title",
        "statement",
        "rationale",
        "category",
        "priority",
        "scope",
        "profiles",
        "objects",
        "concepts",
        "semantic_relationships",
        "temporal_semantics",
        "aggregations",
        "coverage",
        "domains",
        "search_terms",
        "claim_refs",
        "caveats",
    }
)
_COVERAGE_KEYS = frozenset(
    {
        "subject_kind",
        "subject",
        "status",
        "scope",
        "profiles",
        "summary",
        "domains",
        "search_terms",
        "claim_refs",
        "caveats",
    }
)
_VOCABULARY_KEYS = frozenset(
    {"label", "completeness", "parsing", "evidence", "caveats", "codes"}
)
_VOCABULARY_REQUIRED_KEYS = _VOCABULARY_KEYS - {"caveats"}
_CONTEXT_SOURCE_KEYS = frozenset(
    {
        "title",
        "kind",
        "scope",
        "locator_kind",
        "locator",
        "version_scope",
        "profiles",
        "notes",
    }
)
_CLINICAL_CONTEXT_KEYS = frozenset(
    {
        "title",
        "kind",
        "scope",
        "profiles",
        "summary",
        "domains",
        "search_terms",
        "related_concepts",
        "related_tables",
        "related_relationships",
        "claims",
        "workflow_steps",
        "caveats",
    }
)
_CONTEXT_TABLE_REFERENCE_KEYS = frozenset({"profile", "table"})
_CONTEXT_CLAIM_KEYS = frozenset(
    {"id", "statement", "status", "sources", "caveats"}
)
_WORKFLOW_STEP_KEYS = frozenset({"id", "label", "claims"})
_PROFILE_BINDING_KEYS = frozenset(
    {
        "feature_bindings",
        "object_bindings",
        "tables",
        "relationship_bindings",
        "relationship_binding_paths",
    }
)
_BINDING_KEYS = frozenset(
    {
        "id",
        "table",
        "column",
        "concept",
        "grain",
        "role",
        "physical_type",
        "nullable",
        "parameters",
        "notes",
        "occurrence_interpretations",
        "vocabulary",
        "coexists_with",
    }
)
_BINDING_REQUIRED_KEYS = _BINDING_KEYS - {
    "id",
    "parameters",
    "notes",
    "occurrence_interpretations",
    "vocabulary",
    "coexists_with",
}
_OCCURRENCE_INTERPRETATION_KEYS = frozenset(
    {"representation", "meaning", "status", "claim_refs", "caveats"}
)
_OBJECT_BINDING_KEYS = frozenset(
    {
        "id",
        "object",
        "table",
        "columns",
        "representation",
        "claim_refs",
        "caveats",
        "instance_identity",
    }
)
_OBJECT_BINDING_REQUIRED_KEYS = _OBJECT_BINDING_KEYS - {"id", "instance_identity"}
_INSTANCE_IDENTITY_KEYS = frozenset(
    {
        "columns",
        "scope",
        "reserved_exceptions",
        "rows_per_instance",
        "longitudinal_identity",
    }
)
_RESERVED_IDENTITY_EXCEPTION_KEYS = frozenset(
    {"column", "representation", "meaning", "claim_refs", "caveats"}
)
_ROWS_PER_INSTANCE_VALUES = frozenset(
    {"exactly_one", "one_or_more", "unknown"}
)
_TABLE_KEYS = frozenset({"id", "table", "grain", "keys", "caveats"})
_TABLE_REQUIRED_KEYS = _TABLE_KEYS - {"id"}
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
_RELATIONSHIP_BINDING_KEYS = frozenset(
    {
        "id",
        "kind",
        "semantic_relationships",
        "source",
        "target",
        "cardinality",
        "evidence",
        "claim_refs",
        "caveats",
        "join_hazards",
    }
)
_SOURCE_ENDPOINT_KEYS = frozenset({"table", "columns", "completeness"})
_TARGET_ENDPOINT_KEYS = frozenset({"table", "columns"})
_RELATIONSHIP_BINDING_PATH_KEYS = frozenset(
    {
        "id",
        "semantic_relationship",
        "relationship_bindings",
        "description",
        "claim_refs",
        "caveats",
    }
)


class CatalogError(Exception):
    """Base class for catalog failures safe to present to callers."""

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        document: str | Path | None = None,
        json_pointer: str | None = None,
        contribution_key: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.document = str(document) if document is not None else None
        self.json_pointer = json_pointer
        self.contribution_key = contribution_key


class CatalogLoadError(CatalogError):
    """The catalog could not be read or decoded."""


class CatalogValidationError(CatalogError):
    """The decoded catalog violates schema-v6 semantics."""


class CatalogNotFoundError(CatalogError):
    """An exact entity, binding, vocabulary, or code lookup failed."""


class CatalogAmbiguousError(CatalogError):
    """An unqualified physical identifier resolves to different features."""


@dataclass(frozen=True, slots=True)
class ContributionOrigin:
    document_kind: str
    module_id: str
    module_version: str | None = None
    lifecycle_status: str | None = None
    target_profile: str | None = None
    contribution_class: str = "portable"

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "document_kind": self.document_kind,
                "module_id": self.module_id,
                "module_version": self.module_version,
                "lifecycle_status": self.lifecycle_status,
                "target_profile": self.target_profile,
                "contribution_class": self.contribution_class,
            }.items()
            if value is not None
        }


@dataclass(frozen=True, slots=True)
class Qualification:
    id: str
    subject_kind: str
    subject_id: str
    applicability: str
    summary: str
    claim_refs: tuple[str, ...]
    caveats: tuple[str, ...]
    origin: ContributionOrigin

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": {"kind": self.subject_kind, "id": self.subject_id},
            "applicability": self.applicability,
            "summary": self.summary,
            "claim_refs": list(self.claim_refs),
            "caveats": list(self.caveats),
            "origin": self.origin.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class Revision:
    id: str
    kind: str
    original_id: str
    replacement_id: str
    semantic_difference: str | None
    reason: str
    claim_refs: tuple[str, ...]
    limitations: tuple[str, ...]
    original_remains_alternative: bool
    origin: ContributionOrigin

    def to_dict(self) -> dict[str, Any]:
        result = {
            "id": self.id,
            "kind": self.kind,
            "original_id": self.original_id,
            "replacement_id": self.replacement_id,
            "reason": self.reason,
            "claim_refs": list(self.claim_refs),
            "limitations": list(self.limitations),
            "original_remains_alternative": self.original_remains_alternative,
            "origin": self.origin.to_dict(),
        }
        if self.semantic_difference is not None:
            result["semantic_difference"] = self.semantic_difference
        return result


@dataclass(frozen=True, slots=True)
class ClinicalObject:
    id: str
    label: str
    definition: str
    grain: str
    domains: tuple[str, ...]
    search_terms: tuple[str, ...]
    claim_refs: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "definition": self.definition,
            "grain": self.grain,
            "domains": list(self.domains),
            "search_terms": list(self.search_terms),
            "claim_refs": list(self.claim_refs),
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class MissingState:
    id: str
    representation: str
    meaning: str
    claim_refs: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "representation": self.representation,
            "meaning": self.meaning,
            "claim_refs": list(self.claim_refs),
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class Concept:
    id: str
    label: str
    definition: str
    feature_kind: str
    domains: tuple[str, ...]
    objects: tuple[str, ...]
    search_terms: tuple[str, ...]
    caveats: tuple[str, ...]
    evidence: tuple[str, ...]
    claim_refs: tuple[str, ...] = ()
    missing_states: tuple[MissingState, ...] = ()
    temporal_semantics: tuple[str, ...] = ()
    aggregations: tuple[str, ...] = ()
    vocabulary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "definition": self.definition,
            "feature_kind": self.feature_kind,
            "domains": list(self.domains),
            "objects": list(self.objects),
            "search_terms": list(self.search_terms),
            "caveats": list(self.caveats),
            "evidence": list(self.evidence),
            "claim_refs": list(self.claim_refs),
            "missing_states": [state.to_dict() for state in self.missing_states],
            "temporal_semantics": list(self.temporal_semantics),
            "aggregations": list(self.aggregations),
        }
        if self.vocabulary is not None:
            result["vocabulary"] = self.vocabulary
        return result


@dataclass(frozen=True, slots=True)
class SemanticRelationship:
    id: str
    label: str
    kind: str
    source_object: str
    target_object: str
    targets_per_source: str
    sources_per_target: str
    source_optionality: str
    target_optionality: str
    attribution: str
    attribution_limitations: tuple[str, ...]
    temporal_qualification: str
    temporal_semantics: tuple[str, ...]
    domains: tuple[str, ...]
    search_terms: tuple[str, ...]
    claim_refs: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "source_object": self.source_object,
            "target_object": self.target_object,
            "cardinality": {
                "targets_per_source": self.targets_per_source,
                "sources_per_target": self.sources_per_target,
            },
            "optionality": {
                "source": self.source_optionality,
                "target": self.target_optionality,
            },
            "attribution": self.attribution,
            "attribution_limitations": list(self.attribution_limitations),
            "temporal_qualification": self.temporal_qualification,
            "temporal_semantics": list(self.temporal_semantics),
            "domains": list(self.domains),
            "search_terms": list(self.search_terms),
            "claim_refs": list(self.claim_refs),
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class TemporalSemantic:
    id: str
    label: str
    kind: str
    meaning: str
    objects: tuple[str, ...]
    feature_refs: tuple[str, ...]
    relative_to: tuple[str, ...]
    domains: tuple[str, ...]
    search_terms: tuple[str, ...]
    claim_refs: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "meaning": self.meaning,
            "objects": list(self.objects),
            "feature_refs": list(self.feature_refs),
            "relative_to": list(self.relative_to),
            "domains": list(self.domains),
            "search_terms": list(self.search_terms),
            "claim_refs": list(self.claim_refs),
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class Aggregation:
    id: str
    label: str
    status: str
    source_object: str
    target_object: str
    source_concept: str
    result_concept: str | None
    semantic_relationships: tuple[str, ...]
    method: str
    ordering: str
    domains: tuple[str, ...]
    search_terms: tuple[str, ...]
    claim_refs: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "source_object": self.source_object,
            "target_object": self.target_object,
            "source_concept": self.source_concept,
            "result_concept": self.result_concept,
            "semantic_relationships": list(self.semantic_relationships),
            "method": self.method,
            "ordering": self.ordering,
            "domains": list(self.domains),
            "search_terms": list(self.search_terms),
            "claim_refs": list(self.claim_refs),
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class Guardrail:
    id: str
    title: str
    statement: str
    rationale: str
    category: str
    priority: str
    scope: str
    profiles: tuple[str, ...]
    objects: tuple[str, ...]
    concepts: tuple[str, ...]
    semantic_relationships: tuple[str, ...]
    temporal_semantics: tuple[str, ...]
    aggregations: tuple[str, ...]
    coverage: tuple[str, ...]
    domains: tuple[str, ...]
    search_terms: tuple[str, ...]
    claim_refs: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "statement": self.statement,
            "rationale": self.rationale,
            "category": self.category,
            "priority": self.priority,
            "scope": self.scope,
            "profiles": list(self.profiles),
            "objects": list(self.objects),
            "concepts": list(self.concepts),
            "semantic_relationships": list(self.semantic_relationships),
            "temporal_semantics": list(self.temporal_semantics),
            "aggregations": list(self.aggregations),
            "coverage": list(self.coverage),
            "domains": list(self.domains),
            "search_terms": list(self.search_terms),
            "claim_refs": list(self.claim_refs),
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class Coverage:
    id: str
    subject_kind: str
    subject: str
    status: str
    scope: str
    profiles: tuple[str, ...]
    summary: str
    domains: tuple[str, ...]
    search_terms: tuple[str, ...]
    claim_refs: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject_kind": self.subject_kind,
            "subject": self.subject,
            "status": self.status,
            "scope": self.scope,
            "profiles": list(self.profiles),
            "summary": self.summary,
            "domains": list(self.domains),
            "search_terms": list(self.search_terms),
            "claim_refs": list(self.claim_refs),
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class Vocabulary:
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
class ContextSource:
    id: str
    title: str
    kind: str
    scope: str
    locator_kind: str
    locator: str
    version_scope: str
    profiles: tuple[str, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "scope": self.scope,
            "locator_kind": self.locator_kind,
            "locator": self.locator,
            "version_scope": self.version_scope,
            "profiles": list(self.profiles),
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class ContextTableReference:
    profile: str
    table: str

    @property
    def identifier(self) -> str:
        return f"{self.profile}:{self.table}"

    def to_dict(self) -> dict[str, str]:
        return {"profile": self.profile, "table": self.table}


@dataclass(frozen=True, slots=True)
class ContextClaim:
    id: str
    statement: str
    status: str
    sources: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "status": self.status,
            "sources": list(self.sources),
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    id: str
    label: str
    claims: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "claims": list(self.claims)}


@dataclass(frozen=True, slots=True)
class ClinicalContext:
    id: str
    title: str
    kind: str
    scope: str
    profiles: tuple[str, ...]
    summary: str
    domains: tuple[str, ...]
    search_terms: tuple[str, ...]
    related_concepts: tuple[str, ...]
    related_tables: tuple[ContextTableReference, ...]
    related_relationships: tuple[str, ...]
    claims: tuple[ContextClaim, ...]
    workflow_steps: tuple[WorkflowStep, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "scope": self.scope,
            "profiles": list(self.profiles),
            "summary": self.summary,
            "domains": list(self.domains),
            "search_terms": list(self.search_terms),
            "related_concepts": list(self.related_concepts),
            "related_tables": [item.to_dict() for item in self.related_tables],
            "related_relationships": list(self.related_relationships),
            "claims": [item.to_dict() for item in self.claims],
            "workflow_steps": [item.to_dict() for item in self.workflow_steps],
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class OccurrenceInterpretation:
    representation: str
    meaning: str
    status: str
    claim_refs: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "representation": self.representation,
            "meaning": self.meaning,
            "status": self.status,
            "claim_refs": list(self.claim_refs),
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class Binding:
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
    occurrence_interpretations: tuple[OccurrenceInterpretation, ...] = ()
    id: str | None = None
    vocabulary: str | None = None
    coexists_with: tuple[str, ...] = ()

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
        if self.id is not None:
            result["id"] = self.id
        if self.vocabulary is not None:
            result["vocabulary"] = self.vocabulary
        if self.coexists_with:
            result["coexists_with"] = list(self.coexists_with)
        if self.parameters:
            result["parameters"] = dict(self.parameters)
        if self.notes:
            result["notes"] = list(self.notes)
        if self.occurrence_interpretations:
            result["occurrence_interpretations"] = [
                item.to_dict() for item in self.occurrence_interpretations
            ]
        return result


@dataclass(frozen=True, slots=True)
class ReservedIdentityException:
    column: str
    representation: str
    meaning: str
    claim_refs: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "representation": self.representation,
            "meaning": self.meaning,
            "claim_refs": list(self.claim_refs),
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class InstanceIdentity:
    columns: tuple[str, ...]
    scope: str
    reserved_exceptions: tuple[ReservedIdentityException, ...]
    rows_per_instance: str
    longitudinal_identity: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": list(self.columns),
            "scope": self.scope,
            "reserved_exceptions": [
                item.to_dict() for item in self.reserved_exceptions
            ],
            "rows_per_instance": self.rows_per_instance,
            "longitudinal_identity": self.longitudinal_identity,
        }


@dataclass(frozen=True, slots=True)
class ObjectBinding:
    profile: str
    object: str
    table: str
    columns: tuple[str, ...]
    representation: str
    claim_refs: tuple[str, ...]
    caveats: tuple[str, ...]
    instance_identity: InstanceIdentity | None = None
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "profile": self.profile,
            "object": self.object,
            "table": self.table,
            "columns": list(self.columns),
            "representation": self.representation,
            "claim_refs": list(self.claim_refs),
            "caveats": list(self.caveats),
        }
        if self.instance_identity is not None:
            result["instance_identity"] = self.instance_identity.to_dict()
        if self.id is not None:
            result["id"] = self.id
        return result


@dataclass(frozen=True, slots=True)
class KeyCandidate:
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
    profile: str
    table: str
    grain: str
    keys: tuple[KeyCandidate, ...]
    caveats: tuple[str, ...]
    id: str | None = None

    @property
    def identifier(self) -> str:
        return f"{self.profile}:{self.table}"

    def to_dict(self) -> dict[str, Any]:
        result = {
            "identifier": self.identifier,
            "profile": self.profile,
            "table": self.table,
            "grain": self.grain,
            "keys": [key.to_dict() for key in self.keys],
            "caveats": list(self.caveats),
        }
        if self.id is not None:
            result["id"] = self.id
        return result


@dataclass(frozen=True, slots=True)
class RelationshipEndpoint:
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
class RelationshipBinding:
    id: str
    profile: str
    kind: str
    semantic_relationships: tuple[str, ...]
    source: RelationshipEndpoint
    target: RelationshipEndpoint
    targets_per_source: str
    sources_per_target: str
    evidence: tuple[str, ...]
    claim_refs: tuple[str, ...]
    caveats: tuple[str, ...]
    join_hazards: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "profile": self.profile,
            "kind": self.kind,
            "semantic_relationships": list(self.semantic_relationships),
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "cardinality": {
                "targets_per_source": self.targets_per_source,
                "sources_per_target": self.sources_per_target,
            },
            "evidence": list(self.evidence),
            "claim_refs": list(self.claim_refs),
            "caveats": list(self.caveats),
            "join_hazards": list(self.join_hazards),
        }


@dataclass(frozen=True, slots=True)
class RelationshipBindingPath:
    id: str
    profile: str
    semantic_relationship: str
    relationship_bindings: tuple[str, ...]
    description: str
    claim_refs: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "profile": self.profile,
            "semantic_relationship": self.semantic_relationship,
            "relationship_bindings": list(self.relationship_bindings),
            "description": self.description,
            "claim_refs": list(self.claim_refs),
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True, slots=True)
class ProfileBinding:
    profile: str
    feature_bindings: tuple[Binding, ...]
    object_bindings: tuple[ObjectBinding, ...]
    tables: tuple[TableSpec, ...]
    relationship_bindings: tuple[RelationshipBinding, ...]
    relationship_binding_paths: tuple[RelationshipBindingPath, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "feature_bindings": [item.to_dict() for item in self.feature_bindings],
            "object_bindings": [item.to_dict() for item in self.object_bindings],
            "tables": [item.to_dict() for item in self.tables],
            "relationship_bindings": [
                item.to_dict() for item in self.relationship_bindings
            ],
            "relationship_binding_paths": [
                item.to_dict() for item in self.relationship_binding_paths
            ],
        }


@dataclass(frozen=True, slots=True)
class _DiscoveryDocument:
    kind: str
    identifier: str
    label: str
    entity: Any
    fields: tuple[tuple[str, str], ...]
    profile_fields: tuple[tuple[str, str, str], ...]
    domains: tuple[str, ...]
    profiles: tuple[str, ...]
    all_tokens: frozenset[str]


class Catalog:
    """Validated immutable schema-v6 catalog with deterministic indexes."""

    __slots__ = (
        "_schema_version",
        "_clinical_objects",
        "_concepts",
        "_semantic_relationships",
        "_temporal_semantics",
        "_aggregations",
        "_guardrails",
        "_coverage",
        "_vocabularies",
        "_sources",
        "_contexts",
        "_profile_bindings",
        "_bindings",
        "_object_bindings",
        "_tables",
        "_relationship_bindings",
        "_relationship_binding_paths",
        "_tables_by_qualified",
        "_relationship_bindings_by_id",
        "_bindings_by_concept",
        "_bindings_by_id",
        "_bindings_by_physical",
        "_bindings_by_qualified",
        "_claims_by_ref",
        "_discovery_documents",
        "_origins",
        "_qualifications",
        "_revisions",
        "_configuration",
        "_feature_lineage",
        "_sealed",
    )

    def __init__(
        self,
        *,
        clinical_objects: Mapping[str, ClinicalObject],
        concepts: Mapping[str, Concept],
        semantic_relationships: Mapping[str, SemanticRelationship],
        temporal_semantics: Mapping[str, TemporalSemantic],
        aggregations: Mapping[str, Aggregation],
        guardrails: Mapping[str, Guardrail],
        coverage: Mapping[str, Coverage],
        vocabularies: Mapping[str, Vocabulary],
        sources: Mapping[str, ContextSource],
        contexts: Mapping[str, ClinicalContext],
        profile_bindings: Mapping[str, ProfileBinding],
        schema_version: int = SCHEMA_VERSION,
        origins: Mapping[str, ContributionOrigin] | None = None,
        qualifications: Mapping[str, Qualification] | None = None,
        revisions: Mapping[str, Revision] | None = None,
        configuration: Mapping[str, Any] | None = None,
        feature_lineage: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        object.__setattr__(self, "_schema_version", schema_version)
        revision_map = revisions or {}
        for slot, values in (
            ("_clinical_objects", clinical_objects),
            ("_concepts", concepts),
            ("_semantic_relationships", semantic_relationships),
            ("_temporal_semantics", temporal_semantics),
            ("_aggregations", aggregations),
            ("_guardrails", guardrails),
            ("_coverage", coverage),
            ("_vocabularies", vocabularies),
            ("_sources", sources),
            ("_contexts", contexts),
            ("_profile_bindings", profile_bindings),
        ):
            object.__setattr__(
                self, slot, MappingProxyType(dict(sorted(values.items())))
            )

        profiles = tuple(sorted(profile_bindings))
        bindings = tuple(
            sorted(
                (
                    binding
                    for profile in profiles
                    for binding in profile_bindings[profile].feature_bindings
                ),
                key=lambda item: (
                    item.profile,
                    item.table,
                    item.column,
                    item.concept,
                ),
            )
        )
        object_bindings = tuple(
            sorted(
                (
                    binding
                    for profile in profiles
                    for binding in profile_bindings[profile].object_bindings
                ),
                key=lambda item: (
                    item.profile,
                    item.table,
                    item.object,
                    item.columns,
                ),
            )
        )
        tables = tuple(
            sorted(
                (
                    table
                    for profile in profiles
                    for table in profile_bindings[profile].tables
                ),
                key=lambda item: (item.profile, item.table),
            )
        )
        relationships = tuple(
            sorted(
                (
                    relationship
                    for profile in profiles
                    for relationship in profile_bindings[
                        profile
                    ].relationship_bindings
                ),
                key=lambda item: item.id,
            )
        )
        relationship_paths = tuple(
            sorted(
                (
                    path
                    for profile in profiles
                    for path in profile_bindings[
                        profile
                    ].relationship_binding_paths
                ),
                key=lambda item: item.id,
            )
        )
        object.__setattr__(self, "_bindings", bindings)
        object.__setattr__(self, "_object_bindings", object_bindings)
        object.__setattr__(self, "_tables", tables)
        object.__setattr__(self, "_relationship_bindings", relationships)
        object.__setattr__(
            self, "_relationship_binding_paths", relationship_paths
        )
        object.__setattr__(
            self,
            "_tables_by_qualified",
            MappingProxyType({table.identifier: table for table in tables}),
        )
        object.__setattr__(
            self,
            "_relationship_bindings_by_id",
            MappingProxyType({item.id: item for item in relationships}),
        )

        grouped_concepts: defaultdict[str, list[Binding]] = defaultdict(list)
        grouped_physical: defaultdict[str, list[Binding]] = defaultdict(list)
        bindings_by_id: dict[str, Binding] = {}
        qualified: dict[str, Binding] = {}
        for binding in bindings:
            grouped_concepts[binding.concept].append(binding)
            grouped_physical[binding.identifier].append(binding)
            if binding.id is not None:
                bindings_by_id[binding.id] = binding
            previous = qualified.get(binding.qualified_identifier)
            preferred_ids = {
                item.replacement_id
                for item in revision_map.values()
                if item.kind == "replaces_binding"
            }
            if previous is None or binding.id in preferred_ids:
                qualified[binding.qualified_identifier] = binding
        object.__setattr__(
            self,
            "_bindings_by_concept",
            MappingProxyType(
                {
                    key: tuple(
                        sorted(value, key=lambda item: item.qualified_identifier)
                    )
                    for key, value in sorted(grouped_concepts.items())
                }
            ),
        )
        object.__setattr__(
            self, "_bindings_by_id", MappingProxyType(bindings_by_id)
        )
        object.__setattr__(
            self,
            "_bindings_by_physical",
            MappingProxyType(
                {
                    key: tuple(
                        sorted(value, key=lambda item: item.qualified_identifier)
                    )
                    for key, value in sorted(grouped_physical.items())
                }
            ),
        )
        object.__setattr__(
            self, "_bindings_by_qualified", MappingProxyType(qualified)
        )
        claims_by_ref = {
            f"{context.id}#{claim.id}": claim
            for context in contexts.values()
            for claim in context.claims
        }
        object.__setattr__(
            self, "_claims_by_ref", MappingProxyType(claims_by_ref)
        )
        object.__setattr__(self, "_origins", MappingProxyType(dict(origins or {})))
        object.__setattr__(self, "_qualifications", MappingProxyType(dict(qualifications or {})))
        object.__setattr__(self, "_revisions", MappingProxyType(dict(revision_map)))
        object.__setattr__(self, "_configuration", MappingProxyType(dict(configuration or {})))
        object.__setattr__(self, "_feature_lineage", MappingProxyType({key: MappingProxyType(dict(value)) for key, value in (feature_lineage or {}).items()}))
        object.__setattr__(
            self, "_discovery_documents", self._build_discovery_documents()
        )
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
        return tuple(self.profile_bindings)

    @property
    def origins(self) -> Mapping[str, ContributionOrigin]:
        return self._origins

    @property
    def qualifications(self) -> Mapping[str, Qualification]:
        return self._qualifications

    @property
    def revisions(self) -> Mapping[str, Revision]:
        return self._revisions

    @property
    def configuration(self) -> Mapping[str, Any]:
        return self._configuration

    @property
    def fingerprint(self) -> str | None:
        value = self._configuration.get("configuration_fingerprint")
        return str(value) if value is not None else None

    @property
    def feature_lineage(self) -> Mapping[str, Mapping[str, Any]]:
        return self._feature_lineage

    @property
    def binding_grains(self) -> tuple[str, ...]:
        return BINDING_GRAINS

    @property
    def feature_kinds(self) -> tuple[str, ...]:
        return FEATURE_KINDS

    @property
    def domains(self) -> tuple[str, ...]:
        return DOMAINS

    @property
    def context_kinds(self) -> tuple[str, ...]:
        return CONTEXT_KINDS

    @property
    def context_scopes(self) -> tuple[str, ...]:
        return CONTEXT_SCOPES

    @property
    def source_kinds(self) -> tuple[str, ...]:
        return SOURCE_KINDS

    @property
    def source_locator_kinds(self) -> tuple[str, ...]:
        return SOURCE_LOCATOR_KINDS

    @property
    def claim_statuses(self) -> tuple[str, ...]:
        return CLAIM_STATUSES

    @property
    def semantic_relationship_kinds(self) -> tuple[str, ...]:
        return SEMANTIC_RELATIONSHIP_KINDS

    @property
    def temporal_kinds(self) -> tuple[str, ...]:
        return TEMPORAL_KINDS

    @property
    def aggregation_statuses(self) -> tuple[str, ...]:
        return AGGREGATION_STATUSES

    @property
    def coverage_statuses(self) -> tuple[str, ...]:
        return COVERAGE_STATUSES

    @property
    def relationship_binding_kinds(self) -> tuple[str, ...]:
        return tuple(sorted(RELATIONSHIP_BINDING_KINDS))

    @property
    def guardrail_categories(self) -> tuple[str, ...]:
        return GUARDRAIL_CATEGORIES

    @property
    def guardrail_priorities(self) -> tuple[str, ...]:
        return GUARDRAIL_PRIORITIES

    @property
    def clinical_objects(self) -> Mapping[str, ClinicalObject]:
        return self._clinical_objects

    @property
    def concepts(self) -> Mapping[str, Concept]:
        return self._concepts

    @property
    def semantic_relationships(self) -> Mapping[str, SemanticRelationship]:
        return self._semantic_relationships

    @property
    def temporal_semantics(self) -> Mapping[str, TemporalSemantic]:
        return self._temporal_semantics

    @property
    def aggregations(self) -> Mapping[str, Aggregation]:
        return self._aggregations

    @property
    def guardrails(self) -> Mapping[str, Guardrail]:
        return self._guardrails

    @property
    def coverage(self) -> Mapping[str, Coverage]:
        return self._coverage

    @property
    def vocabularies(self) -> Mapping[str, Vocabulary]:
        return self._vocabularies

    @property
    def sources(self) -> Mapping[str, ContextSource]:
        return self._sources

    @property
    def contexts(self) -> Mapping[str, ClinicalContext]:
        return self._contexts

    @property
    def profile_bindings(self) -> Mapping[str, ProfileBinding]:
        return self._profile_bindings

    @property
    def feature_bindings(self) -> tuple[Binding, ...]:
        """Flattened secondary view of all profile feature bindings."""

        return self._bindings

    @property
    def object_bindings(self) -> tuple[ObjectBinding, ...]:
        return self._object_bindings

    @property
    def profile_tables(self) -> tuple[TableSpec, ...]:
        return self._tables

    @property
    def relationship_bindings(self) -> tuple[RelationshipBinding, ...]:
        return self._relationship_bindings

    @property
    def relationship_binding_paths(
        self,
    ) -> tuple[RelationshipBindingPath, ...]:
        return self._relationship_binding_paths

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], *, _allow_empty_profiles: bool = False) -> Catalog:
        data = _expect_mapping(value, "$")
        _require_keys(data, frozenset({"$schema", "schema_version"}), "$")
        version = data["schema_version"]
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version != SCHEMA_VERSION
        ):
            raise CatalogValidationError(
                f"unsupported catalog schema_version {version!r}; "
                f"expected integer {SCHEMA_VERSION}"
            )
        if data["$schema"] != SCHEMA_REFERENCE:
            raise CatalogValidationError(
                f"$.$schema must equal {SCHEMA_REFERENCE!r}"
            )
        _require_exact_keys(data, _TOP_LEVEL_KEYS, _TOP_LEVEL_KEYS, "$")
        _require_constant_array(
            data["binding_grains"], BINDING_GRAINS, "$.binding_grains"
        )
        _require_constant_array(
            data["feature_kinds"], FEATURE_KINDS, "$.feature_kinds"
        )
        _require_constant_array(data["domains"], DOMAINS, "$.domains")
        _require_constant_array(
            data["context_kinds"], CONTEXT_KINDS, "$.context_kinds"
        )
        _require_constant_array(
            data["context_scopes"], CONTEXT_SCOPES, "$.context_scopes"
        )
        _require_constant_array(
            data["source_kinds"], SOURCE_KINDS, "$.source_kinds"
        )
        _require_constant_array(
            data["source_locator_kinds"],
            SOURCE_LOCATOR_KINDS,
            "$.source_locator_kinds",
        )
        _require_constant_array(
            data["claim_statuses"], CLAIM_STATUSES, "$.claim_statuses"
        )
        _require_constant_array(
            data["semantic_relationship_kinds"],
            SEMANTIC_RELATIONSHIP_KINDS,
            "$.semantic_relationship_kinds",
        )
        _require_constant_array(
            data["temporal_kinds"], TEMPORAL_KINDS, "$.temporal_kinds"
        )
        _require_constant_array(
            data["aggregation_statuses"],
            AGGREGATION_STATUSES,
            "$.aggregation_statuses",
        )
        _require_constant_array(
            data["coverage_statuses"],
            COVERAGE_STATUSES,
            "$.coverage_statuses",
        )

        raw_profiles = _expect_mapping(
            data["profile_bindings"], "$.profile_bindings"
        )
        if not raw_profiles and not _allow_empty_profiles:
            raise CatalogValidationError("$.profile_bindings must not be empty")
        profile_ids = frozenset(raw_profiles)
        for profile in profile_ids:
            _require_identifier(profile, f"$.profile_bindings key {profile!r}")
        declared_profiles = _identifier_array(
            data["profiles"], "$.profiles", minimum=0 if _allow_empty_profiles else 1
        )
        if not _allow_empty_profiles:
            for collection in ("guardrails", "coverage"):
                for identifier, raw in _expect_mapping(data[collection], f"$.{collection}").items():
                    if not _expect_list(_expect_mapping(raw, f"$.{collection}.{identifier}")["claim_refs"], f"$.{collection}.{identifier}.claim_refs"):
                        raise CatalogValidationError(f"$.{collection}.{identifier}.claim_refs must contain at least 1 item(s)")
        if set(declared_profiles) != set(profile_ids):
            missing_bindings = sorted(set(declared_profiles) - profile_ids)
            undeclared_bindings = sorted(profile_ids - set(declared_profiles))
            raise CatalogValidationError(
                "$.profiles and $.profile_bindings keys must agree; "
                f"missing_bindings={missing_bindings}, "
                f"undeclared_bindings={undeclared_bindings}"
            )

        sources = _parse_map(
            data["sources"], "$.sources", _parse_context_source, profile_ids
        )
        contexts = _parse_map(
            data["contexts"], "$.contexts", _parse_clinical_context, profile_ids
        )
        clinical_objects = _parse_map(
            data["clinical_objects"],
            "$.clinical_objects",
            _parse_clinical_object,
        )
        if not clinical_objects:
            raise CatalogValidationError("$.clinical_objects must not be empty")
        concepts = _parse_map(data["concepts"], "$.concepts", _parse_concept)
        if not concepts:
            raise CatalogValidationError("$.concepts must not be empty")
        semantic_relationships = _parse_map(
            data["semantic_relationships"],
            "$.semantic_relationships",
            _parse_semantic_relationship,
        )
        temporal_semantics = _parse_map(
            data["temporal_semantics"],
            "$.temporal_semantics",
            _parse_temporal_semantic,
        )
        aggregations = _parse_map(
            data["aggregations"], "$.aggregations", _parse_aggregation
        )
        guardrails = _parse_map(
            data["guardrails"],
            "$.guardrails",
            _parse_guardrail,
            profile_ids,
        )
        coverage = _parse_map(
            data["coverage"], "$.coverage", _parse_coverage, profile_ids
        )
        vocabularies = _parse_map(
            data["vocabularies"], "$.vocabularies", _parse_vocabulary
        )

        profiles: dict[str, ProfileBinding] = {}
        for profile, raw in raw_profiles.items():
            profiles[profile] = _parse_profile_binding(profile, raw)

        _validate_catalog(
            clinical_objects=clinical_objects,
            concepts=concepts,
            semantic_relationships=semantic_relationships,
            temporal_semantics=temporal_semantics,
            aggregations=aggregations,
            guardrails=guardrails,
            coverage=coverage,
            vocabularies=vocabularies,
            sources=sources,
            contexts=contexts,
            profile_bindings=profiles,
        )
        return cls(
            clinical_objects=clinical_objects,
            concepts=concepts,
            semantic_relationships=semantic_relationships,
            temporal_semantics=temporal_semantics,
            aggregations=aggregations,
            guardrails=guardrails,
            coverage=coverage,
            vocabularies=vocabularies,
            sources=sources,
            contexts=contexts,
            profile_bindings=profiles,
        )

    def summary(self) -> dict[str, Any]:
        result = {
            "schema_version": self.schema_version,
            "profiles": list(self.profiles),
            "binding_grains": list(self.binding_grains),
            "feature_kinds": list(self.feature_kinds),
            "domains": list(self.domains),
            "context_kinds": list(self.context_kinds),
            "context_scopes": list(self.context_scopes),
            "source_kinds": list(self.source_kinds),
            "source_locator_kinds": list(self.source_locator_kinds),
            "claim_statuses": list(self.claim_statuses),
            "semantic_relationship_kinds": list(
                self.semantic_relationship_kinds
            ),
            "temporal_kinds": list(self.temporal_kinds),
            "aggregation_statuses": list(self.aggregation_statuses),
            "coverage_statuses": list(self.coverage_statuses),
            "guardrail_categories": list(self.guardrail_categories),
            "guardrail_priorities": list(self.guardrail_priorities),
            "relationship_binding_kinds": list(
                self.relationship_binding_kinds
            ),
            "discovery_kinds": list(DISCOVERY_KINDS),
            "clinical_objects": len(self.clinical_objects),
            "concepts": len(self.concepts),
            "semantic_relationships": len(self.semantic_relationships),
            "temporal_semantics": len(self.temporal_semantics),
            "aggregations": len(self.aggregations),
            "guardrails": len(self.guardrails),
            "coverage": len(self.coverage),
            "vocabularies": len(self.vocabularies),
            "sources": len(self.sources),
            "contexts": len(self.contexts),
            "profile_bindings": len(self.profile_bindings),
            "feature_bindings": len(self.feature_bindings),
            "object_bindings": len(self.object_bindings),
            "tables": len(self.profile_tables),
            "relationship_bindings": len(self.relationship_bindings),
            "relationship_binding_paths": len(
                self.relationship_binding_paths
            ),
        }
        result.update(self.configuration)
        return result

    def get_clinical_object(self, identifier: str) -> dict[str, Any]:
        normalized = _lookup_identifier(identifier, "identifier")
        entity = self.clinical_objects.get(normalized)
        if entity is None:
            raise CatalogNotFoundError(
                f"clinical object {normalized!r} was not found"
            )
        related = self._related_entities(
            "clinical_object", normalized, entity
        )
        claim_refs = tuple(
            dict.fromkeys(
                (
                    *entity.claim_refs,
                    *(
                        reference
                        for binding in self.object_bindings
                        if binding.object == normalized
                        for reference in (
                            *binding.claim_refs,
                            *(
                                exception_ref
                                for exception in (
                                    binding.instance_identity.reserved_exceptions
                                    if binding.instance_identity is not None
                                    else ()
                                )
                                for exception_ref in exception.claim_refs
                            ),
                        )
                    ),
                )
            )
        )
        claim_refs = (*claim_refs, *self._qualification_claim_refs("clinical_object", normalized))
        return self._decorate_effective({
            "kind": "clinical_object",
            "identifier": normalized,
            "clinical_object": entity.to_dict(),
            "constraints": self._constraint_summary(
                "clinical_object",
                normalized,
                entity,
                related,
                claim_refs,
            ),
            "related": related,
            "provenance": self._provenance(claim_refs),
        }, "clinical_object", normalized, None)

    def get_feature(
        self, identifier: str, include_codes: bool = False, profile: str | None = None
    ) -> dict[str, Any]:
        normalized = _lookup_identifier(identifier, "identifier")
        feature = self.concepts.get(normalized)
        if feature is not None:
            bindings = self._bindings_by_concept.get(feature.id, ())
            selected_profile = self._resolve_profile(profile, bindings)
            if selected_profile is not None:
                bindings = tuple(item for item in bindings if item.profile == selected_profile)
            vocabulary = self._vocabulary_for_feature(feature, bindings, selected_profile)
            claim_refs = (*self._feature_claim_refs(feature, bindings), *self._qualification_claim_refs("concept", feature.id, selected_profile))
            related = self._related_entities(
                "feature", feature.id, feature
            )
            related = self._filter_related_profile(related, selected_profile)
            result = {
                "kind": "feature",
                "identifier": feature.id,
                "feature": feature.to_dict(),
                "bindings": self._effective_binding_results(bindings),
                "vocabulary": (
                    vocabulary.to_dict(include_codes=include_codes)
                    if vocabulary
                    else None
                ),
                "constraints": self._constraint_summary(
                    "feature",
                    feature.id,
                    feature,
                    related,
                    claim_refs,
                    bindings=bindings,
                ),
                "related": related,
                "provenance": self._provenance(claim_refs),
            }
            return self._decorate_effective(result, "concept", feature.id, selected_profile)

        bindings = self._resolve_physical(normalized)
        feature = self.concepts[bindings[0].concept]
        selected_profile = self._resolve_profile(profile, bindings)
        if selected_profile is not None:
            bindings = tuple(item for item in bindings if item.profile == selected_profile)
        vocabulary = self._vocabulary_for_feature(feature, bindings, selected_profile)
        related = self._related_entities("feature", feature.id, feature)
        related = self._filter_related_profile(related, selected_profile)
        claim_refs = (*self._feature_claim_refs(feature, bindings), *self._qualification_claim_refs("concept", feature.id, selected_profile))
        result: dict[str, Any] = {
            "kind": "feature_binding" if len(bindings) == 1 else "feature_binding_set",
            "identifier": normalized,
            "feature": feature.to_dict(),
            "bindings": self._effective_binding_results(bindings),
            "vocabulary": (
                vocabulary.to_dict(include_codes=include_codes)
                if vocabulary
                else None
            ),
            "constraints": self._constraint_summary(
                "feature",
                feature.id,
                feature,
                related,
                claim_refs,
                bindings=bindings,
            ),
            "related": related,
            "provenance": self._provenance(claim_refs),
        }
        if len(bindings) == 1:
            result["binding"] = self._effective_binding_result(bindings[0])
        return self._decorate_effective(result, "concept", feature.id, selected_profile)

    def get_semantic_relationship(self, identifier: str) -> dict[str, Any]:
        return self._exact_semantic_result(
            identifier,
            "semantic_relationship",
            self.semantic_relationships,
        )

    def get_temporal_semantic(self, identifier: str) -> dict[str, Any]:
        return self._exact_semantic_result(
            identifier, "temporal_semantic", self.temporal_semantics
        )

    def get_aggregation(self, identifier: str) -> dict[str, Any]:
        return self._exact_semantic_result(
            identifier, "aggregation", self.aggregations
        )

    def get_guardrail(self, identifier: str) -> dict[str, Any]:
        return self._exact_semantic_result(
            identifier, "guardrail", self.guardrails
        )

    def get_coverage(self, identifier: str) -> dict[str, Any]:
        return self._exact_semantic_result(
            identifier, "coverage", self.coverage
        )

    def get_context(self, identifier: str) -> dict[str, Any]:
        """Get one provenance context and resolve every claim source."""

        normalized = _lookup_identifier(identifier, "identifier")
        context = self.contexts.get(normalized)
        if context is None:
            raise CatalogNotFoundError(
                f"context {normalized!r} was not found"
            )
        claim_refs = tuple(
            f"{context.id}#{claim.id}" for claim in context.claims
        )
        related = self._related_entities(
            "context", normalized, context
        )
        return self._decorate_effective({
            "kind": "context",
            "identifier": normalized,
            "context": context.to_dict(),
            "constraints": self._constraint_summary(
                "context",
                normalized,
                context,
                related,
                claim_refs,
            ),
            "related": related,
            "provenance": self._provenance(claim_refs),
        }, "context", normalized, None)

    def _exact_semantic_result(
        self, identifier: str, kind: str, entities: Mapping[str, Any]
    ) -> dict[str, Any]:
        normalized = _lookup_identifier(identifier, "identifier")
        entity = entities.get(normalized)
        if entity is None:
            raise CatalogNotFoundError(
                f"{kind.replace('_', ' ')} {normalized!r} was not found"
            )
        related = self._related_entities(kind, normalized, entity)
        claim_refs = (*entity.claim_refs, *self._qualification_claim_refs(kind, normalized))
        return self._decorate_effective({
            "kind": kind,
            "identifier": normalized,
            kind: entity.to_dict(),
            "constraints": self._constraint_summary(
                kind,
                normalized,
                entity,
                related,
                claim_refs,
            ),
            "related": related,
            "provenance": self._provenance(claim_refs),
        }, kind, normalized, None)

    def _related_entities(
        self, kind: str, identifier: str, entity: Any
    ) -> dict[str, Any]:
        """Compute semantic navigation instead of duplicating link indexes."""

        if kind == "clinical_object":
            return {
                "features": sorted(
                    item.id
                    for item in self.concepts.values()
                    if identifier in item.objects
                ),
                "semantic_relationships": sorted(
                    item.id
                    for item in self.semantic_relationships.values()
                    if identifier
                    in {item.source_object, item.target_object}
                ),
                "temporal_semantics": sorted(
                    item.id
                    for item in self.temporal_semantics.values()
                    if identifier in item.objects
                ),
                "aggregations": sorted(
                    item.id
                    for item in self.aggregations.values()
                    if identifier
                    in {item.source_object, item.target_object}
                ),
                "guardrails": sorted(
                    item.id
                    for item in self.guardrails.values()
                    if identifier in item.objects
                ),
                "coverage": sorted(
                    item.id
                    for item in self.coverage.values()
                    if item.subject_kind == "clinical_object"
                    and item.subject == identifier
                ),
                "object_bindings": [
                    self._object_binding_result(item)
                    for item in self.object_bindings
                    if item.object == identifier
                ],
            }
        if kind == "feature":
            guardrail_ids = sorted(
                item.id
                for item in self.guardrails.values()
                if identifier in item.concepts
            )
            qualification_claims = {
                reference
                for qualification in self.qualifications.values()
                if (
                    qualification.subject_kind == "concept"
                    and qualification.subject_id == identifier
                )
                or (
                    qualification.subject_kind == "guardrail"
                    and qualification.subject_id in guardrail_ids
                )
                for reference in qualification.claim_refs
            }
            return {
                "clinical_objects": list(entity.objects),
                "temporal_semantics": sorted(
                    {
                        *entity.temporal_semantics,
                        *(
                            item.id
                            for item in self.temporal_semantics.values()
                            if identifier in item.feature_refs
                        ),
                    }
                ),
                "aggregations": sorted(
                    {
                        *entity.aggregations,
                        *(
                            item.id
                            for item in self.aggregations.values()
                            if identifier
                            in {item.source_concept, item.result_concept}
                        ),
                    }
                ),
                "guardrails": guardrail_ids,
                "coverage": sorted(
                    {
                        *(
                            item.id
                            for item in self.coverage.values()
                            if item.subject_kind == "concept"
                            and item.subject == identifier
                        ),
                        *(
                            coverage_id
                            for guardrail_id in guardrail_ids
                            for coverage_id in self.guardrails[
                                guardrail_id
                            ].coverage
                        ),
                        *(
                            item.id
                            for item in self.coverage.values()
                            if qualification_claims
                            & set(item.claim_refs)
                        ),
                    }
                ),
                "contexts": sorted(
                    item.id
                    for item in self.contexts.values()
                    if identifier in item.related_concepts
                ),
            }
        if kind == "semantic_relationship":
            return {
                "clinical_objects": [
                    entity.source_object,
                    entity.target_object,
                ],
                "temporal_semantics": list(entity.temporal_semantics),
                "guardrails": sorted(
                    item.id
                    for item in self.guardrails.values()
                    if identifier in item.semantic_relationships
                ),
                "coverage": sorted(
                    item.id
                    for item in self.coverage.values()
                    if item.subject_kind == kind
                    and item.subject == identifier
                ),
                "relationship_bindings": [
                    item.to_dict()
                    for item in self.relationship_bindings
                    if identifier in item.semantic_relationships
                ],
                "relationship_binding_paths": [
                    item.to_dict()
                    for item in self.relationship_binding_paths
                    if item.semantic_relationship == identifier
                ],
            }
        if kind == "temporal_semantic":
            return {
                "clinical_objects": list(entity.objects),
                "features": list(entity.feature_refs),
                "semantic_relationships": sorted(
                    item.id
                    for item in self.semantic_relationships.values()
                    if identifier in item.temporal_semantics
                ),
                "relative_to": list(entity.relative_to),
                "referenced_by": sorted(
                    item.id
                    for item in self.temporal_semantics.values()
                    if identifier in item.relative_to
                ),
                "guardrails": sorted(
                    item.id
                    for item in self.guardrails.values()
                    if identifier in item.temporal_semantics
                ),
                "coverage": sorted(
                    item.id
                    for item in self.coverage.values()
                    if item.subject_kind == kind
                    and item.subject == identifier
                ),
            }
        if kind == "aggregation":
            features = [entity.source_concept]
            if entity.result_concept is not None:
                features.append(entity.result_concept)
            return {
                "clinical_objects": [
                    entity.source_object,
                    entity.target_object,
                ],
                "features": list(dict.fromkeys(features)),
                "semantic_relationships": list(
                    entity.semantic_relationships
                ),
                "guardrails": sorted(
                    item.id
                    for item in self.guardrails.values()
                    if identifier in item.aggregations
                ),
                "coverage": sorted(
                    item.id
                    for item in self.coverage.values()
                    if item.subject_kind == kind
                    and item.subject == identifier
                ),
            }
        if kind == "guardrail":
            return {
                "clinical_objects": list(entity.objects),
                "features": list(entity.concepts),
                "semantic_relationships": list(
                    entity.semantic_relationships
                ),
                "temporal_semantics": list(entity.temporal_semantics),
                "aggregations": list(entity.aggregations),
                "coverage": list(entity.coverage),
            }
        if kind == "coverage":
            return {
                "subject": {
                    "kind": entity.subject_kind,
                    "identifier": entity.subject,
                },
                "guardrails": sorted(
                    item.id
                    for item in self.guardrails.values()
                    if identifier in item.coverage
                ),
            }
        if kind == "context":
            return {
                "features": list(entity.related_concepts),
                "profile_tables": [
                    item.identifier for item in entity.related_tables
                ],
                "relationship_bindings": list(
                    entity.related_relationships
                ),
            }
        return {}

    def _filter_related_profile(
        self, related: Mapping[str, Any], profile: str | None
    ) -> dict[str, Any]:
        result = dict(related)
        if profile is None:
            return result
        if "coverage" in result:
            result["coverage"] = [
                identifier
                for identifier in result["coverage"]
                if (
                    self.coverage[identifier].scope != "profile_specific"
                    or profile in self.coverage[identifier].profiles
                )
            ]
        if "contexts" in result:
            result["contexts"] = [
                identifier
                for identifier in result["contexts"]
                if (
                    self.contexts[identifier].scope != "profile_specific"
                    or profile in self.contexts[identifier].profiles
                )
            ]
        return result

    def _feature_claim_refs(
        self,
        feature: Concept,
        bindings: Sequence[Binding],
    ) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (
                    *feature.claim_refs,
                    *(
                        reference
                        for state in feature.missing_states
                        for reference in state.claim_refs
                    ),
                    *(
                        reference
                        for binding in bindings
                        for interpretation in binding.occurrence_interpretations
                        for reference in interpretation.claim_refs
                    ),
                )
            )
        )

    def _qualification_claim_refs(self, kind: str, identifier: str, profile: str | None = None) -> tuple[str, ...]:
        return tuple(dict.fromkeys(reference for qualification in self.qualifications.values() if qualification.subject_kind == kind and qualification.subject_id == identifier and (profile is None or qualification.origin.target_profile in {None, profile}) for reference in qualification.claim_refs))

    def _constraint_summary(
        self,
        kind: str,
        identifier: str,
        entity: Any,
        related: Mapping[str, Any],
        claim_refs: Sequence[str],
        *,
        bindings: Sequence[Binding] = (),
    ) -> dict[str, list[dict[str, Any]]]:
        """Resolve the most decision-relevant constraints for exact getters."""

        direct_claim_refs = tuple(dict.fromkeys(claim_refs))
        context_ids = {
            reference.split("#", 1)[0] for reference in claim_refs
        }
        context_ids.update(related.get("contexts", ()))
        if kind == "context":
            context_ids.add(identifier)
        if kind == "clinical_object":
            feature_ids = set(related.get("features", ()))
            context_ids.update(
                context.id
                for context in self.contexts.values()
                if feature_ids & set(context.related_concepts)
            )
        if kind == "semantic_relationship":
            physical_ids = {
                binding.id
                for binding in self.relationship_bindings
                if identifier in binding.semantic_relationships
            }
            physical_ids.update(
                binding_id
                for path in self.relationship_binding_paths
                if path.semantic_relationship == identifier
                for binding_id in path.relationship_bindings
            )
            context_ids.update(
                context.id
                for context in self.contexts.values()
                if physical_ids & set(context.related_relationships)
            )

        all_claim_refs = list(direct_claim_refs)
        direct_claim_ref_set = set(direct_claim_refs)
        for context_id in sorted(context_ids):
            context = self.contexts.get(context_id)
            if context is None:
                continue
            all_claim_refs.extend(
                f"{context.id}#{claim.id}"
                for claim in context.claims
                if f"{context.id}#{claim.id}" in direct_claim_ref_set
                or (
                    kind != "clinical_object"
                    and claim.status in {"unresolved", "contradicted"}
                )
            )
        all_claim_refs = list(dict.fromkeys(all_claim_refs))

        supported_facts: list[dict[str, Any]] = []
        unresolved_claims: list[dict[str, Any]] = []
        for reference in all_claim_refs:
            claim = self._claims_by_ref[reference]
            compact = {
                "id": reference,
                "status": claim.status,
                "summary": claim.statement,
            }
            if claim.status in {"verified", "reconciled"}:
                supported_facts.append(compact)
            else:
                unresolved_claims.append(compact)

        coverage_ids = set(related.get("coverage", ()))
        if kind == "coverage":
            coverage_ids.add(identifier)
        for coverage_id in sorted(coverage_ids):
            record = self.coverage[coverage_id]
            compact = {
                "id": record.id,
                "status": record.status,
                "summary": record.summary,
            }
            if record.status == "supported":
                supported_facts.append(compact)
            elif record.status in {
                "unsupported",
                "unresolved",
                "not_cataloged",
            }:
                unresolved_claims.append(compact)

        for binding in bindings:
            for interpretation in binding.occurrence_interpretations:
                compact = {
                    "id": (
                        f"{binding.qualified_identifier}:"
                        f"{interpretation.representation}"
                    ),
                    "status": interpretation.status,
                    "summary": interpretation.meaning,
                }
                if interpretation.status in {"verified", "reconciled"}:
                    supported_facts.append(compact)
                else:
                    unresolved_claims.append(compact)

        guardrail_ids = set(related.get("guardrails", ()))
        if kind == "guardrail":
            guardrail_ids.add(identifier)
        if kind == "context":
            context_features = set(entity.related_concepts)
            guardrail_ids.update(
                guardrail.id
                for guardrail in self.guardrails.values()
                if context_features & set(guardrail.concepts)
            )
        applicable_guardrails = [
            self.guardrails[item] for item in sorted(guardrail_ids)
        ]
        high_priority_guardrails = [
            {
                "id": guardrail.id,
                "status": guardrail.priority,
                "summary": guardrail.statement,
                "category": guardrail.category,
            }
            for guardrail in applicable_guardrails
            if guardrail.priority in {"critical", "high"}
        ]

        temporal_prohibition_terms = {
            "coalesce",
            "fallback",
            "interchangeable",
            "proxy",
            "substitute",
            "substitution",
            "temporal",
            "timestamp",
        }
        unsupported_substitutions = []
        for guardrail in applicable_guardrails:
            text = " ".join(
                (
                    guardrail.title,
                    guardrail.statement,
                    guardrail.rationale,
                    *guardrail.search_terms,
                    *guardrail.caveats,
                )
            )
            if (
                guardrail.category == "prohibition"
                and temporal_prohibition_terms & set(_tokens(text))
            ):
                unsupported_substitutions.append(
                    {
                        "id": guardrail.id,
                        "status": guardrail.priority,
                        "summary": guardrail.statement,
                    }
                )

        aggregation_ids = set(related.get("aggregations", ()))
        if kind == "aggregation":
            aggregation_ids.add(identifier)
        analyst_choices_required = [
            {
                "id": aggregation.id,
                "status": aggregation.status,
                "summary": aggregation.method,
            }
            for aggregation in (
                self.aggregations[item] for item in sorted(aggregation_ids)
            )
            if aggregation.status == "analyst_defined"
        ]
        analyst_choices_required.extend(
            {
                "id": guardrail.id,
                "status": guardrail.priority,
                "summary": guardrail.statement,
            }
            for guardrail in applicable_guardrails
            if guardrail.category == "analyst_choice"
        )

        relevant_contexts = []
        for context_id in sorted(context_ids):
            context = self.contexts.get(context_id)
            if context is None:
                continue
            relevant_contexts.append(
                {
                    "id": context.id,
                    "status": sorted(
                        {claim.status for claim in context.claims}
                    ),
                    "summary": context.summary,
                }
            )

        return {
            "supported_facts": supported_facts,
            "unresolved_claims": unresolved_claims,
            "unsupported_substitutions": unsupported_substitutions,
            "analyst_choices_required": analyst_choices_required,
            "high_priority_guardrails": high_priority_guardrails,
            "relevant_contexts": relevant_contexts,
        }

    def _provenance(
        self, claim_refs: Sequence[str]
    ) -> dict[str, Any]:
        if not claim_refs:
            return {}
        claim_items: list[dict[str, Any]] = []
        context_ids: list[str] = []
        source_ids: list[str] = []
        for reference in dict.fromkeys(claim_refs):
            context_id, _ = reference.split("#", 1)
            context = self.contexts[context_id]
            claim = self._claims_by_ref[reference]
            context_ids.append(context_id)
            source_ids.extend(claim.sources)
            claim_items.append(
                {
                    "id": reference,
                    "context": context_id,
                    "claim_id": claim.id,
                    "statement": claim.statement,
                    "status": claim.status,
                    "sources": list(claim.sources),
                    "caveats": list(claim.caveats),
                }
            )
        return {
            "claims": claim_items,
            "contexts": [
                {
                    "id": context_id,
                    "title": self.contexts[context_id].title,
                    "scope": self.contexts[context_id].scope,
                    "profiles": list(self.contexts[context_id].profiles),
                }
                for context_id in dict.fromkeys(context_ids)
            ],
            "sources": {
                source_id: self.sources[source_id].to_dict()
                for source_id in dict.fromkeys(source_ids)
            },
        }

    def lookup_code(
        self, feature_or_vocabulary: str, code: str, profile: str | None = None
    ) -> dict[str, Any]:
        target = _lookup_identifier(
            feature_or_vocabulary, "feature_or_vocabulary"
        )
        if not isinstance(code, str) or code == "":
            raise CatalogValidationError("code must be a non-empty string")
        feature = self.concepts.get(target)
        feature_id: str | None = None
        bindings: Sequence[Binding] = ()
        selected_profile: str | None = None
        if feature is not None:
            feature_id = feature.id
            bindings = self._bindings_by_concept.get(feature.id, ())
            selected_profile = self._resolve_profile(profile, bindings)
            vocabulary = self._vocabulary_for_feature(feature, bindings, selected_profile)
            if vocabulary is None:
                raise CatalogNotFoundError(
                    f"feature {target!r} has no vocabulary"
                )
        else:
            vocabulary = self.vocabularies.get(target)
            if vocabulary is not None and profile is not None:
                selected_profile = _lookup_identifier(profile, "profile")
                if selected_profile not in self.profile_bindings:
                    raise CatalogNotFoundError(
                        f"profile {selected_profile!r} was not found"
                    )
                origin = self.origins.get(f"vocabulary:{target}")
                if (
                    origin is not None
                    and origin.target_profile is not None
                    and origin.target_profile != selected_profile
                ):
                    raise CatalogNotFoundError(
                        f"vocabulary {target!r} does not apply to profile "
                        f"{selected_profile!r}"
                    )
            if vocabulary is None:
                bindings = self._resolve_physical(target)
                feature = self.concepts[bindings[0].concept]
                feature_id = feature.id
                selected_profile = self._resolve_profile(profile, bindings)
                vocabulary = self._vocabulary_for_feature(feature, bindings, selected_profile)
                if vocabulary is None:
                    raise CatalogNotFoundError(
                        f"feature {target!r} has no vocabulary"
                    )
        meanings = dict(vocabulary.codes)
        if code not in meanings:
            raise CatalogNotFoundError(
                f"code {code!r} was not found in vocabulary {vocabulary.id!r}"
            )
        result: dict[str, Any] = {
            "feature_or_vocabulary": target,
            "feature": feature_id,
            "vocabulary": vocabulary.id,
            "code": code,
            "meaning": meanings[code],
            "completeness": vocabulary.completeness,
            "parsing": vocabulary.parsing,
            "evidence": list(vocabulary.evidence),
            "caveats": list(vocabulary.caveats),
            "profile": selected_profile,
        }
        vocabulary_origin = self.origins.get(f"vocabulary:{vocabulary.id}")
        if vocabulary_origin is not None:
            result["origin"] = vocabulary_origin.to_dict()
        if feature_id is not None:
            feature_origin = self.origins.get(f"concept:{feature_id}")
            if feature_origin is not None:
                result["feature_origin"] = feature_origin.to_dict()
        binding_origins = []
        for binding in bindings:
            if selected_profile is not None and binding.profile != selected_profile:
                continue
            if binding.id is None:
                continue
            binding_origin = self.origins.get(f"binding:{binding.id}")
            if binding_origin is not None:
                binding_origins.append(
                    {"id": binding.id, "origin": binding_origin.to_dict()}
                )
        if binding_origins:
            result["binding_origins"] = binding_origins
        return result

    def get_profile_table(self, profile: str, table: str) -> dict[str, Any]:
        normalized_profile = _lookup_identifier(profile, "profile")
        normalized_table = _lookup_identifier(table, "table")
        identifier = f"{normalized_profile}:{normalized_table}"
        table_spec = self._tables_by_qualified.get(identifier)
        if table_spec is None:
            raise CatalogNotFoundError(
                f"profile table {identifier!r} was not found"
            )
        outgoing = []
        incoming = []
        for relationship in self.relationship_bindings:
            if relationship.profile != normalized_profile:
                continue
            if relationship.source.table == normalized_table:
                outgoing.append(self._binding_contribution_result(relationship))
            if relationship.target.table == normalized_table:
                incoming.append(self._binding_contribution_result(relationship))
        feature_bindings = [
            item
            for item in self.feature_bindings
            if item.profile == normalized_profile
            and item.table == normalized_table
        ]
        object_bindings = [
            item
            for item in self.object_bindings
            if item.profile == normalized_profile
            and item.table == normalized_table
        ]
        concept_ids = {item.concept for item in feature_bindings}
        object_ids = {item.object for item in object_bindings}
        related = {
            "guardrails": sorted(
                guardrail.id
                for guardrail in self.guardrails.values()
                if concept_ids & set(guardrail.concepts)
                or object_ids & set(guardrail.objects)
            ),
            "coverage": sorted(
                record.id
                for record in self.coverage.values()
                if (
                    record.subject_kind == "concept"
                    and record.subject in concept_ids
                )
                or (
                    record.subject_kind == "clinical_object"
                    and record.subject in object_ids
                )
            ),
            "aggregations": sorted(
                aggregation.id
                for aggregation in self.aggregations.values()
                if aggregation.source_concept in concept_ids
                or aggregation.result_concept in concept_ids
            ),
            "contexts": sorted(
                context.id
                for context in self.contexts.values()
                if concept_ids & set(context.related_concepts)
            ),
        }
        claim_refs = tuple(
            dict.fromkeys(
                (
                    *(
                        reference
                        for binding in object_bindings
                        for reference in binding.claim_refs
                    ),
                    *(
                        reference
                        for binding in feature_bindings
                        for interpretation in binding.occurrence_interpretations
                        for reference in interpretation.claim_refs
                    ),
                )
            )
        )
        result = {
            "kind": "profile_table",
            "identifier": identifier,
            "table": self._binding_contribution_result(table_spec),
            "feature_bindings": [
                *self._effective_binding_results(feature_bindings)
            ],
            "object_bindings": [
                self._object_binding_result(item)
                for item in object_bindings
            ],
            "relationship_bindings": {
                "outgoing": outgoing,
                "incoming": incoming,
            },
            "constraints": self._constraint_summary(
                "profile_table",
                identifier,
                table_spec,
                related,
                claim_refs,
                bindings=feature_bindings,
            ),
        }
        origin = (
            self.origins.get(f"binding:{table_spec.id}")
            if table_spec.id is not None
            else None
        )
        if origin is not None:
            result["origin"] = origin.to_dict()
        return result

    def get_relationship_binding(self, identifier: str) -> dict[str, Any]:
        normalized = _lookup_identifier(identifier, "identifier")
        entity = self._relationship_bindings_by_id.get(normalized)
        if entity is None:
            raise CatalogNotFoundError(
                f"relationship binding {normalized!r} was not found"
            )
        semantic_ids = set(entity.semantic_relationships)
        related = {
            "guardrails": sorted(
                guardrail.id
                for guardrail in self.guardrails.values()
                if semantic_ids & set(guardrail.semantic_relationships)
            ),
            "coverage": sorted(
                record.id
                for record in self.coverage.values()
                if record.subject_kind == "semantic_relationship"
                and record.subject in semantic_ids
            ),
            "aggregations": sorted(
                aggregation.id
                for aggregation in self.aggregations.values()
                if semantic_ids & set(aggregation.semantic_relationships)
            ),
        }
        result = {
            "kind": "relationship_binding",
            "identifier": normalized,
            "relationship_binding": self._binding_contribution_result(entity),
            "semantic_relationships": [
                self.semantic_relationships[item].to_dict()
                for item in entity.semantic_relationships
            ],
            "relationship_binding_paths": [
                self._binding_contribution_result(path)
                for path in self.relationship_binding_paths
                if normalized in path.relationship_bindings
            ],
            "constraints": self._constraint_summary(
                "relationship_binding",
                normalized,
                entity,
                related,
                entity.claim_refs,
            ),
            "provenance": self._provenance(entity.claim_refs),
        }
        origin = self.origins.get(f"binding:{entity.id}")
        if origin is not None:
            result["origin"] = origin.to_dict()
        return result

    def _object_binding_result(
        self, binding: ObjectBinding
    ) -> dict[str, Any]:
        """Resolve evidence where a binding has no standalone exact getter."""

        return {
            **self._binding_contribution_result(binding),
            "provenance": self._provenance(binding.claim_refs),
        }

    def _binding_contribution_result(self, binding: Any) -> dict[str, Any]:
        result = binding.to_dict()
        identifier = getattr(binding, "id", None)
        if identifier is not None:
            origin = self.origins.get(f"binding:{identifier}")
            if origin is not None:
                result["origin"] = origin.to_dict()
        return result

    def search_relationship_bindings(
        self,
        *,
        profile: str | None = None,
        table: str | None = None,
        source_table: str | None = None,
        target_table: str | None = None,
        kind: str | None = None,
        semantic_relationship: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        filters = {
            "profile": _optional_filter(profile, "profile"),
            "table": _optional_filter(table, "table"),
            "source_table": _optional_filter(source_table, "source_table"),
            "target_table": _optional_filter(target_table, "target_table"),
            "kind": _optional_filter(kind, "kind"),
            "semantic_relationship": _optional_filter(
                semantic_relationship, "semantic_relationship"
            ),
        }
        _validate_limit(limit)
        if filters["profile"] and filters["profile"] not in self.profile_bindings:
            raise CatalogValidationError(
                f"unknown profile filter {filters['profile']!r}"
            )
        if filters["kind"] and filters["kind"] not in RELATIONSHIP_BINDING_KINDS:
            raise CatalogValidationError(
                f"unknown kind filter {filters['kind']!r}"
            )
        if (
            filters["semantic_relationship"]
            and filters["semantic_relationship"] not in self.semantic_relationships
        ):
            raise CatalogValidationError(
                "unknown semantic_relationship filter "
                f"{filters['semantic_relationship']!r}"
            )
        for name in ("table", "source_table", "target_table"):
            if filters[name]:
                _physical_component(filters[name], name)
        matches = []
        for item in self.relationship_bindings:
            if filters["profile"] and item.profile != filters["profile"]:
                continue
            if filters["table"] and filters["table"] not in {
                item.source.table,
                item.target.table,
            }:
                continue
            if (
                filters["source_table"]
                and item.source.table != filters["source_table"]
            ):
                continue
            if (
                filters["target_table"]
                and item.target.table != filters["target_table"]
            ):
                continue
            if filters["kind"] and item.kind != filters["kind"]:
                continue
            if (
                filters["semantic_relationship"]
                and filters["semantic_relationship"]
                not in item.semantic_relationships
            ):
                continue
            matches.append(item)
        relationships_by_id = {
            item.id: item for item in self.relationship_bindings
        }
        path_matches = []
        if not filters["kind"]:
            for path in self.relationship_binding_paths:
                if (
                    filters["profile"]
                    and path.profile != filters["profile"]
                ):
                    continue
                if (
                    filters["semantic_relationship"]
                    and path.semantic_relationship
                    != filters["semantic_relationship"]
                ):
                    continue
                steps = [
                    relationships_by_id[identifier]
                    for identifier in path.relationship_bindings
                ]
                path_tables = {
                    table_name
                    for step in steps
                    for table_name in (
                        step.source.table,
                        step.target.table,
                    )
                }
                if (
                    filters["table"]
                    and filters["table"] not in path_tables
                ):
                    continue
                if (
                    filters["source_table"]
                    and steps[0].source.table != filters["source_table"]
                ):
                    continue
                if (
                    filters["target_table"]
                    and steps[-1].target.table != filters["target_table"]
                ):
                    continue
                path_matches.append(path)
        return {
            "filters": filters,
            "count": min(len(matches), limit),
            "total": len(matches),
            "matches": [
                self._binding_contribution_result(item)
                for item in matches[:limit]
            ],
            "path_count": min(len(path_matches), limit),
            "path_total": len(path_matches),
            "relationship_binding_paths": [
                self._binding_contribution_result(item)
                for item in path_matches[:limit]
            ],
        }

    def discover(
        self,
        query: str,
        *,
        profile: str | None = None,
        kinds: Sequence[str] | None = None,
        domain: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Discover portable semantics from a clinical-language question."""

        if not isinstance(query, str):
            raise CatalogValidationError("query must be a string")
        _validate_limit(limit)
        query_text = query.strip().casefold()
        query_intents = _recognized_discovery_intents(query_text)
        query_tokens = frozenset(
            token
            for token in _tokens(query_text)
            if token not in _SEARCH_STOPWORDS
        )
        filters = {
            "profile": _optional_filter(profile, "profile"),
            "kinds": None,
            "domain": _optional_filter(domain, "domain"),
        }
        diagnostics: list[dict[str, Any]] = []
        normalized_kinds: tuple[str, ...] | None = None
        unknown_filters: dict[str, Any] = {}
        if kinds is not None:
            if isinstance(kinds, (str, bytes)) or not isinstance(kinds, Sequence):
                unknown_filters["kinds"] = kinds
            else:
                parsed = tuple(
                    _nonempty_string(item, "kinds item") for item in kinds
                )
                unknown = sorted(set(parsed) - set(DISCOVERY_KINDS))
                if unknown:
                    unknown_filters["kinds"] = unknown
                else:
                    normalized_kinds = tuple(dict.fromkeys(parsed))
                    filters["kinds"] = list(normalized_kinds)
        if (
            filters["profile"] is not None
            and filters["profile"] not in self.profile_bindings
        ):
            unknown_filters["profile"] = filters["profile"]
        if filters["domain"] is not None and filters["domain"] not in DOMAINS:
            unknown_filters["domain"] = filters["domain"]
        if unknown_filters:
            diagnostics.append(
                {
                    "category": "unknown_filter",
                    "message": "One or more discovery filters are not catalog values.",
                    "values": unknown_filters,
                }
            )
            return {
                "query": query,
                "filters": filters,
                "count": 0,
                "total": 0,
                "matches": [],
                "matched_terms": [],
                "unmatched_terms": sorted(query_tokens),
                "diagnostics": diagnostics,
            }
        if not query_tokens and not any(
            (filters["profile"], normalized_kinds, filters["domain"])
        ):
            raise CatalogValidationError(
                "provide a query with meaningful terms or at least one filter"
            )

        text_candidates: list[
            tuple[int, _DiscoveryDocument, list[dict[str, Any]], frozenset[str]]
        ] = []
        for document in self._discovery_documents:
            active_tokens = set(document.all_tokens)
            if filters["profile"]:
                active_tokens.update(
                    token
                    for field_profile, _, text in document.profile_fields
                    if field_profile == filters["profile"]
                    for token in _tokens(text)
                )
            matched = query_tokens & frozenset(active_tokens)
            intent_reasons = _discovery_intent_reasons(
                document, query_intents
            )
            if query_tokens and not matched and not intent_reasons:
                continue
            reasons = _discovery_reasons(
                document,
                query_text,
                query_tokens,
                profile=filters["profile"],
            )
            reasons.extend(intent_reasons)
            intent_terms = {
                term
                for reason in intent_reasons
                for term in reason["terms"]
                if term in query_tokens
            }
            matched = matched | frozenset(intent_terms)
            score = _discovery_score(document, query_text, matched, reasons)
            text_candidates.append((score, document, reasons, matched))

        selected_candidates = []
        filtered_out = 0
        unsupported_candidates = 0
        for candidate in text_candidates:
            _, document, _, _ = candidate
            if normalized_kinds and document.kind not in normalized_kinds:
                filtered_out += 1
                continue
            if filters["domain"] and filters["domain"] not in document.domains:
                filtered_out += 1
                continue
            if filters["profile"]:
                profile_match, unsupported = self._document_profile_state(
                    document, filters["profile"]
                )
                if not profile_match:
                    filtered_out += 1
                    continue
                if unsupported:
                    unsupported_candidates += 1
            selected_candidates.append(candidate)

        selected_candidates.sort(
            key=lambda item: (-item[0], item[1].kind, item[1].identifier)
        )
        total = len(selected_candidates)
        composed_candidates = _compose_discovery_candidates(
            selected_candidates,
            limit=limit,
            has_query_intents=bool(query_intents),
        )
        matches = [
            self._discovery_match(
                document,
                score,
                reasons,
                matched,
                query_tokens,
                profile=filters["profile"],
            )
            for score, document, reasons, matched in composed_candidates
        ]
        matched_terms = sorted(
            set().union(
                *(set(item["matched_terms"]) for item in matches)
            )
            if matches
            else set()
        )
        unmatched_terms = sorted(query_tokens - set(matched_terms))

        if filtered_out and not selected_candidates:
            diagnostics.append(
                {
                    "category": "filters_excluded_matches",
                    "message": (
                        "The query matched indexed catalog entities before "
                        "the selected filters were applied."
                    ),
                    "excluded_count": filtered_out,
                }
            )
        if unsupported_candidates:
            diagnostics.append(
                {
                    "category": "unsupported_in_profile",
                    "message": (
                        "At least one matched semantic subject is explicitly "
                        "unsupported or unresolved in the selected profile."
                    ),
                    "count": unsupported_candidates,
                }
            )
        vocabulary = (
            self._vocabulary_mismatch(query_tokens, filters["profile"])
            if query_tokens
            else []
        )
        if vocabulary and unmatched_terms and selected_candidates:
            diagnostics.append(
                {
                    "category": "vocabulary_mismatch",
                    "message": (
                        "The query reached a known vocabulary, but some "
                        "terms did not match an indexed code or meaning."
                    ),
                    "vocabularies": vocabulary,
                    "unmatched_terms": unmatched_terms,
                }
            )
        if not text_candidates and query_tokens:
            if vocabulary:
                diagnostics.append(
                    {
                        "category": "vocabulary_mismatch",
                        "message": (
                            "The query refers to a known vocabulary but no "
                            "indexed code or semantic meaning matched."
                        ),
                        "vocabularies": vocabulary,
                    }
                )
            else:
                diagnostics.append(
                    {
                        "category": "no_catalog_coverage",
                        "message": (
                            "No indexed catalog entity covers the supplied "
                            "terms; this does not establish absence from EMBED."
                        ),
                    }
                )
        return {
            "query": query,
            "filters": filters,
            "count": len(matches),
            "total": total,
            "matches": matches,
            "matched_terms": matched_terms,
            "unmatched_terms": unmatched_terms,
            "diagnostics": diagnostics,
        }

    def _resolve_physical(self, identifier: str) -> tuple[Binding, ...]:
        authored = self._bindings_by_id.get(identifier)
        if authored is not None:
            return (authored,)
        if ":" in identifier:
            binding = self._bindings_by_qualified.get(identifier)
            if binding is None:
                raise CatalogNotFoundError(
                    f"feature binding {identifier!r} was not found"
                )
            return (binding,)
        bindings = self._bindings_by_physical.get(identifier)
        if not bindings:
            raise CatalogNotFoundError(
                f"feature or vocabulary {identifier!r} was not found"
            )
        preferred = {
            revision.replacement_id
            for binding in bindings
            for revision in self._applicable_revisions(binding.profile)
            if revision.kind == "replaces_binding"
        }
        superseded = {
            revision.original_id
            for binding in bindings
            for revision in self._applicable_revisions(binding.profile)
            if revision.kind == "replaces_binding"
        }
        if any(item.id in preferred for item in bindings):
            bindings = tuple(
                item for item in bindings if item.id not in superseded
            )
        concepts = {item.concept for item in bindings}
        if len(concepts) > 1:
            choices = ", ".join(
                item.qualified_identifier for item in bindings
            )
            raise CatalogAmbiguousError(
                f"feature {identifier!r} is ambiguous; use one of: {choices}"
            )
        return bindings

    def _resolve_profile(self, profile: str | None, bindings: Sequence[Binding]) -> str | None:
        if profile is not None:
            selected = _lookup_identifier(profile, "profile")
            if selected not in self.profile_bindings:
                raise CatalogNotFoundError(f"profile {selected!r} was not found")
            return selected
        profiles = {item.profile for item in bindings}
        if self.schema_version >= 7 and len(profiles) > 1:
            raise CatalogAmbiguousError("profile is required because feature bindings or qualifications differ")
        return next(iter(profiles)) if len(profiles) == 1 else None

    def _vocabulary_for_feature(
        self, feature: Concept, bindings: Sequence[Binding] = (), profile: str | None = None
    ) -> Vocabulary | None:
        selected = {item.vocabulary for item in bindings if item.vocabulary is not None and (profile is None or item.profile == profile)}
        if len(selected) > 1:
            raise CatalogAmbiguousError("profile is required because applicable vocabularies differ")
        if selected:
            return self.vocabularies[next(iter(selected))]
        if feature.vocabulary is None:
            return None
        return self.vocabularies[feature.vocabulary]

    def _effective_binding_results(
        self, bindings: Sequence[Binding]
    ) -> list[dict[str, Any]]:
        ordered = sorted(
            bindings,
            key=lambda item: (
                not any(
                    revision.replacement_id == item.id
                    for revision in self._applicable_revisions(item.profile)
                    if revision.kind == "replaces_binding"
                ),
                item.qualified_identifier,
            ),
        )
        return [self._effective_binding_result(item) for item in ordered]

    def _effective_binding_result(self, binding: Binding) -> dict[str, Any]:
        result = binding.to_dict()
        if binding.id is None:
            return result
        origin = self.origins.get(f"binding:{binding.id}")
        if origin is not None:
            result["origin"] = origin.to_dict()
        revisions = tuple(
            revision
            for revision in self._applicable_revisions(binding.profile)
            if revision.kind == "replaces_binding"
            and binding.id in {revision.original_id, revision.replacement_id}
        )
        if revisions:
            result["active_revisions"] = [
                self._revision_result(revision) for revision in revisions
            ]
        original_revision = next(
            (
                revision
                for revision in revisions
                if revision.original_id == binding.id
            ),
            None,
        )
        replacement_revision = next(
            (
                revision
                for revision in revisions
                if revision.replacement_id == binding.id
            ),
            None,
        )
        if original_revision is not None:
            result["effective_view"] = {
                "superseded_in_view": True,
                "replacement_id": original_revision.replacement_id,
                "remains_alternative": (
                    original_revision.original_remains_alternative
                ),
            }
        elif replacement_revision is not None:
            result["effective_view"] = {
                "preferred_in_view": True,
                "replaces_id": replacement_revision.original_id,
            }
        return result

    def _decorate_effective(self, result: dict[str, Any], kind: str, identifier: str, profile: str | None) -> dict[str, Any]:
        if self.schema_version < 7:
            return result
        key = f"{kind}:{identifier}"
        if key in self.origins:
            result["origin"] = self.origins[key].to_dict()
        result["qualifications"] = [q.to_dict() for q in self.qualifications.values() if q.subject_kind == kind and q.subject_id == identifier and (profile is None or q.origin.target_profile in {None, profile})]
        revisions = tuple(
            revision
            for revision in self._applicable_revisions(profile)
            if revision.kind == "reinterprets_concept"
            and identifier in {revision.original_id, revision.replacement_id}
        )
        result["active_revisions"] = [
            self._revision_result(revision) for revision in revisions
        ]
        original_revision = next(
            (
                revision
                for revision in revisions
                if revision.original_id == identifier
            ),
            None,
        )
        replacement_revision = next(
            (
                revision
                for revision in revisions
                if revision.replacement_id == identifier
            ),
            None,
        )
        if original_revision is not None:
            result["effective_view"] = {
                "superseded_in_view": True,
                "replacement_id": original_revision.replacement_id,
            }
        elif replacement_revision is not None:
            result["effective_view"] = {
                "preferred_in_view": True,
                "replaces_id": replacement_revision.original_id,
            }
        lineage = [dict(item) for item in self.feature_lineage.values() if item.get("output_concept") == identifier]
        if lineage:
            result["feature_lineage"] = lineage
        return result

    def _applicable_revisions(self, profile: str | None) -> tuple[Revision, ...]:
        return tuple(
            self.revisions[identifier]
            for identifier in sorted(self.revisions)
            if (
                profile is None
                or self.revisions[identifier].origin.target_profile
                in {None, profile}
            )
        )

    def _revision_result(self, revision: Revision) -> dict[str, Any]:
        return {
            **revision.to_dict(),
            "provenance": self._provenance(revision.claim_refs),
        }

    def _claim_text(self, claim_refs: Sequence[str]) -> str:
        parts: list[str] = []
        for reference in claim_refs:
            claim = self._claims_by_ref[reference]
            parts.extend((reference, claim.statement, *claim.caveats))
            for source_id in claim.sources:
                source = self.sources[source_id]
                parts.extend((source.title, source.version_scope))
        return " ".join(parts)

    def _build_discovery_documents(self) -> tuple[_DiscoveryDocument, ...]:
        documents: list[_DiscoveryDocument] = []
        concept_profiles: defaultdict[str, set[str]] = defaultdict(set)
        object_profiles: defaultdict[str, set[str]] = defaultdict(set)
        semantic_relationship_profiles: defaultdict[str, set[str]] = (
            defaultdict(set)
        )
        for binding in self.feature_bindings:
            concept_profiles[binding.concept].add(binding.profile)
        for binding in self.object_bindings:
            object_profiles[binding.object].add(binding.profile)
        for binding in self.relationship_bindings:
            for identifier in binding.semantic_relationships:
                semantic_relationship_profiles[identifier].add(
                    binding.profile
                )

        def add(
            *,
            kind: str,
            identifier: str,
            label: str,
            entity: Any,
            fields: Sequence[tuple[str, str]],
            domains: Sequence[str],
            profiles: Sequence[str] = (),
            profile_fields: Sequence[tuple[str, str, str]] = (),
        ) -> None:
            qualification_kind = "concept" if kind == "feature" else kind
            qualification_fields = tuple(
                (
                    qualification.origin.target_profile,
                    "claims",
                    self._claim_text(qualification.claim_refs),
                )
                for qualification in self.qualifications.values()
                if qualification.subject_kind == qualification_kind and qualification.subject_id == identifier and qualification.origin.target_profile is not None
            )
            uniquely_applicable_qualifications = (
                tuple((field, text) for _, field, text in qualification_fields)
                if len(self.profiles) == 1
                else ()
            )
            fields = (*fields, *uniquely_applicable_qualifications)
            if len(self.profiles) != 1:
                profile_fields = (*profile_fields, *qualification_fields)
            normalized_fields = tuple(
                (name, text.casefold())
                for name, text in fields
                if isinstance(text, str) and text.strip()
            )
            all_text = " ".join(
                (identifier, label, *(text for _, text in normalized_fields))
            )
            documents.append(
                _DiscoveryDocument(
                    kind=kind,
                    identifier=identifier,
                    label=label,
                    entity=entity,
                    fields=normalized_fields,
                    profile_fields=tuple(
                        dict.fromkeys(
                            (
                                profile,
                                field,
                                text.casefold(),
                            )
                            for profile, field, text in profile_fields
                            if isinstance(text, str) and text.strip()
                        )
                    ),
                    domains=tuple(domains),
                    profiles=tuple(sorted(set(profiles))),
                    all_tokens=frozenset(_tokens(all_text.casefold())),
                )
            )

        for identifier, item in self.clinical_objects.items():
            add(
                kind="clinical_object",
                identifier=identifier,
                label=item.label,
                entity=item,
                fields=(
                    ("identifier", identifier),
                    ("label", item.label),
                    ("definition", item.definition),
                    ("grain", item.grain),
                    ("search_terms", " ".join(item.search_terms)),
                    ("caveats", " ".join(item.caveats)),
                    ("claims", self._claim_text(item.claim_refs)),
                ),
                domains=item.domains,
                profiles=object_profiles[identifier],
            )
        for identifier, item in self.concepts.items():
            vocabulary = self._vocabulary_for_feature(item)
            vocabulary_text = ""
            if vocabulary is not None:
                vocabulary_text = " ".join(
                    (
                        vocabulary.id,
                        vocabulary.label,
                        *(code for code, _ in vocabulary.codes),
                        *(meaning for _, meaning in vocabulary.codes),
                        *vocabulary.caveats,
                    )
                )
            binding_fields = tuple(
                field
                for binding in self._bindings_by_concept.get(identifier, ())
                for field in (
                    (binding.profile, "binding.table", binding.table),
                    (binding.profile, "binding.column", binding.column),
                )
            )
            profile_vocabulary_fields = []
            seen_profile_vocabularies: set[tuple[str, str]] = set()
            for binding in self._bindings_by_concept.get(identifier, ()):
                if binding.vocabulary is None:
                    continue
                key = (binding.profile, binding.vocabulary)
                if key in seen_profile_vocabularies:
                    continue
                seen_profile_vocabularies.add(key)
                selected_vocabulary = self.vocabularies[binding.vocabulary]
                profile_vocabulary_fields.append(
                    (
                        binding.profile,
                        "vocabulary",
                        " ".join(
                            (
                                selected_vocabulary.id,
                                selected_vocabulary.label,
                                *(code for code, _ in selected_vocabulary.codes),
                                *(meaning for _, meaning in selected_vocabulary.codes),
                                *selected_vocabulary.caveats,
                            )
                        ),
                    )
                )
            unique_profile_vocabulary_text = (
                " ".join(text for _, _, text in profile_vocabulary_fields)
                if len(self.profiles) == 1
                else ""
            )
            if len(self.profiles) != 1:
                binding_fields = (
                    *binding_fields,
                    *profile_vocabulary_fields,
                )
            missing_text = " ".join(
                part
                for state in item.missing_states
                for part in (
                    state.id,
                    state.representation,
                    state.meaning,
                    *state.caveats,
                    self._claim_text(state.claim_refs),
                )
            )
            add(
                kind="feature",
                identifier=identifier,
                label=item.label,
                entity=item,
                fields=(
                    ("identifier", identifier),
                    ("label", item.label),
                    ("definition", item.definition),
                    ("search_terms", " ".join(item.search_terms)),
                    ("objects", " ".join(item.objects)),
                    ("missing_states", missing_text),
                    (
                        "vocabulary",
                        " ".join(
                            part
                            for part in (
                                vocabulary_text,
                                unique_profile_vocabulary_text,
                            )
                            if part
                        ),
                    ),
                    ("caveats", " ".join(item.caveats)),
                    ("claims", self._claim_text(item.claim_refs)),
                ),
                domains=item.domains,
                profiles=concept_profiles[identifier],
                profile_fields=binding_fields,
            )
        for identifier, item in self.semantic_relationships.items():
            add(
                kind="semantic_relationship",
                identifier=identifier,
                label=item.label,
                entity=item,
                fields=(
                    ("identifier", identifier),
                    ("label", item.label),
                    ("objects", f"{item.source_object} {item.target_object}"),
                    ("attribution", item.attribution),
                    (
                        "attribution_limitations",
                        " ".join(item.attribution_limitations),
                    ),
                    ("temporal_qualification", item.temporal_qualification),
                    (
                        "temporal_semantics",
                        " ".join(item.temporal_semantics),
                    ),
                    ("search_terms", " ".join(item.search_terms)),
                    ("caveats", " ".join(item.caveats)),
                    ("claims", self._claim_text(item.claim_refs)),
                ),
                domains=item.domains,
                profiles=semantic_relationship_profiles[identifier],
            )
        for identifier, item in self.temporal_semantics.items():
            profiles = {
                binding.profile
                for feature in item.feature_refs
                for binding in self._bindings_by_concept.get(feature, ())
            }
            profiles.update(
                profile
                for record in self.coverage.values()
                if record.subject_kind == "temporal_semantic"
                and record.subject == identifier
                for profile in record.profiles
            )
            add(
                kind="temporal_semantic",
                identifier=identifier,
                label=item.label,
                entity=item,
                fields=(
                    ("identifier", identifier),
                    ("label", item.label),
                    ("meaning", item.meaning),
                    ("objects", " ".join(item.objects)),
                    ("features", " ".join(item.feature_refs)),
                    ("relative_to", " ".join(item.relative_to)),
                    ("search_terms", " ".join(item.search_terms)),
                    ("caveats", " ".join(item.caveats)),
                    ("claims", self._claim_text(item.claim_refs)),
                ),
                domains=item.domains,
                profiles=profiles,
            )
        for identifier, item in self.aggregations.items():
            add(
                kind="aggregation",
                identifier=identifier,
                label=item.label,
                entity=item,
                fields=(
                    ("identifier", identifier),
                    ("label", item.label),
                    ("status", item.status),
                    (
                        "objects",
                        f"{item.source_object} {item.target_object}",
                    ),
                    (
                        "features",
                        " ".join(
                            part
                            for part in (
                                item.source_concept,
                                item.result_concept,
                            )
                            if part
                        ),
                    ),
                    (
                        "semantic_relationships",
                        " ".join(item.semantic_relationships),
                    ),
                    ("method", item.method),
                    ("ordering", item.ordering),
                    ("search_terms", " ".join(item.search_terms)),
                    ("caveats", " ".join(item.caveats)),
                    ("claims", self._claim_text(item.claim_refs)),
                ),
                domains=item.domains,
                profiles=concept_profiles[item.source_concept],
            )
        for identifier, item in self.guardrails.items():
            add(
                kind="guardrail",
                identifier=identifier,
                label=item.title,
                entity=item,
                fields=(
                    ("identifier", identifier),
                    ("title", item.title),
                    ("statement", item.statement),
                    ("rationale", item.rationale),
                    ("category", item.category),
                    ("priority", item.priority),
                    ("objects", " ".join(item.objects)),
                    ("features", " ".join(item.concepts)),
                    (
                        "semantic_relationships",
                        " ".join(item.semantic_relationships),
                    ),
                    ("temporal_semantics", " ".join(item.temporal_semantics)),
                    ("aggregations", " ".join(item.aggregations)),
                    ("coverage", " ".join(item.coverage)),
                    ("search_terms", " ".join(item.search_terms)),
                    ("caveats", " ".join(item.caveats)),
                    ("claims", self._claim_text(item.claim_refs)),
                ),
                domains=item.domains,
                profiles=item.profiles,
            )
        for identifier, item in self.coverage.items():
            add(
                kind="coverage",
                identifier=identifier,
                label=item.summary,
                entity=item,
                fields=(
                    ("identifier", identifier),
                    ("subject", f"{item.subject_kind} {item.subject}"),
                    ("status", item.status),
                    ("summary", item.summary),
                    ("search_terms", " ".join(item.search_terms)),
                    ("caveats", " ".join(item.caveats)),
                    ("claims", self._claim_text(item.claim_refs)),
                ),
                domains=item.domains,
                profiles=item.profiles,
            )
        for identifier, item in self.contexts.items():
            claim_text = " ".join(
                part
                for claim in item.claims
                for part in (
                    claim.id,
                    claim.statement,
                    claim.status,
                    *claim.caveats,
                    *(self.sources[source].title for source in claim.sources),
                )
            )
            add(
                kind="context",
                identifier=identifier,
                label=item.title,
                entity=item,
                fields=(
                    ("identifier", identifier),
                    ("title", item.title),
                    ("summary", item.summary),
                    ("search_terms", " ".join(item.search_terms)),
                    ("claims", claim_text),
                    ("caveats", " ".join(item.caveats)),
                ),
                domains=item.domains,
                profiles=item.profiles,
            )
        return tuple(
            sorted(documents, key=lambda item: (item.kind, item.identifier))
        )

    def _document_profile_state(
        self, document: _DiscoveryDocument, profile: str
    ) -> tuple[bool, bool]:
        origin_kind = "concept" if document.kind == "feature" else document.kind
        origin = self.origins.get(f"{origin_kind}:{document.identifier}")
        if (
            origin is not None
            and origin.target_profile is not None
            and origin.target_profile != profile
        ):
            return False, False
        if document.kind in {"guardrail", "coverage", "context"}:
            entity_scope = getattr(document.entity, "scope", None)
            if (
                entity_scope == "profile_specific"
                and profile not in document.profiles
            ):
                return False, False
        unsupported = any(
            record.status in {"unsupported", "unresolved"}
            and (
                record.scope != "profile_specific"
                or profile in record.profiles
            )
            and (
                (
                    record.subject_kind == "concept"
                    and document.kind == "feature"
                )
                or record.subject_kind == document.kind
                or (
                    record.subject_kind == "topic"
                    and document.kind == "context"
                )
            )
            and record.subject == document.identifier
            for record in self.coverage.values()
        )
        return True, unsupported

    def _discovery_match(
        self,
        document: _DiscoveryDocument,
        score: int,
        reasons: list[dict[str, Any]],
        matched: frozenset[str],
        query_tokens: frozenset[str],
        *,
        profile: str | None,
    ) -> dict[str, Any]:
        result = {
            "kind": document.kind,
            "identifier": document.identifier,
            "score": score,
            "label": document.label,
            "entity": document.entity.to_dict(),
            "match_reasons": reasons,
            "matched_terms": sorted(matched),
            "unmatched_terms": sorted(query_tokens - matched),
        }
        if profile is not None:
            result["implementation_bindings"] = (
                self._discovery_implementation_bindings(document, profile)
            )
            result["profile_coverage"] = [
                item.to_dict()
                for item in self.coverage.values()
                if (
                    item.scope != "profile_specific"
                    or profile in item.profiles
                )
                and (
                    (
                        item.subject_kind == "concept"
                        and document.kind == "feature"
                    )
                    or item.subject_kind == document.kind
                    or (
                        item.subject_kind == "topic"
                        and document.kind == "context"
                    )
                )
                and item.subject == document.identifier
            ]
        origin_kind = "concept" if document.kind == "feature" else document.kind
        return self._decorate_effective(
            result, origin_kind, document.identifier, profile
        )

    def _discovery_implementation_bindings(
        self, document: _DiscoveryDocument, profile: str
    ) -> dict[str, Any]:
        feature_ids: set[str] = set()
        object_ids: set[str] = set()
        relationship_ids: set[str] = set()
        if document.kind == "feature":
            feature_ids.add(document.identifier)
        elif document.kind == "clinical_object":
            object_ids.add(document.identifier)
        elif document.kind == "semantic_relationship":
            relationship_ids.add(document.identifier)
        elif document.kind == "temporal_semantic":
            feature_ids.update(document.entity.feature_refs)
        elif document.kind == "aggregation":
            feature_ids.add(document.entity.source_concept)
            if document.entity.result_concept is not None:
                feature_ids.add(document.entity.result_concept)
            relationship_ids.update(
                document.entity.semantic_relationships
            )
        return {
            "profile": profile,
            "feature_bindings": self._effective_binding_results(
                [
                    item
                    for item in self.feature_bindings
                    if item.profile == profile and item.concept in feature_ids
                ]
            ),
            "object_bindings": [
                self._object_binding_result(item)
                for item in self.object_bindings
                if item.profile == profile and item.object in object_ids
            ],
            "relationship_bindings": [
                self._binding_contribution_result(item)
                for item in self.relationship_bindings
                if item.profile == profile
                and relationship_ids.intersection(
                    item.semantic_relationships
                )
            ],
            "relationship_binding_paths": [
                self._binding_contribution_result(item)
                for item in self.relationship_binding_paths
                if item.profile == profile
                and item.semantic_relationship in relationship_ids
            ],
        }

    def _vocabulary_mismatch(
        self, query_tokens: frozenset[str], profile: str | None = None
    ) -> list[str]:
        matches = []
        applicable = (
            {
                binding.vocabulary
                for binding in self.feature_bindings
                if binding.profile == profile and binding.vocabulary is not None
            }
            if profile is not None
            else set(self.vocabularies)
        )
        applicable.update(
            concept.vocabulary
            for concept in self.concepts.values()
            if concept.vocabulary is not None
        )
        for identifier, vocabulary in self.vocabularies.items():
            if identifier not in applicable:
                continue
            navigation_tokens = frozenset(
                _tokens(f"{identifier} {vocabulary.label}".casefold())
            )
            if query_tokens & navigation_tokens:
                matches.append(identifier)
        return sorted(matches)


def _parse_map(
    value: object,
    path: str,
    parser: Any,
    *parser_args: Any,
) -> dict[str, Any]:
    data = _expect_mapping(value, path)
    parsed: dict[str, Any] = {}
    for identifier, raw in data.items():
        _require_identifier(identifier, f"{path} key {identifier!r}")
        parsed[identifier] = parser(identifier, raw, *parser_args)
    return parsed


def _parse_clinical_object(
    identifier: str, value: object
) -> ClinicalObject:
    path = f"$.clinical_objects.{identifier}"
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data, _CLINICAL_OBJECT_KEYS, _CLINICAL_OBJECT_KEYS, path
    )
    return ClinicalObject(
        id=identifier,
        label=_nonempty_string(data["label"], f"{path}.label"),
        definition=_nonempty_string(
            data["definition"], f"{path}.definition"
        ),
        grain=_nonempty_string(data["grain"], f"{path}.grain"),
        domains=_domain_array(data["domains"], f"{path}.domains"),
        search_terms=_string_array(
            data["search_terms"], f"{path}.search_terms", minimum=1
        ),
        claim_refs=_claim_ref_array(
            data["claim_refs"], f"{path}.claim_refs"
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _parse_concept(identifier: str, value: object) -> Concept:
    path = f"$.concepts.{identifier}"
    data = _expect_mapping(value, path)
    _require_exact_keys(data, _CONCEPT_REQUIRED_KEYS, _CONCEPT_KEYS, path)
    feature_kind = _controlled_string(
        data["feature_kind"], f"{path}.feature_kind", FEATURE_KINDS
    )
    objects = _identifier_array(data["objects"], f"{path}.objects")
    if feature_kind != "technical" and not objects:
        raise CatalogValidationError(
            f"{path}.objects must not be empty for nontechnical features"
        )
    raw_missing = _expect_list(
        data.get("missing_states", []), f"{path}.missing_states"
    )
    missing_states = tuple(
        _parse_missing_state(raw, f"{path}.missing_states[{index}]")
        for index, raw in enumerate(raw_missing)
    )
    state_ids = [state.id for state in missing_states]
    if len(state_ids) != len(set(state_ids)):
        raise CatalogValidationError(
            f"{path}.missing_states contains duplicate IDs"
        )
    vocabulary_raw = data.get("vocabulary")
    vocabulary = (
        _identifier(vocabulary_raw, f"{path}.vocabulary")
        if vocabulary_raw is not None
        else None
    )
    return Concept(
        id=identifier,
        label=_nonempty_string(data["label"], f"{path}.label"),
        definition=_nonempty_string(
            data["definition"], f"{path}.definition"
        ),
        feature_kind=feature_kind,
        domains=_domain_array(data["domains"], f"{path}.domains"),
        objects=objects,
        search_terms=_string_array(
            data["search_terms"], f"{path}.search_terms", minimum=1
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
        evidence=_evidence_array(data["evidence"], f"{path}.evidence"),
        claim_refs=_claim_ref_array(
            data.get("claim_refs", []), f"{path}.claim_refs"
        ),
        missing_states=missing_states,
        temporal_semantics=_identifier_array(
            data.get("temporal_semantics", []),
            f"{path}.temporal_semantics",
        ),
        aggregations=_identifier_array(
            data.get("aggregations", []), f"{path}.aggregations"
        ),
        vocabulary=vocabulary,
    )


def _parse_missing_state(value: object, path: str) -> MissingState:
    data = _expect_mapping(value, path)
    _require_exact_keys(data, _MISSING_STATE_KEYS, _MISSING_STATE_KEYS, path)
    return MissingState(
        id=_identifier(data["id"], f"{path}.id"),
        representation=_nonempty_string(
            data["representation"], f"{path}.representation"
        ),
        meaning=_nonempty_string(data["meaning"], f"{path}.meaning"),
        claim_refs=_claim_ref_array(
            data["claim_refs"], f"{path}.claim_refs"
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _parse_semantic_relationship(
    identifier: str, value: object
) -> SemanticRelationship:
    path = f"$.semantic_relationships.{identifier}"
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data,
        _SEMANTIC_RELATIONSHIP_KEYS,
        _SEMANTIC_RELATIONSHIP_KEYS,
        path,
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
    optionality = _expect_mapping(
        data["optionality"], f"{path}.optionality"
    )
    _require_exact_keys(
        optionality,
        _OPTIONALITY_KEYS,
        _OPTIONALITY_KEYS,
        f"{path}.optionality",
    )
    return SemanticRelationship(
        id=identifier,
        label=_nonempty_string(data["label"], f"{path}.label"),
        kind=_controlled_string(
            data["kind"],
            f"{path}.kind",
            SEMANTIC_RELATIONSHIP_KINDS,
        ),
        source_object=_identifier(
            data["source_object"], f"{path}.source_object"
        ),
        target_object=_identifier(
            data["target_object"], f"{path}.target_object"
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
        source_optionality=_controlled_string(
            optionality["source"],
            f"{path}.optionality.source",
            OPTIONALITY_VALUES,
        ),
        target_optionality=_controlled_string(
            optionality["target"],
            f"{path}.optionality.target",
            OPTIONALITY_VALUES,
        ),
        attribution=_nonempty_string(
            data["attribution"], f"{path}.attribution"
        ),
        attribution_limitations=_string_array(
            data["attribution_limitations"],
            f"{path}.attribution_limitations",
        ),
        temporal_qualification=_nonempty_string(
            data["temporal_qualification"],
            f"{path}.temporal_qualification",
        ),
        temporal_semantics=_identifier_array(
            data["temporal_semantics"],
            f"{path}.temporal_semantics",
        ),
        domains=_domain_array(data["domains"], f"{path}.domains"),
        search_terms=_string_array(
            data["search_terms"], f"{path}.search_terms", minimum=1
        ),
        claim_refs=_claim_ref_array(
            data["claim_refs"], f"{path}.claim_refs"
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _parse_temporal_semantic(
    identifier: str, value: object
) -> TemporalSemantic:
    path = f"$.temporal_semantics.{identifier}"
    data = _expect_mapping(value, path)
    _require_exact_keys(data, _TEMPORAL_KEYS, _TEMPORAL_KEYS, path)
    return TemporalSemantic(
        id=identifier,
        label=_nonempty_string(data["label"], f"{path}.label"),
        kind=_controlled_string(
            data["kind"], f"{path}.kind", TEMPORAL_KINDS
        ),
        meaning=_nonempty_string(data["meaning"], f"{path}.meaning"),
        objects=_identifier_array(
            data["objects"], f"{path}.objects", minimum=1
        ),
        feature_refs=_identifier_array(
            data["feature_refs"], f"{path}.feature_refs"
        ),
        relative_to=_identifier_array(
            data["relative_to"], f"{path}.relative_to"
        ),
        domains=_domain_array(data["domains"], f"{path}.domains"),
        search_terms=_string_array(
            data["search_terms"], f"{path}.search_terms", minimum=1
        ),
        claim_refs=_claim_ref_array(
            data["claim_refs"], f"{path}.claim_refs"
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _parse_aggregation(identifier: str, value: object) -> Aggregation:
    path = f"$.aggregations.{identifier}"
    data = _expect_mapping(value, path)
    _require_exact_keys(data, _AGGREGATION_KEYS, _AGGREGATION_KEYS, path)
    raw_result = data["result_concept"]
    if raw_result is not None:
        result_concept = _identifier(
            raw_result, f"{path}.result_concept"
        )
    else:
        result_concept = None
    return Aggregation(
        id=identifier,
        label=_nonempty_string(data["label"], f"{path}.label"),
        status=_controlled_string(
            data["status"], f"{path}.status", AGGREGATION_STATUSES
        ),
        source_object=_identifier(
            data["source_object"], f"{path}.source_object"
        ),
        target_object=_identifier(
            data["target_object"], f"{path}.target_object"
        ),
        source_concept=_identifier(
            data["source_concept"], f"{path}.source_concept"
        ),
        result_concept=result_concept,
        semantic_relationships=_identifier_array(
            data["semantic_relationships"],
            f"{path}.semantic_relationships",
        ),
        method=_nonempty_string(data["method"], f"{path}.method"),
        ordering=_nonempty_string(data["ordering"], f"{path}.ordering"),
        domains=_domain_array(data["domains"], f"{path}.domains"),
        search_terms=_string_array(
            data["search_terms"], f"{path}.search_terms", minimum=1
        ),
        claim_refs=_claim_ref_array(
            data["claim_refs"], f"{path}.claim_refs"
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _parse_guardrail(
    identifier: str, value: object, profiles: frozenset[str]
) -> Guardrail:
    path = f"$.guardrails.{identifier}"
    data = _expect_mapping(value, path)
    _require_exact_keys(data, _GUARDRAIL_KEYS, _GUARDRAIL_KEYS, path)
    scope, selected_profiles = _scope_and_profiles(data, path, profiles)
    links = {
        name: _identifier_array(data[name], f"{path}.{name}")
        for name in (
            "objects",
            "concepts",
            "semantic_relationships",
            "temporal_semantics",
            "aggregations",
            "coverage",
        )
    }
    if not any(links.values()):
        raise CatalogValidationError(
            f"{path} must reference at least one semantic entity"
        )
    return Guardrail(
        id=identifier,
        title=_nonempty_string(data["title"], f"{path}.title"),
        statement=_nonempty_string(
            data["statement"], f"{path}.statement"
        ),
        rationale=_nonempty_string(
            data["rationale"], f"{path}.rationale"
        ),
        category=_controlled_string(
            data["category"], f"{path}.category", GUARDRAIL_CATEGORIES
        ),
        priority=_controlled_string(
            data["priority"], f"{path}.priority", GUARDRAIL_PRIORITIES
        ),
        scope=scope,
        profiles=selected_profiles,
        objects=links["objects"],
        concepts=links["concepts"],
        semantic_relationships=links["semantic_relationships"],
        temporal_semantics=links["temporal_semantics"],
        aggregations=links["aggregations"],
        coverage=links["coverage"],
        domains=_domain_array(data["domains"], f"{path}.domains"),
        search_terms=_string_array(
            data["search_terms"], f"{path}.search_terms", minimum=1
        ),
        claim_refs=_claim_ref_array(
            data["claim_refs"], f"{path}.claim_refs"
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _parse_coverage(
    identifier: str, value: object, profiles: frozenset[str]
) -> Coverage:
    path = f"$.coverage.{identifier}"
    data = _expect_mapping(value, path)
    _require_exact_keys(data, _COVERAGE_KEYS, _COVERAGE_KEYS, path)
    scope, selected_profiles = _scope_and_profiles(data, path, profiles)
    return Coverage(
        id=identifier,
        subject_kind=_controlled_string(
            data["subject_kind"],
            f"{path}.subject_kind",
            COVERAGE_SUBJECT_KINDS,
        ),
        subject=_identifier(data["subject"], f"{path}.subject"),
        status=_controlled_string(
            data["status"], f"{path}.status", COVERAGE_STATUSES
        ),
        scope=scope,
        profiles=selected_profiles,
        summary=_nonempty_string(data["summary"], f"{path}.summary"),
        domains=_domain_array(data["domains"], f"{path}.domains"),
        search_terms=_string_array(
            data["search_terms"], f"{path}.search_terms", minimum=1
        ),
        claim_refs=_claim_ref_array(
            data["claim_refs"], f"{path}.claim_refs"
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _parse_vocabulary(identifier: str, value: object) -> Vocabulary:
    path = f"$.vocabularies.{identifier}"
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data, _VOCABULARY_REQUIRED_KEYS, _VOCABULARY_KEYS, path
    )
    raw_codes = _expect_mapping(data["codes"], f"{path}.codes")
    if not raw_codes:
        raise CatalogValidationError(f"{path}.codes must not be empty")
    codes: list[tuple[str, str]] = []
    for code, meaning in raw_codes.items():
        if (
            not isinstance(code, str)
            or not code.strip()
            or code != code.strip()
        ):
            raise CatalogValidationError(
                f"{path}.codes keys must be non-empty strings without "
                "surrounding whitespace"
            )
        codes.append(
            (code, _nonempty_string(meaning, f"{path}.codes[{code!r}]"))
        )
    return Vocabulary(
        id=identifier,
        label=_nonempty_string(data["label"], f"{path}.label"),
        completeness=_controlled_string(
            data["completeness"],
            f"{path}.completeness",
            VOCABULARY_COMPLETENESS,
        ),
        parsing=_controlled_string(
            data["parsing"], f"{path}.parsing", VOCABULARY_PARSING
        ),
        evidence=_evidence_array(data["evidence"], f"{path}.evidence"),
        codes=tuple(codes),
        caveats=_string_array(
            data.get("caveats", []), f"{path}.caveats"
        ),
    )


def _parse_context_source(
    identifier: str, value: object, profiles: frozenset[str]
) -> ContextSource:
    path = f"$.sources.{identifier}"
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data, _CONTEXT_SOURCE_KEYS, _CONTEXT_SOURCE_KEYS, path
    )
    scope, selected_profiles = _scope_and_profiles(data, path, profiles)
    kind = _controlled_string(
        data["kind"], f"{path}.kind", SOURCE_KINDS
    )
    if kind in {"release_schema", "release_legend"} and not selected_profiles:
        raise CatalogValidationError(
            f"{path}.profiles must identify a release profile for {kind!r}"
        )
    locator_kind = _controlled_string(
        data["locator_kind"],
        f"{path}.locator_kind",
        SOURCE_LOCATOR_KINDS,
    )
    locator = _nonempty_string(data["locator"], f"{path}.locator")
    if locator_kind == "url" and not locator.startswith("https://"):
        raise CatalogValidationError(
            f"{path}.locator must be an https URL for locator kind 'url'"
        )
    if locator_kind == "repository_path":
        locator_path = Path(locator)
        if locator_path.is_absolute() or ".." in locator_path.parts:
            raise CatalogValidationError(
                f"{path}.locator must be a repository-relative path "
                "without parent traversal"
            )
    return ContextSource(
        id=identifier,
        title=_nonempty_string(data["title"], f"{path}.title"),
        kind=kind,
        scope=scope,
        locator_kind=locator_kind,
        locator=locator,
        version_scope=_nonempty_string(
            data["version_scope"], f"{path}.version_scope"
        ),
        profiles=selected_profiles,
        notes=_string_array(data["notes"], f"{path}.notes"),
    )


def _parse_clinical_context(
    identifier: str, value: object, profiles: frozenset[str]
) -> ClinicalContext:
    path = f"$.contexts.{identifier}"
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data, _CLINICAL_CONTEXT_KEYS, _CLINICAL_CONTEXT_KEYS, path
    )
    scope, selected_profiles = _scope_and_profiles(data, path, profiles)
    raw_tables = _expect_list(
        data["related_tables"], f"{path}.related_tables"
    )
    table_refs: list[ContextTableReference] = []
    seen_tables: set[str] = set()
    for index, raw in enumerate(raw_tables):
        table_path = f"{path}.related_tables[{index}]"
        table_data = _expect_mapping(raw, table_path)
        _require_exact_keys(
            table_data,
            _CONTEXT_TABLE_REFERENCE_KEYS,
            _CONTEXT_TABLE_REFERENCE_KEYS,
            table_path,
        )
        reference = ContextTableReference(
            profile=_controlled_identifier(
                table_data["profile"],
                f"{table_path}.profile",
                profiles,
            ),
            table=_physical_component(
                table_data["table"], f"{table_path}.table"
            ),
        )
        if reference.identifier in seen_tables:
            raise CatalogValidationError(
                f"{path}.related_tables contains duplicate "
                f"{reference.identifier!r}"
            )
        seen_tables.add(reference.identifier)
        table_refs.append(reference)

    raw_claims = _expect_list(data["claims"], f"{path}.claims")
    if not raw_claims:
        raise CatalogValidationError(f"{path}.claims must not be empty")
    claims: list[ContextClaim] = []
    seen_claims: set[str] = set()
    for index, raw in enumerate(raw_claims):
        claim_path = f"{path}.claims[{index}]"
        claim_data = _expect_mapping(raw, claim_path)
        _require_exact_keys(
            claim_data,
            _CONTEXT_CLAIM_KEYS,
            _CONTEXT_CLAIM_KEYS,
            claim_path,
        )
        claim_id = _identifier(claim_data["id"], f"{claim_path}.id")
        if claim_id in seen_claims:
            raise CatalogValidationError(
                f"{path}.claims contains duplicate ID {claim_id!r}"
            )
        seen_claims.add(claim_id)
        claims.append(
            ContextClaim(
                id=claim_id,
                statement=_nonempty_string(
                    claim_data["statement"], f"{claim_path}.statement"
                ),
                status=_controlled_string(
                    claim_data["status"],
                    f"{claim_path}.status",
                    CLAIM_STATUSES,
                ),
                sources=_identifier_array(
                    claim_data["sources"],
                    f"{claim_path}.sources",
                    minimum=1,
                ),
                caveats=_string_array(
                    claim_data["caveats"], f"{claim_path}.caveats"
                ),
            )
        )
    raw_steps = _expect_list(
        data["workflow_steps"], f"{path}.workflow_steps"
    )
    steps: list[WorkflowStep] = []
    seen_steps: set[str] = set()
    for index, raw in enumerate(raw_steps):
        step_path = f"{path}.workflow_steps[{index}]"
        step_data = _expect_mapping(raw, step_path)
        _require_exact_keys(
            step_data, _WORKFLOW_STEP_KEYS, _WORKFLOW_STEP_KEYS, step_path
        )
        step_id = _identifier(step_data["id"], f"{step_path}.id")
        if step_id in seen_steps:
            raise CatalogValidationError(
                f"{path}.workflow_steps contains duplicate ID {step_id!r}"
            )
        seen_steps.add(step_id)
        claim_ids = _identifier_array(
            step_data["claims"], f"{step_path}.claims", minimum=1
        )
        unknown = sorted(set(claim_ids) - seen_claims)
        if unknown:
            raise CatalogValidationError(
                f"{step_path}.claims references unknown claim IDs: "
                + ", ".join(unknown)
            )
        steps.append(
            WorkflowStep(
                id=step_id,
                label=_nonempty_string(
                    step_data["label"], f"{step_path}.label"
                ),
                claims=claim_ids,
            )
        )
    kind = _controlled_string(
        data["kind"], f"{path}.kind", CONTEXT_KINDS
    )
    if kind == "clinical_workflow":
        if len(steps) < 2:
            raise CatalogValidationError(
                f"{path}.workflow_steps must contain at least two steps"
            )
        placed = {claim for step in steps for claim in step.claims}
        missing = sorted(seen_claims - placed)
        if missing:
            raise CatalogValidationError(
                f"{path}.workflow_steps does not place claims: "
                + ", ".join(missing)
            )
    elif steps:
        raise CatalogValidationError(
            f"{path}.workflow_steps must be empty for non-workflow context"
        )
    if scope != "profile_specific" and (table_refs or data["related_relationships"]):
        raise CatalogValidationError(
            f"{path} may reference physical metadata only when profile_specific"
        )
    return ClinicalContext(
        id=identifier,
        title=_nonempty_string(data["title"], f"{path}.title"),
        kind=kind,
        scope=scope,
        profiles=selected_profiles,
        summary=_nonempty_string(data["summary"], f"{path}.summary"),
        domains=_domain_array(data["domains"], f"{path}.domains"),
        search_terms=_string_array(
            data["search_terms"], f"{path}.search_terms", minimum=1
        ),
        related_concepts=_identifier_array(
            data["related_concepts"], f"{path}.related_concepts"
        ),
        related_tables=tuple(table_refs),
        related_relationships=_identifier_array(
            data["related_relationships"],
            f"{path}.related_relationships",
        ),
        claims=tuple(claims),
        workflow_steps=tuple(steps),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _parse_profile_binding(
    profile: str, value: object
) -> ProfileBinding:
    path = f"$.profile_bindings.{profile}"
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data, _PROFILE_BINDING_KEYS, _PROFILE_BINDING_KEYS, path
    )
    raw_features = _expect_list(
        data["feature_bindings"], f"{path}.feature_bindings"
    )
    feature_bindings = tuple(
        _parse_binding(profile, raw, f"{path}.feature_bindings[{index}]")
        for index, raw in enumerate(raw_features)
    )
    object_bindings = tuple(
        _parse_object_binding(
            profile, raw, f"{path}.object_bindings[{index}]"
        )
        for index, raw in enumerate(
            _expect_list(data["object_bindings"], f"{path}.object_bindings")
        )
    )
    tables = tuple(
        _parse_table(profile, raw, f"{path}.tables[{index}]")
        for index, raw in enumerate(
            _expect_list(data["tables"], f"{path}.tables")
        )
    )
    relationships = tuple(
        _parse_relationship_binding(
            profile,
            raw,
            f"{path}.relationship_bindings[{index}]",
        )
        for index, raw in enumerate(
            _expect_list(
                data["relationship_bindings"],
                f"{path}.relationship_bindings",
            )
        )
    )
    relationship_paths = tuple(
        _parse_relationship_binding_path(
            profile,
            raw,
            f"{path}.relationship_binding_paths[{index}]",
        )
        for index, raw in enumerate(
            _expect_list(
                data["relationship_binding_paths"],
                f"{path}.relationship_binding_paths",
            )
        )
    )
    return ProfileBinding(
        profile=profile,
        feature_bindings=feature_bindings,
        object_bindings=object_bindings,
        tables=tables,
        relationship_bindings=relationships,
        relationship_binding_paths=relationship_paths,
    )


def _parse_binding(profile: str, value: object, path: str) -> Binding:
    data = _expect_mapping(value, path)
    _require_exact_keys(data, _BINDING_REQUIRED_KEYS, _BINDING_KEYS, path)
    concept = _identifier(data["concept"], f"{path}.concept")
    has_parameters = "parameters" in data
    if concept == _SLOT_PARAMETER_CONCEPT and not has_parameters:
        raise CatalogValidationError(
            f"{path}.parameters.slot is required for concept "
            f"{_SLOT_PARAMETER_CONCEPT!r}"
        )
    if concept != _SLOT_PARAMETER_CONCEPT and has_parameters:
        raise CatalogValidationError(
            f"{path}.parameters is only allowed for concept "
            f"{_SLOT_PARAMETER_CONCEPT!r}"
        )
    raw_parameters = data.get("parameters", {})
    parameters_data = _expect_mapping(
        raw_parameters, f"{path}.parameters"
    )
    unexpected = sorted(set(parameters_data) - BINDING_PARAMETER_KEYS)
    if unexpected:
        raise CatalogValidationError(
            f"{path}.parameters has unexpected fields: "
            + ", ".join(unexpected)
        )
    parameters: list[tuple[str, int]] = []
    for key, raw in parameters_data.items():
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 1:
            raise CatalogValidationError(
                f"{path}.parameters.{key} must be a positive integer"
            )
        parameters.append((key, raw))
    nullable = data["nullable"]
    if not isinstance(nullable, bool):
        raise CatalogValidationError(f"{path}.nullable must be a boolean")
    notes = (
        _string_array(data["notes"], f"{path}.notes", minimum=1)
        if "notes" in data
        else ()
    )
    occurrence_interpretations = tuple(
        _parse_occurrence_interpretation(
            raw, f"{path}.occurrence_interpretations[{index}]"
        )
        for index, raw in enumerate(
            _expect_list(
                data.get("occurrence_interpretations", []),
                f"{path}.occurrence_interpretations",
            )
        )
    )
    representations = [
        item.representation for item in occurrence_interpretations
    ]
    if len(representations) != len(set(representations)):
        raise CatalogValidationError(
            f"{path}.occurrence_interpretations contains duplicate "
            "representations"
        )
    return Binding(
        profile=profile,
        table=_physical_component(data["table"], f"{path}.table"),
        column=_physical_component(data["column"], f"{path}.column"),
        concept=concept,
        grain=_controlled_string(
            data["grain"], f"{path}.grain", BINDING_GRAINS
        ),
        role=_controlled_string(data["role"], f"{path}.role", ROLES),
        physical_type=_nonempty_string(
            data["physical_type"], f"{path}.physical_type"
        ),
        nullable=nullable,
        parameters=tuple(sorted(parameters)),
        notes=notes,
        occurrence_interpretations=occurrence_interpretations,
        id=(_identifier(data["id"], f"{path}.id") if "id" in data else None),
        vocabulary=(_identifier(data["vocabulary"], f"{path}.vocabulary") if "vocabulary" in data else None),
        coexists_with=_identifier_array(data.get("coexists_with", []), f"{path}.coexists_with"),
    )


def _parse_occurrence_interpretation(
    value: object, path: str
) -> OccurrenceInterpretation:
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data,
        _OCCURRENCE_INTERPRETATION_KEYS,
        _OCCURRENCE_INTERPRETATION_KEYS,
        path,
    )
    return OccurrenceInterpretation(
        representation=_nonempty_string(
            data["representation"], f"{path}.representation"
        ),
        meaning=_nonempty_string(data["meaning"], f"{path}.meaning"),
        status=_controlled_string(
            data["status"], f"{path}.status", CLAIM_STATUSES
        ),
        claim_refs=_claim_ref_array(
            data["claim_refs"], f"{path}.claim_refs"
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _parse_object_binding(
    profile: str, value: object, path: str
) -> ObjectBinding:
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data,
        _OBJECT_BINDING_REQUIRED_KEYS,
        _OBJECT_BINDING_KEYS,
        path,
    )
    instance_identity = (
        _parse_instance_identity(
            data["instance_identity"], f"{path}.instance_identity"
        )
        if "instance_identity" in data
        else None
    )
    return ObjectBinding(
        profile=profile,
        object=_identifier(data["object"], f"{path}.object"),
        table=_physical_component(data["table"], f"{path}.table"),
        columns=_physical_component_array(
            data["columns"], f"{path}.columns", minimum=0
        ),
        representation=_controlled_string(
            data["representation"],
            f"{path}.representation",
            OBJECT_BINDING_REPRESENTATIONS,
        ),
        claim_refs=_claim_ref_array(
            data["claim_refs"], f"{path}.claim_refs"
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
        instance_identity=instance_identity,
        id=(_identifier(data["id"], f"{path}.id") if "id" in data else None),
    )


def _parse_instance_identity(
    value: object, path: str
) -> InstanceIdentity:
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data, _INSTANCE_IDENTITY_KEYS, _INSTANCE_IDENTITY_KEYS, path
    )
    longitudinal_identity = data["longitudinal_identity"]
    if not isinstance(longitudinal_identity, bool):
        raise CatalogValidationError(
            f"{path}.longitudinal_identity must be a boolean"
        )
    reserved_exceptions = tuple(
        _parse_reserved_identity_exception(
            raw, f"{path}.reserved_exceptions[{index}]"
        )
        for index, raw in enumerate(
            _expect_list(
                data["reserved_exceptions"], f"{path}.reserved_exceptions"
            )
        )
    )
    exception_keys = [
        (item.column, item.representation) for item in reserved_exceptions
    ]
    if len(exception_keys) != len(set(exception_keys)):
        raise CatalogValidationError(
            f"{path}.reserved_exceptions contains duplicate column and "
            "representation pairs"
        )
    return InstanceIdentity(
        columns=_physical_component_array(
            data["columns"], f"{path}.columns", minimum=1
        ),
        scope=_nonempty_string(data["scope"], f"{path}.scope"),
        reserved_exceptions=reserved_exceptions,
        rows_per_instance=_controlled_string(
            data["rows_per_instance"],
            f"{path}.rows_per_instance",
            _ROWS_PER_INSTANCE_VALUES,
        ),
        longitudinal_identity=longitudinal_identity,
    )


def _parse_reserved_identity_exception(
    value: object, path: str
) -> ReservedIdentityException:
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data,
        _RESERVED_IDENTITY_EXCEPTION_KEYS,
        _RESERVED_IDENTITY_EXCEPTION_KEYS,
        path,
    )
    return ReservedIdentityException(
        column=_physical_component(data["column"], f"{path}.column"),
        representation=_nonempty_string(
            data["representation"], f"{path}.representation"
        ),
        meaning=_nonempty_string(data["meaning"], f"{path}.meaning"),
        claim_refs=_claim_ref_array(
            data["claim_refs"], f"{path}.claim_refs"
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _parse_table(profile: str, value: object, path: str) -> TableSpec:
    data = _expect_mapping(value, path)
    _require_exact_keys(data, _TABLE_REQUIRED_KEYS, _TABLE_KEYS, path)
    keys = tuple(
        _parse_key(raw, f"{path}.keys[{index}]")
        for index, raw in enumerate(
            _expect_list(data["keys"], f"{path}.keys")
        )
    )
    return TableSpec(
        profile=profile,
        table=_physical_component(data["table"], f"{path}.table"),
        grain=_controlled_string(
            data["grain"], f"{path}.grain", BINDING_GRAINS
        ),
        keys=keys,
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
        id=(_identifier(data["id"], f"{path}.id") if "id" in data else None),
    )


def _parse_key(value: object, path: str) -> KeyCandidate:
    data = _expect_mapping(value, path)
    _require_exact_keys(data, _KEY_KEYS, _KEY_KEYS, path)
    return KeyCandidate(
        id=_identifier(data["id"], f"{path}.id"),
        columns=_physical_component_array(
            data["columns"], f"{path}.columns", minimum=1
        ),
        kind=_controlled_string(
            data["kind"], f"{path}.kind", KEY_KINDS
        ),
        uniqueness=_controlled_string(
            data["uniqueness"], f"{path}.uniqueness", KEY_UNIQUENESS
        ),
        completeness=_controlled_string(
            data["completeness"],
            f"{path}.completeness",
            KEY_COMPLETENESS,
        ),
        evidence=_evidence_array(data["evidence"], f"{path}.evidence"),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _parse_relationship_binding(
    profile: str, value: object, path: str
) -> RelationshipBinding:
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data,
        _RELATIONSHIP_BINDING_KEYS,
        _RELATIONSHIP_BINDING_KEYS,
        path,
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
    return RelationshipBinding(
        id=_identifier(data["id"], f"{path}.id"),
        profile=profile,
        kind=_controlled_string(
            data["kind"],
            f"{path}.kind",
            RELATIONSHIP_BINDING_KINDS,
        ),
        semantic_relationships=_identifier_array(
            data["semantic_relationships"],
            f"{path}.semantic_relationships",
        ),
        source=_parse_relationship_endpoint(
            data["source"], f"{path}.source", source=True
        ),
        target=_parse_relationship_endpoint(
            data["target"], f"{path}.target", source=False
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
        claim_refs=_claim_ref_array(
            data["claim_refs"], f"{path}.claim_refs"
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
        join_hazards=_string_array(
            data["join_hazards"], f"{path}.join_hazards"
        ),
    )


def _parse_relationship_endpoint(
    value: object, path: str, *, source: bool
) -> RelationshipEndpoint:
    data = _expect_mapping(value, path)
    keys = _SOURCE_ENDPOINT_KEYS if source else _TARGET_ENDPOINT_KEYS
    _require_exact_keys(data, keys, keys, path)
    completeness = (
        _controlled_string(
            data["completeness"],
            f"{path}.completeness",
            ENDPOINT_COMPLETENESS,
        )
        if source
        else None
    )
    return RelationshipEndpoint(
        table=_physical_component(data["table"], f"{path}.table"),
        columns=_physical_component_array(
            data["columns"], f"{path}.columns", minimum=1
        ),
        completeness=completeness,
    )


def _parse_relationship_binding_path(
    profile: str, value: object, path: str
) -> RelationshipBindingPath:
    data = _expect_mapping(value, path)
    _require_exact_keys(
        data,
        _RELATIONSHIP_BINDING_PATH_KEYS,
        _RELATIONSHIP_BINDING_PATH_KEYS,
        path,
    )
    return RelationshipBindingPath(
        id=_identifier(data["id"], f"{path}.id"),
        profile=profile,
        semantic_relationship=_identifier(
            data["semantic_relationship"], f"{path}.semantic_relationship"
        ),
        relationship_bindings=_identifier_array(
            data["relationship_bindings"],
            f"{path}.relationship_bindings",
            minimum=1,
        ),
        description=_nonempty_string(
            data["description"], f"{path}.description"
        ),
        claim_refs=_claim_ref_array(
            data["claim_refs"], f"{path}.claim_refs"
        ),
        caveats=_string_array(data["caveats"], f"{path}.caveats"),
    )


def _validate_catalog(
    *,
    clinical_objects: Mapping[str, ClinicalObject],
    concepts: Mapping[str, Concept],
    semantic_relationships: Mapping[str, SemanticRelationship],
    temporal_semantics: Mapping[str, TemporalSemantic],
    aggregations: Mapping[str, Aggregation],
    guardrails: Mapping[str, Guardrail],
    coverage: Mapping[str, Coverage],
    vocabularies: Mapping[str, Vocabulary],
    sources: Mapping[str, ContextSource],
    contexts: Mapping[str, ClinicalContext],
    profile_bindings: Mapping[str, ProfileBinding],
) -> None:
    profiles = frozenset(profile_bindings)
    claims = {
        f"{context.id}#{claim.id}": (context, claim)
        for context in contexts.values()
        for claim in context.claims
    }
    _validate_contexts(
        contexts=contexts,
        sources=sources,
        concepts=concepts,
        profile_bindings=profile_bindings,
    )

    for item in clinical_objects.values():
        _validate_claim_refs(item.claim_refs, claims, f"clinical object {item.id!r}")

    for concept in concepts.values():
        missing_objects = sorted(
            set(concept.objects) - set(clinical_objects)
        )
        if missing_objects:
            raise CatalogValidationError(
                f"concept {concept.id!r} references unknown clinical objects: "
                + ", ".join(missing_objects)
            )
        if concept.vocabulary and concept.vocabulary not in vocabularies:
            raise CatalogValidationError(
                f"concept {concept.id!r} references unknown vocabulary "
                f"{concept.vocabulary!r}"
            )
        missing_temporal = sorted(
            set(concept.temporal_semantics) - set(temporal_semantics)
        )
        if missing_temporal:
            raise CatalogValidationError(
                f"concept {concept.id!r} references unknown temporal semantics: "
                + ", ".join(missing_temporal)
            )
        missing_aggregations = sorted(
            set(concept.aggregations) - set(aggregations)
        )
        if missing_aggregations:
            raise CatalogValidationError(
                f"concept {concept.id!r} references unknown aggregations: "
                + ", ".join(missing_aggregations)
            )
        _validate_claim_refs(
            concept.claim_refs, claims, f"concept {concept.id!r}"
        )
        for state in concept.missing_states:
            _validate_claim_refs(
                state.claim_refs,
                claims,
                f"concept {concept.id!r} missing state {state.id!r}",
            )

    for relationship in semantic_relationships.values():
        for name, identifier in (
            ("source_object", relationship.source_object),
            ("target_object", relationship.target_object),
        ):
            if identifier not in clinical_objects:
                raise CatalogValidationError(
                    f"semantic relationship {relationship.id!r} {name} "
                    f"references unknown clinical object {identifier!r}"
                )
        _validate_claim_refs(
            relationship.claim_refs,
            claims,
            f"semantic relationship {relationship.id!r}",
        )
        missing_temporal = sorted(
            set(relationship.temporal_semantics) - set(temporal_semantics)
        )
        if missing_temporal:
            raise CatalogValidationError(
                f"semantic relationship {relationship.id!r} references "
                "unknown temporal semantics: " + ", ".join(missing_temporal)
            )
    _validate_semantic_hierarchy_acyclic(semantic_relationships)

    for temporal in temporal_semantics.values():
        missing_objects = sorted(
            set(temporal.objects) - set(clinical_objects)
        )
        if missing_objects:
            raise CatalogValidationError(
                f"temporal semantic {temporal.id!r} references unknown objects: "
                + ", ".join(missing_objects)
            )
        missing_features = sorted(
            set(temporal.feature_refs) - set(concepts)
        )
        if missing_features:
            raise CatalogValidationError(
                f"temporal semantic {temporal.id!r} references unknown features: "
                + ", ".join(missing_features)
            )
        incompatible_features = sorted(
            feature
            for feature in temporal.feature_refs
            if not (
                set(concepts[feature].objects)
                & set(temporal.objects)
            )
        )
        if incompatible_features:
            raise CatalogValidationError(
                f"temporal semantic {temporal.id!r} feature_refs do not "
                "belong to any referenced temporal object: "
                + ", ".join(incompatible_features)
            )
        missing_relative = sorted(
            set(temporal.relative_to) - set(temporal_semantics)
        )
        if missing_relative:
            raise CatalogValidationError(
                f"temporal semantic {temporal.id!r} has unknown relative_to IDs: "
                + ", ".join(missing_relative)
            )
        _validate_claim_refs(
            temporal.claim_refs,
            claims,
            f"temporal semantic {temporal.id!r}",
        )
    _validate_temporal_acyclic(temporal_semantics)

    for aggregation in aggregations.values():
        for name, identifier in (
            ("source_object", aggregation.source_object),
            ("target_object", aggregation.target_object),
        ):
            if identifier not in clinical_objects:
                raise CatalogValidationError(
                    f"aggregation {aggregation.id!r} {name} references "
                    f"unknown clinical object {identifier!r}"
                )
        if aggregation.source_concept not in concepts:
            raise CatalogValidationError(
                f"aggregation {aggregation.id!r} references unknown "
                f"source_concept {aggregation.source_concept!r}"
            )
        if (
            aggregation.source_object
            not in concepts[aggregation.source_concept].objects
        ):
            raise CatalogValidationError(
                f"aggregation {aggregation.id!r} source_concept "
                f"{aggregation.source_concept!r} does not belong to "
                f"source_object {aggregation.source_object!r}"
            )
        if (
            aggregation.result_concept is not None
            and aggregation.result_concept not in concepts
        ):
            raise CatalogValidationError(
                f"aggregation {aggregation.id!r} references unknown "
                f"result_concept {aggregation.result_concept!r}"
            )
        if aggregation.status == "provided" and aggregation.result_concept is None:
            raise CatalogValidationError(
                f"provided aggregation {aggregation.id!r} requires result_concept"
            )
        if (
            aggregation.status in {"analyst_defined", "unsupported"}
            and aggregation.result_concept is not None
        ):
            raise CatalogValidationError(
                f"{aggregation.status} aggregation {aggregation.id!r} "
                "must not select a result_concept"
            )
        if (
            aggregation.result_concept is not None
            and aggregation.target_object
            not in concepts[aggregation.result_concept].objects
        ):
            raise CatalogValidationError(
                f"aggregation {aggregation.id!r} result_concept "
                f"{aggregation.result_concept!r} does not belong to "
                f"target_object {aggregation.target_object!r}"
            )
        missing_relationships = sorted(
            set(aggregation.semantic_relationships)
            - set(semantic_relationships)
        )
        if missing_relationships:
            raise CatalogValidationError(
                f"aggregation {aggregation.id!r} references unknown "
                "semantic relationships: " + ", ".join(missing_relationships)
            )
        _validate_claim_refs(
            aggregation.claim_refs,
            claims,
            f"aggregation {aggregation.id!r}",
        )

    entity_maps: dict[str, Mapping[str, Any]] = {
        "clinical_object": clinical_objects,
        "concept": concepts,
        "semantic_relationship": semantic_relationships,
        "temporal_semantic": temporal_semantics,
        "aggregation": aggregations,
        "guardrail": guardrails,
        "topic": contexts,
    }
    for record in coverage.values():
        if record.subject not in entity_maps[record.subject_kind]:
            raise CatalogValidationError(
                f"coverage {record.id!r} references unknown "
                f"{record.subject_kind} subject {record.subject!r}"
            )
        _validate_scoped_claim_refs(
            scope=record.scope,
            profiles=record.profiles,
            references=record.claim_refs,
            claims=claims,
            label=f"coverage {record.id!r}",
        )

    for temporal in temporal_semantics.values() if profile_bindings else ():
        if temporal.feature_refs:
            continue
        qualifying = [
            record
            for record in coverage.values()
            if record.subject_kind == "temporal_semantic"
            and record.subject == temporal.id
            and record.status in {"unsupported", "unresolved"}
        ]
        if not qualifying:
            raise CatalogValidationError(
                f"temporal semantic {temporal.id!r} has no feature_refs and "
                "requires unsupported or unresolved coverage"
            )
        generally_covered = any(
            record.scope in {"general_clinical", "embed_general"}
            for record in qualifying
        )
        covered_profiles = {
            profile
            for record in qualifying
            if record.scope == "profile_specific"
            for profile in record.profiles
        }
        missing_profiles = (
            [] if generally_covered else sorted(profiles - covered_profiles)
        )
        if missing_profiles:
            raise CatalogValidationError(
                f"temporal semantic {temporal.id!r} has no feature_refs and "
                "lacks unsupported or unresolved coverage for profiles: "
                + ", ".join(missing_profiles)
            )

    for guardrail in guardrails.values():
        references = (
            ("objects", guardrail.objects, clinical_objects),
            ("concepts", guardrail.concepts, concepts),
            (
                "semantic_relationships",
                guardrail.semantic_relationships,
                semantic_relationships,
            ),
            (
                "temporal_semantics",
                guardrail.temporal_semantics,
                temporal_semantics,
            ),
            ("aggregations", guardrail.aggregations, aggregations),
            ("coverage", guardrail.coverage, coverage),
        )
        for name, identifiers, target in references:
            missing = sorted(set(identifiers) - set(target))
            if missing:
                raise CatalogValidationError(
                    f"guardrail {guardrail.id!r} {name} references unknown IDs: "
                    + ", ".join(missing)
                )
        _validate_scoped_claim_refs(
            scope=guardrail.scope,
            profiles=guardrail.profiles,
            references=guardrail.claim_refs,
            claims=claims,
            label=f"guardrail {guardrail.id!r}",
        )

    _validate_profile_bindings(
        profile_bindings=profile_bindings,
        concepts=concepts,
        vocabularies=vocabularies,
        clinical_objects=clinical_objects,
        semantic_relationships=semantic_relationships,
        claims=claims,
    )

    concept_profiles: defaultdict[str, set[str]] = defaultdict(set)
    for profile in profile_bindings.values():
        for binding in profile.feature_bindings:
            concept_profiles[binding.concept].add(profile.profile)
    for record in coverage.values():
        if record.status != "supported" or record.subject_kind != "concept":
            continue
        missing_profiles = sorted(
            set(record.profiles) - concept_profiles[record.subject]
        )
        if missing_profiles:
            raise CatalogValidationError(
                f"supported coverage {record.id!r} has no feature binding in "
                "profiles: " + ", ".join(missing_profiles)
            )


def _validate_contexts(
    *,
    contexts: Mapping[str, ClinicalContext],
    sources: Mapping[str, ContextSource],
    concepts: Mapping[str, Concept],
    profile_bindings: Mapping[str, ProfileBinding],
) -> None:
    table_ids = {
        table.identifier
        for profile in profile_bindings.values()
        for table in profile.tables
    }
    relationship_ids = {
        relationship.id: relationship
        for profile in profile_bindings.values()
        for relationship in profile.relationship_bindings
    }
    authoritative = {
        "maintainer_confirmed",
        "release_schema",
        "release_legend",
    }
    for context in contexts.values():
        missing_concepts = sorted(
            set(context.related_concepts) - set(concepts)
        )
        if missing_concepts:
            raise CatalogValidationError(
                f"context {context.id!r} references unknown concepts: "
                + ", ".join(missing_concepts)
            )
        for table in context.related_tables:
            if table.identifier not in table_ids:
                raise CatalogValidationError(
                    f"context {context.id!r} references unknown table "
                    f"{table.identifier!r}"
                )
            if table.profile not in context.profiles:
                raise CatalogValidationError(
                    f"context {context.id!r} references table outside profiles: "
                    f"{table.identifier!r}"
                )
        for identifier in context.related_relationships:
            relationship = relationship_ids.get(identifier)
            if relationship is None:
                raise CatalogValidationError(
                    f"context {context.id!r} references unknown physical "
                    f"relationship {identifier!r}"
                )
            if relationship.profile not in context.profiles:
                raise CatalogValidationError(
                    f"context {context.id!r} references relationship outside "
                    f"profiles: {identifier!r}"
                )
        for claim in context.claims:
            missing_sources = sorted(set(claim.sources) - set(sources))
            if missing_sources:
                raise CatalogValidationError(
                    f"context {context.id!r} claim {claim.id!r} references "
                    "unknown sources: " + ", ".join(missing_sources)
                )
            claim_sources = [sources[item] for item in claim.sources]
            if context.scope != "profile_specific":
                incompatible = sorted(
                    item.id
                    for item in claim_sources
                    if item.scope != context.scope
                )
                if incompatible:
                    raise CatalogValidationError(
                        f"context {context.id!r} claim {claim.id!r} has "
                        "incompatible source scope: " + ", ".join(incompatible)
                    )
            else:
                for source in claim_sources:
                    if source.scope == "profile_specific" and not set(
                        context.profiles
                    ).issubset(source.profiles):
                        raise CatalogValidationError(
                            f"context {context.id!r} claim {claim.id!r} "
                            f"uses source {source.id!r} outside profiles"
                        )
                if claim.status == "verified" and not any(
                    source.scope == "profile_specific"
                    and source.kind in authoritative
                    and set(context.profiles).issubset(source.profiles)
                    for source in claim_sources
                ):
                    raise CatalogValidationError(
                        f"context {context.id!r} claim {claim.id!r} is verified "
                        "but has no applicable authoritative profile source"
                    )
            if claim.status == "contradicted" and len(claim.sources) < 2:
                raise CatalogValidationError(
                    f"contradicted claim {context.id}#{claim.id} must cite "
                    "at least two sources"
                )


def _validate_claim_refs(
    references: Sequence[str],
    claims: Mapping[str, tuple[ClinicalContext, ContextClaim]],
    label: str,
) -> None:
    missing = sorted(set(references) - set(claims))
    if missing:
        raise CatalogValidationError(
            f"{label} references unknown claims: " + ", ".join(missing)
        )


def _validate_scoped_claim_refs(
    *,
    scope: str,
    profiles: Sequence[str],
    references: Sequence[str],
    claims: Mapping[str, tuple[ClinicalContext, ContextClaim]],
    label: str,
) -> None:
    _validate_claim_refs(references, claims, label)
    for reference in references:
        context, _ = claims[reference]
        if scope == "general_clinical":
            if context.scope != "general_clinical":
                raise CatalogValidationError(
                    f"{label} claim {reference!r} has scope "
                    f"{context.scope!r}, expected general_clinical"
                )
        elif scope == "embed_general":
            if context.scope not in {"general_clinical", "embed_general"}:
                raise CatalogValidationError(
                    f"{label} claim {reference!r} has incompatible scope "
                    f"{context.scope!r}"
                )
        elif (
            context.scope == "profile_specific"
            and not set(profiles).issubset(context.profiles)
        ):
            raise CatalogValidationError(
                f"{label} claim {reference!r} is outside selected profiles"
            )


def _validate_profile_bindings(
    *,
    profile_bindings: Mapping[str, ProfileBinding],
    concepts: Mapping[str, Concept],
    vocabularies: Mapping[str, Vocabulary],
    clinical_objects: Mapping[str, ClinicalObject],
    semantic_relationships: Mapping[str, SemanticRelationship],
    claims: Mapping[str, tuple[ClinicalContext, ContextClaim]],
) -> None:
    empty_profiles = sorted(
        profile_id
        for profile_id, profile in profile_bindings.items()
        if not profile.feature_bindings
    )
    if empty_profiles:
        raise CatalogValidationError(
            "catalog profiles have no physical bindings: "
            + ", ".join(empty_profiles)
        )
    global_relationship_ids: set[str] = set()
    global_relationship_path_ids: set[str] = set()
    qualified_bindings: dict[str, Binding] = {}
    for profile_id, profile in profile_bindings.items():
        columns_by_table: defaultdict[str, dict[str, Binding]] = defaultdict(dict)
        grains_by_table: defaultdict[str, set[str]] = defaultdict(set)
        for binding in profile.feature_bindings:
            if binding.concept not in concepts:
                raise CatalogValidationError(
                    f"feature binding {binding.qualified_identifier!r} "
                    f"references unknown concept {binding.concept!r}"
                )
            if (
                binding.vocabulary is not None
                and binding.vocabulary not in vocabularies
            ):
                raise CatalogValidationError(
                    f"feature binding {binding.qualified_identifier!r} "
                    f"references unknown vocabulary {binding.vocabulary!r}"
                )
            previous = qualified_bindings.get(binding.qualified_identifier)
            if previous is not None:
                declared_coexistence = (
                    previous.id is not None
                    and binding.id is not None
                    and (
                        previous.id in binding.coexists_with
                        or binding.id in previous.coexists_with
                    )
                )
                if not declared_coexistence:
                    raise CatalogValidationError(
                        f"duplicate physical binding "
                        f"{binding.qualified_identifier!r}"
                    )
                if (
                    previous.physical_type != binding.physical_type
                    or previous.nullable != binding.nullable
                ):
                    raise CatalogValidationError(
                        f"coexisting physical binding "
                        f"{binding.qualified_identifier!r} has incompatible "
                        "physical metadata"
                    )
            qualified_bindings[binding.qualified_identifier] = binding
            columns_by_table[binding.table][binding.column] = binding
            grains_by_table[binding.table].add(binding.grain)
            for interpretation in binding.occurrence_interpretations:
                _validate_scoped_claim_refs(
                    scope="profile_specific",
                    profiles=(profile_id,),
                    references=interpretation.claim_refs,
                    claims=claims,
                    label=(
                        "feature binding "
                        f"{binding.qualified_identifier!r} occurrence "
                        f"{interpretation.representation!r}"
                    ),
                )

        tables_by_name: dict[str, TableSpec] = {}
        for table in profile.tables:
            if table.table in tables_by_name:
                raise CatalogValidationError(
                    f"duplicate table specification {table.identifier!r}"
                )
            tables_by_name[table.table] = table
            columns = columns_by_table.get(table.table)
            if not columns:
                raise CatalogValidationError(
                    f"table specification {table.identifier!r} has no "
                    "feature bindings"
                )
            if grains_by_table[table.table] != {table.grain}:
                raise CatalogValidationError(
                    f"table {table.identifier!r} grain {table.grain!r} "
                    "does not match feature-binding grains"
                )
            seen_key_ids: set[str] = set()
            key_declarations: dict[
                tuple[str, ...], tuple[str, str, str]
            ] = {}
            for key in table.keys:
                if key.id in seen_key_ids:
                    raise CatalogValidationError(
                        f"table {table.identifier!r} has duplicate key ID "
                        f"{key.id!r}"
                    )
                seen_key_ids.add(key.id)
                missing = sorted(set(key.columns) - set(columns))
                if missing:
                    raise CatalogValidationError(
                        f"table {table.identifier!r} key {key.id!r} "
                        "references unknown columns: " + ", ".join(missing)
                    )
                declaration = (
                    key.kind,
                    key.uniqueness,
                    key.completeness,
                )
                previous = key_declarations.setdefault(
                    key.columns, declaration
                )
                if previous != declaration:
                    raise CatalogValidationError(
                        f"table {table.identifier!r} has conflicting key "
                        f"declarations for columns {list(key.columns)!r}"
                    )
        missing_tables = sorted(set(columns_by_table) - set(tables_by_name))
        if missing_tables:
            raise CatalogValidationError(
                f"profile {profile_id!r} feature bindings lack table "
                "specifications: " + ", ".join(missing_tables)
            )

        seen_object_bindings: set[tuple[str, str, tuple[str, ...]]] = set()
        for binding in profile.object_bindings:
            if binding.object not in clinical_objects:
                raise CatalogValidationError(
                    f"object binding references unknown clinical object "
                    f"{binding.object!r}"
                )
            columns = columns_by_table.get(binding.table)
            if columns is None:
                raise CatalogValidationError(
                    f"object binding references unknown profile table "
                    f"{profile_id}:{binding.table}"
                )
            missing = sorted(set(binding.columns) - set(columns))
            if missing:
                raise CatalogValidationError(
                    f"object binding {profile_id}:{binding.table} references "
                    "unknown columns: " + ", ".join(missing)
                )
            identity = (binding.object, binding.table, binding.columns)
            if identity in seen_object_bindings:
                raise CatalogValidationError(
                    f"duplicate object binding for {binding.object!r} in "
                    f"{profile_id}:{binding.table}"
                )
            seen_object_bindings.add(identity)
            if binding.instance_identity is not None:
                instance_identity = binding.instance_identity
                missing_identity_columns = sorted(
                    set(instance_identity.columns) - set(binding.columns)
                )
                if missing_identity_columns:
                    raise CatalogValidationError(
                        f"object binding {profile_id}:{binding.table} "
                        "instance_identity references columns outside the "
                        "object binding: "
                        + ", ".join(missing_identity_columns)
                    )
                for exception in instance_identity.reserved_exceptions:
                    if exception.column not in instance_identity.columns:
                        raise CatalogValidationError(
                            f"object binding {profile_id}:{binding.table} "
                            "reserved identity exception references "
                            f"non-identity column {exception.column!r}"
                        )
                    _validate_scoped_claim_refs(
                        scope="profile_specific",
                        profiles=(profile_id,),
                        references=exception.claim_refs,
                        claims=claims,
                        label=(
                            f"object binding {profile_id}:{binding.table} "
                            f"reserved identity exception "
                            f"{exception.column}="
                            f"{exception.representation}"
                        ),
                    )
            _validate_scoped_claim_refs(
                scope="profile_specific",
                profiles=(profile_id,),
                references=binding.claim_refs,
                claims=claims,
                label=f"object binding {profile_id}:{binding.table}",
            )

        for relationship in profile.relationship_bindings:
            if relationship.id in global_relationship_ids:
                raise CatalogValidationError(
                    f"duplicate relationship binding ID {relationship.id!r}"
                )
            global_relationship_ids.add(relationship.id)
            missing_semantic = sorted(
                set(relationship.semantic_relationships)
                - set(semantic_relationships)
            )
            if missing_semantic:
                raise CatalogValidationError(
                    f"relationship binding {relationship.id!r} references "
                    "unknown semantic relationships: "
                    + ", ".join(missing_semantic)
                )
            _validate_scoped_claim_refs(
                scope="profile_specific",
                profiles=(profile_id,),
                references=relationship.claim_refs,
                claims=claims,
                label=f"relationship binding {relationship.id!r}",
            )
            _validate_physical_relationship(
                relationship, columns_by_table, tables_by_name
            )
        _validate_physical_hierarchy_acyclic(profile.relationship_bindings)
        relationships_by_id = {
            relationship.id: relationship
            for relationship in profile.relationship_bindings
        }
        for path in profile.relationship_binding_paths:
            if path.id in global_relationship_path_ids:
                raise CatalogValidationError(
                    f"duplicate relationship binding path ID {path.id!r}"
                )
            global_relationship_path_ids.add(path.id)
            if path.semantic_relationship not in semantic_relationships:
                raise CatalogValidationError(
                    f"relationship binding path {path.id!r} references "
                    "unknown semantic relationship "
                    f"{path.semantic_relationship!r}"
                )
            missing_steps = sorted(
                set(path.relationship_bindings) - set(relationships_by_id)
            )
            if missing_steps:
                raise CatalogValidationError(
                    f"relationship binding path {path.id!r} references "
                    "unknown relationship bindings in profile "
                    f"{profile_id!r}: " + ", ".join(missing_steps)
                )
            steps = [
                relationships_by_id[identifier]
                for identifier in path.relationship_bindings
            ]
            for previous, following in zip(steps, steps[1:]):
                if previous.target.table != following.source.table:
                    raise CatalogValidationError(
                        f"relationship binding path {path.id!r} has "
                        "non-adjacent steps "
                        f"{previous.id!r} and {following.id!r}: "
                        f"{previous.target.table!r} does not match "
                        f"{following.source.table!r}"
                    )
            _validate_scoped_claim_refs(
                scope="profile_specific",
                profiles=(profile_id,),
                references=path.claim_refs,
                claims=claims,
                label=f"relationship binding path {path.id!r}",
            )


def _validate_physical_relationship(
    relationship: RelationshipBinding,
    columns_by_table: Mapping[str, Mapping[str, Binding]],
    tables_by_name: Mapping[str, TableSpec],
) -> None:
    source_columns = columns_by_table.get(relationship.source.table)
    target_columns = columns_by_table.get(relationship.target.table)
    if source_columns is None:
        raise CatalogValidationError(
            f"relationship binding {relationship.id!r} references unknown "
            f"source table {relationship.profile}:{relationship.source.table}"
        )
    if target_columns is None:
        raise CatalogValidationError(
            f"relationship binding {relationship.id!r} references unknown "
            f"target table {relationship.profile}:{relationship.target.table}"
        )
    if len(relationship.source.columns) != len(relationship.target.columns):
        raise CatalogValidationError(
            f"relationship binding {relationship.id!r} endpoint column "
            "tuples must have equal length"
        )
    for name, endpoint, available in (
        ("source", relationship.source, source_columns),
        ("target", relationship.target, target_columns),
    ):
        missing = sorted(set(endpoint.columns) - set(available))
        if missing:
            raise CatalogValidationError(
                f"relationship binding {relationship.id!r} {name} "
                "references unknown columns: " + ", ".join(missing)
            )
    for source, target in zip(
        relationship.source.columns,
        relationship.target.columns,
        strict=True,
    ):
        if source_columns[source].physical_type != target_columns[target].physical_type:
            raise CatalogValidationError(
                f"relationship binding {relationship.id!r} has incompatible "
                f"physical types for {source!r} and {target!r}"
            )
    source_table = tables_by_name[relationship.source.table]
    target_table = tables_by_name[relationship.target.table]
    contradictory = {
        "required": "incomplete",
        "optional": "complete",
    }.get(relationship.source.completeness)
    if contradictory and any(
        key.columns == relationship.source.columns
        and key.completeness == contradictory
        for key in source_table.keys
    ):
        raise CatalogValidationError(
            f"relationship binding {relationship.id!r} source completeness "
            "contradicts the documented key"
        )
    if (
        relationship.targets_per_source in {"exactly_one", "one_or_more"}
        and relationship.source.completeness != "required"
    ):
        raise CatalogValidationError(
            f"relationship binding {relationship.id!r} claims at least one "
            "target, so source completeness must be required"
        )
    if relationship.targets_per_source in {"exactly_one", "zero_or_one"}:
        if not any(
            key.columns == relationship.target.columns
            and key.uniqueness == "unique"
            for key in target_table.keys
        ):
            raise CatalogValidationError(
                f"relationship binding {relationship.id!r} claims at most "
                "one target but target columns are not a unique key"
            )
    if relationship.sources_per_target in {"exactly_one", "zero_or_one"}:
        if not any(
            key.columns == relationship.source.columns
            and key.uniqueness == "unique"
            for key in source_table.keys
        ):
            raise CatalogValidationError(
                f"relationship binding {relationship.id!r} claims at most "
                "one source but source columns are not a unique key"
            )


def _validate_semantic_hierarchy_acyclic(
    relationships: Mapping[str, SemanticRelationship],
) -> None:
    graph: defaultdict[str, set[str]] = defaultdict(set)
    nodes: set[str] = set()
    for item in relationships.values():
        if item.kind != "hierarchy":
            continue
        graph[item.source_object].add(item.target_object)
        nodes.update((item.source_object, item.target_object))
    _validate_acyclic(graph, nodes, "semantic hierarchy")


def _validate_temporal_acyclic(
    temporals: Mapping[str, TemporalSemantic],
) -> None:
    graph = {
        identifier: set(item.relative_to)
        for identifier, item in temporals.items()
    }
    _validate_acyclic(graph, set(temporals), "temporal relative_to")


def _validate_physical_hierarchy_acyclic(
    relationships: Sequence[RelationshipBinding],
) -> None:
    graph: defaultdict[str, set[str]] = defaultdict(set)
    nodes: set[str] = set()
    for item in relationships:
        if item.kind != "hierarchy":
            continue
        graph[item.source.table].add(item.target.table)
        nodes.update((item.source.table, item.target.table))
    _validate_acyclic(graph, nodes, "physical hierarchy")


def _validate_acyclic(
    graph: Mapping[Any, set[Any]], nodes: set[Any], label: str
) -> None:
    visiting: set[Any] = set()
    visited: set[Any] = set()

    def visit(node: Any) -> None:
        if node in visited:
            return
        if node in visiting:
            raise CatalogValidationError(f"{label} must be acyclic")
        visiting.add(node)
        for target in graph.get(node, set()):
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(nodes):
        visit(node)


def default_catalog_path() -> Path:
    """Return the source-tree or installed-package catalog path."""

    package_directory = Path(__file__).resolve().parent
    source_catalog = package_directory.parent / "catalog" / "catalog-set.json"
    if source_catalog.is_file():
        return source_catalog
    installed_manifest = package_directory / "_data" / "catalog-set.json"
    return installed_manifest if installed_manifest.is_file() else package_directory / "_data" / "catalog.json"


@dataclass(frozen=True, slots=True)
class _ResolvedDocument:
    """Immutable authored input retained by the canonical catalog resolver."""

    kind: str
    locator_kind: str
    source_path: Path
    source_bytes: bytes
    source_digest: str
    mapping: Mapping[str, Any]
    schema_resource: str
    module_id: str | None = None
    version: str | None = None
    lifecycle_status: str | None = None
    target_profile: str | None = None
    dependency_order: int | None = None

    def mutable_mapping(self) -> dict[str, Any]:
        """Return an isolated JSON-compatible copy for draft editing."""

        return _mutable_json(self.mapping)


@dataclass(frozen=True, slots=True)
class _ResolvedComposition:
    """Validated authored snapshots and their effective query catalog."""

    documents: tuple[_ResolvedDocument, ...]
    catalog: Catalog
    configuration_fingerprint: str | None

    def document_for_path(self, path: str | Path) -> _ResolvedDocument:
        candidate = Path(path).resolve()
        matches = tuple(
            document
            for document in self.documents
            if document.source_path.resolve() == candidate
        )
        if len(matches) != 1:
            raise CatalogValidationError(
                f"resolved path {path} identifies {len(matches)} loaded documents",
                stage="composition",
                document=path,
            )
        return matches[0]


def load_catalog(
    catalog_set: str | Path | None = None,
    *,
    profile_paths: Sequence[str | Path] | None = None,
    extension_paths: Sequence[str | Path] | None = None,
    include_default_profiles: bool = True,
    include_default_extensions: bool = False,
) -> Catalog:
    """Read a legacy v6 catalog or compose a schema-v7 catalog set.

    JSON duplicate keys and the non-standard ``NaN``/``Infinity`` constants
    are rejected before semantic validation so the resulting catalog has one
    deterministic interpretation.
    """

    return _resolve_catalog(
        catalog_set,
        profile_paths=profile_paths,
        extension_paths=extension_paths,
        include_default_profiles=include_default_profiles,
        include_default_extensions=include_default_extensions,
    ).catalog


def _resolve_catalog(
    catalog_set: str | Path | None = None,
    *,
    profile_paths: Sequence[str | Path] | None = None,
    extension_paths: Sequence[str | Path] | None = None,
    include_default_profiles: bool = True,
    include_default_extensions: bool = False,
) -> _ResolvedComposition:
    """Resolve authored inputs once and retain immutable validated snapshots."""

    catalog_path = default_catalog_path() if catalog_set is None else Path(catalog_set)
    root_locator_kind = "bundled" if catalog_set is None else "explicit"
    value, source_bytes = _read_json_document_with_bytes(catalog_path)
    documents: list[_ResolvedDocument] = []
    if "schema_version" in value:
        if profile_paths or extension_paths:
            raise CatalogValidationError(
                "legacy schema-v6 catalogs cannot be composed with module files",
                stage="composition",
                document=catalog_path,
            )
        _validate_json_schema(value, catalog_path, _schema_path_for("catalog.schema.json"))
        document = _resolved_document(
            "legacy", root_locator_kind, catalog_path, source_bytes, value,
            "catalog.schema.json",
        )
        try:
            catalog = Catalog.from_mapping(value)
        except CatalogValidationError as exc:
            if exc.stage is None:
                exc.stage = "domain"
            if exc.document is None:
                exc.document = str(catalog_path)
            raise
        return _ResolvedComposition((document,), catalog, None)
    if "semantic_schema_version" in value:
        _validate_json_schema(
            value,
            catalog_path,
            _schema_path_for("semantic/catalog.schema.json"),
        )
        semantic = value
        documents.append(
            _resolved_document(
                "semantic", root_locator_kind, catalog_path, source_bytes, value,
                "semantic/catalog.schema.json",
            )
        )
        manifest = None
        default_profiles: list[tuple[Path, str]] = []
        default_extensions: list[tuple[Path, str]] = []
    elif "catalog_set_schema_version" in value:
        manifest = value
        manifest_path = catalog_path
        _validate_json_schema(manifest, manifest_path, _schema_path_for("catalog-set.schema.json"))
        documents.append(
            _resolved_document(
                "manifest", root_locator_kind, catalog_path, source_bytes, value,
                "catalog-set.schema.json",
            )
        )
        semantic_path, semantic_locator = _resolve_locator_details(
            manifest["semantic_catalog"], manifest_path, "semantic_catalog"
        )
        semantic, semantic_bytes = _read_and_validate_module_with_bytes(
            semantic_path, "semantic/catalog.schema.json"
        )
        documents.append(
            _resolved_document(
                "semantic", semantic_locator, semantic_path, semantic_bytes,
                semantic, "semantic/catalog.schema.json",
            )
        )
        default_profiles = [
            _resolve_locator_details(item, manifest_path, f"profiles[{index}]")
            for index, item in enumerate(manifest["profiles"])
        ] if include_default_profiles else []
        default_extensions = [
            _resolve_locator_details(item, manifest_path, f"extensions[{index}]")
            for index, item in enumerate(manifest["extensions"])
        ] if include_default_extensions else []
    else:
        raise CatalogValidationError(
            f"{catalog_path}: unknown catalog document discriminator",
            stage="composition",
            document=catalog_path,
            json_pointer="$",
        )
    profile_inputs = (*default_profiles, *((Path(p), "explicit") for p in profile_paths or ()))
    extension_inputs = (*default_extensions, *((Path(p), "explicit") for p in extension_paths or ()))
    profiles: list[Mapping[str, Any]] = []
    for path, locator_kind in profile_inputs:
        mapping, module_bytes = _read_and_validate_module_with_bytes(
            path, "profiles/profile.schema.json"
        )
        profiles.append(mapping)
        documents.append(
            _resolved_document(
                "profile", locator_kind, path, module_bytes, mapping,
                "profiles/profile.schema.json",
            )
        )
    extensions: list[Mapping[str, Any]] = []
    for path, locator_kind in extension_inputs:
        mapping, module_bytes = _read_and_validate_module_with_bytes(
            path, "extensions/extension.schema.json"
        )
        extensions.append(mapping)
        documents.append(
            _resolved_document(
                "extension", locator_kind, path, module_bytes, mapping,
                "extensions/extension.schema.json",
            )
        )
    catalog = _compose_resolved_inputs(semantic, profiles, extensions, manifest)
    extension_order = {
        identifier: index
        for index, identifier in enumerate(
            _extension_order({str(doc["extension"]["id"]): doc for doc in extensions})
        )
    }
    documents = [
        _with_dependency_order(document, extension_order)
        for document in documents
    ]
    fingerprint = catalog.configuration.get("configuration_fingerprint")
    return _ResolvedComposition(
        tuple(documents), catalog, str(fingerprint) if fingerprint else None
    )


def _replace_resolved_document(
    composition: _ResolvedComposition,
    document: _ResolvedDocument,
    replacement: Mapping[str, Any],
    *,
    source_bytes: bytes | None = None,
) -> _ResolvedComposition:
    """Validate and compose one in-memory authored-document replacement."""

    if document not in composition.documents:
        raise CatalogValidationError(
            "replacement target is not part of the resolved composition",
            stage="local",
            document=document.source_path,
        )
    if document.kind not in {"semantic", "profile", "extension"}:
        raise CatalogValidationError(
            f"{document.kind} documents cannot be replaced in memory",
            stage="local",
            document=document.source_path,
        )
    replacement_copy = _mutable_json(replacement)
    _validate_json_schema(
        replacement_copy,
        document.source_path,
        _schema_path_for(document.schema_resource),
    )
    replacement_bytes = source_bytes
    if replacement_bytes is None:
        replacement_bytes = (
            json.dumps(replacement_copy, indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8")
    replacement_document = _resolved_document(
        document.kind,
        document.locator_kind,
        document.source_path,
        replacement_bytes,
        replacement_copy,
        document.schema_resource,
    )
    documents = tuple(
        replacement_document if item is document else item
        for item in composition.documents
    )
    semantic = next(
        _mutable_json(item.mapping) for item in documents if item.kind == "semantic"
    )
    profiles = [
        _mutable_json(item.mapping) for item in documents if item.kind == "profile"
    ]
    extensions = [
        _mutable_json(item.mapping) for item in documents if item.kind == "extension"
    ]
    manifest_document = next(
        (item for item in documents if item.kind == "manifest"), None
    )
    manifest = (
        _mutable_json(manifest_document.mapping)
        if manifest_document is not None else None
    )
    try:
        catalog = _compose_catalog(semantic, profiles, extensions, manifest)
    except CatalogValidationError as exc:
        if exc.stage is None:
            exc.stage = "composition"
        if exc.document is None:
            exc.document = str(document.source_path)
        raise
    order = {
        identifier: index
        for index, identifier in enumerate(
            _extension_order({str(doc["extension"]["id"]): doc for doc in extensions})
        )
    }
    documents = tuple(_with_dependency_order(item, order) for item in documents)
    fingerprint = catalog.configuration.get("configuration_fingerprint")
    return _ResolvedComposition(
        documents, catalog, str(fingerprint) if fingerprint else None
    )


def _read_json_document(catalog_path: Path) -> Mapping[str, Any]:
    value, _ = _read_json_document_with_bytes(catalog_path)
    return value


def _read_json_document_with_bytes(
    catalog_path: Path,
) -> tuple[Mapping[str, Any], bytes]:
    try:
        source_bytes = catalog_path.read_bytes()
    except OSError as exc:
        raise CatalogLoadError(
            f"could not read catalog {catalog_path}: {exc}",
            stage="json_decode",
            document=catalog_path,
        ) from exc
    try:
        text = source_bytes.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except CatalogValidationError as exc:
        if exc.stage is None:
            exc.stage = "json_decode"
        if exc.document is None:
            exc.document = str(catalog_path)
        raise
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise CatalogLoadError(
            f"could not decode catalog {catalog_path}: {exc}",
            stage="json_decode",
            document=catalog_path,
        ) from exc
    if not isinstance(value, Mapping):
        raise CatalogValidationError(
            f"{catalog_path}: $ must be a JSON object",
            stage="json_decode",
            document=catalog_path,
            json_pointer="$",
        )
    return value, source_bytes


def _schema_path_for(resource: str) -> Path:
    """Return the version-matched schema bundled with this installation.

    Authored documents may use a relative ``$schema`` identifier for editor
    discovery, but that identifier is not an authority boundary.  In
    particular, an external module must not be able to weaken runtime
    validation by placing a same-named schema beside itself.
    """

    package = Path(__file__).resolve().parent
    source = package.parent / "catalog" / resource
    return source if source.is_file() else package / "_data" / resource


def _read_and_validate_module(path: Path, schema_resource: str) -> Mapping[str, Any]:
    value, _ = _read_and_validate_module_with_bytes(path, schema_resource)
    return value


def _read_and_validate_module_with_bytes(
    path: Path, schema_resource: str
) -> tuple[Mapping[str, Any], bytes]:
    value, source_bytes = _read_json_document_with_bytes(path)
    _validate_json_schema(value, path, _schema_path_for(schema_resource))
    return value, source_bytes


def _validate_json_schema(value: Mapping[str, Any], document_path: Path, schema_path: Path) -> None:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogLoadError(f"could not load schema {schema_path}: {exc}") from exc
    except jsonschema.ValidationError as exc:
        pointer = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in exc.absolute_path)
        raise CatalogValidationError(
            f"{document_path}: {pointer}: {exc.message}",
            stage="json_schema",
            document=document_path,
            json_pointer=pointer,
            contribution_key=_schema_contribution_key(value, exc.absolute_path),
        ) from exc


def _schema_contribution_key(
    document: Mapping[str, Any], path: Sequence[object]
) -> str | None:
    """Identify the authored record containing a schema error when possible."""

    parts = tuple(path)
    registry_kinds = {
        "clinical_objects": "clinical_object",
        "concepts": "concept",
        "semantic_relationships": "semantic_relationship",
        "temporal_semantics": "temporal_semantic",
        "aggregations": "aggregation",
        "guardrails": "guardrail",
        "coverage": "coverage",
        "vocabularies": "vocabulary",
        "sources": "source",
        "contexts": "context",
        "qualifications": "qualification",
        "feature_lineage": "feature_lineage",
    }
    offset = 0
    if len(parts) >= 1 and parts[0] == "semantic_additions":
        offset = 1
    if len(parts) >= offset + 2:
        collection = parts[offset]
        identifier = parts[offset + 1]
        if collection in registry_kinds and isinstance(identifier, str):
            return f"{registry_kinds[str(collection)]}:{identifier}"
    binding_offset = 0
    if parts[:1] in (("profile_binding",), ("binding_additions",)):
        binding_offset = 1
    if len(parts) >= binding_offset + 2:
        collection = parts[binding_offset]
        index = parts[binding_offset + 1]
        if (
            collection in {
                "feature_bindings",
                "object_bindings",
                "tables",
                "relationship_bindings",
                "relationship_binding_paths",
            }
            and isinstance(index, int)
        ):
            try:
                container = document
                if binding_offset:
                    container = container[str(parts[0])]
                record = container[str(collection)][index]
                identifier = record.get("id")
            except (KeyError, IndexError, TypeError, AttributeError):
                return None
            return f"binding:{identifier}" if identifier else None
    if len(parts) >= 2 and parts[0] == "revisions" and isinstance(parts[1], int):
        try:
            identifier = document["revisions"][parts[1]].get("id")
        except (KeyError, IndexError, TypeError, AttributeError):
            return None
        return f"revision:{identifier}" if identifier else None
    return None


def _resolve_locator(locator: object, manifest_path: Path, field: str) -> Path:
    path, _ = _resolve_locator_details(locator, manifest_path, field)
    return path


def _resolve_locator_details(
    locator: object, manifest_path: Path, field: str
) -> tuple[Path, str]:
    data = _expect_mapping(locator, f"$.{field}")
    if data.get("kind") == "file":
        path = Path(str(data["path"]))
        if path.is_absolute():
            raise CatalogValidationError(
                f"{manifest_path}: $.{field}.path must be relative to its manifest"
            )
        return manifest_path.parent / path, "file"
    if data.get("kind") == "bundled":
        root = Path(__file__).resolve().parent.parent / "catalog"
        installed = Path(__file__).resolve().parent / "_data"
        resource = Path(str(data["resource"]))
        if resource.is_absolute() or ".." in resource.parts:
            raise CatalogValidationError(
                f"{manifest_path}: $.{field}.resource must be a safe "
                "package-relative path"
            )
        candidate = root / resource
        return (candidate if candidate.is_file() else installed / resource), "bundled"
    raise CatalogValidationError(f"{manifest_path}: $.{field}.kind is not a supported locator")


def _resolved_document(
    kind: str,
    locator_kind: str,
    source_path: Path,
    source_bytes: bytes,
    mapping: Mapping[str, Any],
    schema_resource: str,
) -> _ResolvedDocument:
    module_id: str | None = None
    version: str | None = None
    lifecycle_status: str | None = None
    target_profile: str | None = None
    if kind == "semantic":
        module_id = "semantic"
    elif kind == "profile":
        profile = mapping["profile"]
        module_id = str(profile["id"])
        version = str(profile["version"]) if profile.get("version") is not None else None
        lifecycle_status = (
            str(profile["lifecycle_status"])
            if profile.get("lifecycle_status") is not None else None
        )
        target_profile = module_id
    elif kind == "extension":
        extension = mapping["extension"]
        module_id = str(extension["id"])
        version = str(extension["version"])
        lifecycle_status = str(extension["lifecycle_status"])
        target_profile = str(mapping["applies_to"]["profile"])
    return _ResolvedDocument(
        kind=kind,
        locator_kind=locator_kind,
        source_path=source_path,
        source_bytes=source_bytes,
        source_digest="sha256:" + hashlib.sha256(source_bytes).hexdigest(),
        mapping=_freeze_json(mapping),
        schema_resource=schema_resource,
        module_id=module_id,
        version=version,
        lifecycle_status=lifecycle_status,
        target_profile=target_profile,
    )


def _with_dependency_order(
    document: _ResolvedDocument, order: Mapping[str, int]
) -> _ResolvedDocument:
    if document.kind != "extension" or document.module_id not in order:
        return document
    return _ResolvedDocument(
        kind=document.kind,
        locator_kind=document.locator_kind,
        source_path=document.source_path,
        source_bytes=document.source_bytes,
        source_digest=document.source_digest,
        mapping=document.mapping,
        schema_resource=document.schema_resource,
        module_id=document.module_id,
        version=document.version,
        lifecycle_status=document.lifecycle_status,
        target_profile=document.target_profile,
        dependency_order=order[document.module_id],
    )


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_json(item) for item in value)
    return value


def _mutable_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _mutable_json(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_mutable_json(item) for item in value]
    return value


def _compose_resolved_inputs(
    semantic: Mapping[str, Any],
    profiles: Sequence[Mapping[str, Any]],
    extensions: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any] | None,
) -> Catalog:
    try:
        return _compose_catalog(semantic, profiles, extensions, manifest)
    except CatalogValidationError as exc:
        if exc.stage is None:
            exc.stage = "composition"
        raise


def _compose_catalog(semantic: Mapping[str, Any], profile_docs: Sequence[Mapping[str, Any]], extension_docs: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any] | None) -> Catalog:
    if semantic.get("semantic_schema_version") != SEMANTIC_SCHEMA_VERSION:
        raise CatalogValidationError("semantic_schema_version must equal 7")
    profile_by_id: dict[str, Mapping[str, Any]] = {}
    for doc in profile_docs:
        profile_id = str(doc["profile"]["id"])
        if profile_id in profile_by_id:
            raise CatalogValidationError(f"duplicate profile module ID {profile_id!r}")
        if doc["requires"]["semantic_schema_version"] != 7:
            raise CatalogValidationError(f"profile {profile_id!r} requires an incompatible semantic schema")
        profile_by_id[profile_id] = doc
    extension_by_id: dict[str, Mapping[str, Any]] = {}
    for doc in extension_docs:
        extension_id = str(doc["extension"]["id"])
        if extension_id in extension_by_id:
            raise CatalogValidationError(f"duplicate extension module ID {extension_id!r}")
        if not all(str(identifier).startswith(extension_id + ".") for identifier in _extension_contribution_ids(doc)):
            raise CatalogValidationError(f"extension {extension_id!r} contributions must use its namespace")
        target = str(doc["applies_to"]["profile"])
        if target not in profile_by_id:
            raise CatalogValidationError(f"extension {extension_id!r} targets unloaded profile {target!r}")
        if doc["requires"]["semantic_schema_version"] != 7:
            raise CatalogValidationError(
                f"extension {extension_id!r} requires an incompatible "
                "semantic schema"
            )
        if (
            doc["requires"]["profile_schema_version"]
            != profile_by_id[target]["profile_schema_version"]
        ):
            raise CatalogValidationError(
                f"extension {extension_id!r} requires an incompatible "
                f"profile schema for {target!r}"
            )
        extension_by_id[extension_id] = doc
    order = _extension_order(extension_by_id)
    _validate_contribution_id_uniqueness(
        semantic, profile_by_id, extension_by_id
    )
    _validate_module_isolation(
        semantic, profile_by_id, extension_by_id, order
    )

    merged = {key: json.loads(json.dumps(value)) for key, value in semantic.items() if key not in {"$schema", "semantic_schema_version"}}
    merged.update({"$schema": SCHEMA_REFERENCE, "schema_version": 6, "profiles": sorted(profile_by_id), "profile_bindings": {}})
    origins: dict[str, ContributionOrigin] = {}
    for collection, kind in (("clinical_objects", "clinical_object"), ("concepts", "concept"), ("semantic_relationships", "semantic_relationship"), ("temporal_semantics", "temporal_semantic"), ("aggregations", "aggregation"), ("guardrails", "guardrail"), ("coverage", "coverage"), ("sources", "source"), ("contexts", "context"), ("vocabularies", "vocabulary")):
        for identifier in merged.get(collection, {}):
            origins[f"{kind}:{identifier}"] = ContributionOrigin("semantic_catalog", "semantic", contribution_class="portable")
    qualifications: dict[str, Qualification] = {}
    binding_owner: dict[str, str] = {}
    for profile_id, doc in sorted(profile_by_id.items()):
        _merge_module_registries(merged, doc, profile_id, "profile", origins)
        binding = _copy_binding_layer(doc["profile_binding"], profile_id, "profile", origins, binding_owner, profile_id)
        merged["profile_bindings"][profile_id] = binding
        _collect_qualifications(doc, ContributionOrigin("profile", profile_id, target_profile=profile_id, contribution_class="released_profile"), qualifications, merged)
    revisions: dict[str, Revision] = {}
    feature_lineage: dict[str, Mapping[str, Any]] = {}
    for extension_id in order:
        doc = extension_by_id[extension_id]
        metadata = doc["extension"]
        target = str(doc["applies_to"]["profile"])
        origin = ContributionOrigin("extension", extension_id, str(metadata["version"]), str(metadata["lifecycle_status"]), target, "project")
        concepts = doc["semantic_additions"]["concepts"]
        for identifier, raw in concepts.items():
            if identifier in merged["concepts"]:
                raise CatalogValidationError(f"duplicate contribution ID {identifier!r}")
            item = dict(raw); item.pop("lifecycle_status", None)
            merged["concepts"][identifier] = item; origins[f"concept:{identifier}"] = origin
        _merge_module_registries(merged, doc, extension_id, "extension", origins)
        additions = _copy_binding_layer(doc["binding_additions"], extension_id, "extension", origins, binding_owner, target)
        for collection in additions:
            for binding in additions[collection]:
                origins[f"binding:{binding['id']}"] = origin
            merged["profile_bindings"][target][collection].extend(additions[collection])
        _collect_qualifications(doc, origin, qualifications, merged)
        for identifier, raw in doc["feature_lineage"].items():
            if identifier in feature_lineage:
                raise CatalogValidationError(f"duplicate feature lineage ID {identifier!r}")
            if raw["output_concept"] not in merged["concepts"] or any(item not in merged["concepts"] for item in raw["input_concepts"]):
                raise CatalogValidationError(f"feature lineage {identifier!r} references unknown concepts")
            if any(item not in binding_owner for item in raw["input_bindings"]):
                raise CatalogValidationError(f"feature lineage {identifier!r} references unknown bindings")
            feature_lineage[identifier] = {**raw, "origin": origin.to_dict(), "target_profile": target}
            origins[f"feature_lineage:{identifier}"] = origin
        _collect_revisions(doc, origin, revisions, merged, binding_owner, set(doc["requires"]["extensions"]) | {"profile"})
    _validate_revision_graph(revisions)
    _prepare_binding_revisions(merged, revisions)
    try:
        catalog = Catalog.from_mapping(merged, _allow_empty_profiles=True)
    except CatalogValidationError as exc:
        if exc.stage is None:
            exc.stage = "domain"
        raise
    fingerprint_content = {"semantic": semantic, "profiles": [profile_by_id[key] for key in sorted(profile_by_id)], "extensions": [extension_by_id[key] for key in sorted(extension_by_id)]}
    fingerprint = hashlib.sha256(json.dumps(fingerprint_content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return Catalog(clinical_objects=catalog.clinical_objects, concepts=catalog.concepts, semantic_relationships=catalog.semantic_relationships, temporal_semantics=catalog.temporal_semantics, aggregations=catalog.aggregations, guardrails=catalog.guardrails, coverage=catalog.coverage, vocabularies=catalog.vocabularies, sources=catalog.sources, contexts=catalog.contexts, profile_bindings=catalog.profile_bindings, schema_version=7, origins=origins, qualifications=qualifications, revisions=revisions, feature_lineage=feature_lineage, configuration={"semantic_schema_version": 7, "profiles": sorted(profile_by_id), "profile_schema_versions": {key: profile_by_id[key]["profile_schema_version"] for key in sorted(profile_by_id)}, "extension_schema_versions": {key: extension_by_id[key]["extension_schema_version"] for key in order}, "extensions": [{"id": key, "version": extension_by_id[key]["extension"]["version"]} for key in order], "configuration_fingerprint": f"sha256:{fingerprint}", "manifest": "catalog-set" if manifest is not None else None})


def _object_without_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CatalogValidationError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _extension_contribution_ids(doc: Mapping[str, Any]) -> tuple[str, ...]:
    identifiers = list(doc["semantic_additions"]["concepts"])
    for collection in ("qualifications", "feature_lineage", "sources", "contexts", "coverage", "vocabularies"):
        identifiers.extend(doc[collection])
    identifiers.extend(str(item["id"]) for collection in doc["binding_additions"].values() for item in collection)
    identifiers.extend(str(item["id"]) for item in doc["revisions"])
    return tuple(identifiers)


def _validate_contribution_id_uniqueness(
    semantic: Mapping[str, Any],
    profiles: Mapping[str, Mapping[str, Any]],
    extensions: Mapping[str, Mapping[str, Any]],
) -> None:
    """Reject reuse of an authored contribution ID across the catalog set.

    Contribution identity is global even though semantic targets and physical
    occurrences are not.  References such as a binding's ``concept`` and
    ``table`` therefore do not participate here; only the IDs authored for
    records contributed by each selected module do.
    """

    owners: dict[str, str] = {}

    def register(identifier: object, location: str) -> None:
        stable_id = str(identifier)
        previous = owners.get(stable_id)
        if previous is not None:
            raise CatalogValidationError(
                f"duplicate contribution ID {stable_id!r} in {previous} and "
                f"{location}"
            )
        owners[stable_id] = location

    semantic_collections = (
        "clinical_objects",
        "concepts",
        "semantic_relationships",
        "temporal_semantics",
        "aggregations",
        "guardrails",
        "coverage",
        "sources",
        "contexts",
        "vocabularies",
    )
    for collection in semantic_collections:
        for identifier in semantic.get(collection, {}):
            register(identifier, f"semantic_catalog.{collection}")

    module_registries = (
        "qualifications",
        "sources",
        "contexts",
        "coverage",
        "vocabularies",
    )

    def register_binding_layer(
        layer: Mapping[str, Any], location: str
    ) -> None:
        for collection, records in layer.items():
            for record in records:
                register(record["id"], f"{location}.{collection}")

    for profile_id, document in profiles.items():
        prefix = f"profile[{profile_id}]"
        for collection in module_registries:
            for identifier in document.get(collection, {}):
                register(identifier, f"{prefix}.{collection}")
        register_binding_layer(document["profile_binding"], f"{prefix}.profile_binding")

    for extension_id, document in extensions.items():
        prefix = f"extension[{extension_id}]"
        for identifier in document["semantic_additions"]["concepts"]:
            register(identifier, f"{prefix}.semantic_additions.concepts")
        for collection in module_registries + ("feature_lineage",):
            for identifier in document.get(collection, {}):
                register(identifier, f"{prefix}.{collection}")
        register_binding_layer(
            document["binding_additions"], f"{prefix}.binding_additions"
        )
        for revision in document["revisions"]:
            register(revision["id"], f"{prefix}.revisions")


def _extension_order(docs: Mapping[str, Mapping[str, Any]]) -> tuple[str, ...]:
    graph = {identifier: set(map(str, doc["requires"]["extensions"])) for identifier, doc in docs.items()}
    missing = sorted({dep for deps in graph.values() for dep in deps if dep not in docs})
    if missing:
        raise CatalogValidationError("missing extension dependencies: " + ", ".join(missing))
    visiting: set[str] = set(); visited: set[str] = set(); order: list[str] = []
    def visit(identifier: str) -> None:
        if identifier in visiting:
            raise CatalogValidationError("extension dependency graph must be acyclic")
        if identifier in visited: return
        visiting.add(identifier)
        for dependency in sorted(graph[identifier]): visit(dependency)
        visiting.remove(identifier); visited.add(identifier); order.append(identifier)
    for identifier in sorted(graph): visit(identifier)
    return tuple(order)


def _validate_module_isolation(
    semantic: Mapping[str, Any],
    profiles: Mapping[str, Mapping[str, Any]],
    extensions: Mapping[str, Mapping[str, Any]],
    extension_order: Sequence[str],
) -> None:
    """Reject references that borrow from an unrelated module."""

    semantic_contexts = set(semantic["contexts"])
    semantic_sources = set(semantic["sources"])
    profile_context_owner = {
        identifier: profile_id
        for profile_id, document in profiles.items()
        for identifier in document["contexts"]
    }
    profile_source_owner = {
        identifier: profile_id
        for profile_id, document in profiles.items()
        for identifier in document["sources"]
    }
    extension_context_owner = {
        identifier: extension_id
        for extension_id, document in extensions.items()
        for identifier in document["contexts"]
    }
    extension_source_owner = {
        identifier: extension_id
        for extension_id, document in extensions.items()
        for identifier in document["sources"]
    }
    concept_owner = {
        identifier: "semantic"
        for identifier in semantic["concepts"]
    }
    concept_owner.update(
        {
            identifier: extension_id
            for extension_id, document in extensions.items()
            for identifier in document["semantic_additions"]["concepts"]
        }
    )
    binding_owner = {
        str(item["id"]): profile_id
        for profile_id, document in profiles.items()
        for collection in document["profile_binding"].values()
        for item in collection
    }
    binding_owner.update(
        {
            str(item["id"]): extension_id
            for extension_id, document in extensions.items()
            for collection in document["binding_additions"].values()
            for item in collection
        }
    )

    for profile_id, document in profiles.items():
        _validate_module_scopes(document, profile_id, f"profile {profile_id!r}")
        allowed_contexts = semantic_contexts | set(document["contexts"])
        allowed_sources = semantic_sources | set(document["sources"])
        _validate_claim_ref_closure(document, allowed_contexts, f"profile {profile_id!r}")
        _validate_context_source_closure(
            document["contexts"], allowed_sources, f"profile {profile_id!r}"
        )
        own_relationships = {
            str(item["id"])
            for item in document["profile_binding"]["relationship_bindings"]
        }
        for context_id, context in document["contexts"].items():
            if any(
                item["profile"] != profile_id
                for item in context["related_tables"]
            ):
                raise CatalogValidationError(
                    f"profile {profile_id!r} context {context_id!r} "
                    "references another profile table"
                )
            unknown = set(context["related_relationships"]) - own_relationships
            if unknown:
                raise CatalogValidationError(
                    f"profile {profile_id!r} context {context_id!r} "
                    "references another profile relationship"
                )
        for qualification_id, qualification in document["qualifications"].items():
            subject = qualification["subject"]
            collection = {
                "clinical_object": "clinical_objects",
                "concept": "concepts",
                "semantic_relationship": "semantic_relationships",
                "temporal_semantic": "temporal_semantics",
                "aggregation": "aggregations",
                "guardrail": "guardrails",
            }[subject["kind"]]
            if subject["id"] not in semantic[collection]:
                raise CatalogValidationError(
                    f"profile qualification {qualification_id!r} must "
                    "target portable semantics"
                )

    dependencies = {
        identifier: set(map(str, document["requires"]["extensions"]))
        for identifier, document in extensions.items()
    }

    def dependency_closure(identifier: str) -> set[str]:
        result: set[str] = set()
        pending = list(dependencies[identifier])
        while pending:
            dependency = pending.pop()
            if dependency in result:
                continue
            result.add(dependency)
            pending.extend(dependencies[dependency])
        return result

    for extension_id in extension_order:
        document = extensions[extension_id]
        target = str(document["applies_to"]["profile"])
        allowed_extensions = dependency_closure(extension_id)
        if any(
            extensions[dependency]["applies_to"]["profile"] != target
            for dependency in allowed_extensions
        ):
            raise CatalogValidationError(
                f"extension {extension_id!r} has a dependency for another "
                "target profile"
            )
        allowed_modules = {"semantic", target, extension_id, *allowed_extensions}
        _validate_module_scopes(
            document, target, f"extension {extension_id!r}"
        )
        allowed_contexts = (
            semantic_contexts
            | {
                identifier
                for identifier, owner in profile_context_owner.items()
                if owner == target
            }
            | {
                identifier
                for identifier, owner in extension_context_owner.items()
                if owner in allowed_extensions | {extension_id}
            }
        )
        allowed_sources = (
            semantic_sources
            | {
                identifier
                for identifier, owner in profile_source_owner.items()
                if owner == target
            }
            | {
                identifier
                for identifier, owner in extension_source_owner.items()
                if owner in allowed_extensions | {extension_id}
            }
        )
        _validate_claim_ref_closure(
            document, allowed_contexts, f"extension {extension_id!r}"
        )
        _validate_context_source_closure(
            document["contexts"],
            allowed_sources,
            f"extension {extension_id!r}",
        )
        for context_id, context in document["contexts"].items():
            if any(
                item["profile"] != target
                for item in context["related_tables"]
            ):
                raise CatalogValidationError(
                    f"extension {extension_id!r} context {context_id!r} "
                    "references another profile table"
                )
            if any(
                binding_owner.get(identifier) not in allowed_modules
                for identifier in context["related_relationships"]
            ):
                raise CatalogValidationError(
                    f"extension {extension_id!r} context {context_id!r} "
                    "references an undeclared relationship dependency"
                )
        for qualification_id, qualification in document["qualifications"].items():
            subject = qualification["subject"]
            if subject["kind"] == "concept":
                owner = concept_owner.get(subject["id"])
                if owner not in allowed_modules:
                    raise CatalogValidationError(
                        f"extension qualification {qualification_id!r} "
                        "targets an undeclared dependency"
                    )
        for lineage_id, lineage in document["feature_lineage"].items():
            referenced_concepts = {
                lineage["output_concept"], *lineage["input_concepts"]
            }
            if any(
                concept_owner.get(identifier) not in allowed_modules
                for identifier in referenced_concepts
            ):
                raise CatalogValidationError(
                    f"feature lineage {lineage_id!r} references an "
                    "undeclared concept dependency"
                )
            if any(
                binding_owner.get(identifier) not in allowed_modules
                for identifier in lineage["input_bindings"]
            ):
                raise CatalogValidationError(
                    f"feature lineage {lineage_id!r} references an "
                    "undeclared binding dependency"
                )
        for revision in document["revisions"]:
            if revision["kind"] == "reinterprets_concept":
                if concept_owner.get(revision["original_concept"]) not in allowed_modules:
                    raise CatalogValidationError(
                        f"revision {revision['id']!r} references an "
                        "undeclared concept dependency"
                    )
                if concept_owner.get(revision["replacement_concept"]) != extension_id:
                    raise CatalogValidationError(
                        f"revision {revision['id']!r} replacement is not "
                        "owned by its extension"
                    )
            else:
                if binding_owner.get(revision["original_binding"]) not in (
                    {target} | allowed_extensions
                ):
                    raise CatalogValidationError(
                        f"revision {revision['id']!r} references an "
                        "undeclared binding dependency"
                    )
                if binding_owner.get(revision["replacement_binding"]) != extension_id:
                    raise CatalogValidationError(
                        f"revision {revision['id']!r} replacement is not "
                        "owned by its extension"
                    )


def _validate_module_scopes(
    document: Mapping[str, Any], target_profile: str, label: str
) -> None:
    for collection in ("sources", "contexts", "coverage"):
        for identifier, record in document.get(collection, {}).items():
            profiles = set(map(str, record.get("profiles", ())))
            if profiles - {target_profile}:
                raise CatalogValidationError(
                    f"{label} {collection} record {identifier!r} applies "
                    "to another profile"
                )
            if record.get("scope") == "profile_specific" and profiles != {
                target_profile
            }:
                raise CatalogValidationError(
                    f"{label} {collection} record {identifier!r} must "
                    f"apply exactly to {target_profile!r}"
                )


def _validate_claim_ref_closure(
    value: Any, allowed_contexts: set[str], label: str
) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key == "claim_refs":
                for reference in nested:
                    context_id = str(reference).split("#", 1)[0]
                    if context_id not in allowed_contexts:
                        raise CatalogValidationError(
                            f"{label} claim {reference!r} is outside its "
                            "module dependency closure"
                        )
            else:
                _validate_claim_ref_closure(nested, allowed_contexts, label)
    elif isinstance(value, list):
        for nested in value:
            _validate_claim_ref_closure(nested, allowed_contexts, label)


def _validate_context_source_closure(
    contexts: Mapping[str, Any], allowed_sources: set[str], label: str
) -> None:
    for context_id, context in contexts.items():
        for claim in context["claims"]:
            unknown = set(map(str, claim["sources"])) - allowed_sources
            if unknown:
                raise CatalogValidationError(
                    f"{label} context {context_id!r} references sources "
                    "outside its module dependency closure"
                )


def _merge_module_registries(merged: dict[str, Any], doc: Mapping[str, Any], module_id: str, document_kind: str, origins: dict[str, ContributionOrigin]) -> None:
    contribution = "released_profile" if document_kind == "profile" else "project"
    target = module_id if document_kind == "profile" else str(doc["applies_to"]["profile"])
    metadata = doc.get("extension", {})
    origin = ContributionOrigin(document_kind, module_id, metadata.get("version"), metadata.get("lifecycle_status"), target, contribution)
    for collection, kind in (("sources", "source"), ("contexts", "context"), ("coverage", "coverage"), ("vocabularies", "vocabulary")):
        for identifier, raw in doc.get(collection, {}).items():
            if identifier in merged[collection]:
                raise CatalogValidationError(f"duplicate {collection} ID {identifier!r}")
            merged[collection][identifier] = json.loads(json.dumps(raw))
            origins[f"{kind}:{identifier}"] = origin


def _copy_binding_layer(raw: Mapping[str, Any], module_id: str, document_kind: str, origins: dict[str, ContributionOrigin], owners: dict[str, str], target_profile: str) -> dict[str, list[Any]]:
    copied: dict[str, list[Any]] = {key: [] for key in _PROFILE_BINDING_KEYS}
    for collection in copied:
        for authored in raw[collection]:
            item = json.loads(json.dumps(authored)); identifier = str(item.get("id", ""))
            if not identifier or identifier in owners:
                raise CatalogValidationError(f"duplicate or missing binding contribution ID {identifier!r}")
            owners[identifier] = module_id
            origins[f"binding:{identifier}"] = ContributionOrigin(document_kind, module_id, target_profile=target_profile, contribution_class="released_profile" if document_kind == "profile" else "project")
            copied[collection].append(item)
    return copied


def _collect_qualifications(doc: Mapping[str, Any], origin: ContributionOrigin, result: dict[str, Qualification], merged: Mapping[str, Any]) -> None:
    subject_collections = {"clinical_object": "clinical_objects", "concept": "concepts", "semantic_relationship": "semantic_relationships", "temporal_semantic": "temporal_semantics", "aggregation": "aggregations", "guardrail": "guardrails"}
    for identifier, raw in doc.get("qualifications", {}).items():
        if identifier in result: raise CatalogValidationError(f"duplicate qualification ID {identifier!r}")
        subject = raw["subject"]; kind = str(subject["kind"]); subject_id = str(subject["id"])
        if kind not in subject_collections or subject_id not in merged[subject_collections[kind]]:
            raise CatalogValidationError(f"qualification {identifier!r} references unknown subject {kind}:{subject_id}")
        result[identifier] = Qualification(identifier, kind, subject_id, str(raw["applicability"]), str(raw["summary"]), tuple(raw["claim_refs"]), tuple(raw["caveats"]), origin)


def _collect_revisions(doc: Mapping[str, Any], origin: ContributionOrigin, result: dict[str, Revision], merged: Mapping[str, Any], binding_owners: Mapping[str, str], allowed: set[str]) -> None:
    extension_id = origin.module_id
    dependencies = set(map(str, doc["requires"]["extensions"]))
    for raw in doc["revisions"]:
        identifier = str(raw["id"]); kind = str(raw["kind"])
        if identifier in result: raise CatalogValidationError(f"duplicate revision ID {identifier!r}")
        if kind == "reinterprets_concept":
            original = str(raw["original_concept"]); replacement = str(raw["replacement_concept"])
            if original not in merged["concepts"] or replacement not in merged["concepts"]: raise CatalogValidationError(f"revision {identifier!r} references unknown concept")
            if not replacement.startswith(extension_id + "."): raise CatalogValidationError(f"revision {identifier!r} replacement must be owned by its extension")
            owner = next((dep for dep in dependencies if original.startswith(dep + ".")), None)
            if any(original.startswith(other + ".") for other in binding_owners.values()) and owner is None: raise CatalogValidationError(f"revision {identifier!r} lacks dependency authority")
            remains = True
        else:
            original = str(raw["original_binding"]); replacement = str(raw["replacement_binding"])
            if original not in binding_owners or replacement not in binding_owners: raise CatalogValidationError(f"revision {identifier!r} references unknown binding")
            if binding_owners[replacement] != extension_id: raise CatalogValidationError(f"revision {identifier!r} replacement must be owned by its extension")
            if binding_owners[original] not in dependencies and binding_owners[original] not in {origin.target_profile}: raise CatalogValidationError(f"revision {identifier!r} lacks dependency authority")
            remains = bool(raw["original_remains_alternative"])
        result[identifier] = Revision(
            identifier,
            kind,
            original,
            replacement,
            (
                str(raw["semantic_difference"])
                if kind == "reinterprets_concept"
                else None
            ),
            str(raw["reason"]),
            tuple(raw["claim_refs"]),
            tuple(raw["known_limitations"]),
            remains,
            origin,
        )


def _prepare_binding_revisions(
    merged: Mapping[str, Any], revisions: Mapping[str, Revision]
) -> None:
    """Mark the two sides of a validated feature-binding replacement.

    The marker is an internal composition detail added only after standalone
    schema validation. It lets the effective graph retain both authored
    contributions at one physical occurrence without permitting undeclared
    duplicate bindings.
    """

    feature_bindings = {
        str(item["id"]): item
        for profile in merged["profile_bindings"].values()
        for item in profile["feature_bindings"]
        if item.get("id") is not None
    }
    for revision in revisions.values():
        if revision.kind != "replaces_binding":
            continue
        original = feature_bindings.get(revision.original_id)
        replacement = feature_bindings.get(revision.replacement_id)
        if original is None or replacement is None:
            raise CatalogValidationError(
                f"revision {revision.id!r} must replace a feature binding"
            )
        if (
            original["table"] != replacement["table"]
            or original["column"] != replacement["column"]
        ):
            # A replacement may redirect to a new occurrence without needing
            # duplicate-occurrence coexistence markers.
            continue
        original["coexists_with"] = [revision.replacement_id]
        replacement["coexists_with"] = [revision.original_id]


def _validate_revision_graph(revisions: Mapping[str, Revision]) -> None:
    for kind in ("reinterprets_concept", "replaces_binding"):
        selected = [item for item in revisions.values() if item.kind == kind]
        originals = [item.original_id for item in selected]
        if len(originals) != len(set(originals)):
            raise CatalogValidationError(
                f"{kind} revisions must not declare competing replacements"
            )
        graph = {item.original_id: {item.replacement_id} for item in selected}
        if any(source in targets for source, targets in graph.items()):
            raise CatalogValidationError(
                f"{kind} revisions cannot replace a record with itself"
            )
        _validate_acyclic(
            graph,
            set(graph) | {target for targets in graph.values() for target in targets},
            f"{kind} revision graph",
        )


def _reject_json_constant(value: str) -> None:
    raise CatalogValidationError(
        f"non-standard JSON number {value!r} is forbidden"
    )


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
    _require_keys(data, required, path)
    unexpected = sorted(frozenset(data) - allowed)
    if unexpected:
        raise CatalogValidationError(
            f"{path} has unexpected fields: {', '.join(unexpected)}"
        )


def _require_keys(
    data: Mapping[str, Any],
    required: frozenset[str],
    path: str,
) -> None:
    missing = sorted(required - frozenset(data))
    if missing:
        raise CatalogValidationError(
            f"{path} is missing required fields: {', '.join(missing)}"
        )


def _nonempty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogValidationError(f"{path} must be a non-empty string")
    if value != value.strip():
        raise CatalogValidationError(
            f"{path} must not have surrounding whitespace"
        )
    return value


def _physical_component(value: object, path: str) -> str:
    component = _nonempty_string(value, path)
    if ":" in component:
        raise CatalogValidationError(
            f"{path} must not contain ':' because it separates profiles"
        )
    return component


def _physical_component_array(
    value: object,
    path: str,
    *,
    minimum: int = 1,
) -> tuple[str, ...]:
    items = _expect_list(value, path)
    if len(items) < minimum:
        raise CatalogValidationError(
            f"{path} must contain at least {minimum} item(s)"
        )
    parsed = tuple(
        _physical_component(item, f"{path}[{index}]")
        for index, item in enumerate(items)
    )
    if len(set(parsed)) != len(parsed):
        raise CatalogValidationError(f"{path} must contain unique values")
    return parsed


def _controlled_string(
    value: object,
    path: str,
    allowed: Sequence[str] | frozenset[str],
) -> str:
    parsed = _nonempty_string(value, path)
    if parsed not in allowed:
        raise CatalogValidationError(
            f"{path} has unknown value {parsed!r}"
        )
    return parsed


def _controlled_identifier(
    value: object,
    path: str,
    allowed: Sequence[str] | frozenset[str],
) -> str:
    parsed = _identifier(value, path)
    if parsed not in allowed:
        raise CatalogValidationError(
            f"{path} references unknown value {parsed!r}"
        )
    return parsed


def _identifier(value: object, path: str) -> str:
    parsed = _nonempty_string(value, path)
    _require_identifier(parsed, path)
    return parsed


def _identifier_array(
    value: object,
    path: str,
    *,
    minimum: int = 0,
) -> tuple[str, ...]:
    return _string_array(
        value, path, minimum=minimum, identifier=True
    )


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
        item_path = f"{path}[{index}]"
        string = _nonempty_string(item, item_path)
        if identifier:
            _require_identifier(string, item_path)
        parsed.append(string)
    if len(set(parsed)) != len(parsed):
        raise CatalogValidationError(f"{path} must contain unique values")
    return tuple(parsed)


def _domain_array(value: object, path: str) -> tuple[str, ...]:
    domains = _string_array(value, path, minimum=1, identifier=True)
    unknown = sorted(set(domains) - set(DOMAINS))
    if unknown:
        raise CatalogValidationError(
            f"{path} contains unknown domain values: {', '.join(unknown)}"
        )
    return domains


def _claim_ref_array(
    value: object,
    path: str,
    *,
    minimum: int = 0,
) -> tuple[str, ...]:
    references = _string_array(value, path, minimum=minimum)
    for index, reference in enumerate(references):
        if _CLAIM_REF_PATTERN.fullmatch(reference) is None:
            raise CatalogValidationError(
                f"{path}[{index}] must use 'context-id#claim-id' syntax"
            )
    return references


def _evidence_array(value: object, path: str) -> tuple[str, ...]:
    evidence = _string_array(value, path, minimum=1, identifier=True)
    unknown = sorted(set(evidence) - EVIDENCE_VALUES)
    if unknown:
        raise CatalogValidationError(
            f"{path} contains unknown evidence values: {', '.join(unknown)}"
        )
    return evidence


def _scope_and_profiles(
    data: Mapping[str, Any],
    path: str,
    available_profiles: frozenset[str],
) -> tuple[str, tuple[str, ...]]:
    scope = _controlled_string(
        data["scope"], f"{path}.scope", CONTEXT_SCOPES
    )
    profiles = _identifier_array(data["profiles"], f"{path}.profiles")
    unknown = sorted(set(profiles) - available_profiles)
    if unknown:
        raise CatalogValidationError(
            f"{path}.profiles references unknown profiles: "
            + ", ".join(unknown)
        )
    if scope == "profile_specific" and not profiles:
        raise CatalogValidationError(
            f"{path}.profiles must not be empty when scope is "
            "'profile_specific'"
        )
    if scope != "profile_specific" and profiles:
        raise CatalogValidationError(
            f"{path}.profiles must be empty unless scope is "
            "'profile_specific'"
        )
    return scope, profiles


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


def _validate_limit(limit: object) -> None:
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or limit < 1
        or limit > 500
    ):
        raise CatalogValidationError(
            "limit must be an integer between 1 and 500"
        )


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(
        _normalize_token(token)
        for token in _TOKEN_PATTERN.findall(value.casefold())
    )


def _normalize_token(token: str) -> str:
    """Apply a deliberately small plural normalization for discovery."""

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


def _recognized_discovery_intents(
    query_text: str,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Recognize safety-relevant query intent from ordinary language."""

    tokens = frozenset(_tokens(query_text))
    recognized: list[tuple[str, tuple[str, ...]]] = []

    def add(name: str, terms: set[str]) -> None:
        if terms:
            recognized.append((name, tuple(sorted(terms))))

    add(
        "longitudinal",
        set(tokens)
        & {
            "history",
            "longitudinal",
            "nearest",
            "prior",
            "subsequent",
            "within",
        },
    )
    add(
        "temporal_fallback",
        set(tokens)
        & {
            "coalesce",
            "fallback",
            "proxy",
            "substitute",
            "substitution",
        },
    )
    add(
        "probability_calibration",
        set(tokens) & {"brier", "calibration", "probability"},
    )
    finding_terms = set(tokens) & {
        "finding",
        "identity",
        "instance",
        "key",
        "numfind",
        "row",
    }
    if "finding" in tokens and finding_terms & {
        "identity",
        "instance",
        "key",
        "numfind",
        "row",
    }:
        add("finding_identity", finding_terms)
    laterality_terms = set(tokens) & {
        "bilateral",
        "bside",
        "laterality",
        "null",
        "side",
    }
    if laterality_terms & {"bilateral", "bside", "laterality"} or {
        "side",
        "null",
    }.issubset(tokens):
        add("laterality_role", laterality_terms)
    binary_terms = set(tokens) & {
        "binary",
        "biopsy",
        "cancer",
        "endpoint",
        "event",
        "outcome",
        "represented",
        "zero",
    }
    if "binary" in tokens or (
        "represented" in tokens
        and binary_terms & {"biopsy", "cancer", "endpoint", "event", "outcome"}
    ):
        add("represented_binary_endpoint", binary_terms)
    if (
        "finding" in tokens
        and "pathology" in tokens
        and tokens & {"aggregate", "aggregation", "severity"}
    ):
        add(
            "finding_attribution_aggregation",
            set(tokens)
            & {
                "aggregate",
                "aggregation",
                "finding",
                "pathology",
                "severity",
            },
        )
    return tuple(recognized)


def _discovery_intent_reasons(
    document: _DiscoveryDocument,
    intents: Sequence[tuple[str, tuple[str, ...]]],
) -> list[dict[str, Any]]:
    """Return explainable intent bonuses supported by document vocabulary."""

    reasons: list[dict[str, Any]] = []
    discriminating_cues = {
        "longitudinal": {
            "accession",
            "candidate",
            "history",
            "longitudinal",
            "nearest",
            "prior",
            "subsequent",
            "timeline",
        },
        "temporal_fallback": {
            "coalesce",
            "fallback",
            "interchangeable",
            "missingness",
            "proxy",
            "substitute",
            "substitution",
        },
        "probability_calibration": {
            "brier",
            "calibration",
            "exceptional",
            "horizon",
            "probability",
            "risk",
            "scale",
        },
        "finding_identity": {
            "identity",
            "instance",
            "key",
            "longitudinal",
            "multiplicity",
            "numfind",
            "row",
            "synthetic",
        },
        "laterality_role": {
            "bilateral",
            "bside",
            "laterality",
            "null",
            "side",
        },
        "represented_binary_endpoint": {
            "binary",
            "cancer",
            "endpoint",
            "event",
            "outcome",
            "represented",
            "zero",
        },
        "finding_attribution_aggregation": {
            "aggregate",
            "aggregation",
            "attribution",
            "multiplicity",
            "policy",
            "severity",
        },
    }
    for intent, query_terms in intents:
        semantic_cues = sorted(
            document.all_tokens & _DISCOVERY_INTENT_AFFINITIES[intent]
        )
        if not semantic_cues:
            continue
        cue_set = set(semantic_cues)
        has_discriminating_cue = bool(
            cue_set & discriminating_cues[intent]
        )
        longitudinal_patient_pathology = (
            intent == "longitudinal"
            and document.kind == "semantic_relationship"
            and {"patient", "pathology"}.issubset(cue_set)
        )
        if not has_discriminating_cue and not longitudinal_patient_pathology:
            continue
        bonus = 45 + 8 * min(len(semantic_cues), 5)
        if longitudinal_patient_pathology:
            bonus += 50
        if (
            document.kind == "guardrail"
            and document.entity.priority in {"critical", "high"}
        ):
            bonus += 55
        elif (
            document.kind == "coverage"
            and document.entity.status in {"unsupported", "unresolved"}
        ):
            bonus += 45
        reasons.append(
            {
                "field": "query_intent",
                "intent": intent,
                "terms": list(query_terms),
                "matched_terms": list(query_terms),
                "semantic_cues": semantic_cues,
                "score_bonus": bonus,
            }
        )
    return reasons


def _compose_discovery_candidates(
    candidates: Sequence[
        tuple[int, _DiscoveryDocument, list[dict[str, Any]], frozenset[str]]
    ],
    *,
    limit: int,
    has_query_intents: bool,
) -> list[
    tuple[int, _DiscoveryDocument, list[dict[str, Any]], frozenset[str]]
]:
    """Reserve a bounded share for eligible safety/uncertainty records."""

    selected = list(candidates[:limit])
    if not has_query_intents or not candidates:
        return selected
    reserved_slots = min(2, max(1, limit // 4))
    reservable = [
        candidate
        for candidate in candidates
        if any(
            reason.get("field") == "query_intent"
            for reason in candidate[2]
        )
        and (
            (
                candidate[1].kind == "guardrail"
                and candidate[1].entity.priority in {"critical", "high"}
            )
            or (
                candidate[1].kind == "coverage"
                and candidate[1].entity.status
                in {"unsupported", "unresolved"}
            )
        )
    ][:reserved_slots]
    reserved_keys = {
        (candidate[1].kind, candidate[1].identifier)
        for candidate in reservable
    }
    selected_keys = {
        (candidate[1].kind, candidate[1].identifier)
        for candidate in selected
    }
    selected.extend(
        candidate
        for candidate in reservable
        if (candidate[1].kind, candidate[1].identifier)
        not in selected_keys
    )
    while len(selected) > limit:
        for index in range(len(selected) - 1, -1, -1):
            key = (selected[index][1].kind, selected[index][1].identifier)
            if key not in reserved_keys:
                selected.pop(index)
                break
    selected.sort(
        key=lambda item: (-item[0], item[1].kind, item[1].identifier)
    )
    return selected


def _discovery_reasons(
    document: _DiscoveryDocument,
    query_text: str,
    query_tokens: frozenset[str],
    *,
    profile: str | None,
) -> list[dict[str, Any]]:
    """Explain which indexed semantic fields caused a discovery match."""

    reasons: list[dict[str, Any]] = []
    active_fields = list(document.fields)
    if profile is not None:
        active_fields.extend(
            (field, text)
            for field_profile, field, text in document.profile_fields
            if field_profile == profile
        )
    for field, text in active_fields:
        field_tokens = frozenset(_tokens(text))
        matched = sorted(query_tokens & field_tokens)
        phrase_match = bool(query_text and query_text in text)
        if not matched and not phrase_match:
            continue
        reason: dict[str, Any] = {
            "field": field,
            "terms": matched,
            "matched_terms": matched,
        }
        if phrase_match:
            reason["phrase_match"] = True
        reasons.append(reason)
    return reasons


def _discovery_score(
    document: _DiscoveryDocument,
    query_text: str,
    matched_tokens: frozenset[str],
    reasons: Sequence[Mapping[str, Any]],
) -> int:
    """Produce a deterministic relevance score without hiding its causes."""

    if not query_text:
        return 0
    score = 0
    identifier_text = document.identifier.casefold()
    label_text = document.label.casefold()
    if query_text == identifier_text:
        score += 1000
    if query_text == label_text:
        score += 800
    if query_text in identifier_text:
        score += 180
    if query_text in label_text:
        score += 140
    field_weights = {
        "identifier": 50,
        "label": 45,
        "title": 45,
        "search_terms": 35,
        "subject": 30,
        "meaning": 25,
        "statement": 25,
        "definition": 20,
        "summary": 20,
        "objects": 18,
        "features": 18,
        "attribution": 15,
        "temporal_qualification": 15,
        "method": 15,
        "claims": 12,
        "missing_states": 12,
        "vocabulary": 12,
        "binding.table": 15,
        "binding.column": 80,
        "caveats": 5,
    }
    for reason in reasons:
        if "score_bonus" in reason:
            score += int(reason["score_bonus"])
            continue
        weight = field_weights.get(str(reason["field"]), 8)
        score += weight * len(reason.get("matched_terms", ()))
        if reason.get("phrase_match"):
            score += weight * 2
    query_tokens = frozenset(_tokens(query_text)) - _SEARCH_STOPWORDS
    if query_tokens:
        score += round(100 * len(matched_tokens) / len(query_tokens))
    return score
