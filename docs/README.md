# Documentation

Choose the page that matches what you want to do.

## Use the catalog

Start with the repository [README](../README.md). It explains why the catalog
exists, installs the lightweight base command with `uv tool install`, describes
the separately selected `mcp` and `curator` extras, and walks through a
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
- [Architecture v8](architecture-v8.md) explains the current scoped
  contribution model, independent physical schemas, deterministic loading,
  and effective query view.
- [Local catalog curation viewer](curation-viewer-plan.md) records the delivered
  design, companion-distribution boundary, and acceptance contract for the
  temporary local browser, connection graph, query comparison, validated draft
  editing, and atomic module saves.
- [Architecture v7](architecture-v7.md) and the
  [profile-module migration](profile-module-migration.md) preserve the former
  v7/v1/v1 ownership and typed-revision design as history.
- [Architecture v6](architecture-v6.md) preserves the preceding monolithic
  schema-v6 architecture as history.
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
content and safety policy. `catalog/semantic/catalog.json` owns shared
semantics; profiles may add availability-scoped meaning alongside physical
representations. `catalog/catalog-set.json` selects bundled defaults. Their
version-matched JSON Schemas are structural contracts. Markdown explains those
sources but does not override them.

## Review evidence

These pages preserve authoring provenance. They are not onboarding guides or
executable analysis recipes:

- [Manual review batches](manual-review-batches.md)
- [Open-v2 linkage review](open-v2-linkage-review.md)

The ignored `reference_files/` directory is optional maintainer material.
In an authorized environment it may support narrowly scoped investigation of a
specific catalog question, including reconciliation of represented categorical
values. Raw rows, identifiers, dates, report text, extracts, counts, and
distributions must not enter tracked files. The V1 Open Data dictionary and
[public EMBED documentation](https://docs.hitilab.com/datasets/embed) are useful
but historical and non-comprehensive; compare them, and the V2 Open Data
legend, against internal V2 source data before asserting profile behavior. The
dedicated source-profile verifier remains limited to Parquet footer schemas, so a
delimited-text artifact such as the internal V1c image metadata is outside its
scope and its recorded physical types are assessed parse types.
