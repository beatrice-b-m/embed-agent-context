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

- `catalog/semantic/catalog.json` is the canonical portable semantic content.
- `catalog/profiles/open-v2.json` is the canonical Open V2 evidence, coverage,
  vocabulary, qualification, and physical-binding inventory.
- `catalog/catalog-set.json` selects bundled defaults; each document type has
  a standalone version-matched JSON Schema shape contract.
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
   diagnosis date, coalesce different time meanings, or substitute an
   unsupported proxy. Use a separately named endpoint or sensitivity analysis
   when another time is genuinely part of the question.
4. Add the narrowest reviewed `context-id#claim-id` and applicable source.
   Preserve unresolved or contradicted status instead of smoothing it away.
5. Add profile feature/object/relationship bindings only when verified
   physical metadata supports them. Use occurrence interpretations for
   binding-specific value or null meaning, instance identity for bounded
   clinical identity, and relationship-binding paths for supported multi-edge
   routes. Record join hazards and unsupported coverage explicitly.
6. Change the applicable semantic, profile, extension, or manifest schema only
   when its serialized shape or an expressible invariant changes. Keep runtime
   and schema validators in parity.
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
| Local curation viewer | `uv run --locked python -m unittest tests.test_curator_documents tests.test_curator_forms tests.test_curator_graph tests.test_curator_query_diff tests.test_curator_session tests.test_curator_server tests.test_curator_cli -v` |

## Local curation workbench

Launch read-only review with `uv run --locked embed-context curate`. To curate,
load and select exactly one source-tree or external schema-v7 module, for
example:

```bash
uv run --locked embed-context \
  --extension-file project-configs/review.json \
  curate --edit-module project-configs/review.json
```

Before saving, validate the current revision, compare baseline and draft query
behavior, and inspect the exact source diff. A save is refused if any loaded
module changed on disk. After saving, rerun the normal focused checks and
clone-safe baseline, inspect `git diff`, and commit through the ordinary review
flow. The viewer does not stage or commit files.

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

## Continuous integration

GitHub Actions runs the clone-safe baseline on Python 3.11, 3.12, and 3.13 for
every pull request and every push to `main`. A separate packaging job builds
the source distribution and wheel, installs the wheel with its MCP extra into
temporary tool directories outside the checkout, and invokes both installed
entry points. The workflow never accesses EMBED data or `reference_files/`.

## Pull request checklist

- Clinical meaning and instance grain are independent of storage.
- Claims have the narrowest correct scope, evidence, and review status.
- Missing states, attribution, temporal meaning, aggregation, guardrails, and
  coverage stay explicit.
- Instance identity, occurrence-specific interpretations, and composed binding
  paths have applicable evidence and do not promote row keys into clinical
  identity.
- Guardrails have the correct category and priority; exact-result constraints
  and discovery intent boosts preserve stable IDs and explain their basis.
- Physical metadata remains under `profile_bindings`.
- JSON Schema and strict runtime validation agree where their responsibilities
  overlap.
- Examples, command counts, version axes, and cross-references are current.
- Relevant focused tests and the full clone-safe baseline pass.
- Completed changes are split into descriptive, granular commits.
