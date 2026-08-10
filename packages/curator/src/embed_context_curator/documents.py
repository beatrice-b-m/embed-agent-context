"""Authored-document addressing and lossless curator serialization."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONTRIBUTION_COLLECTIONS = {
    "clinical_objects": "clinical_object",
    "concepts": "feature",
    "semantic_relationships": "semantic_relationship",
    "temporal_semantics": "temporal_semantic",
    "aggregations": "aggregation",
    "guardrails": "guardrail",
    "coverage": "coverage",
}
SEMANTIC_COLLECTIONS = {
    **CONTRIBUTION_COLLECTIONS,
    "vocabularies": "vocabulary",
    "sources": "source",
    "contexts": "context",
}
MODULE_COLLECTIONS = {
    "sources": "source",
    "contexts": "context",
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
    container_path: tuple[str | int, ...]
    storage: str
    identity_field: str | None
    identity_value: str
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
        if document.kind == "semantic":
            for collection, kind in SEMANTIC_COLLECTIONS.items():
                entries.extend(_map_entries(document, (collection,), collection, kind, is_editable))
        elif document.kind in {"profile", "extension"}:
            for collection, kind in CONTRIBUTION_COLLECTIONS.items():
                entries.extend(
                    _map_entries(
                        document,
                        ("contributions", collection),
                        collection,
                        kind,
                        is_editable,
                    )
                )
            for collection, kind in MODULE_COLLECTIONS.items():
                if collection in document.mapping:
                    entries.extend(_map_entries(document, (collection,), collection, kind, is_editable))
            for collection, kind in BINDING_COLLECTIONS.items():
                entries.extend(_array_entries(document, ("profile_binding", collection), collection, kind, is_editable))
            entries.extend(_physical_column_entries(document, is_editable))
    return tuple(sorted(entries, key=lambda item: (item.kind, item.identifier, item.key)))


def record_at(mapping: Mapping[str, Any], entry: SourceEntry) -> Mapping[str, Any]:
    container = _container(mapping, entry.container_path)
    if entry.storage == "map":
        value = container[entry.identifier]
    else:
        value = container[_array_index(container, entry.identity_field, entry.identity_value)]
    if not isinstance(value, Mapping):
        raise KeyError(entry.key)
    return value


def replace_record(mapping: dict[str, Any], entry: SourceEntry, record: Mapping[str, Any]) -> None:
    container = _container(mapping, entry.container_path)
    if entry.storage == "map":
        container[entry.identifier] = mutable_copy(record)
        return
    index = _array_index(container, entry.identity_field, entry.identity_value)
    container[index] = mutable_copy(record)


def delete_record(mapping: dict[str, Any], entry: SourceEntry) -> None:
    container = _container(mapping, entry.container_path)
    if entry.storage == "map":
        del container[entry.identifier]
    else:
        del container[_array_index(container, entry.identity_field, entry.identity_value)]


def create_record(
    mapping: dict[str, Any], *, container_path: tuple[str | int, ...], storage: str,
    identifier: str, record: Mapping[str, Any], identity_field: str = "id",
    identity_value: str | None = None,
) -> None:
    container = _container(mapping, container_path)
    if storage == "map":
        if identifier in container:
            raise ValueError(f"record {identifier!r} already exists")
        container[identifier] = mutable_copy(record)
        return
    selected_value = identity_value or identifier
    if any(
        isinstance(item, Mapping) and item.get(identity_field) == selected_value
        for item in container
    ):
        raise ValueError(f"record {identifier!r} already exists")
    item = mutable_copy(record)
    if item.get(identity_field) != selected_value:
        raise ValueError(
            f"array record {identity_field} must match the requested identity"
        )
    container.append(item)


def creation_location(document_kind: str, kind: str) -> tuple[tuple[str, ...], str]:
    if document_kind == "semantic":
        inverse = {value: key for key, value in SEMANTIC_COLLECTIONS.items()}
        collection = inverse.get(kind)
        if collection:
            return (collection,), "map"
    if document_kind in {"profile", "extension"}:
        inverse_contributions = {
            value: key for key, value in CONTRIBUTION_COLLECTIONS.items()
        }
        collection = inverse_contributions.get(kind)
        if collection:
            return ("contributions", collection), "map"
        inverse_modules = {value: key for key, value in MODULE_COLLECTIONS.items()}
        collection = inverse_modules.get(kind)
        if collection and not (document_kind == "profile" and kind == "feature_lineage"):
            return (collection,), "map"
        inverse_bindings = {value: key for key, value in BINDING_COLLECTIONS.items()}
        binding = inverse_bindings.get(kind)
        if binding:
            return ("profile_binding", binding), "array"
    raise ValueError(f"{kind!r} records are not owned by an editable {document_kind} module")


def _map_entries(document: Any, path: tuple[str, ...], collection: str, kind: str, editable: bool) -> list[SourceEntry]:
    container = _container(document.mapping, path)
    if not isinstance(container, Mapping):
        return []
    return [
        _entry(
            document, path, collection, kind, str(identifier), "map", editable,
            position=None, identity_field=None, identity_value=str(identifier),
        )
        for identifier in container
    ]


def _array_entries(document: Any, path: tuple[str | int, ...], collection: str, kind: str, editable: bool) -> list[SourceEntry]:
    container = _container(document.mapping, path)
    if not isinstance(container, Sequence) or isinstance(container, (str, bytes)):
        return []
    result = []
    for position, item in enumerate(container):
        if isinstance(item, Mapping) and isinstance(item.get("id"), str):
            result.append(
                _entry(
                    document, path, collection, kind, item["id"], "array",
                    editable, position=position, identity_field="id",
                    identity_value=item["id"],
                )
            )
    return result


def _physical_column_entries(document: Any, editable: bool) -> list[SourceEntry]:
    result: list[SourceEntry] = []
    tables = document.mapping.get("profile_binding", {}).get("tables", ())
    if not isinstance(tables, Sequence) or isinstance(tables, (str, bytes)):
        return result
    for table_index, table in enumerate(tables):
        if not isinstance(table, Mapping) or not isinstance(table.get("id"), str):
            continue
        columns = table.get("columns", ())
        if not isinstance(columns, Sequence) or isinstance(columns, (str, bytes)):
            continue
        for column_index, column in enumerate(columns):
            if not isinstance(column, Mapping) or not isinstance(column.get("name"), str):
                continue
            identifier = f"{table['id']}::{column['name']}"
            result.append(
                _entry(
                    document,
                    ("profile_binding", "tables", table_index, "columns"),
                    "columns",
                    "physical_column",
                    identifier,
                    "array",
                    editable,
                    position=column_index,
                    identity_field="name",
                    identity_value=column["name"],
                )
            )
    return result


def _entry(document: Any, path: tuple[str | int, ...], collection: str, kind: str, identifier: str, storage: str, editable: bool, position: int | None, identity_field: str | None, identity_value: str) -> SourceEntry:
    pointer_parts = [*_pointer_parts(path)]
    pointer_parts.append(_escape(identifier) if storage == "map" else str(position))
    return SourceEntry(
        key=f"{kind}:{identifier}", kind=kind, identifier=identifier,
        document_path=document.source_path, document_kind=document.kind,
        locator_kind=document.locator_kind, module_id=document.module_id,
        target_profile=document.target_profile, collection=collection,
        container_path=path, storage=storage,
        identity_field=identity_field, identity_value=identity_value,
        json_pointer="/" + "/".join(pointer_parts), editable=editable,
    )


def _container(mapping: Any, path: tuple[str | int, ...]) -> Any:
    value = mapping
    for key in path:
        value = value[key]
    return value


def _array_index(
    values: Sequence[Any], identity_field: str | None, identity_value: str
) -> int:
    if identity_field is None:
        raise KeyError(identity_value)
    for index, item in enumerate(values):
        if isinstance(item, Mapping) and item.get(identity_field) == identity_value:
            return index
    raise KeyError(identity_value)


def _pointer_parts(path: tuple[str | int, ...]) -> list[str]:
    return [_escape(str(part)) for part in path]


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")
