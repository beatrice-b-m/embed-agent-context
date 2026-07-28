# Project scope and authoring requirements

## Purpose

This project builds a concise context bundle for agents working with the
EMBED Open Data version 2 clinical data. The bundle should make the data easier
to interpret without hiding uncertainty or importing outdated assumptions from
EMBED V1.

The primary goal is comprehension of the dataset. Prefer clear Markdown,
concrete references to V2 tables and columns, and short explanations over
software infrastructure. Add scripts or generated artifacts only if a later
task demonstrates that they are necessary to verify or maintain the written
context.

## Intended deliverable

`bundle/` is the portable product of this repository. It should remain:

- Markdown-first and readable without special tooling.
- Small enough to reference directly by file path or zip for a web chat.
- Navigable from a single entry-point document once bundle authoring begins.
- Focused on durable context rather than copied rows or bulk source data.
- Explicit about evidence, uncertainty, and V1-to-V2 compatibility concerns.

Keep the number of files low. Organize content by the conceptual layers below,
and split a document only when that materially improves navigation or keeps
agent context focused. Do not introduce a site generator, retrieval service,
database, or custom schema merely to organize the prose.

## Phased implementation

Work should proceed from facts closest to the data toward higher-level
interpretation.

### 1. Feature meanings

Document the meaning of individual columns and coded values in each V2 table.
For each feature, capture the source table, data representation, meaning,
important missing or sentinel values, and interpretation caveats when these can
be verified. Resolve ambiguous names through the V2 files and maintainer input
before relying on V1 documentation.

### 2. Table linkages

Describe the V2 clinical information hierarchy and how records connect across
tables. Identify keys, cardinality, record grain, optional relationships, and
join hazards from direct inspection of the released tables. Distinguish a
verified relationship from one inferred only from matching column names or
values.

### 3. Clinical and procedural context

Explain the workflows and clinical concepts that give the fields and
relationships their meaning. This may include imaging, reporting, assessment,
risk, and pathology processes where relevant to correct dataset use. Keep this
layer tied to specific dataset behavior and clearly separate general clinical
background from EMBED-specific conventions.

Later phases may refine earlier documents as relationships or clinical
workflows expose a more accurate interpretation. Such revisions should retain
useful compatibility notes rather than silently replacing prior assumptions.

## Implemented bundle structure

As of July 28, 2026, the feature layer is implemented in five portable
documents:

- `bundle/README.md` — standalone entry point, evidence labels, table map, and
  cross-cutting interpretation rules;
- `bundle/patient-exam-side-risk.md` — patient, exam, side-level, and risk
  features;
- `bundle/imaging-findings.md` — imaging-finding features and coded
  vocabularies;
- `bundle/pathology-reports-and-wide-table.md` — pathology and report features
  plus a complete `combined_anon` occurrence crosswalk; and
- `bundle/pathology-vocabularies.md` — complete applicable pathology,
  procedure, and location code-to-meaning maps from the release legend.

The documents account for all 243 physical table-column occurrences. They use
the released legend plus the aggregate-only probes registered in
[feature-context-investigation-results.md](feature-context-investigation-results.md).
No report text, clinical table row, identifier value, anonymized date value, or
exam description is copied into the bundle. Applicable release-legend code
maps are intentionally included as feature context.

Phase 2 and Phase 3 are not complete. The feature layer includes only
release-specific grain, relationship, and timing cautions needed to prevent
feature misinterpretation; it does not yet provide a full linkage specification
or clinical workflow guide.

## Evidence and source priority

When sources disagree, use the following order of authority:

1. Facts supplied or confirmed by the EMBED V2 maintainers.
2. Findings verified directly and reproducibly from the V2 reference files.
3. Supporting internal material, including the Cortex knowledge-base vault.
4. Public EMBED documentation and other external sources.

Maintainer statements and direct V2 evidence supersede public numbers,
definitions, and claims. The public documentation at `docs.hitilab.com` was
written for EMBED V1 and must not be treated as authoritative for V2 without
verification. The Cortex vault at `~/AgentFiles/vaults/Cortex/` may provide
useful background, but its claims should also be checked against V2 data or
confirmed by a maintainer when they affect the bundle.

External sources may supply general clinical context. They must not be used to
fill a dataset-specific gap as if the result were verified. Record the source
near claims whose authority or version is not obvious, and label unresolved
conflicts, assumptions, and inferences plainly.

## Current source inventory

As of July 28, 2026, `reference_files/` contains:

- Eight extracted Parquet tables under `clinical_tables/`:
  `combined_anon`, `exam_level_anon`, `imaging_findings_anon`,
  `pathology_findings_anon`, `patients_anon`, `reports_anon`, `risk_anon`, and
  `side_level_anon`.
- `EMBEDv2-open-data-clinical-legend.csv`, a code legend with the columns
  `Header in export`, `Discription`, `Code`, and `Meaning`.

This inventory records filenames plus format metadata verified without reading
clinical data pages. The source files, footer-level row and column counts, and
the question-driven inspection gates are recorded in
[feature-context-investigation-plan.md](feature-context-investigation-plan.md).
The inventory does not assert table grain, keys, feature definitions, or
clinical meaning; those require phased inspection and verification.

The reference directory is ignored by Git so local source data are not
accidentally committed. Bundle documents should refer to the source artifacts
by stable names and should not reproduce bulk data.

## Bundle and documentation synchronization

Every change under `bundle/` must include a review of this documentation and
other relevant files under `docs/`. In the same commit:

- Update the documented bundle structure or status when it changes.
- Update source and verification notes when a claim is added, revised, or
  removed.
- Record compatibility or migration implications when V1 assumptions are
  corrected for V2.
- Check examples and cross-references for stale filenames, fields, and
  relationships.

If a bundle change genuinely requires no documentation edit, state why in the
commit message or task report, as required by `AGENTS.md`. Documentation should
describe implemented bundle content, not planned content as though it already
exists.

## Completion criteria for a bundle addition

A context addition is complete when it:

- Is supported at the claimed evidence level.
- Identifies the relevant V2 table and columns where applicable.
- Separates verified facts from inference and general background.
- Notes known ambiguity, missing-value behavior, and version caveats that
  materially affect interpretation.
- Is linked from the bundle entry point and is understandable in a zipped,
  standalone copy of `bundle/`.
- Has corresponding project documentation updates and a focused Git commit.
