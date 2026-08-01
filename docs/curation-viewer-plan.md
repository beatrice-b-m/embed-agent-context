# Local catalog curation viewer implementation plan

## Status

This document is the implementation plan for a temporary, maintainer-operated
web viewer and editor for the schema-v7 catalog set. It is a design and delivery
contract, not documentation for an already available command.

The viewer must remain a metadata-only tool. It must not inspect EMBED clinical
artifacts, connect to a database, execute cohort logic, or weaken any catalog
validation or authoring boundary.

## Goal

Provide a local web workbench that lets a maintainer:

- browse portable semantics, released-profile contributions, and project
  extensions without reading large JSON files directly;
- follow the typed connections among clinical objects, concepts,
  relationships, time meanings, aggregations, guardrails, coverage, evidence,
  vocabularies, and physical bindings;
- run the real deterministic discovery query and understand why each item was
  returned;
- curate one explicitly selected authored module through structured forms;
- validate a draft through the same schemas, parser, composer, and domain
  invariants used by the CLI and MCP server;
- compare baseline and draft query behavior before saving; and
- inspect the exact source diff and save atomically without hidden catalog
  transformations.

The initial implementation is a temporary local maintainer tool, not a hosted
multi-user application. It should be easy to launch when review is needed and
leave no daemon running after the session ends.

## Catalog boundaries the viewer must preserve

The UI must make the schema-v7 ownership boundary visible at all times:

```text
portable semantic catalog
  -> released dataset profile
    -> explicitly selected project extension
```

A concept definition belongs to the portable semantic catalog unless it is a
namespaced project concept. A released profile may qualify and bind a portable
concept, but it may not redefine that concept. An extension may add a project
concept or declare a typed revision without mutating the original contribution.

The viewer therefore has two representations of the loaded catalog:

- the **authored view**, which retains source documents, collection locations,
  list positions, stable IDs, and JSON pointers and is the only writable view;
- the **effective view**, which is an immutable `Catalog` returned by
  `load_catalog` and is used for browsing, exact queries, constraints,
  provenance, graph navigation, and discovery.

The effective view must never be serialized back into an authored module.
Origins, qualifications, revisions, and computed related records are query
results, not an overlay to merge into portable records.

## Scope

### Initial supported documents

The viewer supports schema-v7 documents only for editing:

- one semantic catalog;
- any independently loaded profile module; and
- any independently loaded extension module.

A legacy schema-v6 monolith may be opened in review-only mode while transition
support remains in `load_catalog`, but the viewer must refuse to edit or save
it. There is no conversion or migration behavior in the viewer.

### Initial editing scope

One source document is editable per browser session. All other loaded modules
remain read-only context. This avoids partial multi-file saves and makes every
draft validation and diff unambiguous.

The first editable record families are:

- semantic catalog clinical objects, concepts, semantic relationships,
  temporal semantics, aggregations, guardrails, coverage, vocabularies,
  sources, and contexts;
- profile sources, contexts, coverage, qualifications, vocabularies, feature
  bindings, object bindings, tables, relationship bindings, and relationship
  binding paths; and
- extension concepts, qualifications, lineage, sources, contexts, coverage,
  vocabularies, binding additions, and typed revisions.

Controlled-value registries and module identity fields are visible but not
editable in the first release. Changing those fields is schema or module
governance work and should continue through normal source review.

### Non-goals

The initial viewer will not provide:

- clinical data previews, values, rows, counts, statistics, or distributions;
- SQL, dataframe expressions, cohort definitions, labels, or analysis recipes;
- arbitrary filesystem browsing;
- arbitrary JSON Patch or free-form mutation of an effective result;
- automatic stable-ID renaming or reference rewrites;
- simultaneous editing of several source modules;
- collaborative editing, authentication accounts, remote hosting, or network
  access outside the loopback interface;
- git staging, commits, rebases, pushes, or conflict resolution;
- an MCP write tool; or
- automatic publication of an extension into a released profile.

## Launch contract

Add a `curate` subcommand to the existing CLI:

```text
embed-context
  [--catalog PATH]
  [--profile-file PATH ...]
  [--extension-file PATH ...]
  [--no-default-profiles]
  [--include-default-extensions]
  curate
  [--edit-module PATH]
  [--port PORT]
  [--no-open]
```

The existing composition options retain their current meanings. Additional
behavior is:

- without `--edit-module`, the session is read-only;
- `--edit-module` must resolve to exactly one loaded, filesystem-backed v7
  semantic, profile, or extension document;
- bundled installed resources are never writable; a maintainer must provide a
  source-tree or external module path explicitly;
