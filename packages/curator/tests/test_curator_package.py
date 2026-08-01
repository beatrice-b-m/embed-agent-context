"""Companion-package compatibility contracts."""

import unittest

from embed_context_curator import __version__, _require_compatible_core_version


class CuratorPackageTests(unittest.TestCase):
    def test_compatible_core_version_is_accepted(self) -> None:
        self.assertIsNone(_require_compatible_core_version(__version__))

    def test_mismatched_core_version_has_actionable_diagnostic(self) -> None:
        with self.assertRaises(RuntimeError) as caught:
            _require_compatible_core_version("0.8.0")

        message = str(caught.exception)
        self.assertIn("embedv2-agent-context-curator 0.9.0", message)
        self.assertIn("requires embedv2-agent-context 0.9.0", message)
        self.assertIn("found 0.8.0", message)
        self.assertIn("Install matching core and curator versions", message)


if __name__ == "__main__":
    unittest.main()
