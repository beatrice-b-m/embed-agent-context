# Local catalog curation viewer implementation plan

## Status

Delivered on the `codex/curation-viewer` implementation branch. This document
now records the design, acceptance contract, and intentional implementation
boundaries for the temporary maintainer-operated schema-v7 viewer and editor.

Phases 0 through 4 are implemented. The initial connection renderer remains an
accessible typed edge list and grouped neighborhood; no SVG renderer was added
because it was not required for the delivered workbench. Frontend automation
is limited to DOM-independent state-helper and static-shell contracts, with the
HTTP API covered separately; manual browser acceptance remains the DOM-level
check described below.

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
- curate one explicitly selected authored module through a lossless hybrid
  record editor;
- validate a draft through the same schemas, parser, composer, and domain
  invariants used by the CLI and MCP server;
- compare baseline and draft query behavior before saving; and
- inspect the exact bytes that will be written, including any canonical-format
  changes, and save them atomically without serializing the effective catalog.

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

The viewer also depends on a shared **resolved composition** produced by the
canonical loader. It retains the validated authored documents, resolved
locators, source bytes, schemas, module identities, and effective `Catalog`.
The CLI, MCP server, and curator must not implement separate catalog-set
resolution rules.

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

The viewer must be able to preserve and edit every schema-valid field in these
record families:

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

Editing uses a hybrid record editor. Frequently curated fields receive
schema-derived controls and targeted usability metadata; uncommon or deeply
nested shapes remain editable as record-scoped JSON. This is not a free-form
editor for an effective result: the JSON always represents exactly one
authored record in the selected module. No record family may become lossy merely
because a custom form has not been implemented for all of its fields.

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
- `--no-open` suppresses browser launch;
- the local URL is printed even when the browser is opened;
- `--format json` is rejected for `curate`, because it is a long-running
  interactive command rather than a result-envelope command; and
- interrupting the command shuts down the HTTP server, reports whether an
  unsaved draft was discarded, and exits without prompting on standard input.

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

`curate` has a distinct CLI lifecycle. After argument parsing, it resolves the
authored composition, starts the server, optionally opens the browser, blocks
until shutdown, and maps startup or runtime failures to an exit status. It is
dispatched before the ordinary load-command-format path used by finite query
commands. Tests receive an injected browser opener and server lifecycle so they
never block or launch a real application.

## User experience

### Page layout

Use a responsive three-pane workbench with a persistent query drawer:

1. **Navigator**: collection, profile, origin, lifecycle, domain, status, and
   text filters plus an incrementally rendered record list.
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

Forms use a schema-driven field layer plus a record-scoped JSON fallback. The
schemas remain authoritative for shape, required fields, closed values, basic
types, and conditional alternatives. A small field-description layer adds only
maintainer-facing presentation that the schemas do not express:

- human labels and concise help;
- field order and sections;
- multiline versus single-line inputs;
- stable-ID and claim-reference pickers;
- controlled-value selectors;
- ordered versus set-like list behavior; and
- warnings for fields with clinical or ownership consequences.

The field layer must not duplicate schema requiredness or conditional logic.
Parity tests verify that every editable record family can round-trip fields
that lack a custom control. Enhanced forms should initially target concepts,
contexts and claims, qualifications, feature bindings, and revisions; later
families are added only where the enhancement is materially better than the
record JSON editor.

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

An incomplete create or edit form is a browser-local buffer and is not yet a
server draft mutation. The browser submits a create or replacement only after
the record passes local shape checks. The server draft may still fail
cross-reference, composition, or domain validation; those failures are retained
as draft diagnostics. This prevents incomplete skeletal records from creating
ambiguous server state. Saving an applied server draft preserves unapplied
buffers for other records. Reset explicitly discards both server-draft and
browser-local changes, and shutdown requires confirmation when either layer has
unsaved work.

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

The first renderer is an accessible typed edge list plus grouped one-hop cards
for incoming and outgoing connections. The user may expand an individual node
or request a second hop. Never render the entire catalog as a single graph by
default.

