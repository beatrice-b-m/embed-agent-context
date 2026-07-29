# Project scope and authoring requirements

## Purpose

This project maintains a concise feature-context backbone for agents working
with EMBED clinical data. It should answer questions such as:

- What does a feature capture?
- At which patient, exam, side, finding, report, risk, or wide-table grain does
  it occur?
- Which physical columns represent the same semantic feature?
- Which features concern pathology, demographics, social determinants of
  health, imaging, risk, or another controlled domain?
- What does a released code mean, and what interpretation caveats apply?

The backbone is intended to support both open and non-open EMBED profiles.
Dataset measurements are not feature definitions and do not belong in the
portable catalog.

## Canonical deliverable

`catalog/catalog.json` is the source of truth. It must remain:

- valid against the version-matched `catalog/catalog.schema.json`;
- directly usable without a database, index service, or generated Markdown;
- normalized so one semantic concept can have many physical bindings;
- explicit about evidence and unresolved interpretation;
- queryable by stable identifiers, physical names, text, grain, table, feature
  kind, and domain; and
- safe to extend with another profile without copying shared concepts.

Markdown documents explain the implementation but are not parsed as feature
data. If a human-readable feature reference is ever generated, it must be a
derived view of the JSON catalog rather than a second source of truth.

## Portability and count-free policy

Do not record empirical dataset summaries in the catalog or agent-facing
feature documentation. Prohibited examples include:

- table or row totals;
- null, non-null, blank, duplicate, or distinct-value counts;
- value frequencies or proportions;
- quantiles, observed extrema, and prevalence estimates; and
- release-specific cardinality claims presented as feature semantics.

The policy does not prohibit semantic numbers. Documented code values, units,
time horizons, physical types, path-slot parameters, and genuinely defined
sentinel meanings belong when they explain a feature. A physical binding may
record schema nullability because that is part of its representation; it must
not record how often null occurs.

Unresolved missing-value or sentinel behavior may be stated as a caveat without
an empirical frequency. Prefer “null semantics are not documented” over a
release measurement.

## Normalization rules

Create one concept for one stable meaning. Bind all equivalent physical
occurrences to it, including projections into convenience or wide tables.
Examples include anonymized patient/accession identifiers, breast side, dates,
and repeated pathology code slots.

Create separate concepts when the meaning actually changes. A finding-presence
flag and a side- or exam-level aggregate are not interchangeable even when
their names share a stem. Put physical differences such as profile, table,
column, grain, role, type, nullability, or slot number in bindings rather than
copying definitions.

Reusable code dictionaries belong under `vocabularies`. Vocabulary
completeness and parsing behavior must stay explicit: a released list is not
automatically exhaustive, and comma-composed strings must not be split when
delimiter semantics are undocumented.

## Minimal tooling boundary

The catalog loader, validator, exact lookup, and deterministic text/filter
search use only the Python standard library. The search implementation is
intentionally transparent and small; embeddings, a vector database, a search
service, SQLite FTS, and fuzzy-matching dependencies are outside Phase 1.

The stdio MCP adapter is optional and adds one direct runtime integration
dependency: the official MCP SDK. It must call the same core API as the CLI,
emit protocol messages only on stdout, and expose read-only tools.

## Phased implementation

### 1. Feature meanings

Implemented in the structured catalog. Concepts describe feature meaning,
controlled facets, code vocabularies, evidence, and caveats. Bindings describe
where each concept occurs in a profile.

### 2. Table linkages

Implemented as a structured, profile-scoped layer for table grains, key
candidates, optional relationships, hierarchy edges, cardinality expectations,
and join hazards. Relationship claims are
structured separately from feature concepts and must not smuggle
release-specific counts into the feature catalog.

The `open-v2` profile records all eight physical table grains and conservative
linkages among patient, exam, side, imaging-finding, pathology-finding, report,
risk, and wide-row surfaces. Non-unique clinical tuples, optional or unresolved
references, nullable side components, technical-index projections, temporal
availability, and the wide table's unresolved construction remain explicit
hazards rather than being promoted to foreign-key guarantees.

### 3. Clinical and procedural context

Future work may explain imaging, reporting, assessment, risk, procedure, and
pathology workflows where necessary for correct use. General clinical
background must remain distinguishable from EMBED-specific behavior.

## Evidence and source priority

When sources disagree, use the following order:

1. Facts supplied or confirmed by EMBED maintainers.
2. Definitions verified from the applicable release schema and legend.
3. Supporting internal material.
4. Public EMBED documentation and other external sources.

Public EMBED V1 material is not authoritative for V2 without verification.
External material can supply general clinical context, but it cannot fill a
dataset-specific gap as though the result were verified. Keep inference and
unresolved meaning visible.

## Local source boundary

The ignored `reference_files/` directory contains local release artifacts used
to construct and verify the `open-v2` profile. Source-profile validation may
read Parquet footer schemas and the release legend. It must not copy clinical
rows, identifiers, anonymized dates, report text, or empirical summaries into
the catalog.

## Documentation synchronization

Any functional catalog, CLI, or MCP change must update the relevant usage,
format, architecture, and migration documentation in the same logical commit.
Examples and cross-references must be checked for stale identifiers, commands,
filters, and file paths.

## Completion criteria

A catalog-context change is complete when it:

- passes strict catalog validation;
- uses the correct evidence level;
- identifies relevant profile bindings and declares every bound physical table
  at the correct grain;
- records assessed natural and technical key candidates with explicit
  uniqueness, completeness, evidence, and caveats;
- records intended relationships with ordered endpoints, source completeness,
  directional cardinality, evidence, caveats, and join hazards;
- reuses an existing concept or vocabulary whenever the meaning is shared;
- keeps inference, missing-value ambiguity, and version caveats explicit;
- adds no empirical dataset summary;
- has focused synthetic tests for changed behavior and checked-in profile
  integration assertions for required tables, key caveats, and expected
  relationships; and
- includes synchronized documentation and a focused Git commit.
