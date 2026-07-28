# EMBED Open Data V2 Agent Context

This repository will contain a small, agent-facing knowledge bundle for the
Emory Breast Imaging Dataset (EMBED) Open Data version 2. The bundle is intended
to help an agent understand the released clinical data: first the meanings of
individual fields, then the relationships between tables, and finally the
clinical and procedural context needed to interpret them correctly.

The deliverable is intentionally simple. Context belongs in portable Markdown
under `bundle/` so that the directory can be referenced by path in an agent
session or zipped for use in a web chat. The project is not intended to become
an application, database, or general-purpose data-processing framework.

## Repository layout

- `bundle/` — the agent-facing context bundle. It is currently empty while the
  source material is being reviewed.
- `docs/` — project documentation for maintainers and agents.
- `reference_files/` — local EMBED V2 source artifacts used to build and verify
  the bundle. This directory is intentionally ignored by Git.
- `AGENTS.md` — repository contribution, commit, and documentation-sync rules.

The current reference inventory and the rules for developing the bundle are in
[docs/project-scope.md](docs/project-scope.md).
The question-driven, minimal-access plan for the feature layer is in
[docs/feature-context-investigation-plan.md](docs/feature-context-investigation-plan.md).

## Current status

The feature investigation is planned and initialized. Its scope, evidence
labels, targeted-access gates, and completion checks are defined, but no dataset
field definitions, table relationships, or clinical interpretations have yet
been added to the context bundle.
