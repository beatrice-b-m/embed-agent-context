# EMBED clinical-semantic context

This repository provides a count-free, machine-queryable clinical-semantic
catalog for the Emory Breast Imaging Dataset (EMBED). It helps an unfamiliar
agent understand what clinical objects, events, features, timelines,
relationships, and uncertainty EMBED can represent before the agent chooses a
cohort or analysis design.

The portable model is independent of physical storage. Profile-specific tables,
columns, types, keys, and join tuples form a secondary implementation-binding
layer. The same clinical concepts can therefore describe EMBED loaded from
release tables, denormalized views, another database, or a future release.

The catalog is descriptive. It does not choose a diagnosis date, outcome
window, exclusion rule, cohort definition, or aggregation policy on an
analyst's behalf.

## Clinical-semantic model

Schema version 5 organizes breast-imaging context around this clinical
hierarchy:

```text
patient
  → breast-imaging episode
  → imaging exam
  → breast side and imaging finding
  → assessment / recommendation
  → linked procedure
  → pathology observation / diagnosis
```

The hierarchy is not a claim that every object has one row or one table. Each
semantic relationship records clinical meaning, direction, cardinality,
optionality, attribution limitations, temporal qualifications, evidence,
scope, and unresolved questions. Physical relationship bindings separately
describe how one profile approximates those relationships.

The portable semantic layer contains:

- `clinical_objects` for independently meaningful entities and observations;
- `concepts` for semantic features owned by clinical objects;
- `semantic_relationships` for storage-independent clinical adjacency and
  attribution;
- `temporal_semantics` for event, documentation, and availability meanings;
- `aggregations` for supplied rollups and explicitly unresolved transitions;
- `guardrails` for reusable interpretation constraints;
- `coverage` for supported, unsupported, unresolved, and uncataloged scope;
- vocabularies, contexts, claims, and sources for meanings and provenance.

`profile_bindings` contains the secondary implementation layer: feature
bindings, object/table representations, table specifications, and physical
relationship bindings.

See [the v5 architecture](docs/architecture-v5.md) and
[catalog format](docs/catalog-format.md) for the complete contract.

### Terms and version axes

- A **clinical object** is an independently meaningful entity or observation;
  its **clinical grain** says what one instance means.
- A **concept** is a portable feature meaning. The CLI and MCP call it a
  feature so queries read naturally.
- A **profile** is one physical representation of those meanings.
  `open-v2` is the profile ID for the registered open EMBED V2 layout; it is
  not a schema version.
- A **binding grain** describes one physical row. It need not equal a clinical
  object's grain.
- A **semantic relationship** describes clinical adjacency or attribution. A
  **relationship binding** describes a profile-specific physical association,
  not an executable join.
- A **context** contains reviewed claims and sources. A **guardrail** is a
  reusable interpretation constraint, not an executable policy.
- **Coverage** records what the catalog represents; it is not a measurement of
  empirical dataset completeness.

| Axis | Current value | Meaning |
| --- | --- | --- |
| Software | `0.6.0` | Python package, CLI, and MCP server release |
| Catalog contract | schema `5` | Serialized `catalog.json` format |
| Registered dataset layout | `open-v2` | Profile-specific physical bindings |
| MCP dependency | SDK `2.0.0` | Optional pinned protocol implementation |

## Start in two minutes

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and
Python 3.12 or 3.13. Clone the repository, then install the command-line
interface and optional Model Context Protocol (MCP) server as a persistent uv
tool:

```bash
git clone https://github.com/beatrice-b-m/embedv2-agent-context.git
cd embedv2-agent-context
uv tool install '.[mcp]'
```

The install creates an isolated environment and places `embed-context` and
`embed-context-mcp` in uv's executable directory. It does not need EMBED data
and remains usable if your working directory changes. Verify both executables:

```bash
command -v embed-context
command -v embed-context-mcp
embed-context validate
embed-context discover "What does absent pathology mean?" \
  --profile open-v2 --limit 5
```

