# Maintainer clarification batches

## Purpose

This is the human-review queue for catalog questions that cannot be settled by
schema validation, source-profile comparison, catalog consistency checks, or
query tests. It is intentionally not a full catalog walkthrough.

Baseline: commit `dfe297e` (`fix(context): incorporate maintainer
clarifications`). At this baseline the catalog has 116 concepts, 243 bindings,
49 vocabularies, 8 tables, 18 relationships, 8 sources, 9 contexts, and 38
context claims. The complete test suite passes.

For each question, a short answer, a pointer to the authoritative person or
artifact, or “leave unresolved” is sufficient. “Leave unresolved” is a valid
decision and preserves the current guardrail.

## Excluded from human review

The following checks are mechanical and should not consume maintainer review
time:

- table, column, physical-type, and schema-nullability manifests;
- JSON shape, controlled values, reference closure, and duplicate detection;
- key and relationship compatibility checks that follow from declared schema;
- exact lookup, search, CLI, and MCP behavior;
- vocabulary transcription against an available legend; and
- empirical referential coverage or uniqueness checks that can be run locally
  without publishing counts.

Those checks should be automated or handled by the implementation reviewer.
They should reach the maintainer only if automation exposes a genuine semantic
choice.

## Batch 1 — Risk outputs

**Why maintainer input is needed:** Physical types and observed values cannot
establish model identity, scale, or sentinel meanings. Incorrect assumptions
could produce invalid clinical labels or risk comparisons.

Related catalog items:

- `risk.nci_five_year`, `risk.nci_lifetime`
- `risk.ibis_ten_year`, `risk.ibis_lifetime`
- `risk.ibis_brca1`, `risk.ibis_brca2`
- `risk.ibis_population_ten_year`, `risk.ibis_population_lifetime`
- `risk.ibis_td1` through `risk.ibis_td4`
- context claim `open-v2.risk-context/risk-semantics`

Questions:

1. Are the ordinary NCI and IBIS values fractions, percentage points, or
   another representation?
2. What do exceptional values `-35`, `-2`, and `100` mean? If the meaning is
   model-specific, which fields use which interpretation?
3. Which NCI and IBIS model versions generated these fields?
4. What do `IBISPOP10`, `IBISPOPL`, and `IBIS_TD1` through `IBIS_TD4`
   represent?

If the answers live with another team, naming the owner or source artifact is
enough for this batch.

## Batch 2 — Derived counts and pathology-severity rollups

**Why maintainer input is needed:** The schema identifies the fields but not
their aggregation algorithms. Row-level inspection can suggest formulas but
cannot establish intended meaning.

Related catalog items:

- exam-level and side-level mass, calcification, asymmetry, and architectural
  distortion aggregates;
- `exam.left_finding_total` and `exam.right_finding_total`; and
- `exam.pathology_severity_aggregate` and
  `breast_side.pathology_severity_aggregate`.

Questions:

1. Are the imaging aggregate fields counts of findings, Boolean summaries,
   source-system values, or another calculation?
2. What records and modalities contribute to each exam-level versus side-level
   aggregate?
3. How are `left_finding_total` and `right_finding_total` calculated, and why
   are they repeated on side-level rows?
4. When multiple procedure-associated pathology records exist, how is the
   exam-level or side-level pathology-severity value selected or combined?

## Batch 3 — Flags, ordinals, measurements, and sentinels

**Why maintainer input is needed:** Numeric storage does not distinguish a
clinical measurement from a source-system sentinel or establish flag
encoding.

Related catalog items:

- `imaging.addendum_flag`, `imaging.new_flag`, and `imaging.stable_flag`;
- mammography mass, calcification, asymmetry, and architectural-distortion
  presence flags;
- `imaging.finding_number`, `imaging.distance`, and `imaging.finding_size`;
- `mammography.calcification_number`; and
- `pathology.biopsy_distance`.

Questions:

1. What are the encodings and null meanings for each flag family? A single
   general rule is preferable if they share one.
