"""Dependency-free access to the EMBED V2 feature catalog."""

from .catalog import (
    Binding,
    Catalog,
    CatalogAmbiguousError,
    CatalogError,
    CatalogLoadError,
    CatalogNotFoundError,
    CatalogValidationError,
    Concept,
    Vocabulary,
    load_catalog,
)

__all__ = [
    "Binding",
    "Catalog",
    "CatalogAmbiguousError",
    "CatalogError",
    "CatalogLoadError",
    "CatalogNotFoundError",
    "CatalogValidationError",
    "Concept",
    "Vocabulary",
    "load_catalog",
]