- the default port is `0`, allowing the operating system to allocate an unused
  port;
- the server binds only to `127.0.0.1`; no CLI option permits another host;
- the default behavior opens the system browser after the server is listening;
  `--no-open` prints the local URL instead; and
- interrupting the command shuts down the HTTP server and discards unsaved
  drafts after an explicit terminal warning when possible.

Examples:

```bash
# Review the bundled default catalog set.
uv run --locked embed-context curate

# Curate a work-in-progress extension while retaining open-v2 as context.
uv run --locked embed-context \
  --extension-file project-configs/review.json \
  curate --edit-module project-configs/review.json

# Direct profile maintenance is explicit.
uv run --locked embed-context curate \
  --edit-module catalog/profiles/open-v2.json
```

Composition flags remain global and precede `curate`. Viewer-only flags follow
the subcommand. CLI tests must lock this syntax before release.

## User experience

### Page layout

Use a responsive three-pane workbench with a persistent query drawer:

1. **Navigator**: collection, profile, origin, lifecycle, domain, status, and
   text filters plus a virtualized or incrementally rendered record list.
2. **Record workspace**: summary, authored fields, effective qualifications,
   constraints, provenance, bindings, and edit form for the selected record.
3. **Connections**: a focused typed neighborhood and an accessible edge list.
4. **Query drawer**: discovery inputs, ranked results, diagnostics, match
   explanations, and baseline-versus-draft comparison.

Every record header shows:

- kind and stable ID;
- contribution class: portable, released profile, or project;
- owning document and module;
- target profile and lifecycle when applicable;
- read-only or editable state; and
- baseline, modified, new, or deleted draft status.

### Browsing

The navigator must support an empty text query. It is an inventory browser,
not a wrapper around `discover`. Sorting is deterministic by kind, label, and
stable ID. Physical aliases are searchable only within their profile, matching
the existing discovery policy.

Clicking a reference opens the target in place and adds the prior selection to
browser history. Broken references should normally be impossible in a valid
baseline; a draft broken reference is rendered as an error edge linked to its
validation diagnostic.

### Structured editing

Forms should be purpose-built from a small field-description layer informed by
the JSON Schemas. Do not attempt to render every schema construct through a
generic JSON Schema form library. The schemas provide shape, required fields,
closed values, and basic types, while the field-description layer provides:

- human labels and concise help;
- field order and sections;
- multiline versus single-line inputs;
- stable-ID and claim-reference pickers;
- controlled-value selectors;
- ordered versus set-like list behavior; and
- warnings for fields with clinical or ownership consequences.

Reference pickers list only compatible loaded targets. They must still permit
the user to type a new value so that a set of mutually dependent draft records
can be completed before full validation.

Stable IDs are immutable after a record is created in the first release.
Renaming is delete-and-create work performed outside the viewer because it may
require coordinated reference changes across modules.

Creation requires the destination collection and stable ID before displaying
the remaining fields. Extension-owned IDs must be checked against the full
extension namespace immediately. Deletion requires a confirmation showing all
known incoming references and remains blocked from saving until full
validation succeeds.

### Layered record presentation

Do not flatten profile or project content into the portable record form. A
portable concept page, for example, presents:

- **Portable meaning**: the authored semantic concept;
- **Profile interpretation**: applicable qualifications and coverage;
- **Physical representation**: feature bindings and selected vocabularies;
- **Project view**: lineage and active typed revisions;
- **Constraints**: graph-derived supported facts, unresolved claims,
  unsupported substitutions, analyst choices, and guardrails; and
- **Provenance**: resolved claims, contexts, and sources.

Only fields owned by the editable module receive edit controls.

## Connection graph

### Graph model

Use a canonical node key of `kind:id`. Physical nodes use explicit kinds such
as `table`, `feature_binding`, `object_binding`, `relationship_binding`, and
`relationship_binding_path`. The graph index records:

```text
node key, label, kind, origin, profile, lifecycle, editable, draft state
edge source, target, type, direction, source JSON pointer, draft state
```

Edges are derived, never separately authored by the UI. Initial edge types
include:

- concept ownership by clinical object;
- semantic relationship source and target;
- concept-to-time and concept-to-aggregation references;
- aggregation source concept, result concept, source object, and target object;
- guardrail links to objects, concepts, relationships, times, aggregations,
  and coverage;
- coverage subject links;
- context and claim provenance links;
- qualification subject links;
- feature binding concept, table, and vocabulary links;
- object binding object and table links;
- physical relationship endpoints and semantic relationship links;
- relationship path step links;
- feature lineage input, output, and binding links; and
- revision original and replacement links.

