"""Thread-safe authored draft session for the local curator."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import stat
import tempfile
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from embed_context.catalog import (
    CatalogError,
    _replace_resolved_document,
    _resolve_catalog,
    _schema_path_for,
)

from .documents import (
    SourceEntry,
    build_source_index,
    canonical_json_bytes,
    create_record as insert_authored_record,
    creation_location,
    delete_record as remove_authored_record,
    mutable_copy,
    record_at,
    replace_record as replace_authored_record,
)
from .graph import AuthoredGraphRecord, build_graph
from .query_diff import run_discovery_comparison
from .forms import build_form_spec


class CuratorError(ValueError):
    """Safe private-API failure with an HTTP mapping."""

    def __init__(
        self, message: str, *, error_type: str = "curator_error",
        http_status: int = 400, details: Any = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.http_status = http_status
        self.details = details


class CuratorSession:
    """Own one immutable baseline and at most one authored draft document."""

    INVENTORY_LIMIT = 1000

    def __init__(
        self,
        catalog_set: str | Path | None = None,
        *,
        profile_paths: Sequence[str | Path] | None = None,
        extension_paths: Sequence[str | Path] | None = None,
        include_default_profiles: bool = True,
        include_default_extensions: bool = False,
        edit_module: str | Path | None = None,
    ) -> None:
        self._arguments = {
            "catalog_set": catalog_set,
            "profile_paths": tuple(profile_paths or ()),
            "extension_paths": tuple(extension_paths or ()),
            "include_default_profiles": include_default_profiles,
            "include_default_extensions": include_default_extensions,
        }
        self._lock = threading.RLock()
        self._composition = _resolve_catalog(**self._arguments)
        self._baseline_catalog = self._composition.catalog
        self._editable_document = self._select_editable(edit_module)
        self.editable_path = (
            self._editable_document.source_path
            if self._editable_document is not None else None
        )
        self._baseline_bytes = (
            self._editable_document.source_bytes
            if self._editable_document is not None else None
        )
        self._draft = (
            mutable_copy(self._editable_document.mapping)
            if self._editable_document is not None else None
        )
        self._revision = 0
        self._valid_revision = 0 if self._draft is not None else None
        self._draft_composition = self._composition if self._draft is not None else None
        self._diagnostics: list[dict[str, Any]] = []
        self._index = build_source_index(self._composition.documents, self.editable_path)

    @property
    def dirty(self) -> bool:
        with self._lock:
            return self._draft is not None and canonical_json_bytes(self._draft) != self._baseline_bytes

    def session_info(self) -> dict[str, Any]:
        with self._lock:
            editable = self._editable_document
            return {
                "schema_version": self._baseline_catalog.schema_version,
                "configuration_fingerprint": self._baseline_catalog.fingerprint,
                "draft_fingerprint": (
                    self._draft_composition.catalog.fingerprint
                    if self._draft_composition is not None and self._valid_revision == self._revision
                    else None
                ),
                "documents": [self._document_info(item) for item in self._composition.documents],
                "editable": editable is not None,
                "editable_document": self._document_info(editable) if editable else None,
                "revision": self._revision,
                "dirty": self.dirty,
                "valid": self._valid_revision == self._revision if editable else True,
                "last_valid_revision": self._valid_revision,
                "diagnostics": list(self._diagnostics),
            }

    def list_records(
        self, *, text: str | None = None, kind: str | None = None,
        origin: str | None = None, profile: str | None = None,
        lifecycle: str | None = None, domain: str | None = None,
        status: str | None = None, limit: int = 500,
    ) -> dict[str, Any]:
        if limit < 1 or limit > self.INVENTORY_LIMIT:
            raise CuratorError(f"limit must be between 1 and {self.INVENTORY_LIMIT}")
        with self._lock:
            entries = list(self._current_index())
            if self._draft is not None:
                current_keys = {(entry.kind, entry.identifier) for entry in entries}
                entries.extend(
                    entry
                    for entry in self._index
                    if entry.editable
                    and (entry.kind, entry.identifier) not in current_keys
                )
            records = [self._inventory_item(entry) for entry in entries]
            needle = (text or "").casefold().strip()
            def matches(item: Mapping[str, Any]) -> bool:
                return (
                    (not kind or item["kind"] == kind)
                    and (not origin or item["contribution_class"] == origin)
                    and (not profile or item.get("target_profile") == profile)
                    and (not lifecycle or item.get("lifecycle") == lifecycle)
                    and (not status or item["draft_state"] == status)
                    and (not domain or domain in item["domains"])
                    and (not needle or needle in " ".join((item["identifier"], item["label"], *item["domains"])).casefold())
                )
            filtered = [item for item in records if matches(item)]
            filtered.sort(key=lambda item: (item["kind"], item["label"].casefold(), item["identifier"]))
            return {"records": filtered[:limit], "total": len(filtered), "limit": limit}

    def get_record(self, kind: str, identifier: str) -> dict[str, Any]:
        with self._lock:
            deleted = False
            try:
                entry = self._find_entry(kind, identifier)
            except CuratorError:
                authored_kind = "feature" if kind == "concept" else kind
                matches = [
                    item
                    for item in self._index
                    if item.editable
                    and item.kind == authored_kind
                    and item.identifier == identifier
                    and self._draft_state(item) == "deleted"
                ]
                if len(matches) != 1:
                    raise
                entry = matches[0]
                deleted = True
            document = self._editable_document if deleted else self._document_for_entry(entry)
            raw = record_at(document.mapping, entry)
            origin = self._origin(kind, identifier)
            result = {
                "kind": kind,
                "identifier": identifier,
                "authored": mutable_copy(raw),
                "source": self._entry_info(entry),
                "origin": origin,
                "effective": self._effective_record(kind, identifier),
                "draft_state": "deleted" if deleted else self._draft_state(entry),
                "revision": self._revision,
                "editable": entry.editable and not deleted,
            }
            result["form_spec"] = None if deleted else self._form_spec(entry, raw)
            return result

    def neighborhood(self, kind: str, identifier: str, *, depth: int = 1) -> dict[str, Any]:
        with self._lock:
            catalog = self._current_catalog()
            def graph_key(entry: SourceEntry) -> str:
                graph_kind = "concept" if entry.kind == "feature" else entry.kind
                return f"{graph_kind}:{entry.identifier}"

            editable_keys = {
                graph_key(entry) for entry in self._current_index() if entry.editable
            }
            states = {
                graph_key(entry): self._draft_state(entry)
                for entry in self._current_index()
            }
            graph_kind = "concept" if kind == "feature" else kind
            return build_graph(
                catalog,
                editable_keys=editable_keys,
                draft_states=states,
                authored_overlay=self._graph_overlay(),
                diagnostics=self._diagnostics,
            ).neighborhood(graph_kind, identifier, depth=depth)

    def _graph_overlay(self) -> tuple[AuthoredGraphRecord, ...]:
        """Return current editable authorship, including invalid draft state."""

        if self._draft is None:
            return ()
        before = {
            (entry.kind, entry.identifier): entry
            for entry in self._index
            if entry.editable
        }
        after = {
            (entry.kind, entry.identifier): entry
            for entry in self._current_index()
            if entry.editable
        }
        overlay = []
        for key in sorted(set(before) | set(after)):
            entry = after.get(key) or before[key]
            current = after.get(key)
            if current is not None and key in before:
                baseline_record = record_at(
                    self._editable_document.mapping, before[key]
                )
                current_record = record_at(self._draft_document().mapping, current)
                if baseline_record == current_record:
                    continue
            document = self._document_for_entry(current or entry)
            origin = self._origin(entry.kind, entry.identifier)
            if not origin:
                origin = {
                    "contribution_class": _class_for(entry.document_kind),
                    "document_kind": entry.document_kind,
                    "module_id": entry.module_id,
                    "target_profile": entry.target_profile,
                    "lifecycle_status": self._editable_document.lifecycle_status,
                }
            overlay.append(
                AuthoredGraphRecord(
                    kind=entry.kind,
                    identifier=entry.identifier,
                    record=(record_at(document.mapping, current) if current else None),
                    source_pointer=entry.json_pointer,
                    origin=origin,
                    profile=entry.target_profile,
                    lifecycle=origin.get("lifecycle_status"),
                    draft_state=self._draft_state(current) if current else "deleted",
                )
            )
        return tuple(overlay)

    def discover(self, request: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"query", "profile", "kinds", "domain", "limit"}
        extra = set(request) - allowed
        if extra:
            raise CuratorError(f"unknown discovery fields: {', '.join(sorted(extra))}")
        query = request.get("query", "")
        if not isinstance(query, str):
            raise CuratorError("query must be a string")
        kinds = request.get("kinds")
        if kinds is not None and (not isinstance(kinds, list) or not all(isinstance(item, str) for item in kinds)):
            raise CuratorError("kinds must be an array of strings")
        limit = request.get("limit", 10)
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise CuratorError("limit must be an integer")
        with self._lock:
            draft = (
                self._draft_composition.catalog
                if self._valid_revision == self._revision and self.dirty and self._draft_composition is not None
                else None
            )
            result = run_discovery_comparison(
                self._baseline_catalog, draft, query=query,
                profile=request.get("profile"), kinds=tuple(kinds) if kinds else None,
                domain=request.get("domain"), limit=limit,
                draft_revision=self._revision if draft is not None else None,
            )
            if self._draft is not None and self._valid_revision != self._revision:
                result["draft_unavailable"] = {
                    "reason": "invalid_draft", "revision": self._revision,
                    "last_valid_revision": self._valid_revision,
                    "diagnostics": list(self._diagnostics),
                }
            return result

    def create_record(self, request: Mapping[str, Any]) -> dict[str, Any]:
        self._require_editable()
        revision = request.get("revision")
        kind = request.get("kind")
        identifier = request.get("identifier")
        record = request.get("record")
        if not isinstance(kind, str) or not isinstance(identifier, str) or not isinstance(record, Mapping):
            raise CuratorError("kind, identifier, and record are required")
        with self._lock:
            self._check_revision(revision)
            path, storage = creation_location(self._editable_document.kind, kind)
            insert_authored_record(self._draft, container_path=path, storage=storage, identifier=identifier, record=record)
            return self._finish_mutation()

    def replace_record(self, kind: str, identifier: str, request: Mapping[str, Any]) -> dict[str, Any]:
        record = request.get("record")
        if not isinstance(record, Mapping):
            raise CuratorError("record is required")
        with self._lock:
            self._check_revision(request.get("revision"))
            entry = self._find_entry(kind, identifier, editable=True)
            if entry.storage == "array" and record.get("id") != identifier:
                raise CuratorError("stable IDs are immutable")
            if entry.storage == "map" and "id" in record:
                existing = record_at(self._draft, entry)
                if existing.get("id") is not None and record.get("id") != existing.get("id"):
                    raise CuratorError("stable IDs are immutable")
            replace_authored_record(self._draft, entry, record)
            return self._finish_mutation()

    def delete_record(self, kind: str, identifier: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if request.get("confirm") is not True:
            raise CuratorError("deletion requires confirm=true")
        with self._lock:
            self._check_revision(request.get("revision"))
            entry = self._find_entry(kind, identifier, editable=True)
            remove_authored_record(self._draft, entry)
            return self._finish_mutation()

    def validate(self, *, expected_revision: Any = None) -> dict[str, Any]:
        with self._lock:
            if self._draft is None:
                return {"valid": True, "revision": self._revision, "diagnostics": []}
            if expected_revision is not None:
                self._check_revision(expected_revision)
            self._validate_current()
            return self._validation_result()

    def diff(self) -> dict[str, Any]:
        with self._lock:
            if self._draft is None:
                return {"diff": "", "changed_records": [], "formatting_only": False, "prospective_bytes_sha256": None}
            prospective = canonical_json_bytes(self._draft)
            before = self._baseline_bytes.decode("utf-8").splitlines(keepends=True)
            after = prospective.decode("utf-8").splitlines(keepends=True)
            diff = "".join(difflib.unified_diff(before, after, fromfile=str(self.editable_path), tofile=str(self.editable_path)))
            changed = self._changed_records()
            return {
                "diff": diff, "changed_records": changed,
                "formatting_only": bool(diff and not changed),
                "prospective_bytes_sha256": _digest(prospective),
                "revision": self._revision,
            }

    def reset(self, *, expected_revision: Any = None) -> dict[str, Any]:
        self._require_editable()
        with self._lock:
            self._check_revision(expected_revision)
            self._draft = mutable_copy(self._editable_document.mapping)
            self._revision += 1
            self._valid_revision = self._revision
            self._draft_composition = self._composition
            self._diagnostics = []
            return self.session_info()

    def save(self, *, expected_revision: Any = None) -> dict[str, Any]:
        self._require_editable()
        with self._lock:
            self._check_revision(expected_revision)
            self._validate_current()
            if self._valid_revision != self._revision:
                raise CuratorError("Draft validation failed.", error_type="validation_error", details=self._diagnostics)
            self._check_source_digests()
            path = self.editable_path
            if path.is_symlink():
                raise CuratorError("Editable module is a symlink.", error_type="symlink_rejected", http_status=409)
            prospective = canonical_json_bytes(self._draft)
            mode = stat.S_IMODE(path.stat().st_mode)
            temporary_path: Path | None = None
            try:
                descriptor, raw_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
                temporary_path = Path(raw_path)
                with os.fdopen(descriptor, "wb") as stream:
                    os.fchmod(stream.fileno(), mode)
                    stream.write(prospective)
                    stream.flush()
                    os.fsync(stream.fileno())
                if path.is_symlink():
                    raise CuratorError("Editable module became a symlink.", error_type="symlink_rejected", http_status=409)
                os.replace(temporary_path, path)
                temporary_path = None
                try:
                    directory_fd = os.open(path.parent, os.O_RDONLY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                except OSError:
                    pass
            finally:
                if temporary_path is not None:
                    try:
                        temporary_path.unlink()
                    except FileNotFoundError:
                        pass
            try:
                reloaded = _resolve_catalog(**self._arguments)
            except Exception as exc:
                raise CuratorError(
                    "File was saved but the composition could not be reloaded; run embed-context validate.",
                    error_type="saved_reload_failed", http_status=500,
                ) from exc
            self._composition = reloaded
            self._baseline_catalog = reloaded.catalog
            self._editable_document = reloaded.document_for_path(path)
            self._baseline_bytes = prospective
            self._draft = mutable_copy(self._editable_document.mapping)
            self._draft_composition = reloaded
            self._valid_revision = self._revision
            self._diagnostics = []
            self._index = build_source_index(reloaded.documents, path)
            return {"saved": True, "revision": self._revision, "configuration_fingerprint": reloaded.catalog.fingerprint, "source_digest": _digest(prospective)}

    def _finish_mutation(self) -> dict[str, Any]:
        self._revision += 1
        self._validate_current()
        return self._validation_result()

    def _validate_current(self) -> None:
        prospective = canonical_json_bytes(self._draft)
        try:
            candidate = _replace_resolved_document(
                self._composition, self._editable_document, self._draft,
                source_bytes=prospective,
            )
        except (CatalogError, OSError, ValueError) as exc:
            self._diagnostics = [_diagnostic(exc, self.editable_path)]
            return
        self._draft_composition = candidate
        self._valid_revision = self._revision
        self._diagnostics = []

    def _validation_result(self) -> dict[str, Any]:
        return {
            "valid": self._valid_revision == self._revision,
            "revision": self._revision,
            "last_valid_revision": self._valid_revision,
            "diagnostics": list(self._diagnostics),
            "dirty": self.dirty,
        }

    def _select_editable(self, edit_module: str | Path | None) -> Any | None:
        if edit_module is None:
            return None
        requested = Path(edit_module).resolve()
        matches = [item for item in self._composition.documents if item.source_path.resolve() == requested and item.kind in {"semantic", "profile", "extension"}]
        if len(matches) != 1:
            raise CuratorError("--edit-module must resolve to exactly one loaded schema-v7 semantic, profile, or extension document")
        item = matches[0]
        if "embed_context/_data" in item.source_path.as_posix():
            raise CuratorError("installed bundled resources are read-only; load an external or source-tree module explicitly")
        return item

    def _require_editable(self) -> None:
        if self._editable_document is None:
            raise CuratorError("This curator session is read-only.", error_type="read_only", http_status=403)

    def _check_revision(self, expected: Any) -> None:
        if not isinstance(expected, int) or isinstance(expected, bool):
            raise CuratorError("A numeric draft revision is required.")
        if expected != self._revision:
            raise CuratorError(
                "Draft revision does not match the current session.",
                error_type="revision_conflict", http_status=409,
                details={"current_revision": self._revision},
            )

    def _current_index(self) -> tuple[SourceEntry, ...]:
        if self._draft is None:
            return self._index
        others = [item for item in self._composition.documents if item is not self._editable_document]
        return build_source_index((*others, self._draft_document()), self.editable_path)

    def _draft_document(self) -> Any:
        item = self._editable_document
        return SimpleNamespace(
            kind=item.kind, locator_kind=item.locator_kind,
            source_path=item.source_path, mapping=self._draft,
            module_id=item.module_id, target_profile=item.target_profile,
        )

    def _document_for_entry(self, entry: SourceEntry) -> Any:
        if self._draft is not None and entry.document_path.resolve() == self.editable_path.resolve():
            return self._draft_document()
        return next(item for item in self._composition.documents if item.source_path == entry.document_path)

    def _find_entry(self, kind: str, identifier: str, *, editable: bool = False) -> SourceEntry:
        authored_kind = "feature" if kind == "concept" else kind
        matches = [item for item in self._current_index() if item.kind == authored_kind and item.identifier == identifier and (not editable or item.editable)]
        if len(matches) != 1:
            raise CuratorError(f"record {kind}:{identifier} was not found", error_type="not_found", http_status=404)
        return matches[0]

    def _inventory_item(self, entry: SourceEntry) -> dict[str, Any]:
        draft_state = self._draft_state(entry)
        document = (
            self._editable_document
            if draft_state == "deleted"
            else self._document_for_entry(entry)
        )
        record = record_at(document.mapping, entry)
        origin = self._origin(entry.kind, entry.identifier)
        domains = record.get("domains", [])
        return {
            "kind": entry.kind, "identifier": entry.identifier,
            "label": str(record.get("label") or record.get("title") or record.get("summary") or entry.identifier),
            "domains": list(domains) if isinstance(domains, (list, tuple)) else [],
            "document": str(entry.document_path), "module_id": entry.module_id,
            "target_profile": entry.target_profile,
            "contribution_class": origin.get("contribution_class", _class_for(entry.document_kind)),
            "lifecycle": origin.get("lifecycle_status"),
            "editable": entry.editable and draft_state != "deleted",
            "draft_state": draft_state,
        }

    def _origin(self, kind: str, identifier: str) -> dict[str, Any]:
        aliases = {"feature": "concept", "table": "table", "feature_binding": "binding", "object_binding": "binding", "relationship_binding": "binding", "relationship_binding_path": "binding"}
        origin = self._current_catalog().origins.get(f"{aliases.get(kind, kind)}:{identifier}")
        return origin.to_dict() if origin is not None else {}

    def _current_catalog(self) -> Any:
        if self._draft_composition is not None and self._valid_revision == self._revision:
            return self._draft_composition.catalog
        return self._baseline_catalog

    def _effective_record(self, kind: str, identifier: str) -> Any:
        catalog = self._current_catalog()
        getters = {
            "clinical_object": catalog.get_clinical_object,
            "feature": catalog.get_feature,
            "concept": catalog.get_feature,
            "semantic_relationship": catalog.get_semantic_relationship,
            "temporal_semantic": catalog.get_temporal_semantic,
            "aggregation": catalog.get_aggregation,
            "guardrail": catalog.get_guardrail,
            "coverage": catalog.get_coverage,
            "context": catalog.get_context,
            "relationship_binding": catalog.get_relationship_binding,
        }
        getter = getters.get(kind)
        if getter is None:
            return None
        try:
            return getter(identifier)
        except Exception:
            return None

    def _form_spec(self, entry: SourceEntry, record: Mapping[str, Any]) -> dict[str, Any] | None:
        document = next(
            item for item in self._composition.documents
            if item.source_path.resolve() == entry.document_path.resolve()
        )
        if document.kind == "legacy" or not document.schema_resource:
            return None
        family = {
            "feature": "extension_concept" if document.kind == "extension" else "concept",
            "context": "clinical_context",
            "source": "context_source",
        }.get(entry.kind, entry.kind)
        try:
            schema = json.loads(
                _schema_path_for(document.schema_resource).read_text(encoding="utf-8")
            )
            references: dict[str, list[dict[str, str]]] = {}
            for item in self._current_index():
                reference_kind = "concept" if item.kind == "feature" else item.kind
                references.setdefault(reference_kind, []).append(
                    {"id": item.identifier, "label": item.identifier}
                )
            return build_form_spec(
                schema, family, record=record, references=references
            )
        except (KeyError, OSError, json.JSONDecodeError):
            return None

    def _draft_state(self, entry: SourceEntry) -> str:
        if not entry.editable or self._draft is None:
            return "baseline"
        baseline_entries = {(item.kind, item.identifier): item for item in self._index if item.editable}
        baseline = baseline_entries.get((entry.kind, entry.identifier))
        if baseline is None:
            return "new"
        try:
            old = record_at(self._editable_document.mapping, baseline)
            new = record_at(self._draft_document().mapping, entry)
            return "baseline" if old == new else "modified"
        except (KeyError, StopIteration):
            return "deleted"

    def _changed_records(self) -> list[dict[str, str]]:
        before = {(item.kind, item.identifier): item for item in self._index if item.editable}
        after = {(item.kind, item.identifier): item for item in self._current_index() if item.editable}
        result = []
        for key in sorted(set(before) | set(after)):
            if key not in before:
                state = "new"
            elif key not in after:
                state = "deleted"
            elif record_at(self._editable_document.mapping, before[key]) != record_at(self._draft_document().mapping, after[key]):
                state = "modified"
            else:
                continue
            result.append({"kind": key[0], "identifier": key[1], "state": state})
        return result

    def _check_source_digests(self) -> None:
        for document in self._composition.documents:
            try:
                current = document.source_path.read_bytes()
            except OSError as exc:
                raise CuratorError("A loaded composition document is no longer readable.", error_type="composition_changed", http_status=409) from exc
            if _digest(current) != document.source_digest:
                error_type = "source_changed" if document is self._editable_document else "composition_changed"
                raise CuratorError("A loaded source changed on disk; reload before saving.", error_type=error_type, http_status=409)

    @staticmethod
    def _entry_info(entry: SourceEntry) -> dict[str, Any]:
        return {
            "document": str(entry.document_path), "document_kind": entry.document_kind,
            "locator_kind": entry.locator_kind, "module_id": entry.module_id,
            "target_profile": entry.target_profile, "collection": entry.collection,
            "json_pointer": entry.json_pointer,
        }

    @staticmethod
    def _document_info(document: Any) -> dict[str, Any]:
        return {
            "kind": document.kind, "locator_kind": document.locator_kind,
            "path": str(document.source_path), "source_digest": document.source_digest,
            "module_id": document.module_id, "module_version": document.version,
            "lifecycle_status": document.lifecycle_status,
            "target_profile": document.target_profile,
            "dependency_order": document.dependency_order,
        }


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _diagnostic(exc: Exception, fallback: Path) -> dict[str, Any]:
    return {
        "stage": getattr(exc, "stage", "domain"),
        "document": str(getattr(exc, "document", None) or fallback),
        "json_pointer": getattr(exc, "json_pointer", None),
        "contribution_key": getattr(exc, "contribution_key", None),
        "message": str(exc),
    }


def _class_for(document_kind: str) -> str:
    return {"semantic": "portable", "profile": "released_profile", "extension": "project"}.get(document_kind, "portable")
