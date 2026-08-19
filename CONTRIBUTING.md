# Contributing

Contributions should make the catalog easier to trust without turning it into
an analysis recipe. Shared semantics remain reusable, while profiles and
extensions may add availability-scoped meaning as well as secondary physical
schemas and mappings.

## Development setup

You need uv and Python 3.11, 3.12, or 3.13:

```bash
git clone https://github.com/beatrice-b-m/embedv2-agent-context.git
cd embedv2-agent-context
uv sync --locked --all-extras
uv run --locked embed-context validate
```

This repository is a uv workspace. The root project builds the lightweight
`embedv2-agent-context` distribution; `packages/curator` builds the optional
`embedv2-agent-context-curator` companion. `--all-extras` selects the root MCP
and curator extras, and the workspace source mapping resolves the companion
locally. The two projects use one lockfile and the same software version.

This setup and the baseline test suite need no EMBED data. Read
[the documentation map](docs/README.md), then
[project scope](docs/project-scope.md) before changing catalog meaning.

## Canonical sources

- `catalog/semantic/catalog.json` is the canonical shared semantic content.
- `catalog/profiles/open-v2.json` is the canonical Open V2 evidence, coverage,
  vocabulary, qualification, and physical-binding inventory.
- `catalog/profiles/internal-v2.json` is the non-default working internal
  profile. Phase 1 inventories the wide `magview_all_cohorts_PACS_v2_anon`
  clinical table, binds its supported patient, episode, finding, date,
  procedure, pathology, and registry-reference meanings, and contributes
  internal-only specimen, staging, biomarker, nodal, and source-workflow
  semantics. Procedure information is supported; specimen-level reliability,
  identity, completeness, and cardinality are unresolved. Image metadata and
  image/ROI physical bindings remain deferred to Phase 2.
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
   uses a different column. Put profile-specific meaning in that module's
   `contributions` with the narrowest correct availability.
3. Add or reuse a `temporal_semantic` record that states whether the value is
   event, documentation, or availability time. Do not designate a universal
   diagnosis date, coalesce different time meanings, or substitute an
   unsupported proxy. Use a separately named endpoint or sensitivity analysis
   when another time is genuinely part of the question.
4. Add the narrowest reviewed `context-id#claim-id` and applicable source.
   Preserve unresolved or contradicted status instead of smoothing it away.
5. Declare physical columns once on their table, then add feature mappings only
   when their meaning is supported. Use mapping status and scalar qualifiers
   for direct, derived, conditional, ambiguous, or unresolved interpretations.
   Keep object completeness, authority, and derivation independent; co-location
   is inferred from shared tables. Use occurrence interpretations, instance
   identity, and relationship-binding paths where applicable.
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
empirical counts, distributions, or raw clinical data to the catalog. In an
authorized environment, targeted source-data inspection may inform a specific
semantic decision under the boundary below.

## Clone-safe validation

Run the complete baseline:

```bash
uv run --locked python -m unittest discover -v
uv run --locked embed-context validate
uv run --locked --no-dev --extra mcp python -m unittest \
  tests.test_mcp_server -v
uv run --locked --package embedv2-agent-context-curator python -m unittest \
  discover -s packages/curator/tests -v
```

`tests/test_catalog_schema.py` checks the current semantic and profile modules
against Draft 2020-12 JSON Schema. Synthetic runtime tests cover independent
column inventories, many-to-many mappings, inferred co-location, and same-table
relationships. The core loader additionally enforces reference closure and
semantic invariants.

Use focused checks while iterating:

| Change | Minimum focused checks |
| --- | --- |
| Catalog content or core query | `uv run --locked python -m unittest tests.test_catalog tests.test_catalog_integration -v` |
| JSON Schema or loader validation | `uv run --locked python -m unittest tests.test_catalog_schema tests.test_catalog -v` |
| CLI | `uv run --locked python -m unittest tests.test_cli -v` |
| MCP adapter | `uv run --locked --no-dev --extra mcp python -m unittest tests.test_mcp_server -v` |
| Packaging or entry points | Build both workspace distributions; inspect core exclusion and companion ownership; install base-only and combined wheels into temporary uv tool directories; run installed commands outside the checkout |
| Source-profile verifier | `uv run --locked python -m unittest tests.test_source_profile -v` |
| Local curation viewer | `uv run --locked --package embedv2-agent-context-curator python -m unittest discover -s packages/curator/tests -v` plus the root missing-extra CLI tests |