The graph index is part of the initial implementation because it also powers
reference navigation, broken-reference diagnostics, and deletion-impact
checks. A bundled SVG visualization is a later enhancement, added only if the
grouped connection UI proves insufficient. If added, it must use deterministic
layout, ordinary browser APIs, keyboard focus, and the edge list as its
accessible and high-density representation. No CDN assets or remote fonts are
allowed.

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

If the current draft is invalid, baseline queries remain available. The UI
reports that draft comparison is unavailable and identifies the last valid
draft revision, if one exists. It may run the current query against that
last-valid catalog only when the result is labeled with that revision; it does
not preserve or present a stale result from a different query.

## Internal architecture

### Components

```text
browser assets
  -> loopback HTTP API
    -> curator session
      -> shared resolved composition
      -> authored document snapshots and source index
      -> baseline Catalog
      -> in-memory draft document
      -> last valid draft Catalog
      -> graph and query-diff adapters
```

Keep this implementation private to a new `embed_context.curator` package. Do
not add viewer-only mutation methods to `Catalog`.

Before the curator package is implemented, refactor the canonical loader to
produce a private resolved-composition value containing:

```text
resolved document kind and locator kind
resolved source path when filesystem-backed
original source bytes and source digest
validated authored mapping and schema identity
module ID, version, lifecycle, target profile, and dependency order
effective Catalog and configuration fingerprint
```

`load_catalog` becomes a thin wrapper that returns the resolved composition's
`Catalog`. The existing CLI and MCP behavior must remain unchanged. Draft
validation substitutes one in-memory authored mapping into an immutable
resolved composition and calls the same schema, composition, and domain
validators. The curator must not reconstruct manifests, duplicate locator
resolution, or add viewer-only loading rules.

Recommended files:

```text
embed_context/
  catalog.py            shared resolver and structured validation diagnostics
  curator/
    __init__.py
    server.py          loopback server, routing, headers, lifecycle
    session.py         baseline/draft state, validation, diff, save
    documents.py       authored source index, addressing, and serialization
    graph.py           node and edge derivation
    query_diff.py      baseline/draft discovery comparison
    forms.py           presentation metadata over schema-derived fields
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

The initial automated frontend contract is exercised through HTTP API tests
and tests of extracted, DOM-independent JavaScript state helpers. End-to-end
browser automation is not claimed without declaring a dev-only browser test
dependency. A documented manual browser acceptance pass covers the small DOM
shell until such a dependency is intentionally added.

### Session state

`CuratorSession` owns:

- immutable composition arguments;
- immutable raw baseline document snapshots;
- baseline source digests;
- baseline effective catalog and fingerprint;
- optional editable document path and kind;
- monotonically increasing draft revision;
- in-memory draft mapping;
- validation diagnostics;
- last valid draft catalog and fingerprint; and
- last saved source digest.

Only one server process and one shared editing session are supported. Multiple
tabs may view it, but they do not receive independent drafts. Every mutation
request includes the expected draft revision. A mismatch returns HTTP `409`
and the current revision so two tabs cannot silently overwrite each other.

`CuratorSession` protects all mutable state with a lock. Revision comparison
and mutation, validation-result installation, reset, save, and baseline updates
are atomic session operations. Full validation is synchronous initially. If
background validation is added later, every result is tagged with its input
revision and discarded when that revision is no longer current.

Draft composition uses the immutable session snapshots for every non-editable
document, so a baseline-versus-draft comparison cannot absorb unrelated disk
changes. Before save, all filesystem-backed loaded documents are digest-checked.
If any context document changed, the session reports `composition_changed` and
requires reload; if the editable document changed, it reports `source_changed`.

### Source index

The authored-document loader builds an explicit index rather than inferring a
write location from effective output. Each entry contains:

```text
contribution key
document path and document kind
locator kind: bundled or explicit file
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
| `GET` | `/api/records` | Deterministic inventory with filters and a documented result limit |
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
| `POST` | `/api/shutdown` | Stop the local server after an explicit dirty-state acknowledgement |

