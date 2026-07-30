# EMBED clinical-semantic context

Ask useful questions about the Emory Breast Imaging Dataset (EMBED) before
turning table names into cohort logic.

EMBED is a breast-imaging research dataset from Emory Healthcare containing
screening and diagnostic mammography images, image metadata, and structured
clinical information. The HITI Lab's
[public EMBED documentation](https://docs.hitilab.com/datasets/embed) introduces
the dataset, its organization, access requirements, and supporting resources.
This project does not distribute the dataset or replace its official
documentation and data-use terms.

EMBED contains rich imaging, assessment, procedure, and pathology data, but its
physical layout alone cannot tell you what a row means, whether two records can
be attributed to each other, or which date is appropriate for a study. This
project provides a reviewed, machine-queryable guide to those meanings.

Use it to answer questions such as:

- What does missing pathology mean?
- Which breast-cancer outcome states are represented?
- Can pathology be attributed to a particular imaging finding?
- Which timestamps are event dates and which are documentation dates?
- How does a clinical concept map to an EMBED V2 table and column?

The catalog works without access to EMBED data. It contains no clinical rows,
counts, distributions, or executable cohort definitions.

## Install

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). Install
the CLI and optional MCP server directly from GitHub:

```bash
uv tool install \
  'embedv2-agent-context[mcp] @ git+https://github.com/beatrice-b-m/embedv2-agent-context.git'
```

This creates an isolated environment and installs two commands into uv's
executable directory:

- `embed-context` queries the catalog from a terminal or script.
- `embed-context-mcp` lets an AI client query the same catalog over stdio MCP.

If uv says its executable directory is not on `PATH`, run:

```bash
uv tool update-shell
```

Then start a new shell and verify the installation:

```bash
embed-context --version
embed-context validate
```

To install from a local clone instead, run `uv tool install '.[mcp]'` in the
repository root. Contributors should use the development environment described
in [CONTRIBUTING.md](CONTRIBUTING.md).

## Start with a clinical question

You do not need to know a table name or catalog identifier:

```bash
embed-context discover "What does absent pathology mean?" \
  --profile open-v2 --limit 5
```

Each match explains why it was returned and gives you a stable identifier.
Follow that identifier with the matching exact command:

```bash
embed-context guardrail guardrail.null-pathology-not-negative
```

The result explains that pathology which is not attached through the represented
field is not evidence of a negative diagnosis, benign disease, or complete
follow-up. It also links to related concepts and reviewed provenance.

Other useful starting points:

```bash
# Understand represented cancer outcomes and when they become known.
embed-context discover \
  "How is breast cancer represented and when is it known?" --limit 5

# Examine attribution between imaging findings and pathology.
embed-context discover \
  "pathology attribution to imaging findings" \
  --kind semantic_relationship --kind guardrail --limit 5

# Find candidate pathology timestamps.
embed-context discover \
  "Which timestamps could anchor pathology?" \
  --kind temporal_semantic --limit 5
```

Discovery can return clinical objects, features, relationships, time meanings,
aggregations, interpretation guardrails, coverage statements, and supporting
context. A no-result response means the catalog has no indexed answer under
the selected filters; it does not prove that a concept is absent from EMBED or
clinical reality.

## Move from meaning to implementation

Use portable clinical semantics first. Once you know which concepts your work
needs, inspect how the registered `open-v2` profile represents them:

```bash
embed-context feature pathology.severity --include-codes
embed-context object imaging_finding
embed-context profile-table open-v2 exam_level_anon
embed-context relationship-bindings \
  --profile open-v2 \
  --semantic-relationship clinical.finding-pathology-observation
```

Profile bindings describe tables, columns, physical associations, evidence,
and known join hazards. They are not executable joins and do not choose an
analysis policy for you.

Run `embed-context --help` to see all commands. The main navigation pattern is:

```text
clinical question
  -> discover
  -> exact semantic record
  -> related records and provenance
  -> profile binding, if implementation detail is needed
```

## Use structured output

Put `--format json` before the subcommand for a stable response envelope:

```bash
embed-context --format json discover \
  "What does absent pathology mean?" --limit 5
```

Successful responses have `ok: true`, the command name, and a `data` object.
Errors use the same envelope with `ok: false`, a structured error type, and a
message. This makes the CLI suitable for scripts and agent tooling as well as
interactive use.

## Connect an AI client

The optional `embed-context-mcp` command exposes the catalog as thirteen
read-only MCP tools. The client starts the command itself and communicates over
standard input/output; you do not run the server in a separate terminal.

