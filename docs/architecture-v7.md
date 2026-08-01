# Architecture v7: composable catalog sets

## Decision

The current catalog is a deterministic composition of one portable semantic
catalog, zero or more independently authored dataset profiles, and zero or more
explicitly selected project extensions. The public manifest bundles the
semantic catalog with `open-v2` and enables no extensions by default.

This replaces the schema-v6 monolith. [Architecture v6](architecture-v6.md) is
retained as historical rationale for the portable/physical separation inside
that earlier file. [Profile-module migration](profile-module-migration.md)
contains the full schema-v7 design and staged decision record.

## Boundaries

```text
portable meaning
  └── released profile representation
        └── explicitly selected project extensions
```

The semantic catalog owns clinical objects, concepts, relationships, temporal
meaning, aggregations, reusable guardrails, and portable provenance. A profile
owns release evidence, coverage, vocabulary choices, qualifications, and
physical bindings. An extension owns project concepts, qualifications,
descriptive lineage, additive bindings, and typed project revisions.

Modules do not inherit, deep-merge, patch, or mutate each other. Qualifications
are additive and evidence-backed. Typed revisions preserve both original and
replacement records. Every contribution retains origin and lifecycle in the
effective query view.

## Loading and determinism

The catalog-set manifest uses closed bundled or file locators. Explicit module
paths are supplied by the caller; no directory, environment-variable, home, or
working-directory discovery occurs. JSON Schema validates each document before
domain validation and composition.

Extension dependencies are topologically resolved. Duplicate IDs, dependency
cycles, cross-profile references, incompatible schema versions, unauthorized
revisions, and ambiguous physical interpretations are errors. The effective
configuration fingerprint derives from canonical validated content and module
identities, so absolute paths and argument order do not affect it.

## Query model

Portable queries work with no profile. A unique applicable loaded profile may
be inferred. Profile-dependent operations require explicit selection when
several loaded profiles differ. Feature lookup, code lookup, discovery
vocabulary indexing, diagnostics, and code inclusion share one resolution
policy.

Exact and discovery responses distinguish portable, released-profile, and
project contributions. Qualifications, coverage, lineage, and revisions remain
separate from authored portable entities. The Python, CLI, and MCP interfaces
all load the same effective catalog and return structured ambiguity or
validation errors.

## Safety and deployment

All modules are descriptive, count-free, and non-executable. Loading and normal
validation require no clinical data. The wheel includes the manifest, every
bundled manifest target, and every standalone schema. Runtime JSON Schema
validation is part of the core package; MCP remains an optional interface.

Current independent version axes are software `0.8.0`, semantic schema `7`,
profile-module schema `1`, extension-module schema `1`, profile ID `open-v2`,
and optional MCP SDK `2.0.0`.
