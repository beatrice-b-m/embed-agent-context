"""Synthetic catalog fixtures shared by core and CLI tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from embed_context.catalog import DOMAINS, FEATURE_KINDS, GRAINS


def synthetic_catalog() -> dict[str, Any]:
    return {
        "$schema": "./catalog.schema.json",
        "schema_version": 2,
        "profiles": ["open-v2"],
        "grains": list(GRAINS),
        "feature_kinds": list(FEATURE_KINDS),
        "domains": list(DOMAINS),
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
    }


def write_catalog(path: Path, data: dict[str, Any] | None = None) -> Path:
    path.write_text(
        json.dumps(synthetic_catalog() if data is None else data),
        encoding="utf-8",
    )
    return path
