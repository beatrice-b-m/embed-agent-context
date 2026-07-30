# Documentation map

Choose the shortest route for what you are doing.

## First-time user or agent

1. Start with the repository [README](../README.md) to install the CLI or MCP
   server and run a clinical-first discovery query.
2. Read the [clinical-semantic model](clinical-semantic-model.md) for the
   object graph, outcome states, time meanings, aggregations, and interpretation
   limits.
3. Use `embed-context discover ... --limit 5`, then follow a returned stable ID
   with the matching exact getter.

No EMBED data is needed for this path.

## Application or MCP integrator

- [Catalog format](catalog-format.md) defines serialized records, strict
  validation, query envelopes, and the Python/CLI/MCP surfaces.
- [Architecture v5](architecture-v5.md) explains why portable semantics and
  profile-specific physical bindings are separate.
- [Migration v4 to v5](migration-v4-to-v5.md) maps removed and renamed
  commands, methods, tools, and fields.
- The [README MCP section](../README.md#stdio-mcp-server) contains verified
  Codex, Claude Code, and OpenCode stdio configurations.

## Contributor or maintainer

1. Follow [Contributing](../CONTRIBUTING.md) for environment setup, a worked
   semantic-change flow, and the exact validation matrix.
2. Treat [Project scope and authoring requirements](project-scope.md) as the
   normative content and safety policy.
3. Treat `catalog/catalog.json` as the canonical content source and
   `catalog/catalog.schema.json` as its structural contract. Markdown explains
   those sources; it does not override them.

The ignored `reference_files/` directory is optional. Never read or copy
clinical rows, identifiers, anonymized dates, report text, statistics, or
counts. The only permitted automated access is Parquet footer schema
inspection through the dedicated verifier.

## Evidence records

These files preserve review provenance; they are not general onboarding
guides or executable workflow specifications:

- [Manual review batches](manual-review-batches.md) records the reviewed
  clinical responses incorporated into the catalog.
- [Open-v2 linkage review](open-v2-linkage-review.md) records the historical
  release-layout evidence behind physical association caveats. `open-v2` is
  the registered EMBED V2 physical profile ID, not a catalog schema version.
