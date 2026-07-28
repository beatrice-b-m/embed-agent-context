# EMBED Open Data V2 Agent Context

This repository contains a small, agent-facing knowledge bundle for the
Emory Breast Imaging Dataset (EMBED) Open Data version 2. The bundle is intended
to help an agent understand the released clinical data: first the meanings of
individual fields, then the relationships between tables, and finally the
clinical and procedural context needed to interpret them correctly.

The deliverable is intentionally simple. Context belongs in portable Markdown
under `bundle/` so that the directory can be referenced by path in an agent
session or zipped for use in a web chat. The project is not intended to become
an application, database, or general-purpose data-processing framework.

## Repository layout

- [`bundle/`](bundle/README.md) — the agent-facing context bundle, with a
  standalone entry point and feature references grouped by conceptual level.
- `docs/` — project documentation for maintainers and agents.
- `reference_files/` — local EMBED V2 source artifacts used to build and verify
  the bundle. This directory is intentionally ignored by Git.
- `AGENTS.md` — repository contribution, commit, and documentation-sync rules.

The current reference inventory and the rules for developing the bundle are in
[docs/project-scope.md](docs/project-scope.md).
The question-driven, minimal-access plan for the feature layer is in
[docs/feature-context-investigation-plan.md](docs/feature-context-investigation-plan.md).

## Current status

The feature layer is implemented. It accounts for all 243 physical column
occurrences across the eight released tables and records representations,
released legend meanings, observed bounded domains, missing/sentinel evidence,
and unresolved interpretation questions at the appropriate evidence level.

The targeted access ledger and aggregate findings are in
[docs/feature-context-investigation-results.md](docs/feature-context-investigation-results.md).
Full table-linkage and clinical/procedural-context phases remain future work;
the current bundle includes only the key and timing cautions needed to interpret
features safely.

## Maintainer verification

The narrow bundle verifier reads Parquet footer schemas from the explicit
eight-file manifest. It checks that every physical table-column occurrence is
named in a Markdown table cell, local links and heading fragments resolve
inside the bundle, and every document is reachable from the entry point:

```bash
uv run --locked python scripts/validate_bundle.py
```

It does not open clinical data pages, inspect value statistics, or read report
text.
