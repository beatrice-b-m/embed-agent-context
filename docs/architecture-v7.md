# Architecture v7: composable catalog sets

> Historical decision. Schema v8 replaced this ownership and binding contract.
> See [architecture v8](architecture-v8.md) for current behavior. Version
> numbers and compatibility statements below describe the former v7 release.

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
validation require no clinical data. The core wheel includes the manifest,
every bundled manifest target, and every standalone schema. Runtime JSON Schema
validation is part of the core package. MCP remains an optional dependency, and
the local web viewer is shipped in a separate optional companion distribution.

Current independent version axes are software `0.9.0`, semantic schema `7`,
profile-module schema `1`, extension-module schema `1`, profile ID `open-v2`,
optional MCP SDK `2.0.0`, and lockstep curator companion `0.9.0`.

## Optional local authoring adapter

The separately installed `embedv2-agent-context-curator` distribution owns the
private `embed_context_curator` package and all browser assets. It depends on
the same-version core distribution and uses the core's narrow private curator
integration surface to access canonical resolver snapshots alongside the
effective `Catalog`. The base distribution keeps the `curate` CLI dispatch stub
and installation diagnostic, but its wheel contains no viewer implementation or
HTML, JavaScript, or CSS.

A loopback-only standard-library HTTP server exposes the companion's static
assets, typed graph and discovery adapters, and one lock-protected draft
session. The adapter adds no catalog mutation methods and does not alter
composition semantics. The two distributions are developed in one uv workspace
so resolver and viewer changes can be tested atomically; their distinct import
namespaces preserve wheel ownership and clean uninstall behavior.

Only one explicitly selected schema-v7 source document is writable. Drafts are
recomposed from immutable session snapshots, validated synchronously, compared
with baseline discovery, digest-checked against every filesystem input, and
saved by atomic replacement. Legacy schema-v6 input remains review-only. This
is a temporary local maintainer interface, not a hosted or stable remote API.