The API is private to the bundled browser application. It is not a new stable
remote integration contract and must not be advertised as an alternative to
the Python, CLI query, or MCP interfaces.

The initial catalog does not justify cursor pagination or list virtualization.
The inventory endpoint returns a deterministically sorted, bounded result and
reports the total matching metadata records. Pagination is added only if
measured response size or rendering cost requires it.

## Draft validation and diagnostics

Before submission, the browser performs inexpensive checks for types, required
fields, controlled values, ID syntax, duplicate list entries, and editable
ownership. The server repeats security- and ownership-relevant checks. Full
validation is synchronous and runs explicitly after each accepted record
mutation and again before a draft query or save.

Full validation must:

1. canonicalize the in-memory draft mapping to the exact prospective save
   bytes;
2. validate it with the version-matched schema selected by the shared resolver;
3. substitute the validated mapping into the immutable resolved composition;
4. call the same composition and domain validators used by `load_catalog`;
5. retain the resulting `Catalog` only when the validated revision is still
   current; and
6. return normalized diagnostics without exposing unrelated file contents.

Diagnostics use a common shape:

```text
stage: local | json_decode | json_schema | composition | domain
document when resolvable
JSON pointer when available
contribution key when resolvable
message
```

Do not duplicate catalog invariants in the viewer. Local form checks improve
feedback, but the shared resolver used by `load_catalog` remains authoritative.

Structured diagnostics are a core-loader responsibility, not parsed exception
strings in the curator. Catalog load and validation exceptions gain optional
stage, document, JSON pointer, and contribution-key fields while preserving the
existing human-readable messages and CLI/MCP error envelopes. JSON decoding is
normally relevant only during initial source loading or external-change reload,
because draft mutations carry parsed JSON values.

## Diff and save semantics

The baseline authored bytes and SHA-256 digest are retained when the session
starts and after every successful save. The draft is serialized as UTF-8 JSON
with two-space indentation and a trailing newline, which matches the checked-in
catalog format. The displayed unified diff compares the original source bytes
with the exact prospective save bytes. If an external module is not already in
canonical form, the UI explicitly identifies formatting-only changes outside
the changed-record inventory; it never describes them as authored record
changes.

Saving follows this sequence:

1. require a valid current draft revision whose validated bytes exactly match
   the prospective save bytes;
2. digest-check every filesystem-backed document in the resolved composition;
3. return `409 source_changed` for an editable-source change or
   `409 composition_changed` for another loaded-source change;
4. reject an editable path that is or has become a symlink;
5. write the already validated prospective bytes to a sibling temporary file
   with the original mode;
6. flush and `fsync` the file;
7. recheck all source digests, then atomically replace the exact editable path
   with `os.replace`;
8. `fsync` the containing directory where supported;
9. reload the saved composition from its real path as a consistency assertion;
   and
10. update baseline bytes, digest, catalog, fingerprint, and draft state.

A successful save rebases the revision associated with browser-local record
buffers but does not clear them. Those buffers have not been submitted to the
server and are therefore neither included in the prospective bytes nor made
safe by saving a different applied record.

Validation occurs against exactly the bytes written. A failure after
`os.replace` is therefore reported as `saved_reload_failed`, not as an unsaved
draft; the file has already been atomically replaced and the message directs
the maintainer to run the normal validator. The first release has no
session-level restore operation. Source control and the displayed pre-save diff
remain the recovery mechanism.

The viewer never writes any other path, creates migration artifacts, or saves
an effective catalog. It does not automatically run git commands. The diff
panel reminds repository maintainers to review and commit through the normal
workflow.

## Local-browser containment

The viewer is not an authenticated service. Its security boundary prevents an
unrelated web origin from driving the maintainer's loopback editor; it does not
attempt to defend against malware or another process running as the same local
user. No session token, login, or authorization subsystem is used.

The server must:

- bind only to `127.0.0.1` and accept only the exact bound-address `Host`
  values required by the bundled page;
- require the exact server `Origin` on every state-changing request;
- require `application/json` for state-changing requests and reject unsupported
  methods, transfer encodings, and CORS preflights;
- send no permissive CORS headers;
- serve no remote scripts, styles, fonts, images, or source maps;
- set a restrictive Content Security Policy and `Cache-Control: no-store`;
- reject request bodies above a small documented limit;
- allow writes only to the single resolved `--edit-module` path;
- never follow a changed symlink when saving;
- HTML-escape authored content and use DOM text nodes rather than `innerHTML`;
  and
- avoid logging request bodies, catalog records, or full source files.

The server should print the bound address, read-only/editable module state, and
shutdown instructions, but no catalog contents.

Because the API is browser-private, automated tests send the same exact
`Origin` header as the bundled page. Mutation requests without `Origin` are not
supported as a secondary command-line API.

## Implementation phases

Each phase is a separate coherent commit with synchronized documentation and
tests.

### Phase 0: resolved composition and structured diagnostics — delivered

Refactor catalog-set loading so one canonical resolver returns immutable
authored document snapshots and the effective `Catalog`. Add structured fields
to validation diagnostics without changing existing CLI, Python, or MCP query
behavior.

Acceptance criteria:

- `load_catalog` delegates to the resolver and returns the same catalogs,
  fingerprints, errors, and deterministic query results as before;
- bundled, manifest-file, explicit profile, and explicit extension origins and
  source bytes are retained without changing locator policy;
- an in-memory replacement can be validated and composed without a temporary
  manifest or duplicate default modules;
- domain and schema errors expose structured location fields where known while
  retaining existing human-readable messages; and
- focused loader, composition, CLI, MCP, and fingerprint regressions pass.

### Phase 1: read-only session, inventory, and query inspector — delivered

Implement the `curator` package, source-document index, effective inventory,
loopback server, packaged static shell, distinct `curate` CLI lifecycle,
read-only layered record pages, typed connection lists, and baseline discovery.

Acceptance criteria:

- the default catalog opens without clinical artifacts;
- all effective record families can be browsed and filtered;
- record pages show origins and source ownership correctly;
- no API route can mutate state without `--edit-module`;
- legacy v6 opens only as explicitly labeled read-only content;
- discovery results and match explanations agree with direct `Catalog.discover`;
- server headers, Host, Origin, content-type, method, and body-limit checks pass
  HTTP contract tests without an authentication token; and
- installed-wheel launch finds all static and catalog resources.

### Phase 2: extension draft editing — delivered

Add the hybrid record editor, browser-local incomplete form buffers, draft
revisions, create/update/delete operations, synchronous snapshot-based
validation, exact prospective-byte diff, stale-composition detection, and
atomic save for extension modules.

Acceptance criteria:

- every extension record family and schema-valid field round-trips through an
  enhanced control or the record-scoped JSON fallback;
- representative concepts, qualifications, feature bindings, contexts/claims,
  and revisions have enhanced controls;
- invalid namespace, reference, dependency, and revision changes cannot save;
- two browser tabs cannot silently overwrite draft state;
- incomplete browser-local forms do not mutate the server draft;
- saving applied changes preserves unapplied buffers for other records;
- shutdown acknowledges both server-draft and browser-local unsaved work;
- changes to the editable source or any loaded filesystem context prevent save;
- the displayed diff is byte-for-byte the content that will be written; and
- a successfully saved extension reloads to the same configuration
  fingerprint shown by the viewer.

### Phase 3: draft query comparison and graph enhancements — delivered

Add baseline-versus-current-valid-draft discovery comparison, the complete
typed graph index, incoming-reference and deletion-impact navigation, and
grouped second-hop exploration. Add SVG visualization only if review of the
connection UI demonstrates a material need.

Acceptance criteria:

- graph edges resolve to the same stable IDs as exact getter navigation;
- profile and project edges retain origin, applicability, and authored pointer;
- graph ordering and query comparison are deterministic;
- rank, score, reasons, diagnostics, coverage, qualifications, revisions, and
  binding-inventory changes are explained;
- an invalid draft never presents a stale result as current; and
- no graph or query code accesses clinical artifacts.

### Phase 4: semantic and profile maintainer editing — delivered

Enable the same draft workflow for filesystem-backed semantic and profile
modules. Add stronger warnings for portable meaning and released-profile
evidence changes. Add enhanced forms for additional families only where they
improve on the lossless record JSON editor.

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

- resolved locator and authored-document snapshots for every composition path;
- equivalence between `load_catalog` and the shared resolver;
- in-memory module substitution without manifest or default-module duplication;
- structured diagnostic fields and compatibility of rendered error messages;
- document discriminator, module identity, and editable-path resolution;
- contribution-to-JSON-pointer indexing for maps and ID-addressed arrays;
- graph nodes and every supported edge type;
- deterministic inventory filtering and result limiting;
- schema-derived field coverage, JSON fallback round-trips, local form
  validation, and compatible reference choices;
- incomplete browser-local form behavior, including save and shutdown
  interactions, in extracted JavaScript state helpers;
- baseline/draft discovery comparison;
- draft revision conflicts and last-valid-draft behavior;
- session locking and rejection of stale validation results;
- JSON serialization stability and source diff;
- editable and context-source digest conflicts, symlink rejection, path
  allowlist, and atomic replacement behavior; and
- Host, Origin, CORS preflight, method, transfer encoding, content type, body
  limit, and security headers.

### Interface and acceptance tests

- CLI help, launch arguments, startup errors, exit status, and read-only
  defaults;
- JSON API success and error envelopes;
- full `load_catalog` validation for semantic, profile, and extension drafts;
- installed-wheel static-resource and command checks;
- documented manual browser acceptance for navigation, editing, validation,
  query comparison, reset, and save, unless a dev-only browser-test dependency
  is intentionally added; and
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
| Curator duplicates or drifts from catalog-set loading | Resolve documents, validate, substitute drafts, and compose through one shared core resolver |
| Baseline/draft comparison absorbs an unrelated file edit | Compose drafts from immutable session snapshots and digest-check every filesystem document before save |
| A profile edit silently changes portable meaning | Layer-specific forms and write ownership; profiles can edit only profile-owned contributions |
| Custom forms become a second, lossy schema | Derive shape from schemas, keep presentation metadata narrow, provide a lossless record JSON fallback, and test round-trips |
| Generic controls imply schema validation is sufficient | Treat local checks as advisory and require full shared-resolver composition before query or save |
| Large graph becomes unreadable | Begin with deterministic grouped one-hop connections and an edge list; add SVG only after demonstrated need |
| Query changes are hard to notice | Baseline/draft rank, score, reason, diagnostic, coverage, revision, and binding comparison |
| Concurrent editor or external tool overwrites work | Draft revision checks plus source-byte digest comparison before atomic save |
| Installed package resources are modified | Require an explicit filesystem-backed edit module and reject installed package-data resources |
| Unrelated browser content drives the local editor | Loopback bind, exact Host and Origin validation, JSON-only mutations, no CORS, strict CSP, and no remote assets; local-process attacks are out of scope |
| Viewer grows into a second catalog implementation | Reuse `load_catalog`, `Catalog` getters, and `discover`; keep viewer adapters private |
| Temporary tooling becomes an undocumented production service | No remote host option, no accounts, no persistent daemon, and explicit local-maintainer positioning |

## Completion definition

The viewer goal is complete when a maintainer can launch the installed or
source-tree command, browse the composed schema-v7 catalog, understand a
selected record's layered connections, edit one explicit authored module
without losing schema-valid fields, validate the draft through the shared
canonical resolver against immutable context snapshots, compare actual
discovery behavior before and after the edit, inspect the exact prospective
save bytes, save atomically, and rerun the normal repository validation without
accessing clinical data.
