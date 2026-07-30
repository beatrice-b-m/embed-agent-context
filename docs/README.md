# Documentation

Choose the page that matches what you want to do.

## Use the catalog

Start with the repository [README](../README.md). It explains why the catalog
exists, installs the commands with `uv tool install`, and walks through a
clinical-first query. No EMBED data or repository checkout is needed.

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
- [Architecture v6](architecture-v6.md) explains why portable clinical meaning
  is separate from occurrence-aware release bindings and how query results
  surface applicable constraints.
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
content and safety policy. `catalog/catalog.json` is the canonical content
source and `catalog/catalog.schema.json` is its structural contract. Markdown
explains those sources but does not override them.

## Review evidence

These pages preserve authoring provenance. They are not onboarding guides or
executable analysis recipes:

- [Manual review batches](manual-review-batches.md)
- [Open-v2 linkage review](open-v2-linkage-review.md)

The ignored `reference_files/` directory is optional maintainer material.
Never inspect or copy clinical rows, identifiers, anonymized dates, report
text, statistics, or counts. The dedicated source-profile verifier is limited
to Parquet footer schemas.
