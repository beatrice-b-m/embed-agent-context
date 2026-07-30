# Contributing

Contributions should make the catalog easier to trust without turning it into
an analysis recipe. Portable clinical semantics are primary; release-specific
tables, columns, and physical associations remain secondary profile bindings.

## Development setup

You need uv and Python 3.11, 3.12, or 3.13:

```bash
git clone https://github.com/beatrice-b-m/embedv2-agent-context.git
cd embedv2-agent-context
uv sync --locked --all-extras
uv run --locked embed-context validate
```

This setup and the baseline test suite need no EMBED data. Read
[the documentation map](docs/README.md), then
[project scope](docs/project-scope.md) before changing catalog meaning.

## Canonical sources

- `catalog/catalog.json` is the canonical semantic content and physical
  binding inventory.
- `catalog/catalog.schema.json` is the standalone JSON Schema shape contract.
- `embed_context/catalog.py` adds strict semantic, cross-reference, scope, and
  profile invariants that JSON Schema cannot express.
- Human-facing Markdown is manually synchronized explanatory material. It is
  neither generated output nor a competing source of truth.

Search for an existing stable ID, concept, claim, or vocabulary before adding
one:

```bash
rg -n "candidate phrase|candidate.identifier" \
  catalog embed_context tests docs README.md
```

## Worked semantic-change flow

Suppose a review establishes a new timestamp meaning.

1. Identify the clinical object and what one instance represents. Reuse an
   existing object when its clinical grain is unchanged.
2. Check whether an existing concept already has the same meaning. Create a
   new concept only when meaning changes, not merely because another profile
   uses a different column.
3. Add or reuse a `temporal_semantic` record that states whether the value is
   event, documentation, or availability time. Do not designate a universal
   diagnosis date or substitute an unsupported proxy.
4. Add the narrowest reviewed `context-id#claim-id` and applicable source.
   Preserve unresolved or contradicted status instead of smoothing it away.
5. Add profile feature/object/relationship bindings only when verified
   physical metadata supports them. Record join hazards and unsupported
   coverage explicitly.
6. Change `catalog.schema.json` only when the serialized shape or invariant
   expressible in JSON Schema changes. Keep runtime and schema validators in
   parity.
7. Add focused synthetic unit tests, checked-in catalog acceptance assertions,
   and interface tests for every changed CLI, Python, or MCP surface.
8. Synchronize README, format, architecture, and agent instructions affected
   by the change.
9. Commit the coherent change with an informative
   `type(scope): subject` message.

Never add SQL, dataframe logic, executable cohort rules, preferred outcomes,
empirical counts, distributions, or clinical data to the catalog.

## Clone-safe validation

Run the complete baseline:

```bash
uv run --locked python -m unittest discover -v
uv run --locked embed-context validate
uv run --locked --no-dev --extra mcp python -m unittest \
  tests.test_mcp_server -v
```

`tests/test_catalog_schema.py` checks the canonical and synthetic catalogs
against Draft 2020-12 JSON Schema and tests schema/runtime parity. The core
loader additionally enforces reference closure and semantic invariants.

Use focused checks while iterating:

| Change | Minimum focused checks |
| --- | --- |
| Catalog content or core query | `uv run --locked python -m unittest tests.test_catalog tests.test_catalog_integration -v` |
| JSON Schema or loader validation | `uv run --locked python -m unittest tests.test_catalog_schema tests.test_catalog -v` |
| CLI | `uv run --locked python -m unittest tests.test_cli -v` |
| MCP adapter | `uv run --locked --no-dev --extra mcp python -m unittest tests.test_mcp_server -v` |
| Packaging or entry points | `uv build`; install the wheel or checkout into temporary uv tool directories; run `embed-context validate` outside the checkout |
| Source-profile verifier | `uv run --locked python -m unittest tests.test_source_profile -v` |

Before committing, inspect `git diff`, stage only the coherent unit, and verify:

```bash
git status --short
git log --oneline -3
```

## Optional local-artifact verification

Maintainers who separately possess the ignored
`reference_files/clinical_tables/` artifacts may run:

```bash
uv run --locked python scripts/validate_source_profile.py
```

The verifier reads Parquet footer schemas only. It must never inspect or copy
rows, clinical values, identifiers, anonymized dates, report text, statistics,
or counts. `reference_files/` is not required for a fresh clone and must never
be committed.

## Pull request checklist

- Clinical meaning and instance grain are independent of storage.
- Claims have the narrowest correct scope, evidence, and review status.
- Missing states, attribution, temporal meaning, aggregation, guardrails, and
  coverage stay explicit.
- Physical metadata remains under `profile_bindings`.
- JSON Schema and strict runtime validation agree where their responsibilities
  overlap.
- Examples, command counts, version axes, and cross-references are current.
- Relevant focused tests and the full clone-safe baseline pass.
- Completed changes are split into descriptive, granular commits.
