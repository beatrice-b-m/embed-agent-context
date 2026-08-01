"""Contained loopback HTTP server for the local curator."""

from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from collections.abc import Callable, Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit


MAX_REQUEST_BODY = 1_048_576
_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)


class CuratorServer(ThreadingHTTPServer):
    """One shared curator session bound to the IPv4 loopback interface."""

    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, session: Any, port: int = 0) -> None:
        self.session = session
        super().__init__(("127.0.0.1", port), _CuratorHandler)
        self.url = f"http://127.0.0.1:{self.server_port}"


def serve_curator(
    session: Any,
    *,
    port: int = 0,
    open_browser: bool = True,
    browser_opener: Callable[[str], Any] = webbrowser.open,
    server_factory: Callable[[Any, int], CuratorServer] = CuratorServer,
) -> None:
    """Start, announce, and block on a local curator server."""

    server = server_factory(session, port)
    state = "read-only"
    editable = getattr(session, "editable_path", None)
    if editable is not None:
        state = f"editable module: {editable}"
    print(f"Catalog curator: {server.url} ({state})")
    print("Press Ctrl-C to stop the curator.")
    if open_browser:
        browser_opener(server.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        discarded = bool(getattr(session, "dirty", False))
        suffix = " Unsaved draft discarded." if discarded else ""
        print(f"Catalog curator stopped.{suffix}")


class _CuratorHandler(BaseHTTPRequestHandler):
    server: CuratorServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        # Deliberately omit paths and all request/catalog content.
        return

    def do_GET(self) -> None:  # noqa: N802
        if not self._valid_host():
            return
        parsed = urlsplit(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api_get(parsed.path, parse_qs(parsed.query))
            return
        self._serve_asset(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        self._handle_mutation("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._handle_mutation("PUT")

    def do_DELETE(self) -> None:  # noqa: N802
        self._handle_mutation("DELETE")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", "CORS preflights are not supported.")

    def do_PATCH(self) -> None:  # noqa: N802
        self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", "Method is not supported.")

    def _valid_host(self) -> bool:
        expected = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != expected:
            self._error(HTTPStatus.BAD_REQUEST, "invalid_host", "Host header is not accepted.")
            return False
        return True

    def _handle_api_get(self, path: str, query: Mapping[str, list[str]]) -> None:
        try:
            if path == "/api/session":
                data = self.server.session.session_info()
            elif path == "/api/records":
                data = self.server.session.list_records(
                    text=_one(query, "text"), kind=_one(query, "kind"),
                    origin=_one(query, "origin"), profile=_one(query, "profile"),
                    lifecycle=_one(query, "lifecycle"), domain=_one(query, "domain"),
                    status=_one(query, "status"), limit=_integer(query, "limit", 500),
                )
            elif path == "/api/draft/diff":
                data = self.server.session.diff()
            elif path.startswith("/api/forms/"):
                kind = unquote(path.removeprefix("/api/forms/"))
                if not kind or "/" in kind:
                    raise SessionHTTPError(
                        404, "not_found", "Form specification was not found."
                    )
                data = self.server.session.creation_form_spec(kind)
            elif path.startswith("/api/records/"):
                kind, identifier = _route_key(path, "/api/records/")
                data = self.server.session.get_record(kind, identifier)
            elif path.startswith("/api/graph/"):
                kind, identifier = _route_key(path, "/api/graph/")
                data = self.server.session.neighborhood(
                    kind, identifier, depth=_integer(query, "depth", 1)
                )
            else:
                self._error(HTTPStatus.NOT_FOUND, "not_found", "API route was not found.")
                return
        except Exception as exc:  # converted by session errors when available
            self._session_error(exc)
            return
        self._json(HTTPStatus.OK, {"ok": True, "data": data})

    def _handle_mutation(self, method: str) -> None:
        if not self._valid_host():
            return
        expected_origin = self.server.url
        if self.headers.get("Origin") != expected_origin:
            self._error(HTTPStatus.FORBIDDEN, "invalid_origin", "Origin header is not accepted.")
            return
        if self.headers.get("Transfer-Encoding") is not None:
            self._error(HTTPStatus.BAD_REQUEST, "unsupported_transfer_encoding", "Transfer encoding is not supported.")
            return
        media_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "unsupported_media_type", "Content-Type must be application/json.")
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = -1
        if length < 0:
            self._error(HTTPStatus.LENGTH_REQUIRED, "length_required", "A valid Content-Length is required.")
            return
        if length > MAX_REQUEST_BODY:
            self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body_too_large", "Request body exceeds 1 MiB.")
            return
        try:
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("request body must be a JSON object")
            path = urlsplit(self.path).path
            data = self._dispatch_mutation(method, path, body)
        except json.JSONDecodeError:
            self._error(HTTPStatus.BAD_REQUEST, "json_decode", "Request body is not valid JSON.")
            return
        except ValueError as exc:
            self._error(HTTPStatus.BAD_REQUEST, "invalid_request", str(exc))
            return
        except Exception as exc:
            self._session_error(exc)
            return
        self._json(HTTPStatus.OK, {"ok": True, "data": data})

    def _dispatch_mutation(self, method: str, path: str, body: dict[str, Any]) -> Any:
        session = self.server.session
        if method == "POST" and path == "/api/discover":
            return session.discover(body)
        if method == "POST" and path == "/api/draft/records":
            return session.create_record(body)
        if method == "POST" and path == "/api/draft/validate":
            return session.validate(expected_revision=body.get("revision"))
        if method == "POST" and path == "/api/draft/reset":
            return session.reset(expected_revision=body.get("revision"))
        if method == "POST" and path == "/api/draft/save":
            return session.save(expected_revision=body.get("revision"))
        if method == "POST" and path == "/api/shutdown":
            if session.dirty and body.get("discard_unsaved") is not True:
                raise SessionHTTPError(409, "dirty_draft", "Acknowledge the unsaved draft before shutdown.")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return {"shutting_down": True, "discarded_unsaved": bool(session.dirty)}
        if path.startswith("/api/draft/records/") and method in {"PUT", "DELETE"}:
            kind, identifier = _route_key(path, "/api/draft/records/")
            if method == "PUT":
                return session.replace_record(kind, identifier, body)
            return session.delete_record(kind, identifier, body)
        raise SessionHTTPError(404, "not_found", "API route was not found.")

    def _serve_asset(self, path: str) -> None:
        name = "index.html" if path in {"", "/"} else path.removeprefix("/")
        if name not in {"index.html", "app.js", "styles.css"}:
            self._error(HTTPStatus.NOT_FOUND, "not_found", "Asset was not found.")
            return
        resource = files("embed_context_curator.static").joinpath(name)
        try:
            payload = resource.read_bytes()
        except (FileNotFoundError, OSError):
            self._error(HTTPStatus.NOT_FOUND, "not_found", "Asset was not found.")
            return
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _session_error(self, exc: Exception) -> None:
        if isinstance(exc, SessionHTTPError):
            self._error(exc.status, exc.error_type, str(exc), exc.details)
            return
        status = int(getattr(exc, "http_status", 400))
        error_type = str(getattr(exc, "error_type", "curator_error"))
        details = getattr(exc, "details", None)
        self._error(status, error_type, str(exc), details)

    def _error(self, status: int, error_type: str, message: str, details: Any = None) -> None:
        # Some checks intentionally reject a request before consuming its body.
        # Close that connection so unread bytes cannot become a second request.
        self.close_connection = True
        error: dict[str, Any] = {"type": error_type, "message": message}
        if details is not None:
            error["details"] = details
        self._json(status, {"ok": False, "error": error})

    def _json(self, status: int, value: Mapping[str, Any]) -> None:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._security_headers()
        if self.close_connection:
            self.send_header("Connection", "close")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", _CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")


class SessionHTTPError(Exception):
    def __init__(self, status: int, error_type: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.error_type = error_type
        self.details = details


def _one(query: Mapping[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    return values[-1] if values else None


def _integer(query: Mapping[str, list[str]], key: str, default: int) -> int:
    raw = _one(query, key)
    try:
        return default if raw is None else int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc


def _route_key(path: str, prefix: str) -> tuple[str, str]:
    parts = path.removeprefix(prefix).split("/")
    if len(parts) != 2 or not all(parts):
        raise SessionHTTPError(404, "not_found", "Record route was not found.")
    return unquote(parts[0]), unquote(parts[1])
