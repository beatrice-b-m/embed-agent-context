"""Mechanically build the checked-in schema-v7 catalog-set artifacts.

This migration helper reads only the count-free schema-v6 catalog metadata.
It never reads release artifacts or clinical data.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def authored_id(*parts: str) -> str:
    value = ".".join(parts).lower()
    return re.sub(r"[^a-z0-9_.-]+", "-", value).strip(".-")


def profile_claims(value: Any) -> list[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "claim_refs" and isinstance(nested, list):
                found.update(
                    claim for claim in nested if claim.startswith("open-v2.")
                )
            else:
                found.update(profile_claims(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(profile_claims(nested))
    return sorted(found)


def strip_profile_links(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, nested in value.items():
            if key == "claim_refs" and isinstance(nested, list):
                result[key] = [
                    claim for claim in nested if not claim.startswith("open-v2.")
                ]
            elif key == "coverage" and isinstance(nested, list):
                result[key] = [
                    item
                    for item in nested
                    if not item.startswith("coverage.open-v2.")
                ]
            else:
                result[key] = strip_profile_links(nested)
        return result
    if isinstance(value, list):
        return [strip_profile_links(item) for item in value]
    return value


def record_map(definition: str, *, min_properties: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": "object",
        "patternProperties": {
            "^[a-z][a-z0-9_.-]*(?![\\s\\S])": {"$ref": f"#/$defs/{definition}"}
        },
        "additionalProperties": False,
    }
    if min_properties is not None:
        result["minProperties"] = min_properties
    return result


def locator_schema() -> dict[str, Any]:
    return {
        "oneOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "resource"],
                "properties": {
                    "kind": {"const": "bundled"},
                    "resource": {"$ref": "#/$defs/nonblank_string"},
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "path"],
                "properties": {
                    "kind": {"const": "file"},
                    "path": {"$ref": "#/$defs/nonblank_string"},
                },
            },
        ]
    }


def manifest_schema(old_defs: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "catalog-set.schema.json",
        "title": "EMBED composable catalog-set manifest",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "$schema",
            "catalog_set_schema_version",
            "semantic_catalog",
            "profiles",
            "extensions",
        ],
        "properties": {
            "$schema": {"const": "./catalog-set.schema.json"},
            "catalog_set_schema_version": {"const": 1},
            "semantic_catalog": {"$ref": "#/$defs/resource_locator"},
            "profiles": {
                "type": "array",
                "uniqueItems": True,
                "items": {"$ref": "#/$defs/resource_locator"},
            },
            "extensions": {
                "type": "array",
                "uniqueItems": True,
                "items": {"$ref": "#/$defs/resource_locator"},
            },
        },
        "$defs": {
            "nonblank_string": deepcopy(old_defs["nonblank_string"]),
            "resource_locator": locator_schema(),
        },
    }


def semantic_schema(old_defs: dict[str, Any]) -> dict[str, Any]:
    collections = {
        "clinical_objects": ("clinical_object", 1),
        "concepts": ("concept", 1),
        "semantic_relationships": ("semantic_relationship", None),
        "temporal_semantics": ("temporal_semantic", None),
        "aggregations": ("aggregation", None),
        "guardrails": ("guardrail", None),
        "coverage": ("coverage", None),
        "vocabularies": ("vocabulary", None),
        "sources": ("context_source", None),
        "contexts": ("clinical_context", None),
    }
    required = [
        "$schema",
        "semantic_schema_version",
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
        *collections,
    ]
    properties = {
        "$schema": {"const": "./catalog.schema.json"},
        "semantic_schema_version": {"const": 7},
    }
    old_schema = json.loads(
        (CATALOG / "catalog.schema.json").read_text(encoding="utf-8")
    )
    for name in (
        "binding_grains", "feature_kinds", "domains", "context_kinds",
        "context_scopes", "source_kinds", "source_locator_kinds",
        "claim_statuses", "semantic_relationship_kinds", "temporal_kinds",
        "aggregation_statuses", "coverage_statuses",
    ):
        properties[name] = deepcopy(old_schema["properties"][name])
    properties.update(
        {
            name: record_map(definition, min_properties=minimum)
            for name, (definition, minimum) in collections.items()
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "semantic/catalog.schema.json",
        "title": "EMBED portable clinical-semantic catalog",
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
        "$defs": deepcopy(old_defs),
    }


def add_authored_binding_ids(binding: dict[str, Any]) -> None:
    used: set[str] = set()
    specs = (
        ("feature_bindings", lambda item: ("feature", item["concept"], item["table"], item["column"])),
        ("object_bindings", lambda item: ("object", item["object"], item["table"])),
        ("tables", lambda item: ("table", item["table"])),
    )
    for collection, parts_for in specs:
        for index, item in enumerate(binding[collection], start=1):
            base = authored_id("open-v2", "binding", *parts_for(item))
            identifier = base if base not in used else f"{base}.{index}"
            item["id"] = identifier
            used.add(identifier)
    for item in binding["relationship_bindings"]:
        used.add(item["id"])
    for item in binding["relationship_binding_paths"]:
        used.add(item["id"])


def profile_schema(old_defs: dict[str, Any]) -> dict[str, Any]:
    defs = deepcopy(old_defs)
    for name in ("feature_binding", "object_binding", "table"):
        defs[name]["required"] = ["id", *defs[name]["required"]]
        defs[name]["properties"] = {
            "id": {"$ref": "#/$defs/identifier"},
            **defs[name]["properties"],
        }
    defs["feature_binding"]["properties"]["vocabulary"] = {
        "$ref": "#/$defs/identifier"
    }
    defs["qualification_subject"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "id"],
        "properties": {
            "kind": {
                "enum": [
                    "clinical_object",
                    "concept",
                    "semantic_relationship",
                    "temporal_semantic",
                    "aggregation",
                    "guardrail",
                ]
            },
            "id": {"$ref": "#/$defs/identifier"},
        },
    }
    defs["qualification"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "subject",
            "applicability",
            "summary",
            "claim_refs",
            "caveats",
        ],
        "properties": {
            "id": {"$ref": "#/$defs/identifier"},
            "subject": {"$ref": "#/$defs/qualification_subject"},
            "applicability": {
                "enum": [
                    "supported",
                    "unsupported",
                    "unresolved",
                    "interpretation_limit",
                ]
            },
            "summary": {"$ref": "#/$defs/nonblank_string"},
            "claim_refs": {"$ref": "#/$defs/claim_refs"},
            "caveats": {"$ref": "#/$defs/nonblank_strings"},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "profile.schema.json",
        "title": "EMBED dataset profile module",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "$schema",
            "profile_schema_version",
            "profile",
            "requires",
            "sources",
            "contexts",
            "coverage",
            "qualifications",
            "vocabularies",
            "profile_binding",
        ],
        "properties": {
            "$schema": {"const": "./profile.schema.json"},
            "profile_schema_version": {"const": 1},
            "profile": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "label"],
                "properties": {
                    "id": {"$ref": "#/$defs/identifier"},
                    "label": {"$ref": "#/$defs/nonblank_string"},
                },
            },
            "requires": {
                "type": "object",
                "additionalProperties": False,
                "required": ["semantic_schema_version"],
                "properties": {"semantic_schema_version": {"const": 7}},
            },
            "sources": record_map("context_source"),
            "contexts": record_map("clinical_context"),
            "coverage": record_map("coverage"),
            "qualifications": record_map("qualification"),
            "vocabularies": record_map("vocabulary"),
            "profile_binding": {"$ref": "#/$defs/profile_binding"},
        },
        "$defs": defs,
    }


def extension_schema(profile: dict[str, Any]) -> dict[str, Any]:
    defs = deepcopy(profile["$defs"])
    defs["extension_concept"] = deepcopy(defs["concept"])
    defs["extension_concept"]["required"] = [
        *defs["extension_concept"]["required"],
        "lifecycle_status",
    ]
    defs["extension_concept"]["properties"]["lifecycle_status"] = {
        "$ref": "#/$defs/lifecycle_status"
    }
    defs["lifecycle_status"] = {
        "enum": ["work_in_progress", "candidate", "adopted", "deprecated"]
    }
    defs["feature_lineage"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id", "output_concept", "input_concepts", "input_bindings",
            "summary", "claim_refs", "known_limitations", "lifecycle_status",
        ],
        "properties": {
            "id": {"$ref": "#/$defs/identifier"},
            "output_concept": {"$ref": "#/$defs/identifier"},
            "input_concepts": {"$ref": "#/$defs/identifiers"},
            "input_bindings": {"$ref": "#/$defs/identifiers"},
            "summary": {"$ref": "#/$defs/nonblank_string"},
            "claim_refs": {"$ref": "#/$defs/claim_refs"},
            "known_limitations": {"$ref": "#/$defs/nonblank_strings"},
            "lifecycle_status": {"$ref": "#/$defs/lifecycle_status"},
            "source_locator": {"$ref": "#/$defs/source_locator"},
        },
    }
    defs["source_locator"] = locator_schema()
    revision_common = {
        "id": {"$ref": "#/$defs/identifier"},
        "reason": {"$ref": "#/$defs/nonblank_string"},
        "claim_refs": {"$ref": "#/$defs/claim_refs"},
        "known_limitations": {"$ref": "#/$defs/nonblank_strings"},
    }
    defs["revision"] = {
        "oneOf": [
            {
                "type": "object", "additionalProperties": False,
                "required": ["id", "kind", "original_concept", "replacement_concept", "semantic_difference", "reason", "claim_refs", "known_limitations"],
                "properties": {
                    **revision_common,
                    "kind": {"const": "reinterprets_concept"},
                    "original_concept": {"$ref": "#/$defs/identifier"},
                    "replacement_concept": {"$ref": "#/$defs/identifier"},
                    "semantic_difference": {"$ref": "#/$defs/nonblank_string"},
                },
            },
            {
                "type": "object", "additionalProperties": False,
                "required": ["id", "kind", "original_binding", "replacement_binding", "reason", "claim_refs", "known_limitations", "original_remains_alternative"],
                "properties": {
                    **revision_common,
                    "kind": {"const": "replaces_binding"},
                    "original_binding": {"$ref": "#/$defs/identifier"},
                    "replacement_binding": {"$ref": "#/$defs/identifier"},
                    "original_remains_alternative": {"type": "boolean"},
                },
            },
        ]
    }
    binding_properties = deepcopy(defs["profile_binding"]["properties"])
    binding_properties["feature_bindings"].pop("minItems", None)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "extension.schema.json",
        "title": "EMBED project extension module",
        "type": "object",
        "additionalProperties": False,
        "required": ["$schema", "extension_schema_version", "extension", "applies_to", "requires", "semantic_additions", "qualifications", "feature_lineage", "sources", "contexts", "coverage", "vocabularies", "binding_additions", "revisions"],
        "properties": {
            "$schema": {"const": "./extension.schema.json"},
            "extension_schema_version": {"const": 1},
            "extension": {
                "type": "object", "additionalProperties": False,
                "required": ["id", "version", "label", "lifecycle_status"],
                "properties": {
                    "id": {"$ref": "#/$defs/identifier"},
                    "version": {"$ref": "#/$defs/nonblank_string"},
                    "label": {"$ref": "#/$defs/nonblank_string"},
                    "lifecycle_status": {"$ref": "#/$defs/lifecycle_status"},
                },
            },
            "applies_to": {
                "type": "object", "additionalProperties": False,
                "required": ["profile"],
                "properties": {"profile": {"$ref": "#/$defs/identifier"}},
            },
            "requires": {
                "type": "object", "additionalProperties": False,
                "required": ["semantic_schema_version", "profile_schema_version", "extensions"],
                "properties": {
                    "semantic_schema_version": {"const": 7},
                    "profile_schema_version": {"const": 1},
                    "extensions": {"$ref": "#/$defs/identifiers"},
                },
            },
            "semantic_additions": {
                "type": "object", "additionalProperties": False,
                "required": ["concepts"],
                "properties": {"concepts": record_map("extension_concept")},
            },
            "qualifications": record_map("qualification"),
            "feature_lineage": record_map("feature_lineage"),
            "sources": record_map("context_source"),
            "contexts": record_map("clinical_context"),
            "coverage": record_map("coverage"),
            "vocabularies": record_map("vocabulary"),
            "binding_additions": {
                "type": "object", "additionalProperties": False,
                "required": list(binding_properties),
                "properties": binding_properties,
            },
            "revisions": {"type": "array", "items": {"$ref": "#/$defs/revision"}},
        },
        "$defs": defs,
    }


def main() -> None:
    old = json.loads((CATALOG / "catalog.json").read_text(encoding="utf-8"))
    old_schema = json.loads((CATALOG / "catalog.schema.json").read_text(encoding="utf-8"))
    old_defs = old_schema["$defs"]

    portable_collections = (
        "clinical_objects", "concepts", "semantic_relationships",
        "temporal_semantics", "aggregations", "guardrails",
    )
    qualifications: dict[str, Any] = {}
    semantic_records: dict[str, Any] = {}
    for collection in portable_collections:
        semantic_records[collection] = {}
        subject_kind = collection[:-1] if collection != "clinical_objects" else "clinical_object"
        for identifier, original in old[collection].items():
            claims = profile_claims(original)
            record = strip_profile_links(original)
            if collection == "guardrails" and record.get("scope") == "profile_specific":
                record["scope"] = "embed_general"
                record["profiles"] = []
            if identifier == "guardrail.risk-probability-readiness":
                record["rationale"] = (
                    "Association or ranking studies may be possible with an "
                    "explicitly qualified score interpretation, but unresolved "
                    "scale, horizon, exceptional-value, and model-version "
                    "semantics limit probability interpretation."
                )
            semantic_records[collection][identifier] = record
            if claims:
                qualification_id = authored_id("open-v2", "qualification", subject_kind, identifier)
                qualifications[qualification_id] = {
                    "id": qualification_id,
                    "subject": {"kind": subject_kind, "id": identifier},
                    "applicability": "supported",
                    "summary": "Open V2 evidence qualifies this portable semantic record.",
                    "claim_refs": claims,
                    "caveats": [],
                }

    semantic = {
        "$schema": "./catalog.schema.json",
        "semantic_schema_version": 7,
        **{name: deepcopy(old[name]) for name in (
            "binding_grains", "feature_kinds", "domains", "semantic_relationship_kinds",
            "temporal_kinds", "aggregation_statuses", "coverage_statuses", "context_kinds",
            "context_scopes", "source_kinds", "source_locator_kinds", "claim_statuses",
        )},
        **semantic_records,
        "coverage": {},
        "vocabularies": {},
        "sources": {
            key: value for key, value in old["sources"].items()
            if value["scope"] != "profile_specific"
        },
        "contexts": {
            key: value for key, value in old["contexts"].items()
            if value["scope"] != "profile_specific"
        },
    }

    binding = deepcopy(old["profile_bindings"]["open-v2"])
    add_authored_binding_ids(binding)
    concept_vocabularies = {
        identifier: record.get("vocabulary")
        for identifier, record in old["concepts"].items()
        if record.get("vocabulary")
    }
    for item in binding["feature_bindings"]:
        vocabulary = concept_vocabularies.get(item["concept"])
        if vocabulary:
            item["vocabulary"] = f"open-v2.{vocabulary}"
    for record in semantic["concepts"].values():
        record.pop("vocabulary", None)

    profile = {
        "$schema": "./profile.schema.json",
        "profile_schema_version": 1,
        "profile": {"id": "open-v2", "label": "EMBED Open Data V2"},
        "requires": {"semantic_schema_version": 7},
        "sources": {
            key: value for key, value in old["sources"].items()
            if value["scope"] == "profile_specific"
        },
        "contexts": {
            key: value for key, value in old["contexts"].items()
            if value["scope"] == "profile_specific"
        },
        "coverage": deepcopy(old["coverage"]),
        "qualifications": qualifications,
        "vocabularies": {
            f"open-v2.{identifier}": value
            for identifier, value in old["vocabularies"].items()
        },
        "profile_binding": binding,
    }

    manifest = {
        "$schema": "./catalog-set.schema.json",
        "catalog_set_schema_version": 1,
        "semantic_catalog": {"kind": "bundled", "resource": "semantic/catalog.json"},
        "profiles": [{"kind": "bundled", "resource": "profiles/open-v2.json"}],
        "extensions": [],
    }

    manifest_contract = manifest_schema(old_defs)
    semantic_contract = semantic_schema(old_defs)
    profile_contract = profile_schema(old_defs)
    extension_contract = extension_schema(profile_contract)

    dump(CATALOG / "catalog-set.json", manifest)
    dump(CATALOG / "catalog-set.schema.json", manifest_contract)
    dump(CATALOG / "semantic" / "catalog.json", semantic)
    dump(CATALOG / "semantic" / "catalog.schema.json", semantic_contract)
    dump(CATALOG / "profiles" / "open-v2.json", profile)
    dump(CATALOG / "profiles" / "profile.schema.json", profile_contract)
    dump(CATALOG / "extensions" / "extension.schema.json", extension_contract)


if __name__ == "__main__":
    main()
