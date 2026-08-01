"""Private implementation package for the local catalog curation viewer."""

from embed_context import __version__ as _core_version


__version__ = "0.9.0"


def _require_compatible_core_version(core_version: str) -> None:
    if core_version != __version__:
        raise RuntimeError(
            "embedv2-agent-context-curator "
            f"{__version__} requires embedv2-agent-context {__version__}; "
            f"found {core_version}. Install matching core and curator versions."
        )


_require_compatible_core_version(_core_version)

from .server import CuratorServer, serve_curator
from .session import CuratorSession

__all__ = ("__version__", "CuratorServer", "CuratorSession", "serve_curator")
