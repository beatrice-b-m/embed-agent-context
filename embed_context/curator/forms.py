"""Schema-derived presentation metadata for the curator's hybrid editor.

The JSON Schemas remain authoritative.  This module only chooses browser
controls and supplies human-facing labels, help, sections, and compatible
reference choices.  Every field is represented, even when its control is the
lossless record-JSON fallback.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator


_MULTILINE_FIELDS = {
    "definition",
    "description",
    "summary",
    "statement",
    "rationale",
    "meaning",
    "attribution",
    "version_scope",
}
_SET_LIKE_FIELDS = {
    "aliases",
    "caveats",
    "claim_refs",
    "domains",
    "evidence",
    "objects",
    "search_terms",
    "semantic_relationships",
}
_REFERENCE_KINDS: dict[str, tuple[str, ...]] = {
    "aggregation": ("aggregation",),
    "aggregations": ("aggregation",),
    "claim_refs": ("claim",),
    "concept": ("concept",),
    "concepts": ("concept",),
    "coverage": ("coverage",),
    "coverage_ids": ("coverage",),
    "input_concepts": ("concept",),
    "object": ("clinical_object",),
    "objects": ("clinical_object",),
    "original": ("concept",),
    "original_binding": ("feature_binding",),
    "original_concept": ("concept",),
    "output_concept": ("concept",),
    "relationship_bindings": ("relationship_binding",),
    "replacement": ("concept",),
    "replacement_binding": ("feature_binding",),
    "replacement_concept": ("concept",),
    "semantic_relationship": ("semantic_relationship",),
    "semantic_relationships": ("semantic_relationship",),
    "source_concept": ("concept",),
    "source_object": ("clinical_object",),
    "sources": ("source",),
    "subject": ("clinical_object", "concept", "semantic_relationship", "temporal_semantic", "aggregation", "guardrail"),
    "table": ("table",),
    "target_object": ("clinical_object",),
    "temporal_semantic": ("temporal_semantic",),
    "temporal_semantics": ("temporal_semantic",),
    "vocabulary": ("vocabulary",),
}

_ENHANCED_FAMILIES = {
    "concept",
    "extension_concept",
    "clinical_context",
    "context_claim",
    "qualification",
    "feature_binding",
    "revision",
}

_FIELD_HELP = {
    "claim_refs": "Reviewed context-id#claim-id references supporting this field.",
    "id": "Stable identifier. Existing record identifiers cannot be renamed in the viewer.",
    "lifecycle_status": "Project contribution lifecycle; this does not alter released semantics.",
    "subject": "Portable record qualified by this profile or extension contribution.",
    "replacement": "Project-owned replacement selected by this typed revision.",
}

_FIELD_WARNINGS = {
    "definition": "Changing clinical meaning may require a new concept rather than editing an existing one.",
    "id": "Stable IDs are immutable after record creation.",
    "replacement": "A revision changes the active project view without mutating the original contribution.",
    "subject": "Qualifications add scoped interpretation; they do not redefine portable meaning.",
}


def _label(name: str) -> str:
    return name.replace("_", " ").strip().title()


def _pointer(parts: Iterable[str]) -> str:
    escaped = (part.replace("~", "~0").replace("/", "~1") for part in parts)
    return "/" + "/".join(escaped)


def _resolve(schema: Mapping[str, Any], node: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve local refs and merge simple allOf overlays for presentation."""

    result: dict[str, Any] = {}
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/"):
        target: Any = schema
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        result.update(_resolve(schema, target))
    for branch in node.get("allOf", []):
        if isinstance(branch, Mapping):
            result.update(_resolve(schema, branch))
    result.update({key: deepcopy(value) for key, value in node.items() if key not in {"$ref", "allOf"}})
    return result


def definition_schema(schema: Mapping[str, Any], family: str) -> dict[str, Any]:
    """Return the resolved schema for an editable record family."""

    definitions = schema.get("$defs", {})
    if family not in definitions:
        raise KeyError(f"unknown schema record family: {family}")
    return _resolve(schema, definitions[family])


def _type_for(node: Mapping[str, Any]) -> str | None:
    value = node.get("type")
    if isinstance(value, str):
        return value
    if "enum" in node:
        return "string"
    if "properties" in node:
        return "object"
    return None


def _control_for(name: str, node: Mapping[str, Any], enhanced: bool) -> str:
    if not enhanced:
        return "json"
    if name in _REFERENCE_KINDS:
        return "reference"
    if "enum" in node:
        return "select"
    node_type = _type_for(node)
    if node_type == "boolean":
        return "checkbox"
    if node_type in {"integer", "number"}:
        return "number"
    if node_type in {"array", "object"}:
        return "json"
    if name in _MULTILINE_FIELDS:
        return "textarea"
    return "text"


