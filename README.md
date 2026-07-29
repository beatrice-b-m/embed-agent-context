# EMBED feature context

This repository provides a small, machine-queryable feature catalog for the
Emory Breast Imaging Dataset (EMBED). It describes what clinical-data features
capture, how physical columns bind to those concepts at different grains, and
which released code meanings apply.

The canonical product is structured JSON rather than Markdown tables. It
deliberately excludes release-specific row counts, null counts, value
frequencies, quantiles, prevalence estimates, and similar statistics. The same
semantic concepts can therefore support open and non-open data profiles without
turning one release's measurements into apparent contracts.

## Repository layout

- [`catalog/catalog.json`](catalog/catalog.json) — the canonical feature
  concepts, physical bindings, facets, and code vocabularies.
- [`catalog/catalog.schema.json`](catalog/catalog.schema.json) — the versioned
  JSON Schema for the catalog.
- `embed_context/` — the dependency-free query core and command-line interface,
  plus an optional stdio MCP adapter.
- `tests/` — synthetic contract, validation, search, CLI, MCP, and
  source-profile tests.
- [`docs/catalog-format.md`](docs/catalog-format.md) — the data model,
  extension rules, and portability policy.
- [`docs/project-scope.md`](docs/project-scope.md) — project boundaries and
  authoring requirements.
- `reference_files/` — local EMBED V2 source artifacts used to build and verify
  profile bindings. This directory is intentionally ignored by Git.
- `AGENTS.md` — repository contribution, commit, and documentation-sync rules.

## Current status

Phase 1 is represented as a normalized catalog: shared features have one
canonical concept, while profile/table/column occurrences are separate
bindings. Finding-level flags remain distinct from side- and exam-level
aggregates because those levels carry different meanings. Repeated physical
projections, including the wide table, do not duplicate semantic definitions.

The query CLI and optional MCP adapter expose the same validated in-memory
catalog. Full relationship/cardinality specifications and broader clinical
workflow context remain later phases.

## Command-line queries

The catalog core uses only the Python standard library. Run it from the
repository without installing a package:

```bash
uv run --locked --no-dev python -m embed_context validate
uv run --locked --no-dev python -m embed_context get pathology.diagnosis_code_slot
uv run --locked --no-dev python -m embed_context get imaging_findings_anon.asses --include-codes
uv run --locked --no-dev python -m embed_context search "breast density"
uv run --locked --no-dev python -m embed_context search --domain pathology --grain pathology_finding
uv run --locked --no-dev python -m embed_context code imaging.assessment N
```

Use `--format json` before the subcommand for a stable machine-readable
envelope:

```bash
uv run --locked --no-dev python -m embed_context --format json search "social determinants"
```

Search returns each semantic concept once and includes the physical bindings
that matched the query and filters. It is deterministic token-overlap search,
not semantic embedding search. Exact lookup accepts a concept ID,
`table.column`, or `profile:table.column`. The profile-qualified form is needed
only when the same physical name has different meanings in different profiles.
Search returns up to fifty concepts by default; use `--limit` for a broader
result set when needed.

Run `python -m embed_context --help` or a subcommand's `--help` for the complete
filter surface. `--format json validate` also returns the controlled grains,
domains, and feature kinds for programmatic discovery.

## Stdio MCP server

MCP support is optional so the catalog and CLI remain dependency-free. Start
the server with the pinned official SDK extra:

```bash
uv run --locked --no-dev --extra mcp python -m embed_context.mcp_server
```

An MCP client configuration can invoke it from any working directory:

```json
{
  "command": "uv",
  "args": [
    "--directory",
    "/absolute/path/to/embedv2-agent-context",
    "run",
    "--locked",
    "--no-dev",
    "--extra",
    "mcp",
    "python",
    "-m",
    "embed_context.mcp_server"
  ]
}
```

The server exposes three read-only structured-output tools:
`get_feature`, `search_features`, and `lookup_code`. It writes MCP protocol
messages only to stdout; startup errors and diagnostics go to stderr. The
search tool's input schema enumerates the controlled grain, domain, and feature
kind filters, while its description lists the profiles and tables present in
the loaded catalog.

## Maintainer verification

Run the complete test suite and the footer-only source-profile check:

```bash
uv run --locked python -m unittest discover -v
uv run --locked python scripts/validate_source_profile.py
```

The second command derives the expected manifest from the selected profile and
compares table names, columns, physical types, and schema nullability. It reads
Parquet footers only and does not inspect clinical values or statistics.

To exercise the optional protocol adapter against the pinned MCP SDK:

```bash
uv run --locked --no-dev --extra mcp python -m unittest tests.test_mcp_server -v
```

## Migration from the Markdown feature bundle

The former feature tables and empirical investigation ledger were removed.
They mixed semantic definitions with open-release measurements and repeated
shared features across physical tables. Git history retains that work for
audit, but it is no longer an agent-facing source. New feature context must be
added to the structured catalog and queried through the shared core.
