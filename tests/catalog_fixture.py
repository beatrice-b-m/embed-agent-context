"""Synthetic catalog fixtures shared by core and CLI tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from embed_context.catalog import (
    ANALYSIS_PATTERN_STATUSES,
    CLAIM_STATUSES,
    CONTEXT_KINDS,
    CONTEXT_SCOPES,
    DOMAINS,
    FEATURE_KINDS,
    GRAINS,
    SOURCE_KINDS,
    SOURCE_LOCATOR_KINDS,
)


def synthetic_catalog() -> dict[str, Any]:
    return {
        "$schema": "./catalog.schema.json",
        "schema_version": 4,
        "profiles": ["open-v2"],
        "grains": list(GRAINS),
        "feature_kinds": list(FEATURE_KINDS),
        "domains": list(DOMAINS),
        "context_kinds": list(CONTEXT_KINDS),
        "context_scopes": list(CONTEXT_SCOPES),
        "source_kinds": list(SOURCE_KINDS),
        "source_locator_kinds": list(SOURCE_LOCATOR_KINDS),
        "claim_statuses": list(CLAIM_STATUSES),
        "analysis_pattern_statuses": list(ANALYSIS_PATTERN_STATUSES),
        "concepts": {
            "exam.tissue_density": {
                "label": "Breast tissue density",
                "definition": "Breast tissue density code.",
                "feature_kind": "coded",
                "domains": ["exam", "mammography"],
                "search_terms": ["tissueden", "breast composition"],
                "caveats": ["Null has no documented code meaning."],
                "evidence": ["release_schema", "release_legend"],
                "vocabulary": "exam.tissue_density",
            },
            "identity.accession": {
                "label": "Exam accession identifier",
                "definition": "Opaque exam record identifier.",
                "feature_kind": "identifier",
                "domains": ["identity", "exam"],
                "search_terms": ["acc_anon", "accession"],
                "caveats": ["Do not expose identifier values."],
                "evidence": ["release_schema", "inference"],
            },
        },
        "bindings": [
            {
                "profile": "open-v2",
                "table": "exam_level_anon",
                "column": "tissueden",
                "concept": "exam.tissue_density",
                "grain": "exam",
                "role": "canonical",
                "physical_type": "int8",
                "nullable": True,
            },
            {
                "profile": "open-v2",
                "table": "combined_anon",
                "column": "tissueden",
                "concept": "exam.tissue_density",
                "grain": "wide_row",
                "role": "wide_projection",
                "physical_type": "int8",
                "nullable": True,
                "notes": ["Wide-value equality is not established."],
            },
            {
                "profile": "open-v2",
                "table": "exam_level_anon",
                "column": "acc_anon",
                "concept": "identity.accession",
                "grain": "exam",
                "role": "canonical",
                "physical_type": "int64",
                "nullable": True,
            },
        ],
        "vocabularies": {
            "exam.tissue_density": {
                "label": "Tissue-density codes",
                "completeness": "unknown",
                "parsing": "atomic",
                "evidence": ["release_legend"],
                "caveats": ["The list is not guaranteed to be exhaustive."],
                "codes": {
                    "1": "Almost entirely fat",
                    "2": "Scattered fibroglandular densities",
                },
            }
        },
        "tables": [
            {
                "profile": "open-v2",
                "table": "combined_anon",
                "grain": "wide_row",
                "keys": [],
                "caveats": ["Synthetic wide table has no declared key."],
            },
            {
                "profile": "open-v2",
                "table": "exam_level_anon",
                "grain": "exam",
                "keys": [
                    {
                        "id": "exam.accession",
                        "columns": ["acc_anon"],
                        "kind": "natural",
                        "uniqueness": "unique",
                        "completeness": "complete",
                        "evidence": ["cross_table_check"],
                        "caveats": [],
                    }
                ],
                "caveats": [],
            },
        ],
        "relationships": [],
        "sources": {
            "open-v2.release-schema": {
                "title": "Synthetic open-v2 release schema",
                "kind": "release_schema",
                "scope": "profile_specific",
                "locator_kind": "logical_artifact",
                "locator": "synthetic open-v2 footer schema",
                "version_scope": "Synthetic open-v2 contract fixture.",
                "profiles": ["open-v2"],
                "notes": [],
            }
        },
        "contexts": {
            "open-v2.density-interpretation": {
                "title": "Density interpretation boundary",
                "kind": "interpretation_guardrail",
                "scope": "profile_specific",
                "profiles": ["open-v2"],
                "summary": "Density is a coded exam feature.",
                "domains": ["exam", "mammography"],
                "search_terms": ["density interpretation"],
                "related_concepts": ["exam.tissue_density"],
                "related_tables": [
                    {
                        "profile": "open-v2",
                        "table": "exam_level_anon",
                    }
                ],
                "related_relationships": [],
                "claims": [
                    {
                        "id": "coded-feature",
                        "statement": (
                            "The synthetic density field is represented as a "
                            "coded exam feature."
                        ),
                        "status": "verified",
                        "sources": ["open-v2.release-schema"],
                        "caveats": [],
                    }
                ],
                "workflow_steps": [],
                "caveats": ["Synthetic context for contract tests."],
            }
        },
        "analysis_patterns": {
            "open-v2.density-analysis": {
                "title": "Synthetic density analysis guidance",
                "status": "draft",
                "scope": "profile_specific",
                "profiles": ["open-v2"],
                "summary": "Choose a density analysis policy explicitly.",
                "domains": ["exam", "mammography"],
                "search_terms": ["density analysis"],
                "applicable_grains": ["exam"],
                "related_concepts": ["exam.tissue_density"],
                "related_tables": [
                    {
                        "profile": "open-v2",
                        "table": "exam_level_anon",
                    }
                ],
                "related_relationships": [],
                "related_contexts": ["open-v2.density-interpretation"],
                "alternatives": [
                    {
                        "id": "coded-groups",
                        "label": "Coded density groups",
                        "description": "Retain the released categories.",
                        "appropriate_when": "Category-specific effects matter.",
                        "limitations": ["Sparse groups may require review."],
                    }
                ],
                "required_decisions": [
                    {
                        "id": "grouping",
                        "question": "How are density groups represented?",
                        "rationale": "The analysis determines grouping.",
                    }
                ],
                "prohibited_shortcuts": [
                    {
                        "id": "null-as-category",
                        "statement": "Do not assign null to a density category.",
                        "reason": "Null has no documented code meaning.",
                    }
                ],
                "caveats": ["Synthetic pattern for contract tests."],
            }
        },
    }


def write_catalog(path: Path, data: dict[str, Any] | None = None) -> Path:
    path.write_text(
        json.dumps(synthetic_catalog() if data is None else data),
        encoding="utf-8",
    )
    return path