Confirm that the command is visible in the environment where your client
starts:

```bash
command -v embed-context-mcp
embed-context-mcp --version
```

### Codex

```bash
codex mcp add embed_context -- embed-context-mcp
codex mcp list
```

Equivalent configuration:

```toml
[mcp_servers.embed_context]
command = "embed-context-mcp"
```

### Claude Code

```bash
claude mcp add --transport stdio --scope user \
  embed-context -- embed-context-mcp
claude mcp list
```

### OpenCode

Add this local server to `opencode.json` or `opencode.jsonc`:

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

If a desktop client does not inherit your shell `PATH`, `uv tool dir --bin`
prints uv's executable directory. Use the absolute path to
`embed-context-mcp` in that client's configuration.

Agents should begin with the MCP `discover` tool, follow returned identifiers
with exact semantic getters, review the returned `constraints`, and inspect
profile bindings only when they need release-specific implementation detail.
For longitudinal pathology questions, candidate search follows the patient's
timeline; the candidate pathology accession is not forced to equal the index
exam accession.

## Use the Python API

The dependency-free Python package exposes the same validated catalog:

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
```

A uv tool installation is intentionally isolated and does not add
`embed_context` to unrelated Python environments. Add the package as a normal
dependency when importing it from another project.

## What the catalog will not decide

This project supplies context for designing an analysis; it does not design
the analysis itself. In particular, it does not:

- choose a cohort, diagnosis date, outcome window, exclusion rule, censoring
  rule, or aggregation policy;
- turn physical associations into guaranteed clinical attribution;
- treat imaging assessment as pathology truth;
- treat absent pathology as a negative outcome; or
- claim complete outcome capture or scientific validity.

One important example is time. EMBED represents imaging exam dates, procedure
dates, and pathology report dates with different meanings. The registered
profile does not supply a supported specimen-collection time, and no candidate
is designated as a universal diagnosis date. A missing selected endpoint stays
missing: procedure and report dates must not be coalesced or fallback-substituted
for one another. Separately named endpoints or sensitivity analyses can compare
their implications. Downstream pathology can also leak future information into
an earlier prediction target.

Risk outputs may support association or ranking questions while their scale,
horizon, model version, exceptional values, or probability meaning remains
unresolved. Probability calibration and Brier-score interpretation require
those semantics to be validated first.

See the [clinical-semantic model](docs/clinical-semantic-model.md) for the
outcome, attribution, time, aggregation, and uncertainty details that should
inform study design.

## Terms and version axes

- A **clinical object** is an independently meaningful entity or observation.
- A **feature** is a portable meaning owned by one or more clinical objects.
- A **semantic relationship** describes clinical adjacency or attribution.
- A **profile binding** describes how a physical release represents a meaning.
- **Clinical instance identity** states how bound columns identify one
  represented object instance and where that identity stops.
- An **occurrence interpretation** qualifies the meaning of a value or null at
  one physical feature occurrence.
- A **binding path** composes ordered physical relationships that together
  implement one portable semantic relationship.
- A **guardrail** records a reusable interpretation constraint, not a policy.
- **Resolved constraints** summarize supported facts, unresolved claims,
  prohibited substitutions, required analyst choices, high-priority
  guardrails, and relevant contexts for an exact result.
- **Coverage** says what the catalog represents, not how complete the dataset
  is empirically.

The version numbers describe different things:

| Axis | Current value |
| --- | --- |
| Software package and commands | `0.7.0` |
| Serialized catalog schema | `6` |
| Registered EMBED V2 physical profile | `open-v2` |
| Optional MCP SDK dependency | `2.0.0` |

## Learn more

- [Documentation map](docs/README.md) — choose the shortest route for your role.
- [Clinical-semantic model](docs/clinical-semantic-model.md) — understand the
  clinical graph and interpretation limits.
- [Catalog format](docs/catalog-format.md) — integrate with the serialized
  model or Python, CLI, and MCP interfaces.
- [Architecture v6](docs/architecture-v6.md) — understand portable meaning,
  occurrence-aware bindings, composed paths, and query-time constraints.
- [Contributing](CONTRIBUTING.md) — set up a development environment and make
  catalog or code changes safely.

Questions and defects belong in
[GitHub Issues](https://github.com/beatrice-b-m/embedv2-agent-context/issues).
Citation metadata is provided in [`CITATION.cff`](CITATION.cff). Cite the
software version or commit SHA used, and cite EMBED separately according to the
dataset's documentation.

The repository currently declares no software license. Obtain the owner's
terms before reuse or redistribution.