If uv reports that its executable directory is not on `PATH`, run
`uv tool update-shell`, start a new shell, and try again. `uv tool dir --bin`
prints the directory when you need to inspect or add it manually. See uv's
[tool installation guide](https://docs.astral.sh/uv/guides/tools/) for the
underlying install and `PATH` behavior.

For repository development without a persistent tool install, replace
`embed-context` with `uv run --locked embed-context` after following
[Contributing](CONTRIBUTING.md).

## Breast-cancer outcome and time semantics

The initial outcome model distinguishes invasive breast cancer, in-situ breast
cancer, high-risk lesion, borderline lesion, benign finding, and non-breast
cancer. `unattached_pathology` is an attachment state, not a seventh diagnosis
code: it does not establish absence of disease, a benign diagnosis, complete
follow-up, or a negative outcome. The non-breast-cancer state is likewise not
benign, healthy, or absence of malignancy. Restricting to attached pathology
also conditions on a represented tissue-sampling procedure.

Supplied side- and exam-level pathology severity use the minimum numeric value
because the represented scale is inverse. The catalog does not invent a
finding-to-side, exam-to-patient, or patient-level outcome policy where one is
not supplied.

Candidate dates retain their distinct meanings:

- exam study date is an imaging-exam event time;
- procedure date is a procedure event time;
- specimen collection time is clinically meaningful but is not represented by
  a supported open-v2 feature;
- pathology report date is a documentation/report time.

None is designated a universal diagnosis date. Availability may lag event or
documentation time, and using downstream procedure or pathology information
for an earlier prediction target may cause temporal leakage.

## Discovery first

Start with a clinical question; table names and stable IDs are not required:

```bash
embed-context discover \
  "How is breast cancer represented and when is it known?" --limit 5
embed-context discover \
  "What does absent pathology mean?" --profile open-v2 --limit 5
embed-context discover \
  "pathology attribution to imaging findings" \
  --kind semantic_relationship --kind guardrail --domain pathology --limit 5
```

Discovery searches clinical objects, features, semantic relationships,
temporal semantics, aggregations, guardrails, coverage, and supporting context.
Each match reports its kind, identifier, score, label, matched fields, matched
terms, and unmatched query terms. Diagnostics distinguish:

- matches excluded by filters;
- unknown filter or vocabulary values;
- semantics explicitly unsupported in the selected profile;
- missing catalog coverage.

Missing catalog coverage means that the portable catalog has no indexed
assertion for the question. It does not prove that the clinical concept is
absent from EMBED or clinical reality.

Use exact getters to navigate a discovery result:

```bash
embed-context object imaging_finding
embed-context feature pathology.severity
embed-context feature pathology.severity --include-codes
embed-context semantic-relationship \
  clinical.finding-pathology-observation
embed-context temporal \
  time.pathology-report-documentation
embed-context aggregation \
  aggregation.pathology-severity-to-exam
embed-context guardrail \
  guardrail.null-pathology-not-negative
embed-context coverage \
  coverage.open-v2.specimen-time
embed-context context open-v2.pathology-procedure-context
embed-context code pathology.severity 0
```

For a first walkthrough, run the absent-pathology discovery query, note that
its highest-ranked match is the `guardrail.null-pathology-not-negative`
guardrail, then open that exact ID. The result explains why missing attachment
is not a negative diagnosis and exposes adjacent stable IDs plus provenance.
Open `open-v2.pathology-procedure-context` when you need the underlying
reviewed claims, source records, and profile scope. Discovery ranks candidates;
an exact getter supplies the contract you should reason from.

After selecting semantic concepts, inspect a release implementation through the
explicitly secondary binding commands:

```bash
embed-context profile-table open-v2 exam_level_anon
embed-context relationship-binding \
  open-v2.pathology_findings_anon.imaging_finding
embed-context relationship-bindings \
  --profile open-v2 \
  --semantic-relationship clinical.finding-pathology-observation
```

Physical relationship bindings are descriptive metadata, not executable joins.
Callers must honor their optionality, cardinality, evidence, caveats, and join
hazards. They can be filtered by profile, endpoint table, physical relationship
kind, or linked portable semantic relationship ID. Object bindings returned by
object discovery, exact object lookup, or `profile-table` include resolved
claim, context, and source provenance; exact relationship-binding lookup
resolves the same evidence layers.

Place `--format json` before the subcommand for a stable machine-readable
envelope:

```bash
embed-context --format json discover \
  "Which timestamps could anchor pathology?" \
  --kind temporal_semantic --limit 5
```

Successful responses use:

```json
{"ok": true, "command": "discover", "data": {}}
```

Errors—including invalid options and missing required arguments—use the same
envelope with `ok: false`, a structured error type, and a message. A usage
error has type `usage`; its `command` is `null` when no subcommand can be
identified. All errors exit with status 2. `validate` runs the strict core
validator, including cross-reference and clinical-semantic invariants, then
summarizes schema-v5 inventories and controlled facets.

## Python API

The dependency-free core exposes the same validated catalog operations:

```python
from embed_context import load_catalog

catalog = load_catalog()
matches = catalog.discover(
    "absent pathology",
    profile="open-v2",
    limit=5,
)
guardrail = catalog.get_guardrail(
    "guardrail.null-pathology-not-negative"
)
context = catalog.get_context(
    "open-v2.pathology-procedure-context"
)
```

Exact getter results consistently contain `kind`, `identifier`, the requested
entity, `related`, and `provenance`. Discovery results contain `matches`,
`diagnostics`, `count`, and `total`. `uv tool install` deliberately isolates
command-line tools; it does not add `embed_context` to arbitrary Python
environments. Contributors can import it through `uv run` in the checkout, and
another Python project can install the checkout as a normal local dependency.

## Stdio MCP server

The `uv tool install '.[mcp]'` command above puts the read-only stdio server on
`PATH` as `embed-context-mcp`. The client starts this command and communicates
with it over standard input/output; do not start it in a separate terminal.
The server writes only MCP protocol messages to stdout and sends startup errors
to stderr.

Before configuring a client, confirm that the executable is visible in the
same environment from which that client launches:

```bash
command -v embed-context-mcp
embed-context-mcp --version
```

If a desktop or GUI client does not inherit your updated shell `PATH`, run
`uv tool dir --bin` and replace `embed-context-mcp` in that client's
configuration with the absolute path to the executable in that directory.

### Codex

Codex stores user configuration in `~/.codex/config.toml`. A trusted project
can instead use `.codex/config.toml` in its repository. Add the user-scoped
server with the CLI:

```bash
codex mcp add embed_context -- embed-context-mcp
codex mcp list
codex mcp get embed_context --json
```

The equivalent TOML entry is:

```toml
[mcp_servers.embed_context]
command = "embed-context-mcp"
```

Restart an already-running Codex session after changing the configuration. In
the terminal UI, `/mcp` shows the connected server and tools. Codex CLI, the
Codex IDE extension, and the Codex app use the same configuration on the same
host. See the official [Codex MCP guide](https://learn.chatgpt.com/docs/extend/mcp)
and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

### Claude Code

Claude Code recommends its configuration command for private user scope:

```bash
claude mcp add --transport stdio --scope user \
  embed-context -- embed-context-mcp
claude mcp get embed-context
claude mcp list
```

User- and local-scoped entries are stored in `~/.claude.json`; use
`claude mcp add` rather than editing that application-state file by hand. For
a reviewable configuration shared by one repository, run:

```bash
claude mcp add --transport stdio --scope project \
  embed-context -- embed-context-mcp
```

That creates or updates `.mcp.json` at the repository root with this shape:

```json
{
  "mcpServers": {
    "embed-context": {
      "type": "stdio",
      "command": "embed-context-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

Restart Claude Code, approve a project-scoped server the first time it is
used, and run `/mcp` to inspect or reconnect it. If startup fails,
`claude --debug mcp` provides diagnostics. See Anthropic's official
[MCP configuration guide](https://code.claude.com/docs/en/mcp) and
[settings locations](https://code.claude.com/docs/en/settings#settings-files).

### OpenCode

OpenCode reads user configuration from
`~/.config/opencode/opencode.json` or `.jsonc`. Put a project configuration in
`opencode.json` or `opencode.jsonc` at the repository root:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "embed_context": {
      "type": "local",
      "command": ["embed-context-mcp"],
      "enabled": true
    }
  }
}
```

For local stdio servers, OpenCode puts the executable and all arguments in one
`command` array. Restart OpenCode after changing configuration, then verify the
connection:

```bash
opencode mcp list
```

See OpenCode's official
[configuration guide](https://opencode.ai/docs/config/),
[MCP server reference](https://opencode.ai/docs/mcp-servers/), and
[MCP CLI reference](https://opencode.ai/docs/cli/#mcp).

The server exposes thirteen read-only tools with closed input schemas and
structured JSON results:

1. `discover`
2. `get_clinical_object`
3. `get_feature`
4. `get_semantic_relationship`
5. `get_temporal_semantic`
6. `get_aggregation`
7. `get_guardrail`
8. `get_coverage`
9. `get_context`
10. `lookup_code`
11. `get_profile_table`
12. `get_relationship_binding`
13. `search_relationship_bindings`

Agents should begin with `discover`, follow exact semantic references, and use
the final three profile/binding operations only to implement chosen semantics
in a release. All tools are read-only, idempotent, and closed-world with
respect to catalog metadata. Input schemas reject undeclared arguments.
Outputs are structured JSON objects, while their MCP output schemas
intentionally remain generic so explanatory fields can evolve without
breaking clients.

## Repository layout

- [docs/README.md](docs/README.md) — role-based documentation index.
- [catalog/catalog.json](catalog/catalog.json) — canonical portable semantics,
  provenance, and profile bindings.
- [catalog/catalog.schema.json](catalog/catalog.schema.json) — versioned JSON
  Schema.
- `embed_context/` — dependency-free query core and CLI plus the optional MCP
  adapter.
- `tests/` — synthetic contracts, validation, discovery, interface, and
  source-profile checks.
- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, change workflow, and validation
  matrix.
- [docs/clinical-semantic-model.md](docs/clinical-semantic-model.md) —
  human-readable tour of the clinical graph and its limitations.
- [docs/architecture-v5.md](docs/architecture-v5.md) — semantic/binding layer
  decision and discovery contract.
- [docs/catalog-format.md](docs/catalog-format.md) — authoring and query
  contract.
- [docs/migration-v4-to-v5.md](docs/migration-v4-to-v5.md) — breaking-change
  guidance.
- [docs/project-scope.md](docs/project-scope.md) — boundaries and authoring
  requirements.
- [docs/manual-review-batches.md](docs/manual-review-batches.md) and
  [docs/open-v2-linkage-review.md](docs/open-v2-linkage-review.md) —
  historical evidence records behind reviewed claims.
- `reference_files/` — ignored, optional local EMBED V2 source artifacts used
  only for footer-level profile verification; never commit its contents.

Questions and defects belong in
[GitHub Issues](https://github.com/beatrice-b-m/embedv2-agent-context/issues).
Until a formal citation file is added, cite the
[repository](https://github.com/beatrice-b-m/embedv2-agent-context) together
with the commit SHA used. The repository currently declares no software
license; obtain the owner's terms before reuse or redistribution.

## Breaking migration from schema v4

Schema v5 is intentionally breaking. There is no automatic v4-to-v5 in-memory
conversion because physical metadata cannot reliably invent clinical objects,
attribution, time roles, coverage, or guardrails.

The CLI commands `search`, `get`, `table`, `relationship`, `relationships`,
`contexts`, `pattern`, and `patterns` are removed. Replace them with
`discover`, an exact semantic getter, and—when needed—an explicitly named
profile-binding command. The exact `context ID` command remains available with
a schema-v5 result envelope; context search moves to
`discover --kind context`.

The MCP tools `search_features`, `get_table`, `get_relationship`,
`search_relationships`, `search_contexts`,
`get_analysis_pattern`, and `search_analysis_patterns` are removed. Use the
thirteen tools listed above; `get_context` is the exact context lookup.

Task-specific analysis patterns are not migrated as cohort recipes. Their
supported clinical facts move into outcome, temporal, aggregation, coverage,
and guardrail semantics; generic modeling advice is removed. See
[the full v4-to-v5 migration guide](docs/migration-v4-to-v5.md).

## Explicit non-goals

The portable catalog does not:

- encode SQL, dataframe operations, executable predicates, or pipelines;
- select preferred cohort definitions, anchors, follow-up windows, outcomes,
  exclusions, or aggregation policies;
- claim that a cohort or analysis is scientifically valid;
- treat physical tables as the clinical conceptual model;
- anticipate every research workflow;
- include empirical row counts, distributions, prevalences, or completeness
  measurements;
- interpret imaging assessment as pathology truth or absent pathology as a
  negative diagnosis.

Agents and users remain responsible for constructing and defending their
analysis design.

## Verification

The clone-safe baseline needs no EMBED data or ignored local artifacts:

```bash
uv run --locked python -m unittest discover -v
uv run --locked --no-dev --extra mcp python -m unittest \
  tests.test_mcp_server -v
```

Maintainers who separately possess the ignored open-v2 reference artifacts may
also run:

```bash
uv run --locked python scripts/validate_source_profile.py
```

That optional verifier derives the expected physical manifest from the
selected profile and compares table names, columns, physical types, and schema
nullability. It reads Parquet footers only; it does not inspect rows, clinical
values, identifiers, dates, report text, counts, or statistics.
