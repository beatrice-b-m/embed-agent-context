# Feature-context investigation plan

## Scope decision

The requested feature-level context system is the first phase of the portable
Markdown bundle described in this repository. It is not a runtime ingestion,
retrieval, or database system. The investigation will produce a compact,
agent-readable feature reference under `bundle/`, backed by reproducible,
question-driven inspection of the EMBED V2 reference files.

The immediate scope is:

- every physical column in the eight released Parquet tables;
- every applicable header, code, and meaning in the released legend;
- physical representation, dataset-specific meaning, coded values,
  missing/sentinel behavior, interpretation caveats, and evidence status;
- enough table-grain and provenance analysis to avoid describing a feature at
  the wrong conceptual level; and
- an explicit register of unresolved meanings and maintainer questions.

Full relationship documentation and general clinical workflow guidance remain
later phases. This investigation may establish relationship facts needed to
interpret features, but it will not present a schema-derived join as verified
or expand into a general data-processing framework.

## Scope assessment against the available references

Footer-only inspection confirms that the planned Phase 1 source set is present:

| Table | Rows | Columns | Immediate feature-context role |
| --- | ---: | ---: | --- |
| `patients_anon` | 22,936 | 8 | Patient identity and demographics |
| `exam_level_anon` | 131,052 | 23 | Exam identity, descriptors, and exam aggregates |
| `risk_anon` | 77,499 | 16 | Risk-model outputs |
| `combined_anon` | 172,553 | 101 | Wide derived or convenience representation |
| `reports_anon` | 125,959 | 6 | Report sequence and text |
| `imaging_findings_anon` | 171,378 | 54 | Finding-level imaging attributes |
| `side_level_anon` | 159,939 | 9 | Breast-side aggregates |
| `pathology_findings_anon` | 170,633 | 26 | Procedure and pathology attributes |

The four-column legend
`EMBEDv2-open-data-clinical-legend.csv` is also present. Its source header uses
the spelling `Discription`; the bundle will preserve the source filename while
using correctly spelled prose labels.

This is sufficient to investigate feature meanings, but not sufficient by
itself to guarantee them. Parquet schemas declare all columns optional and do
not declare keys or semantic constraints. The legend must therefore be checked
for coverage, ambiguity, code scope, and agreement with observed V2
representations. In particular:

- `combined_anon` substantially overlaps several level-specific tables, but its
  construction and authority are not documented by the file metadata;
- matching field names at finding, side, and exam levels do not imply matching
  grain or interchangeable meaning;
- a serialized `__index_level_0__` column occurs in six tables and must be
  classified as data or an export artifact;
- opaque, misspelled, or duplicated names require explicit treatment rather
  than silent normalization; and
- report, linked-accession, procedure, and pathology fields may encode
  information from different points in the clinical timeline.

## Questions the investigation must resolve

### Coverage and traceability

1. What are the exact columns and physical/logical types in each table?
2. Which table-column occurrences have legend definitions and coded meanings?
3. Which legend headers or codes are unused, duplicated, conflicting, or scoped
   differently between tables?
4. Can every physical column be accounted for as a documented feature, an
   identifier, or a verified export artifact?

### Representation and values

5. Is each feature binary, nominal, ordinal, continuous, text, date/time, or an
   identifier in this release?
6. Which values mean missing, unknown, not applicable, not assessed, or another
   non-clinical state?
7. Do observed bounded categorical domains agree with the legend?
8. What units, scales, and rounding conventions apply to numeric fields where
   those facts can be verified?

### Meaning and conceptual level

9. At what patient, exam, side, imaging-finding, pathology-finding, report, or
   risk-assessment level should each feature be interpreted?
10. Are similarly named aggregate fields at finding, side, and exam levels
    distinct, derived, or equivalent?
11. Are fields repeated in `combined_anon` authoritative copies, transformations,
    or products of a multiplicative join?
12. Which fields are direct source values versus derived summaries or model
    outputs?

### Identity, time, and safe interpretation

13. What minimal key facts are necessary to state a feature's grain correctly?
14. Do identifiers and anonymized dates remain stable across the tables where
    they recur?
15. What ordering or interval properties are actually preserved by anonymized
    dates?
16. Which report, recommendation, linked-study, procedure, biopsy, and pathology
    fields could represent post-exam information and therefore require a
    temporal-leakage caveat?

### Evidence and escalation

17. Which claims are directly supported by release metadata, legend entries,
    or targeted value checks?
18. Which interpretations remain inferred, conflict with the V2 representation,
    or require maintainer confirmation?
19. What concise maintainer questions would resolve the highest-impact
    uncertainties without substituting V1 documentation for V2 evidence?

## Evidence labels

Feature entries will distinguish:

- **Release schema** — verified from a Parquet schema or file metadata.
- **Release legend** — stated by the V2 legend, with source spelling or
  ambiguity noted where material.