def _normalize_choices(
    references: Mapping[str, Iterable[Any]] | None, compatible: tuple[str, ...]
) -> list[dict[str, str]]:
    choices: list[dict[str, str]] = []
    if not references:
        return choices
    for kind in compatible:
        for item in references.get(kind, ()):
            if isinstance(item, str):
                choices.append({"kind": kind, "id": item, "label": item})
            elif isinstance(item, Mapping) and isinstance(item.get("id"), str):
                choices.append(
                    {
                        "kind": kind,
                        "id": item["id"],
                        "label": str(item.get("label", item["id"])),
                    }
                )
    return sorted(choices, key=lambda item: (item["kind"], item["label"].casefold(), item["id"]))


def build_form_spec(
    schema: Mapping[str, Any],
    family: str,
    *,
    record: Mapping[str, Any] | None = None,
    references: Mapping[str, Iterable[Any]] | None = None,
    creating: bool = False,
) -> dict[str, Any]:
    """Build JSON-serializable form metadata for one authored record.

    Unknown or deeply nested fields deliberately use a JSON control.  The
    original record is returned separately and is never reconstructed from the
    presentation metadata, which keeps the editor lossless.
    """

    record_schema = definition_schema(schema, family)
    properties = dict(record_schema.get("properties", {}))
    variants = []
    for index, raw_variant in enumerate(record_schema.get("oneOf", ())):
        variant = _resolve(schema, raw_variant)
        discriminator = None
        for name, node in variant.get("properties", {}).items():
            resolved_node = _resolve(schema, node)
            if "const" in resolved_node:
                discriminator = {"field": name, "value": resolved_node["const"]}
            properties.setdefault(name, node)
        variants.append(
            {
                "index": index,
                "discriminator": discriminator,
                "required": list(variant.get("required", ())),
            }
        )
    required_sets = [set(item["required"]) for item in variants]
    required = (
        set.intersection(*required_sets)
        if required_sets
        else set(record_schema.get("required", ()))
    )
    enhanced = family in _ENHANCED_FAMILIES
    fields: list[dict[str, Any]] = []
    for position, (name, raw_node) in enumerate(properties.items()):
        node = _resolve(schema, raw_node)
        compatible = _REFERENCE_KINDS.get(name, ())
        field = {
            "name": name,
            "label": _label(name),
            "position": position,
            "required": name in required,
            "required_in_variants": [
                item["index"] for item in variants if name in item["required"]
            ],
            "immutable": name == "id" and not creating,
            "type": _type_for(node),
            "control": _control_for(name, node, enhanced),
            "section": "Identity" if name in {"id", "label", "subject"} else "Details",
            "list_behavior": "set" if name in _SET_LIKE_FIELDS else "ordered",
            "help": _FIELD_HELP.get(name, node.get("description", "")),
            "warning": _FIELD_WARNINGS.get(name, ""),
            "enum": deepcopy(node.get("enum", [])),
            "compatible_kinds": list(compatible),
            "choices": _normalize_choices(references, compatible),
            "schema": node,
        }
        fields.append(field)
    return {
        "family": family,
        "enhanced": enhanced,
        "variants": variants,
        "fields": fields,
        "record": deepcopy(dict(record or {})),
        "fallback": {
            "control": "record_json",
            "label": "Complete authored record JSON",
            "help": "Lossless fallback for every schema-valid field in this authored record.",
        },
    }


def merge_record_json(original: Mapping[str, Any], replacement: Mapping[str, Any]) -> dict[str, Any]:
    """Return a lossless record replacement without mutating either input."""

    merged = deepcopy(dict(original))
    merged.update(deepcopy(dict(replacement)))
    return merged


def local_validate_record(
    schema: Mapping[str, Any], family: str, record: Any
) -> list[dict[str, Any]]:
    """Run inexpensive JSON-Schema shape checks and normalize diagnostics."""

    wrapper = {
        "$schema": schema.get("$schema", "https://json-schema.org/draft/2020-12/schema"),
        "$defs": deepcopy(schema.get("$defs", {})),
        "$ref": f"#/$defs/{family}",
    }
    validator = Draft202012Validator(wrapper)
    diagnostics = []
    for error in sorted(validator.iter_errors(record), key=lambda item: (list(item.absolute_path), item.message)):
        diagnostics.append(
            {
                "stage": "local",
                "pointer": _pointer(str(part) for part in error.absolute_path),
                "message": error.message,
                "validator": error.validator,
            }
        )
    return diagnostics


__all__ = [
    "build_form_spec",
    "definition_schema",
    "local_validate_record",
    "merge_record_json",
]