Every edge retains its source contribution and JSON pointer so that selecting
an edge can open the field that authored it.

### Rendering

The default graph is a deterministic one-hop neighborhood. The user may expand
individual nodes or request a second hop. Never render the entire catalog as a
single force-directed graph by default.

Implement the first renderer as bundled SVG and ordinary browser APIs. Group
nodes by layer and kind, use a deterministic breadth-first layout, and provide
pan, zoom, keyboard focus, and a text edge list. No CDN assets or remote fonts
are allowed. The edge list is the accessibility and high-density fallback when
the visual graph becomes crowded.

## Query lab

The query lab invokes `Catalog.discover` directly. Inputs are:

- clinical-language query;
- selected profile;
- zero or more discovery kinds;
- optional domain; and
- limit.

Results show rank, score, stable ID, kind, label, matched and unmatched terms,
every match reason, diagnostics, origin, qualifications, profile coverage,
active revisions, and implementation bindings. Clicking a result opens its
record without losing the query.

When a valid draft exists, run the same request against both baseline and draft
catalogs. Compare results by `(kind, identifier)` and report:

- added or removed result;
- rank movement;
- score change;
- changed match reasons;
- changed diagnostics;
- changed profile coverage, qualifications, or active revisions; and
- changed implementation-binding inventory.

The comparison must not describe a query as simulated against synthetic
clinical data. It is a deterministic catalog-query preview and accesses no
clinical rows.

If the draft is invalid, preserve the last valid draft query result, label it
with the draft revision that produced it, and disable new draft queries until
validation succeeds.

## Internal architecture

### Components

```text
browser assets
  -> loopback HTTP API
    -> curator session
      -> authored document store and source index
      -> baseline Catalog
      -> in-memory draft document
      -> last valid draft Catalog
      -> graph and query-diff adapters
```

Keep this implementation private to a new `embed_context.curator` package. Do
not add viewer-only mutation methods to `Catalog`.

Recommended files:

```text
embed_context/
  curator/
    __init__.py
    server.py          loopback server, routing, headers, lifecycle
    session.py         baseline/draft state, validation, diff, save
    documents.py       raw document loading, source locations, serialization
    graph.py           node and edge derivation
    query_diff.py      baseline/draft discovery comparison
    forms.py           field-description metadata
    static/
      index.html
      app.js
      styles.css
tests/
  test_curator_documents.py
  test_curator_graph.py
  test_curator_session.py
  test_curator_server.py
  test_curator_cli.py
```

Use the Python standard library `ThreadingHTTPServer` and bundled vanilla
HTML, CSS, and JavaScript for the first release. This adds no core or optional
runtime dependency and requires no frontend compilation step. Static assets
must be packaged into the wheel and covered by packaging tests.

### Session state

`CuratorSession` owns:

- immutable composition arguments;
- raw baseline documents;
- baseline source digests;
- baseline effective catalog and fingerprint;
- optional editable document path and kind;
- monotonically increasing draft revision;
- in-memory draft mapping;
- validation diagnostics;
- last valid draft catalog and fingerprint; and
- last saved source digest.

Only one server process and one active browser editing session are supported.
Every mutation request includes the expected draft revision. A mismatch returns
HTTP `409` and the current revision so two tabs cannot silently overwrite each
other.

### Source index

The authored-document loader builds an explicit index rather than inferring a
write location from effective output. Each entry contains:

```text
contribution key
document path and document kind
module ID and target profile
collection name
stable ID
JSON pointer or ID-addressed array location
editable flag
```

Map-like registries use their object key as the stable ID even when the record
also contains an `id` field. Binding and revision arrays are addressed by their
authored `id`, never retained array position; the current position is resolved
again immediately before mutation.

## HTTP API

Use one JSON response envelope:

```json
{"ok": true, "data": {}}
```

Errors use:

```json
{
  "ok": false,
  "error": {
    "type": "validation_error",
    "message": "Draft validation failed.",
    "details": []
  }
}
```

