# Documentation

Choose the page that matches what you want to do.

## Use the catalog

Start with the repository [README](../README.md). It explains why the catalog
exists, installs the commands with `uv tool install`, and walks through a
clinical-first query. No EMBED data or repository checkout is needed.

If EMBED itself is new to you, begin with the HITI Lab's
[public dataset documentation](https://docs.hitilab.com/datasets/embed) for the
dataset overview, organization, access requirements, and data-use terms. This
repository documents a separate clinical-semantic catalog and does not
distribute EMBED.

Then read the [clinical-semantic model](clinical-semantic-model.md) when you
need the details behind pathology outcomes, finding attribution, candidate
dates, aggregation, and incomplete outcome capture.

The usual workflow is:

```text
ask a clinical question with `embed-context discover`
  -> open a returned stable identifier
  -> inspect resolved constraints, related meaning, and provenance
  -> consult an open-v2 profile binding only when implementing against tables
```

## Integrate the catalog

- [Catalog format](catalog-format.md) documents the serialized records,
  validation rules, result envelopes, and Python, CLI, and MCP interfaces.
- [Architecture v7](architecture-v7.md) explains the current catalog-set
  composition, module boundaries, deterministic loading, and effective query
  view.
- [Local catalog curation viewer](curation-viewer-plan.md) records the delivered
  design and acceptance contract for the temporary local browser, connection
  graph, query comparison, validated draft editing, and atomic module saves.
- [Architecture v6](architecture-v6.md) preserves the preceding monolithic
  schema-v6 architecture as history.
- [Profile-module migration](profile-module-migration.md) records the design and
  implementation contract for the schema-v7 catalog set: independently
  loadable public and internal profiles plus layered project extensions for
  work-in-progress features.
- [Architecture v5](architecture-v5.md) preserves the preceding schema-v5
  design as history.
- The README's [AI client section](../README.md#connect-an-ai-client) shows
  Codex, Claude Code, and OpenCode stdio MCP configuration.

## Contribute

Follow [Contributing](../CONTRIBUTING.md) for the development environment,
worked change flow, and validation matrix. The `uv run --locked` commands in
that guide are intentionally development-only; installed users invoke
`embed-context` directly.

[Project scope and authoring requirements](project-scope.md) is the normative
content and safety policy. `catalog/semantic/catalog.json` is the portable
semantic source, `catalog/profiles/open-v2.json` owns the released Open V2
representation, and `catalog/catalog-set.json` selects bundled defaults. Their
version-matched JSON Schemas are structural contracts. Markdown explains those
sources but does not override them.

## Review evidence

These pages preserve authoring provenance. They are not onboarding guides or
executable analysis recipes:

- [Manual review batches](manual-review-batches.md)
- [Open-v2 linkage review](open-v2-linkage-review.md)

The ignored `reference_files/` directory is optional maintainer material.
Never inspect or copy clinical rows, identifiers, anonymized dates, report
text, statistics, or counts. The dedicated source-profile verifier is limited
to Parquet footer schemas.