For the packaging row, build the distributions independently:

```bash
uv build
uv build --package embedv2-agent-context-curator
```

The root wheel must contain no `embed_context_curator` files or browser assets.
The companion wheel must contain its Python package and all files under
`embed_context_curator/static`, and must declare the exact matching core
version. Installed-tool acceptance covers a base-only environment and a
combined environment containing both optional interfaces; isolated MCP and
curator tests cover each extra separately. It also checks that base-only
`curate` exits with the installation hint instead of an import traceback.

## Local curation workbench

The viewer lives in the `packages/curator` workspace member and is not included
in the base wheel. After the workspace setup above, launch read-only review
with `uv run --locked embed-context curate`. To curate, load and select exactly
one source-tree or external schema-v8 module, for example:

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

## Optional local-source investigation

The ignored `reference_files/` directory may contain authorized internal V2
tables, an older V1 Open Data dictionary, and release legends. Before reading
source rows, write down the specific catalog question and use the smallest
practical set of columns and records. Appropriate investigations include
reconciling an existing dictionary entry with all represented categorical
values, checking a sentinel interpretation, and testing a proposed row grain or
linkage. Broad profiling and general-purpose dataset summaries are out of
scope.

Compare internal V2 observations with all applicable evidence:

- maintainer-confirmed meaning;
- the current internal schema and source representation;
- the V2 Open Data legend;
- the non-comprehensive V1 Open Data dictionary; and
- [public EMBED documentation](https://docs.hitilab.com/datasets/embed), which
  primarily describes earlier public representations.

Do not assume historical documentation was carried forward unchanged. Record
conflicts and uncertainty at claim level. Never copy raw rows, identifiers,
dates, report text, extracts, empirical counts, distributions, or statistics
into tracked files or task reports. Only reconciled non-identifying controlled
values and their supported meanings belong in the catalog. Keep temporary
scripts and outputs ignored or outside the checkout, and never commit anything
under `reference_files/`.

For an exact footer-only comparison, maintainers may run:

```bash
uv run --locked python scripts/validate_source_profile.py
```

This verifier remains footer-only. It checks the selected profile's exact
table-owned column inventory, types, and schema nullability; it does not
validate keys, joins, cardinality, clinical meaning, represented values, or ROI
geometry. `reference_files/` is not required for a fresh clone.

## Continuous integration

GitHub Actions runs the clone-safe core and companion baselines on Python 3.11,
3.12, and 3.13 for every pull request and every push to `main`. A separate
packaging job builds both distributions and verifies that the core wheel has no
viewer modules or browser assets while the companion wheel owns all of them.
It tests base-only and combined optional-interface tool installations outside
the checkout, including the base CLI's missing-curator diagnostic; isolated
test steps cover MCP and curator independently. The workflow never accesses
EMBED data or `reference_files/`.

## Pull request checklist

- Clinical meaning and instance grain are independent of storage.
- Claims have the narrowest correct scope, evidence, and review status.
- Targeted source-data findings are reconciled with applicable current and
  historical references without copying raw data or empirical summaries.
- Missing states, attribution, temporal meaning, aggregation, guardrails, and
  coverage stay explicit.
- Instance identity, occurrence-specific interpretations, and composed binding
  paths have applicable evidence and do not promote row keys into clinical
  identity.
- Guardrails have the correct category and priority; exact-result constraints
  and discovery intent boosts preserve stable IDs and explain their basis.
- Tables own complete physical column metadata; semantic mappings do not repeat
  type, nullability, or grain.
- Profile/extension contributions have explicit or module-default availability.
- JSON Schema and strict runtime validation agree where their responsibilities
  overlap.
- Examples, command counts, version axes, and cross-references are current.
- Relevant focused tests and the full clone-safe baseline pass.
- Completed changes are split into descriptive, granular commits.
