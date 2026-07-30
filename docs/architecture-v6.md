# Clinical-semantic architecture v6

## Decision

Schema version 6 keeps portable clinical semantics primary and adds structured
qualifications where a physical profile needs more precision: bounded clinical
instance identity, occurrence-specific value meaning, and ordered multi-edge
relationship paths. Query surfaces resolve applicable constraints and make
clinically important discovery intent explicit.

The catalog remains descriptive, count-free, and non-executable. It does not
contain SQL, dataframe operations, cohort predicates, preferred estimands, or
claims of scientific validity.

## Semantic and binding layers

The portable layer continues to contain clinical objects, concepts, semantic
relationships, temporal semantics, aggregations, guardrails, coverage,
vocabularies, sources, and reviewed contexts. These records define clinical
meaning independently of storage.

`profile_bindings` remains the secondary implementation layer. Version 6 adds:

- `instance_identity` on an object binding, with identifying columns, identity
  scope, reserved exceptions, rows per clinical instance, and an explicit
  longitudinal-identity flag;
- `occurrence_interpretations` on a feature binding, preserving
  representation-specific meaning and review status for a value or null; and
- `relationship_binding_paths`, which name one semantic relationship and the
  ordered physical relationship bindings that implement it.

A clinical instance identity is not a row key. An identity such as a finding
number may be scoped within an accession, may have several physical rows, and
may explicitly lack longitudinal persistence. An occurrence interpretation
does not redefine the portable concept globally. A relationship path is
descriptive navigation, not an executable join; its steps retain their own
cardinality, completeness, caveats, and hazards.

## Structured interpretation constraints

Every guardrail has a category and priority. Categories distinguish:

- `prohibition`: an invalid inference or substitution;
- `analyst_choice`: a decision the analysis must name; and
- `interpretation_limit`: a boundary on what the representation supports.

Priorities are `critical`, `high`, and `standard`. Priority affects salience,
not policy.

Exact semantic getters compute a top-level `constraints` section before
`related` and `provenance`. Its categories are:

- `supported_facts`;
- `unresolved_claims`;
- `unsupported_substitutions`;
- `analyst_choices_required`;
- `high_priority_guardrails`; and
- `relevant_contexts`.

Entries remain compact but retain stable identifiers and applicable status,
category, priority, and summary. The section is graph-derived; it is not a
second author-maintained policy layer. Reverse context links through related
concepts ensure that a feature lookup surfaces relevant reviewed claims.

## Deterministic discovery

`discover` remains the clinical-first entry point. Transparent token matching
is augmented by deterministic query intents for longitudinal search, temporal
fallback, probability calibration, identity, laterality, and represented
endpoints. Intent-based boosts appear in `match_reasons`.

Constraint-aware composition may reserve result slots for applicable
high-priority guardrails and unresolved coverage. Explicit kind filters are
always respected, ties remain deterministic, and an empty result never proves
clinical or dataset absence.

## Longitudinal and temporal safety

Longitudinal pathology candidate search operates across the patient timeline
even when output remains at exam-side or finding grain. The pathology accession
belongs to the candidate pathology-associated exam; it must not be forced equal
to the index exam accession.

Exam, procedure, specimen, pathology-report, and availability times answer
different questions. No date is a universal diagnosis date. Distinct time
semantics cannot be coalesced or fallback-substituted; missingness stays missing
for the selected endpoint. Another time can be used as a separately named
endpoint or sensitivity analysis.

## Risk and endpoint interpretation

Unresolved risk-output scale, horizon, model version, exceptional values, or
probability semantics do not prevent every association or ranking analysis.
They do preclude interpreting the output as a calibrated probability or using
probability-calibration and Brier-score metrics until those semantics are
validated.

An analysis may define “no represented event under this extraction policy.”
That endpoint is not evidence of “never biopsied,” “cancer-free,” or complete
follow-up. Pathology-conditioned estimands are not inherently invalid, but the
conditioning and generalizability boundary must be named. Same-day inclusion,
episode construction, tie-breaking, follow-up opportunity, observation proxies,
and cross-grain aggregation remain explicit analyst choices.

## Validation and delivery

JSON Schema validates closed version-6 shapes and local controlled values. The
dependency-free core additionally validates reference closure, occurrence
claims, instance-identity columns, same-profile path steps, and adjacent path
tables. Python, CLI, and MCP expose the same core query results; profile
bindings remain read-only implementation metadata.

The four independent version axes are:

- software `0.7.0`;
- catalog schema version `6`;
- physical profile `open-v2`; and
- optional MCP SDK `2.0.0`.

Schema v5's original portable-versus-physical separation is preserved in
[`architecture-v5.md`](architecture-v5.md) as historical design context.
