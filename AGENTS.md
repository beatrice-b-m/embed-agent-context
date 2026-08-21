# Repository guidelines for agents

## Start here

Read these in order before changing behavior or catalog meaning:

1. `README.md` for the first-use contract and public interfaces.
2. `docs/README.md` for the role-based documentation map.
3. `docs/project-scope.md` for normative clinical, evidence, portability, and
   safety boundaries.
4. `CONTRIBUTING.md` for the worked change flow and validation matrix.
5. `docs/catalog-format.md` and `docs/architecture-v8.md` when changing the
   serialized model or query behavior.

The current version axes are independent: software `0.10.0`, semantic catalog
schema version `8`, profile-module schema version `2`, extension-module schema
version `2`, registered public profile `open-v2`, and optional MCP SDK
dependency `2.0.0`. The optional `embedv2-agent-context-curator` companion is
versioned in lockstep with the core distribution.

## Canonical-source hierarchy

- `catalog/semantic/catalog.json` is the source of truth for shared clinical
  semantics, provenance, controlled values, and vocabularies.
- `catalog/profiles/open-v2.json` is the source of truth for the released Open
  V2 profile, its qualifications, evidence, coverage, and physical bindings.
- `catalog/profiles/internal-v2.json` is the non-default working internal
  profile. It covers the wide MagView clinical table; its procedure-level
  representation is supported and its specimen-level reliability and identity
  remain unresolved. It also covers the internal V1c image-metadata table with
  image, co-located patient/exam/side,
  DICOM-attribute, modality, enrichment, and serialized region-of-interest
  representations. The clinical surface is internal V2 while the paired image
  metadata is the most recent internal V1c artifact, covers every EMBEDv1 exam
  and patient, and is narrower than clinical V2, so an unmatched later clinical
  exam means missing extraction coverage rather than missing images. The
  ROI collections use inclusive `[y_min, x_min, y_max, x_max]` target-image
  pixel bounds, normally curated in bounds with safe downstream clipping for
  residual out-of-bounds values, and originate through multiple clinical
  annotation workflows rather than only ROI_SS/ROI_SSC screen captures. The
  patient and exam identifiers share their cross-table namespaces, every
  accession belongs to exactly one patient, and any cross-patient association
  is a data-quality error. The anonymized DICOM locator is intended for every
  extracted image; its basename is the anonymized SOP Instance UID within one
  dataset version, and a missing locator likely means anonymization failed
  before the de-identified file could be saved.
- `catalog/catalog-set.json` selects the bundled semantic and default profile
  modules; version-matched schemas are standalone structural contracts.
- `embed_context/catalog.py` implements strict parsing, cross-reference,
  clinical-semantic, scope, and profile invariants.
- README and `docs/` are manually synchronized explanations. They must agree
  with the structured catalog and implementation but never override them.
- `docs/manual-review-batches.md` and `docs/open-v2-linkage-review.md` are
  historical evidence records, not executable policy or general onboarding.

Search for existing objects, concepts, claims, sources, and vocabularies before
adding stable IDs. Reuse shared semantics when meaning is unchanged. Profiles
and extensions may add every semantic family with explicit or module-default
availability; keep physical columns in table inventories and interpretations
in stable-ID mappings. Typed revisions and legacy catalog loading are not part
of schema v8.

## Clinical-source investigation boundary

The catalog and normal test suite remain count-free and require no EMBED data.
When authorized local artifacts are present, maintainers and agents may inspect
clinical source data narrowly to answer a specific catalog question.

- State the question first and inspect only the columns and rows needed to
  answer it. Targeted uses include reconciling a documented feature with the
  complete set of represented categorical values, checking a sentinel, or
  testing a proposed row-grain or linkage interpretation. Do not perform broad,
  open-ended profiling.
- Direct internal-V2 observations establish what the working data represents;
  they do not by themselves establish clinical meaning, exhaustiveness, or a
  preferred analysis policy. Reconcile them with maintainer knowledge,
  applicable legends, dictionaries, and documentation.
- Use the release-neutral evidence value `observed_source_values` for targeted
  source observations. The containing profile, claims, and sources carry the
  V1c, V2, public, or internal version boundary.
- The V1 Open Data dictionary and public EMBED documentation are historical,
  non-comprehensive references. The V2 Open Data legend is a closer comparison
  source, but none may be assumed to describe internal V2 without checking the
  source data and recording disagreements or uncertainty.
- Never copy or commit raw rows, patient or exam identifiers, anonymized dates,
  report text, source extracts, empirical counts, distributions, or statistics.
  Non-identifying controlled values may enter the catalog only after their
  meaning and scope have been reconciled.
- `reference_files/` is ignored local material. Never add or commit any of its
  contents. Keep temporary investigation outputs there or outside the checkout
  and review staged changes for accidental clinical content.
- `scripts/validate_source_profile.py` remains a footer-only, Parquet-only exact
  schema verifier. Its narrow implementation must not be expanded into a row
  reader or a delimited-text reader; separate, question-specific investigation
  may be used during authorized catalog authoring. The internal V1c
  image-metadata table is delimited text and is therefore outside its scope.
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
