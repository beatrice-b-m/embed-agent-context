"""Distinct CLI launch syntax and lifecycle contracts."""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from embed_context.cli import (
    CURATOR_INSTALL_HINT,
    CuratorUnavailableError,
    _require_curator,
    build_parser,
    main,
)


class CuratorCLITests(unittest.TestCase):
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

    def test_missing_curator_returns_actionable_error(self) -> None:
        error = io.StringIO()
        with patch.dict(
            sys.modules,
            {"embed_context_curator": None},
        ), redirect_stderr(error):
            status = main(["curate", "--no-open"])

        self.assertEqual(status, 2)
        self.assertEqual(error.getvalue(), f"error: {CURATOR_INSTALL_HINT}\n")
        self.assertIn("embedv2-agent-context[curator]", error.getvalue())
        self.assertIn("#subdirectory=packages/curator", error.getvalue())

    def test_curator_nested_missing_dependency_is_not_masked(self) -> None:
        nested_error = ModuleNotFoundError(
            "No module named 'curator_dependency'",
            name="curator_dependency",
        )
        with patch.dict(sys.modules, {"embed_context_curator": None}), patch(
            "builtins.__import__",
            side_effect=nested_error,
        ):
            with self.assertRaises(ModuleNotFoundError) as raised:
                _require_curator()

        self.assertIs(raised.exception, nested_error)

    def test_absent_curator_has_specific_error_type(self) -> None:
        with patch.dict(sys.modules, {"embed_context_curator": None}):
            with self.assertRaises(CuratorUnavailableError) as raised:
                _require_curator()

        self.assertEqual(str(raised.exception), CURATOR_INSTALL_HINT)


if __name__ == "__main__":
    unittest.main()
