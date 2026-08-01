"""Narrow integration surface for the optional curator distribution.

This module is private to the separately packaged curator.  Keeping the
authored-composition hooks here makes that coupling explicit without exposing
catalog mutation through the public :mod:`embed_context` API.
"""

from .catalog import (
    CatalogError,
    _replace_resolved_document,
    _resolve_catalog,
    _schema_path_for,
)

__all__ = (
    "CatalogError",
    "_replace_resolved_document",
    "_resolve_catalog",
    "_schema_path_for",
)
