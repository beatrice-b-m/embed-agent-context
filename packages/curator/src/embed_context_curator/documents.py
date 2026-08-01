"""Authored-document addressing and lossless curator serialization."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SEMANTIC_COLLECTIONS = {
    "clinical_objects": "clinical_object",
    "concepts": "feature",
    "semantic_relationships": "semantic_relationship",
    "temporal_semantics": "temporal_semantic",
    "aggregations": "aggregation",
    "guardrails": "guardrail",
    "coverage": "coverage",
    "vocabularies": "vocabulary",
    "sources": "source",
    "contexts": "context",
}
MODULE_COLLECTIONS = {
    "sources": "source",
    "contexts": "context",
    "coverage": "coverage",
    "qualifications": "qualification",
    "vocabularies": "vocabulary",
    "feature_lineage": "feature_lineage",
}
BINDING_COLLECTIONS = {
    "feature_bindings": "feature_binding",
    "object_bindings": "object_binding",
    "tables": "table",
    "relationship_bindings": "relationship_binding",
    "relationship_binding_paths": "relationship_binding_path",
}


@dataclass(frozen=True, slots=True)
class SourceEntry:
    key: str
    kind: str
    identifier: str
    document_path: Path
    document_kind: str
    locator_kind: str
    module_id: str | None
    target_profile: str | None
    collection: str
    container_path: tuple[str, ...]
    storage: str
    json_pointer: str
    editable: bool


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def mutable_copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): mutable_copy(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [mutable_copy(item) for item in value]
    return value


def build_source_index(
    documents: Sequence[Any], editable_path: Path | None = None
) -> tuple[SourceEntry, ...]:
    editable = editable_path.resolve() if editable_path else None
    entries: list[SourceEntry] = []
    for document in documents:
        if document.kind == "manifest":
            continue
        is_editable = editable is not None and document.source_path.resolve() == editable
        if document.kind in {"semantic", "legacy"}:
            for collection, kind in SEMANTIC_COLLECTIONS.items():
                entries.extend(_map_entries(document, (collection,), collection, kind, is_editable))
            if document.kind == "legacy":
                for profile in document.mapping.get("profile_bindings", {}):
                    for collection, kind in BINDING_COLLECTIONS.items():
                        entries.extend(
                            _array_entries(
                                document,
                                ("profile_bindings", profile, collection),
                                collection,
                                kind,
                                False,
                            )
                        )
        elif document.kind == "profile":
            for collection, kind in MODULE_COLLECTIONS.items():
                if collection in document.mapping:
                    entries.extend(_map_entries(document, (collection,), collection, kind, is_editable))
            for collection, kind in BINDING_COLLECTIONS.items():
                entries.extend(_array_entries(document, ("profile_binding", collection), collection, kind, is_editable))
        elif document.kind == "extension":
            entries.extend(_map_entries(document, ("semantic_additions", "concepts"), "concepts", "feature", is_editable))
            for collection, kind in MODULE_COLLECTIONS.items():
                if collection in document.mapping:
                    entries.extend(_map_entries(document, (collection,), collection, kind, is_editable))
            for collection, kind in BINDING_COLLECTIONS.items():
                entries.extend(_array_entries(document, ("binding_additions", collection), collection, kind, is_editable))
            entries.extend(_array_entries(document, ("revisions",), "revisions", "revision", is_editable))
    return tuple(sorted(entries, key=lambda item: (item.kind, item.identifier, item.key)))


def record_at(mapping: Mapping[str, Any], entry: SourceEntry) -> Mapping[str, Any]:
    container = _container(mapping, entry.container_path)
    if entry.storage == "map":
        value = container[entry.identifier]
    else:
        value = next(
            item for item in container
            if isinstance(item, Mapping) and item.get("id") == entry.identifier
        )
    if not isinstance(value, Mapping):
        raise KeyError(entry.key)
    return value


def replace_record(mapping: dict[str, Any], entry: SourceEntry, record: Mapping[str, Any]) -> None:
    container = _container(mapping, entry.container_path)
    if entry.storage == "map":
        container[entry.identifier] = mutable_copy(record)
        return
    index = _array_index(container, entry.identifier)
    container[index] = mutable_copy(record)


def delete_record(mapping: dict[str, Any], entry: SourceEntry) -> None:
    container = _container(mapping, entry.container_path)
    if entry.storage == "map":
        del container[entry.identifier]
    else:
        del container[_array_index(container, entry.identifier)]


def create_record(
    mapping: dict[str, Any], *, container_path: tuple[str, ...], storage: str,
    identifier: str, record: Mapping[str, Any]
) -> None:
    container = _container(mapping, container_path)
    if storage == "map":
        if identifier in container:
            raise ValueError(f"record {identifier!r} already exists")
        container[identifier] = mutable_copy(record)
        return
    if any(isinstance(item, Mapping) and item.get("id") == identifier for item in container):
        raise ValueError(f"record {identifier!r} already exists")
    item = mutable_copy(record)
    if item.get("id") != identifier:
        raise ValueError("array record id must match the requested stable ID")
    container.append(item)


def creation_location(document_kind: str, kind: str) -> tuple[tuple[str, ...], str]:
    if document_kind == "semantic":
        inverse = {value: key for key, value in SEMANTIC_COLLECTIONS.items()}
        collection = inverse.get(kind)
        if collection:
            return (collection,), "map"
    if document_kind in {"profile", "extension"}:
        inverse_modules = {value: key for key, value in MODULE_COLLECTIONS.items()}
        collection = inverse_modules.get(kind)
        if collection and not (document_kind == "profile" and kind == "feature_lineage"):
            return (collection,), "map"
        inverse_bindings = {value: key for key, value in BINDING_COLLECTIONS.items()}
        binding = inverse_bindings.get(kind)
        if binding:
            parent = "profile_binding" if document_kind == "profile" else "binding_additions"
            return (parent, binding), "array"
    if document_kind == "extension" and kind == "feature":
        return ("semantic_additions", "concepts"), "map"
    if document_kind == "extension" and kind == "revision":
        return ("revisions",), "array"
    raise ValueError(f"{kind!r} records are not owned by an editable {document_kind} module")


def _map_entries(document: Any, path: tuple[str, ...], collection: str, kind: str, editable: bool) -> list[SourceEntry]:
    container = _container(document.mapping, path)
    if not isinstance(container, Mapping):
        return []
    return [
        _entry(document, path, collection, kind, str(identifier), "map", editable, position=None)
        for identifier in container
    ]


def _array_entries(document: Any, path: tuple[str, ...], collection: str, kind: str, editable: bool) -> list[SourceEntry]:
    container = _container(document.mapping, path)
    if not isinstance(container, Sequence) or isinstance(container, (str, bytes)):
        return []
    result = []
    for position, item in enumerate(container):
        if isinstance(item, Mapping) and isinstance(item.get("id"), str):
            result.append(_entry(document, path, collection, kind, item["id"], "array", editable, position=position))
    return result


def _entry(document: Any, path: tuple[str, ...], collection: str, kind: str, identifier: str, storage: str, editable: bool, position: int | None) -> SourceEntry:
    pointer_parts = [*_pointer_parts(path)]
    pointer_parts.append(_escape(identifier) if storage == "map" else str(position))
    return SourceEntry(
        key=f"{kind}:{identifier}", kind=kind, identifier=identifier,
        document_path=document.source_path, document_kind=document.kind,
        locator_kind=document.locator_kind, module_id=document.module_id,
        target_profile=document.target_profile, collection=collection,
        container_path=path, storage=storage,
        json_pointer="/" + "/".join(pointer_parts), editable=editable,
    )


def _container(mapping: Any, path: tuple[str, ...]) -> Any:
    value = mapping
    for key in path:
        value = value[key]
    return value


def _array_index(values: Sequence[Any], identifier: str) -> int:
    for index, item in enumerate(values):
        if isinstance(item, Mapping) and item.get("id") == identifier:
            return index
    raise KeyError(identifier)


def _pointer_parts(path: tuple[str, ...]) -> list[str]:
    return [_escape(part) for part in path]


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")
