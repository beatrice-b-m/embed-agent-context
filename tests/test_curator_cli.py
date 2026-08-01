"""Distinct CLI launch syntax and lifecycle contracts."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from embed_context.cli import build_parser, main


class CuratorCLITests(unittest.TestCase):
    def test_curator_package_exports_cli_lifecycle_components(self) -> None:
        from embed_context.curator import CuratorSession, serve_curator

        self.assertTrue(callable(CuratorSession))
        self.assertTrue(callable(serve_curator))

    def test_global_composition_flags_precede_viewer_flags(self) -> None:
        args = build_parser().parse_args([
            "--extension-file", "project.json", "curate",
            "--edit-module", "project.json", "--port", "8123", "--no-open",
        ])
        self.assertEqual(args.command, "curate")
        self.assertEqual(args.port, 8123)
        self.assertTrue(args.no_open)

    def test_json_format_is_rejected_without_starting_lifecycle(self) -> None:
        error = io.StringIO()
        with redirect_stdout(error):
            status = main(["--format", "json", "curate", "--no-open"])
        self.assertEqual(status, 2)
        payload = json.loads(error.getvalue())
        self.assertEqual(payload["error"]["type"], "usage")

    def test_curate_dispatches_before_finite_catalog_loader(self) -> None:
        with patch("embed_context.cli._run_curator_command", return_value=0) as launch, patch("embed_context.cli.load_catalog") as loader:
            self.assertEqual(main(["curate", "--no-open"]), 0)
        launch.assert_called_once()
        loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
