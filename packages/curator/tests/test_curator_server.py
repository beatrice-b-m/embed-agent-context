"""Loopback HTTP containment and API envelope contracts."""

from __future__ import annotations

import http.client
import json
import threading
import unittest

from embed_context_curator.server import CuratorServer


class FakeSession:
    editable_path = None
    dirty = False

    def session_info(self):
        return {"editable": False, "revision": 0, "valid": True}

    def list_records(self, **filters):
        return {"records": [], "total": 0, "limit": filters["limit"]}

    def discover(self, body):
        return {"request": body, "baseline": {"matches": []}}

    def creation_form_spec(self, kind):
        return {"family": kind, "fields": []}


class CuratorServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = CuratorServer(FakeSession(), 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        self.host = f"127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.connection.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, method, path, body=None, headers=None):
        payload = None if body is None else json.dumps(body)
        sent = {"Host": self.host, **(headers or {})}
        self.connection.request(method, path, body=payload, headers=sent)
        response = self.connection.getresponse()
        data = response.read()
        return response, data

    def test_static_and_json_responses_have_containment_headers(self) -> None:
        response, body = self.request("GET", "/")
        self.assertEqual(response.status, 200)
        self.assertIn("default-src 'none'", response.getheader("Content-Security-Policy"))
        self.assertEqual(response.getheader("Cache-Control"), "no-store")
        self.assertIn(b"EMBED catalog curator", body)
        response, body = self.request("GET", "/api/session")
        self.assertEqual(json.loads(body)["data"]["revision"], 0)
        response, body = self.request("GET", "/api/forms/qualification")
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(body)["data"]["family"], "qualification")

    def test_host_origin_content_type_and_preflight_are_rejected(self) -> None:
        response, _ = self.request("GET", "/api/session", headers={"Host": "localhost:1"})
        self.assertEqual(response.status, 400)
        response, _ = self.request("POST", "/api/discover", {}, {"Content-Type": "application/json"})
        self.assertEqual(response.status, 403)
        response, _ = self.request("POST", "/api/discover", {}, {"Origin": self.server.url, "Content-Type": "text/plain"})
        self.assertEqual(response.status, 415)
        response, _ = self.request("OPTIONS", "/api/discover")
        self.assertEqual(response.status, 405)
        self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))

    def test_exact_origin_json_request_and_shutdown_acknowledgement(self) -> None:
        headers = {"Origin": self.server.url, "Content-Type": "application/json"}
        response, body = self.request("POST", "/api/discover", {"query": "x"}, headers)
        self.assertEqual(response.status, 200)
        self.assertTrue(json.loads(body)["ok"])


if __name__ == "__main__":
    unittest.main()