Initial endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/session` | Composition, fingerprints, editability, revision, dirty and validation state |
| `GET` | `/api/records` | Deterministic inventory with filters and pagination cursor |
| `GET` | `/api/records/{kind}/{id}` | Authored and effective layered record |
| `GET` | `/api/graph/{kind}/{id}` | Typed neighborhood with depth one or two |
| `POST` | `/api/discover` | Run baseline and, when valid, draft discovery |
| `POST` | `/api/draft/records` | Create an editable-module record |
| `PUT` | `/api/draft/records/{kind}/{id}` | Replace the authored draft record after revision check |
| `DELETE` | `/api/draft/records/{kind}/{id}` | Delete an authored draft record after revision check |
| `POST` | `/api/draft/validate` | Recompose and validate the current draft |
| `GET` | `/api/draft/diff` | Unified source diff plus structured changed-record inventory |
| `POST` | `/api/draft/reset` | Reset draft to the current saved baseline |
| `POST` | `/api/draft/save` | Validate, check source digest, and atomically replace the editable file |
| `POST` | `/api/shutdown` | Stop the local server after dirty-state confirmation |

The API is private to the bundled browser application. It is not a new stable
remote integration contract and must not be advertised as an alternative to
the Python, CLI query, or MCP interfaces.

## Draft validation and diagnostics

Every form mutation performs inexpensive local checks for types, required
fields, controlled values, ID syntax, duplicate list entries, and editable
ownership. Full validation is debounced and always runs explicitly before a
draft query or save.

Full validation must:

1. serialize the draft document to a temporary file outside the repository;
2. reconstruct the original composition with that temporary file substituted
   for the editable module;
3. call `load_catalog` with the same profile, extension, and default-selection
   arguments;
4. retain the resulting `Catalog` only on success; and
5. return normalized diagnostics without exposing unrelated file contents.

Diagnostics use a common shape:

```text
stage: local | json_decode | json_schema | composition | domain
document
JSON pointer when available
contribution key when resolvable
message
```

Do not duplicate catalog invariants in the viewer. Local form checks improve
feedback, but `load_catalog` remains authoritative.

## Diff and save semantics

The baseline authored bytes and SHA-256 digest are retained when the session
starts and after every successful save. The source diff is generated from
canonical UTF-8 JSON with two-space indentation and a trailing newline, which
matches the checked-in catalog format.

Saving follows this sequence:

1. require a valid current draft revision;
2. read the editable source again and compare its digest with the last known
   digest;
3. return `409 source_changed` if another process modified it;
4. write canonical JSON to a sibling temporary file with the original mode;
5. flush and `fsync` the file;
6. atomically replace the exact editable path with `os.replace`;
7. `fsync` the containing directory where supported;
8. reload the saved composition from its real path;
9. update baseline bytes, digest, catalog, fingerprint, and draft state; and
10. retain the pre-save bytes in memory for a session-level restore action.

The viewer never writes any other path, creates migration artifacts, or saves
an effective catalog. It does not automatically run git commands. The diff
panel reminds repository maintainers to review and commit through the normal
workflow.

## Local-server security

Even a temporary loopback editor needs a narrow security boundary:

- bind only to `127.0.0.1` and reject unexpected `Host` headers;
- generate a cryptographically random session token;
- require the token on every `/api/` request and every state-changing request;
- verify `Origin` on state-changing requests;
- send no permissive CORS headers;
- serve no remote scripts, styles, fonts, images, or source maps;
- set a restrictive Content Security Policy and `Cache-Control: no-store`;
- reject request bodies above a small documented limit;
- accept JSON only for mutation endpoints;
- allow writes only to the single resolved `--edit-module` path;
- never follow a changed symlink when saving;
- HTML-escape authored content and use DOM text nodes rather than `innerHTML`;
  and
- avoid logging request bodies, catalog records, tokens, or full source files.

The server should print the bound address, read-only/editable module state, and
shutdown instructions, but no catalog contents.

## Implementation phases

Each phase is a separate coherent commit with synchronized documentation and
tests.

### Phase 1: read-only session and inventory

Implement the `curator` package, source-document index, effective inventory,
loopback server, packaged static shell, `curate` CLI command, and read-only
record pages.

Acceptance criteria:

- the default catalog opens without clinical artifacts;
- all effective record families can be browsed and filtered;
- record pages show origins and source ownership correctly;
- no API route can mutate state without `--edit-module`;
- legacy v6 opens only as explicitly labeled read-only content;
- server security headers and token checks pass HTTP contract tests; and
- installed-wheel launch finds all static and catalog resources.

### Phase 2: connection graph and query lab

Add typed graph derivation, focused SVG navigation, the accessible edge list,
exact-result panels, and discovery query execution.

Acceptance criteria:

- graph edges resolve to the same stable IDs as exact getter navigation;
- profile and project edges retain origin and applicability;
- graph order and discovery results are deterministic;
- all match reasons and diagnostics are visible; and
- no graph or query code accesses clinical artifacts.

### Phase 3: extension draft editing

Add structured forms, draft revisions, create/update/delete operations, full
temporary composition, validation diagnostics, query comparison, source diff,
stale-source detection, and atomic save for extension modules.

Acceptance criteria:

- representative extension concepts, qualifications, bindings, lineage, and
  revisions can be curated without raw JSON editing;
- invalid namespace, reference, dependency, and revision changes cannot save;
- baseline and draft discovery differences are explained;
- two browser tabs cannot silently overwrite draft state;
- external source changes prevent save; and
- a successfully saved extension reloads to the same configuration
  fingerprint shown by the viewer.

### Phase 4: semantic and profile maintainer editing

Enable the same draft workflow for filesystem-backed semantic and profile
modules. Add stronger warnings for portable meaning and released-profile
evidence changes.

Acceptance criteria:

- only the owning layer is editable;
- a profile cannot redefine portable semantics through the UI;
- claim and source references remain scoped correctly;
- direct semantic/profile edits pass standalone schema and full composition
  validation before save; and
- the UI explicitly distinguishes project experimentation from changes to the
  released Open V2 representation.

## Test and validation plan

All fixtures must remain synthetic and count-free.

### Unit tests

- document discriminator, module identity, and editable-path resolution;
- contribution-to-JSON-pointer indexing for maps and ID-addressed arrays;
- graph nodes and every supported edge type;
- deterministic inventory filtering and pagination;
- local form validation and compatible reference choices;
- baseline/draft discovery comparison;
- draft revision conflicts and last-valid-draft behavior;
- JSON serialization stability and source diff;
- stale digest, symlink, path allowlist, and atomic replacement behavior; and
- token, Host, Origin, content type, body limit, and security headers.

### Interface and acceptance tests

- CLI help, launch arguments, startup errors, exit status, and read-only
  defaults;
- JSON API success and error envelopes;
- full `load_catalog` validation for semantic, profile, and extension drafts;
- installed-wheel static-resource and command checks;
- browser smoke test for navigation, editing, validation, query comparison,
  reset, and save; and
- regression tests proving existing CLI and MCP query results are unchanged.

Run the repository clone-safe baseline after every phase:

```bash
uv run --locked python -m unittest discover -v
uv run --locked embed-context validate
uv run --locked --no-dev --extra mcp python -m unittest \
  tests.test_mcp_server -v