- **Observed V2 values** — verified through a named, projected-column query.
- **Cross-table check** — verified through a named, identifier-only or
  feature-specific comparison.
- **Inference** — plausible interpretation not established by a higher-priority
  source.
- **Unresolved** — insufficient or conflicting evidence; maintainer input is
  needed.

An evidence label describes support, not clinical importance. Inferences and
unresolved items will remain visible rather than being silently promoted to
facts.

## Minimal, targeted data-access protocol

The investigation will use a project-local `.venv` managed by `uv`. Only the
smallest library set needed for Parquet metadata and projected-column queries
will be installed. The environment is an investigation aid, not part of the
agent-facing bundle.

Access proceeds in escalating gates:

1. **Names and file metadata.** Inventory filenames, sizes, Parquet schemas,
   row counts, and footer statistics. Do not open data pages.
2. **Legend crosswalk.** Read the four legend columns for the specific purpose
   of mapping all released definitions and codes to the schema inventory. This
   is a bounded authoritative source, not a request for clinical-row data.
3. **Metadata-first characterization.** Use footer null counts and min/max
   statistics where present. Because each Parquet file has one row group,
   row-group filtering cannot reduce access further.
4. **Projected bounded domains.** Read only named categorical columns whose
   code domain, blank handling, or legend agreement is under investigation.
   Never select unrelated columns or full rows.
5. **Key-only checks.** Read only candidate identifier columns to answer a
   stated grain, uniqueness, referential-integrity, or `combined_anon`
   construction question.
6. **Focused numeric checks.** Read one named numeric column only when a
   concrete range, unit, or sentinel question cannot be resolved from metadata
   or the legend.
7. **Exceptional text access.** Do not read `report_anon` values during the
   feature phase unless a specific representation or leakage question cannot
   be answered from its schema, identifiers, and legend. Never reproduce
   report text in tracked artifacts.

Each query must have a written question, a limited column projection, and a
recorded aggregate answer. Do not dump rows, export source subsets, calculate
full-file hashes merely for inventory, or retain copied clinical data.

## Investigation work packages

### A. Schema and legend coverage

- Build the table-column inventory from schemas.
- Normalize the legend's source formatting without silently correcting field
  identifiers.
- Crosswalk table-column occurrences to legend header/code rows.
- Identify orphan legend entries, undocumented columns, duplicate meanings,
  conflicting codes, and case-sensitive mismatches.

### B. Patient, exam, side, and risk features

- Establish the representation and vocabulary of demographics, exam
  descriptors, laterality, aggregate flags, and risk outputs.
- Verify only the minimal key/grain facts needed for correct level labels.
- Resolve missing states, units, model horizons, and density variants where the
  V2 evidence supports them.

### C. Imaging and pathology finding features

- Map finding flags, assessment, recommendation, location, procedure, surgery,
  and pathology code fields.
- Keep finding-level, side-level, and exam-level aggregates distinct.
- Check bounded coded domains against the legend.
- Flag outcome or post-event fields that should not be treated as
  contemporaneous predictors without a defined anchor.

### D. Reports and `combined_anon`

- Characterize report identifiers, sequencing, and text representation without
  opening report content.
- Use key-only comparisons to determine whether the wide table is a documented
  projection, a convenience join, or an unresolved derived representation.
- Prefer canonical level-specific definitions in the bundle unless V2 evidence
  establishes a different role for `combined_anon`.

### E. Synthesis and challenge review

- Review every claim against its evidence label.
- Challenge inferred units, date behavior, ordinal assumptions, and
  cross-table equivalence.
- Produce a prioritized maintainer-question register.
- Confirm that no row values or report text entered tracked files.

Independent work packages may run in parallel after the schema/legend
crosswalk fixes the shared feature vocabulary. Cross-table synthesis and final
coverage review remain centralized to prevent contradictory definitions.

## Planned bundle shape

Keep the deliverable small:

- `bundle/README.md` — standalone entry point, how to use the reference, evidence
  labels, and navigation.
- A small number of feature-reference documents grouped by conceptual level
  when a single document would be unwieldy.
- One concise unresolved-questions and caveats section, either in the entry
  point or the relevant feature document, rather than a hidden work log.

The final split will be based on the verified feature count and navigation
cost. Generated machine schemas, copied source rows, a database, and a runtime
retrieval layer are out of scope.

## Completion checks

The feature layer is complete for this investigation when:

- every physical table-column occurrence appears in a coverage check;
- every applicable legend code is represented or explicitly marked orphaned or
  unresolved;
- each agent-facing feature entry states its table/level, representation,
  meaning, missing/sentinel behavior, caveats, and evidence;
- similarly named fields at different levels are not conflated;
- `combined_anon` duplicates are either explained or clearly marked unresolved;
- all inference, conflict, and maintainer-input needs are visible;
- the bundle has one standalone entry point and contains no source rows or
  clinical text;
- project status and source/verification documentation are synchronized; and
- focused validation plus a final coverage review pass with no unexplained
  omissions.

