# Repository guidelines for agents

## Start here

Read these in order before changing behavior or catalog meaning:

1. `README.md` for the first-use contract and public interfaces.
2. `docs/README.md` for the role-based documentation map.
3. `docs/project-scope.md` for normative clinical, evidence, portability, and
   safety boundaries.
4. `CONTRIBUTING.md` for the worked change flow and validation matrix.
5. `docs/catalog-format.md` and `docs/architecture-v7.md` when changing the
   serialized model or query behavior.

The current version axes are independent: software `0.9.0`, semantic catalog
schema version `7`, profile-module schema version `1`, extension-module schema
version `1`, registered physical profile `open-v2`, and optional MCP SDK
dependency `2.0.0`. The optional `embedv2-agent-context-curator` companion is
versioned in lockstep with the core distribution.

## Canonical-source hierarchy

- `catalog/semantic/catalog.json` is the source of truth for portable clinical
  semantics, provenance, controlled values, and vocabularies.
- `catalog/profiles/open-v2.json` is the source of truth for the released Open
  V2 profile, its qualifications, evidence, coverage, and physical bindings.
- `catalog/catalog-set.json` selects the bundled semantic and default profile
  modules; version-matched schemas are standalone structural contracts.
- `embed_context/catalog.py` implements strict parsing, cross-reference,
  clinical-semantic, scope, and profile invariants.
- README and `docs/` are manually synchronized explanations. They must agree
  with the structured catalog and implementation but never override them.
- `docs/manual-review-batches.md` and `docs/open-v2-linkage-review.md` are
  historical evidence records, not executable policy or general onboarding.

Search for existing objects, concepts, claims, sources, and vocabularies before
adding stable IDs. Keep portable semantics primary, released representation in
its profile module, and project-owned additions or revisions in explicitly
selected extension modules.

## Clinical-data safety boundary

The catalog and normal test suite are count-free and require no EMBED data.

- Never inspect, sample, copy, summarize, or commit clinical rows, identifiers,
  anonymized dates, report text, values, statistics, distributions, or counts.
- `reference_files/` is ignored local material. Never add or commit any of its
  contents.
- The only permitted automated access to local clinical table artifacts is the
  dedicated `scripts/validate_source_profile.py` footer-schema check. It reads
  Parquet metadata only and must remain row-, statistics-, and count-free.
- Treat release-schema and legend evidence as profile-specific. Public or
  historical material cannot silently fill a verified profile gap.
- Do not turn guardrails or historical recipes into SQL, dataframe logic,
  cohort definitions, target labels, preferred dates, aggregation defaults, or
  scientific-validity claims.

## Environment and validation

Set up all development dependencies and optional interfaces with:

```bash
uv sync --locked --all-extras
```

The clone-safe baseline is:

```bash
uv run --locked python -m unittest discover -v
uv run --locked embed-context validate
uv run --locked --no-dev --extra mcp python -m unittest \
  tests.test_mcp_server -v
uv run --locked --package embedv2-agent-context-curator python -m unittest \
  discover -s packages/curator/tests -v
```

Run focused tests while iterating:

- core/catalog: `tests.test_catalog tests.test_catalog_integration`
- JSON Schema parity: `tests.test_catalog_schema`
- CLI: `tests.test_cli`
- MCP: `tests.test_mcp_server` with `--extra mcp`
- curator companion: `packages/curator/tests` with
  `--package embedv2-agent-context-curator`
- footer verifier implementation: `tests.test_source_profile`

Run `uv run --locked python scripts/validate_source_profile.py` only when the
optional ignored artifacts are already present and footer verification is
actually in scope.

For packaging changes, build both workspace distributions. Verify that the core
wheel contains the catalog resources and entry points but no curator
implementation or browser assets, and that the companion wheel owns all viewer
code and static resources. Test base-only and combined installs in temporary
`UV_TOOL_DIR` and `UV_TOOL_BIN_DIR` locations from outside the checkout.

## Change-specific interface checklist

- Catalog or schema: update both validators where responsibilities overlap,
  add parity and acceptance tests, and document shape/invariant changes.
- Core getter/discovery: update Python, CLI, and MCP surfaces plus response
  documentation and navigation examples.
- CLI: test text output, JSON success and error envelopes, exit status, and
  help.
- MCP: test the advertised tool set, closed input schemas, read-only
  annotations, generic structured output, dispatch, and stderr-only startup
  errors.
- Packaging: keep the bundled catalog/schema, console scripts, package version,
  companion version, README install paths, and client configurations
  synchronized.
- Any public interface change: update the relevant usage, format, and
  architecture documentation.

If a functional change genuinely needs no documentation update, record the
reason in the commit message or task report.

## Git commit policy

Every completed change must be tracked in a descriptive, granular git commit.
Do not leave completed work uncommitted.

- Commit after each distinct logical unit rather than batching unrelated
  changes.
- Keep each commit focused on one coherent change.
- Use informative `type(scope): subject` messages, with a body when the subject
  alone is insufficient.
- Stage files selectively so each commit contains only its logical unit.
- Do not amend, rewrite, or force-push unless the user explicitly asks.
- Before yielding a completed task, verify `git status --short` and
  `git log --oneline -3`.

Documentation synchronization is part of each logical unit: update relevant
user, operator, architecture, configuration, command, and agent references
before considering a functional change complete.