```

Packaging changes additionally require the documented wheel inspection and
installed-tool checks from `CONTRIBUTING.md`.

## Documentation changes required with implementation

The implementation is not complete until these remain synchronized:

- `README.md`: installation, launch examples, local-only warning, and curation
  workflow;
- `docs/README.md`: viewer navigation entry;
- this plan: mark delivered phases and record intentional deviations;
- `docs/catalog-format.md`: clarify that authored modules, not effective
  results, are edited and validated;
- `docs/architecture-v7.md`: add the optional local authoring adapter without
  changing catalog-set composition;
- `CONTRIBUTING.md`: viewer validation matrix and maintainer save/review flow;
- CLI help and tests; and
- packaging configuration and tests for browser assets.

No MCP write tool should be added. MCP remains a read-only query surface.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Flattened effective output is saved as authored content | Maintain separate raw-document and effective-catalog models; only raw draft documents serialize |
| A profile edit silently changes portable meaning | Layer-specific forms and write ownership; profiles can edit only profile-owned contributions |
| Generic forms imply schema validation is sufficient | Treat local checks as advisory and require full `load_catalog` composition before query or save |
| Large graph becomes unreadable | Default to deterministic one-hop neighborhoods, expandable nodes, filters, and an edge list |
| Query changes are hard to notice | Baseline/draft rank, score, reason, diagnostic, coverage, revision, and binding comparison |
| Concurrent editor or external tool overwrites work | Draft revision checks plus source-byte digest comparison before atomic save |
| Installed package resources are modified | Require an explicit filesystem-backed edit module and reject bundled resources |
| Local web page is reached by hostile browser content | Loopback bind, Host and Origin validation, session token, no CORS, strict CSP, and no remote assets |
| Viewer grows into a second catalog implementation | Reuse `load_catalog`, `Catalog` getters, and `discover`; keep viewer adapters private |
| Temporary tooling becomes an undocumented production service | No remote host option, no accounts, no persistent daemon, and explicit local-maintainer positioning |

## Completion definition

The viewer goal is complete when a maintainer can launch the installed or
source-tree command, browse the composed schema-v7 catalog, understand a
selected record's layered connections, edit one explicit authored module,
validate the draft through the canonical loader, compare actual discovery
behavior before and after the edit, inspect the exact JSON diff, save atomically,
and rerun the normal repository validation without accessing clinical data.