2. What do zero and negative values mean for finding number, distance, size,
   calcification number, and biopsy distance?
3. What are the units for distance and size fields?
4. Is finding number an ordinal within accession/side, an opaque source
   identifier, or conditionally either?

## Batch 4 — MRI fields without an exact legend contract

**Why maintainer input is needed:** Similar names and observed values are not
enough to establish semantic equivalence.

Related catalog items:

- `mri.delayed_kinetics_secondary`
- `mri.other_finding`
- `mri.size`
- MRI fields whose legend association currently relies on a case-only header
  match

Questions:

1. Is the secondary delayed-kinetics field semantically equivalent to the
   primary delayed-kinetics field? If not, what distinguishes it?
2. What does the MRI other-finding field represent, and does it use an existing
   released vocabulary?
3. What does the MRI size field measure, and in what units?
4. Is case-insensitive header matching an intended general rule for the MRI
   legend, or should the current matches remain explicitly inferred?

## Batch 5 — Demographic and administrative semantics

**Why maintainer input is needed:** Names alone do not establish provenance,
units, anonymization behavior, or the distinction between clinical and
administrative categories.

Related catalog items:

- `demographics.age_at_exam`, `demographics.age_at_menarche`,
  `demographics.age_at_menopause`, and `demographics.age_at_pregnancy`;
- `demographics.ashkenazi_indicator` and
  `demographics.gender_description`;
- `exam.release_version`, `exam.location`, and `exam.accession_identifier`.

Questions:

1. Are all age fields measured in years? What do zero and other sentinel-like
   age values mean?
2. How is age at exam anonymized, if at all?
3. What is the source and intended interpretation of the Ashkenazi indicator?
4. Does gender description represent administrative sex, gender identity,
   another source-system category, or a mixture?
5. Does the released version field represent source membership, processing
   lineage, schema version, or something else?
6. Are the current `loc_num` and accession legend associations intentional
   despite the physical header differences?

## Batch 6 — Side, report revision, and composed-code behavior

**Why maintainer input is needed:** These questions concern source-system
workflow and representation conventions rather than schema structure.

Related catalog items:

- `breast.side`;
- `report.sequence` and `imaging.addendum_flag`;
- vocabularies marked `comma_composed_undocumented`; and
- context claim `open-v2.report-context/addendum-link`.

Questions:

1. What does a null side mean, and how should a bilateral row relate to left
   and right rows?
2. Does report sequence greater than the accession minimum always identify an
   addended report version?
3. What, if any, is the exact relationship between report sequence and the
   imaging addendum flag?
4. For comma-containing coded fields, is comma always a delimiter? Are order,
   repetition, or combinations meaningful?
5. Is there a general null convention for coded fields, or must null semantics
   remain field-specific and unresolved?

## Batch 7 — Mapping-owner routing

**Why this is routing rather than a code-list review:** The catalog already
preserves unknown source-system codes and forbids guessed mappings. Reviewing
hundreds of codes manually would be a poor use of maintainer time.

Related unresolved claims:

- `open-v2.assessment-recommendation-context/recommendation-code-mappings`
- `open-v2.pathology-procedure-context/pathology-code-mappings`

Questions:

1. Who owns the authoritative mapping for recommendation codes absent from the
   released legend?
2. Who owns the authoritative mapping for pathology descriptor codes absent
   from the released legend?
3. Is there an export, versioned dictionary, or MagView configuration artifact
   that can replace person-by-person clarification?

Until an owner or artifact is identified, both claims should remain unresolved
and the raw codes should remain uninterpreted.

## Suggested review order

For the highest value per unit of maintainer time:

1. Risk outputs
2. Derived counts and pathology-severity rollups
3. Flags, measurements, and sentinels
4. Mapping-owner routing
5. Side and report-revision behavior
6. MRI semantics
7. Demographic and administrative semantics

The batches are independent. They do not need to be completed in one session,
and unanswered questions do not block retention of the current safe caveats.
