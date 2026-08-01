/* DOM-independent state helpers are exported for focused contract tests. */
export function createDraftBuffer(revision = 0) {
  return { revision, records: Object.create(null), dirty: false };
}

export function bufferRecord(buffer, key, value) {
  const records = Object.assign(Object.create(null), buffer.records, { [key]: structuredClone(value) });
  return { revision: buffer.revision, records, dirty: true };
}

export function discardBufferedRecord(buffer, key) {
  const records = Object.assign(Object.create(null), buffer.records);
  delete records[key];
  return { revision: buffer.revision, records, dirty: Object.keys(records).length > 0 };
}

export function bufferedRecordValue(buffer, key, fallback) {
  return Object.hasOwn(buffer.records, key) ? structuredClone(buffer.records[key]) : structuredClone(fallback);
}

export function recordBufferKey(identity) {
  return `${identity.kind}:${identity.id}`;
}

export function rebaseDraftBuffer(buffer, revision) {
  const records = Object.assign(Object.create(null), buffer.records);
  return { revision, records, dirty: Object.keys(records).length > 0 };
}

export function hasUnsavedWork(session, buffer) {
  return Boolean(session?.dirty || buffer?.dirty);
}

export const CREATE_FORM_BUFFER_KEY = "$create-record";

export function updateCreateFormBuffer(buffer, values) {
  const snapshot = {
    kind: values.kind,
    identifier: values.identifier,
    recordJson: values.recordJson,
  };
  const isEmpty = snapshot.kind === "" && snapshot.identifier === "" && snapshot.recordJson === "{}";
  return isEmpty
    ? discardBufferedRecord(buffer, CREATE_FORM_BUFFER_KEY)
    : bufferRecord(buffer, CREATE_FORM_BUFFER_KEY, snapshot);
}

export function trackCreateFormChanges(controls, onChange) {
  const update = () => onChange({
    kind: controls.kind.value,
    identifier: controls.identifier.value,
    recordJson: controls.recordJson.value,
  });
  for (const control of Object.values(controls)) control.addEventListener("input", update);
}

export function mergeRecordValues(original, replacement) {
  return Object.assign({}, structuredClone(original), structuredClone(replacement));
}

export function localShapeChecks(spec, record) {
  const errors = [];
  if (!record || Array.isArray(record) || typeof record !== "object") {
    return [{ pointer: "/", message: "Record must be a JSON object." }];
  }
  for (const field of spec?.fields || []) {
    const value = record[field.name];
    if (field.required && value === undefined) {
      errors.push({ pointer: `/${field.name}`, message: "Required field is missing." });
      continue;
    }
    if (value === undefined) continue;
    if (field.enum?.length && !field.enum.includes(value)) {
      errors.push({ pointer: `/${field.name}`, message: "Value is not in the controlled registry." });
    }
    if (field.type === "array" && !Array.isArray(value)) {
      errors.push({ pointer: `/${field.name}`, message: "Value must be an array." });
    }
    if (field.list_behavior === "set" && Array.isArray(value)) {
      const encoded = value.map((item) => JSON.stringify(item));
      if (new Set(encoded).size !== encoded.length) {
        errors.push({ pointer: `/${field.name}`, message: "Duplicate list entries are not allowed." });
      }
    }
  }
  return errors;
}

export function parseKinds(value) {
  return [...new Set(String(value || "").split(",").map((item) => item.trim()).filter(Boolean))];
}

export function encodeEnhancedValue(field, value) {
  if (field?.type === "array") return JSON.stringify(value ?? [], null, 2);
  if (field?.type === "object") return JSON.stringify(value ?? {}, null, 2);
  return value ?? "";
}

export function decodeEnhancedValue(field, raw, checked = false) {
  if (field?.control === "checkbox") return checked;
  if (field?.control === "number") return Number(raw);
  if (field?.type === "array" || field?.type === "object") {
    const value = JSON.parse(raw);
    if (field.type === "array" && !Array.isArray(value)) throw new TypeError("Value must be an array.");
    if (field.type === "object" && (!value || Array.isArray(value) || typeof value !== "object")) throw new TypeError("Value must be an object.");
    return value;
  }
  return raw;
}

export function applyEnhancedValues(record, controls) {
  const replacement = structuredClone(record);
  for (const { field, raw, checked } of controls) {
    replacement[field.name] = decodeEnhancedValue(field, raw, checked);
  }
  return replacement;
}

export function nextRenderBatch(records, rendered, size = 50) {
  return records.slice(rendered, rendered + size);
}

export function recordOwnershipFacts(data, identity) {
  const source = data?.source || {};
  const origin = data?.origin || {};
  return [
    ["Stable ID", identity.id], ["Kind", identity.kind],
    ["Contribution class", origin.contribution_class],
    ["Owning document", source.document],
    ["Document kind", source.document_kind || origin.document_kind],
    ["Module", source.module_id || origin.module_id],
    ["Target profile", source.target_profile || origin.target_profile],
    ["Lifecycle", origin.lifecycle_status],
    ["Access", data?.editable ? "Editable" : "Read only"],
    ["Draft status", data?.draft_state],
  ];
}

const state = {
  session: null,
  selection: null,
  record: null,
  formSpec: null,
  graph: null,
  graphDepth: 1,
  buffer: createDraftBuffer(),
  enhancedControls: [],
  navigatorRecords: [],
  navigatorRendered: 0,
};

const byId = (id) => document.getElementById(id);

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function element(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(options)) {
    if (name === "className") node.className = value;
    else if (name === "text") node.textContent = value;
    else node.setAttribute(name, value);
  }
  for (const child of children) node.append(child);
  return node;
}

function showNotice(id, message, kind = "error") {
  const node = byId(id);
  node.textContent = message;
  node.className = `notice ${kind}`;
  node.hidden = !message;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers, body: options.body === undefined ? undefined : JSON.stringify(options.body) });
  let payload;
  try { payload = await response.json(); }
  catch { throw new Error(`The curator returned a non-JSON response (${response.status}).`); }
  if (!response.ok || !payload?.ok) {
    const error = new Error(payload?.error?.message || `Request failed (${response.status}).`);
    error.details = payload?.error?.details || [];
    error.type = payload?.error?.type;
    throw error;
  }
  return payload.data;
}

function renderSession() {
  const cluster = byId("session-state");
  clear(cluster);
  const session = state.session || {};
  cluster.append(
    element("span", { className: `badge ${session.valid === false ? "invalid" : "valid"}`, text: session.valid === false ? "Invalid draft" : "Validated" }),
    element("span", { className: "badge", text: session.editable ? "Editable module" : "Read only" }),
    element("span", { className: "badge", text: session.dirty ? `Draft r${session.revision}` : "Baseline" }),
    ...(state.buffer.dirty ? [element("span", { className: "badge", text: "Unapplied local edits" })] : []),
  );
  byId("save-draft").disabled = !session.editable || !session.dirty || session.valid === false;
  byId("validate-draft").disabled = !session.editable;
  byId("reset-draft").disabled = !session.editable || !hasUnsavedWork(session, state.buffer);
  byId("new-record").disabled = !session.editable;
}

async function loadSession() {
  state.session = await api("/api/session");
  state.buffer = createDraftBuffer(state.session.revision || 0);
  renderSession();
}

function recordIdentity(item) {
  return { kind: item.kind, id: item.id || item.identifier };
}

async function loadRecords(params = new URLSearchParams()) {
  if (!params.has("limit")) params.set("limit", "1000");
  const data = await api(`/api/records?${params.toString()}`);
  const records = data.records || data.items || [];
  byId("record-total").textContent = String(data.total ?? records.length);
  const list = byId("record-list");
  clear(list);
  const kinds = new Set();
  for (const item of records) {
    kinds.add(recordIdentity(item).kind);
  }
  state.navigatorRecords = records;
  state.navigatorRendered = 0;
  renderNavigatorBatch();
  const select = byId("filter-kind");
  if (select.options.length === 1) {
    for (const kind of [...kinds].sort()) select.append(element("option", { value: kind, text: kind }));
  }
}

function renderNavigatorBatch() {
  const list = byId("record-list");
  const batch = nextRenderBatch(
    state.navigatorRecords,
    state.navigatorRendered,
  );
  for (const item of batch) {
    const identity = recordIdentity(item);
    const button = element("button", { type: "button" }, [
      element("span", { className: "record-label", text: item.label || identity.id }),
      element("span", { className: "record-meta", text: `${identity.kind} · ${identity.id}` }),
    ]);
    button.addEventListener("click", () => selectRecord(identity.kind, identity.id));
    list.append(element("li", {}, [button]));
  }
  state.navigatorRendered += batch.length;
  const remaining = state.navigatorRecords.length - state.navigatorRendered;
  const more = byId("load-more-records");
  more.hidden = remaining <= 0;
  more.textContent = remaining > 0
    ? `Show ${Math.min(50, remaining)} more records (${remaining} remaining)`
    : "Show more records";
}

function jsonText(value) {
  return value === undefined ? "Not provided" : JSON.stringify(value, null, 2);
}

function editableAuthored(data) {
  return data.authored || data.record || data.contribution || null;
}

function bufferCurrentEditor() {
  if (!state.selection) return;
  state.buffer = bufferRecord(
    state.buffer,
    recordBufferKey(state.selection),
    byId("record-editor").value,
  );
  renderSession();
}

function renderRecord(data) {
  const identity = state.selection;
  const authored = editableAuthored(data);
  byId("record-kind").textContent = identity.kind;
  byId("record-title").textContent = data.label || authored?.label || identity.id;
  byId("record-state").textContent = `${data.editable ? "editable" : "read only"} · ${data.draft_state || "baseline"}`;
  byId("authored-record").textContent = jsonText(authored);
  byId("layered-record").textContent = jsonText(data.effective || data.layers || data);
  const summary = byId("record-summary");
  clear(summary);
  const facts = recordOwnershipFacts(data, identity);
  for (const [term, description] of facts) {
    if (description === undefined || description === null) continue;
    summary.append(element("div", {}, [element("dt", { text: term }), element("dd", { text: String(description) })]));
  }
  const canEdit = Boolean(data.editable && state.session?.editable && authored);
  byId("editor-section").hidden = !canEdit;
  if (canEdit) {
    const buffered = bufferedRecordValue(
      state.buffer,
      recordBufferKey(identity),
      jsonText(authored),
    );
    byId("record-editor").value = buffered;
    let enhancedRecord = authored;
    try {
      const parsed = JSON.parse(buffered);
      if (parsed && !Array.isArray(parsed) && typeof parsed === "object") enhancedRecord = parsed;
    } catch { /* Preserve invalid JSON text while rendering controls from the server draft. */ }
    renderEnhancedFields(state.formSpec, enhancedRecord);
  }
}

function renderEnhancedFields(spec, authored) {
  const container = byId("enhanced-fields"); clear(container);
  state.enhancedControls = [];
  if (!spec?.enhanced) return;
  for (const field of spec.fields || []) {
    if (field.control === "json" || field.immutable) continue;
    let input;
    if (field.type === "array" || field.type === "object") {
      input = element("textarea", { rows: "5", spellcheck: "false" });
    } else if (field.control === "select") {
      input = element("select");
      for (const value of field.enum || []) input.append(element("option", { value, text: value }));
    } else if (field.control === "textarea") input = element("textarea");
    else input = element("input", { type: field.control === "number" ? "number" : field.control === "checkbox" ? "checkbox" : "text" });
    if (field.control === "checkbox") input.checked = Boolean(authored[field.name]);
    else input.value = encodeEnhancedValue(field, authored[field.name]);

    const updateRecord = () => {
      input.dataset.enhancedDirty = "true";
      let record;
      try { record = JSON.parse(byId("record-editor").value); } catch { return; }
      try { record[field.name] = decodeEnhancedValue(field, input.value, input.checked); }
      catch (error) {
        renderDiagnostics([{ pointer: `/${field.name}`, message: error.message }]);
        return;
      }
      renderDiagnostics([]);
      byId("record-editor").value = jsonText(record);
      bufferCurrentEditor();
    };
    input.addEventListener("input", updateRecord);
    input.addEventListener("change", updateRecord);
    state.enhancedControls.push({ field, input });
    const label = element("label", {}, [element("span", { text: field.label }), input]);
    const help = field.warning || field.help;
    if (help) label.append(element("small", { text: help }));
    const wrapper = element("div", { className: "enhanced-field" }, [label]);
    if (field.control === "reference" && field.choices?.length) {
      const choices = element("div", { className: "reference-choices" });
      for (const choice of field.choices) {
        const button = element("button", { type: "button", text: choice.label || choice.id, title: `${choice.kind}: ${choice.id}` });
        button.addEventListener("click", () => {
          if (field.type === "array") {
            let values;
            try { values = decodeEnhancedValue(field, input.value); } catch { values = []; }
            if (!values.includes(choice.id)) values.push(choice.id);
            input.value = encodeEnhancedValue(field, values);
          } else if (field.type === "object" && field.schema?.properties?.kind && field.schema?.properties?.id) {
            input.value = encodeEnhancedValue(field, { kind: choice.kind, id: choice.id });
          } else if (field.type !== "object") input.value = choice.id;
          updateRecord();
        });
        choices.append(button);
      }
      wrapper.append(choices);
    }
    container.append(wrapper);
  }
}

async function selectRecord(kind, id, options = {}) {
  if (options.depth === undefined && options.history !== "none") state.graphDepth = 1;
  const depth = options.depth || state.graphDepth;
  state.selection = { kind, id };
  state.formSpec = null;
  showNotice("record-notice", "", "info");
  try {
    const path = `/api/records/${encodeURIComponent(kind)}/${encodeURIComponent(id)}`;
    const [record, graph] = await Promise.all([api(path), api(`/api/graph/${encodeURIComponent(kind)}/${encodeURIComponent(id)}?depth=${depth}`)]);
    state.record = record;
    state.graph = graph;
    state.formSpec = record.form || record.form_spec || null;
    renderRecord(record);
    renderConnections(graph);
    const depthButton = byId("graph-depth");
    depthButton.disabled = false;
    depthButton.textContent = depth === 2 ? "Show one hop" : "Show second hop";
    if (options.history !== "none") history.pushState({ kind, id }, "", `#${encodeURIComponent(kind)}:${encodeURIComponent(id)}`);
  } catch (error) { showNotice("record-notice", error.message); }
}

function renderConnections(graph) {
  const container = byId("connection-groups");
  clear(container);
  byId("connection-help").hidden = true;
  for (const direction of ["outgoing", "incoming"]) {
    const selected = graph[direction] || [];
    const section = element("section", { className: "edge-group" }, [element("h3", { text: `${direction[0].toUpperCase()}${direction.slice(1)} (${selected.length})` })]);
    const list = element("ul", { className: "edge-list" });
    for (const edge of selected) {
      const target = direction === "incoming" ? edge.source : edge.target;
      const key = typeof target === "string" ? target : target?.key;
      const [kind, ...idParts] = String(key || "unknown:").split(":");
      const id = idParts.join(":");
      const button = element("button", { type: "button", text: edge.label || id || key });
      if (kind && id) button.addEventListener("click", () => selectRecord(kind, id));
      list.append(element("li", {}, [element("span", { className: "edge-type", text: edge.type || "reference" }), button]));
    }
    section.append(list);
    container.append(section);
  }
  if (graph.depth === 2) {
    const direct = new Set([graph.focus]);
    for (const edge of [...(graph.incoming || []), ...(graph.outgoing || [])]) {
      direct.add(edge.source); direct.add(edge.target);
    }
    const nodes = (graph.nodes || []).filter((node) => !direct.has(node.key));
    const section = element("section", { className: "edge-group" }, [element("h3", { text: `Second-hop neighborhood (${nodes.length})` })]);
    const list = element("ul", { className: "edge-list" });
    for (const node of nodes) {
      const button = element("button", { type: "button", text: node.label || node.identifier });
      button.addEventListener("click", () => selectRecord(node.kind, node.identifier));
      list.append(element("li", {}, [element("span", { className: "edge-type", text: node.kind }), button]));
    }
    section.append(list); container.append(section);
  }
}

function renderDiagnostics(errors) {
  const list = byId("editor-errors");
  clear(list);
  for (const error of errors) list.append(element("li", { text: `${error.pointer || "/"}: ${error.message}` }));
}

async function applyRecord() {
  let replacement;
  try { replacement = JSON.parse(byId("record-editor").value); }
  catch (error) { renderDiagnostics([{ pointer: "/", message: error.message }]); return; }
  try {
    replacement = applyEnhancedValues(
      replacement,
      state.enhancedControls
        .filter(({ input }) => input.dataset.enhancedDirty === "true")
        .map(({ field, input }) => ({
          field,
          raw: input.value,
          checked: input.checked,
        })),
    );
    byId("record-editor").value = jsonText(replacement);
  } catch (error) {
    renderDiagnostics([{ pointer: "/", message: error.message }]);
    return;
  }
  const checks = localShapeChecks(state.formSpec, replacement);
  renderDiagnostics(checks);
  if (checks.length) return;
  const { kind, id } = state.selection;
  try {
    const data = await api(`/api/draft/records/${encodeURIComponent(kind)}/${encodeURIComponent(id)}`, {
      method: "PUT", body: { revision: state.session.revision, record: replacement },
    });
    state.session = { ...state.session, ...data, dirty: true };
    state.buffer = discardBufferedRecord(
      { ...state.buffer, revision: state.session.revision },
      recordBufferKey({ kind, id }),
    );
    renderSession();
    await selectRecord(kind, id, { history: "none" });
  } catch (error) { renderDiagnostics(error.details?.length ? error.details : [{ pointer: "/", message: error.message }]); }
}

async function deleteRecord() {
  const { kind, id } = state.selection || {};
  if (!kind || !id || !state.record?.editable) return;
  const incoming = state.graph?.incoming || [];
  const impact = incoming.length ? ` ${incoming.length} incoming reference(s) are currently known.` : " No incoming references are currently known.";
  if (!window.confirm(`Delete ${kind}:${id}?${impact} Saving remains blocked until full validation succeeds.`)) return;
  try {
    const data = await api(`/api/draft/records/${encodeURIComponent(kind)}/${encodeURIComponent(id)}`, {
      method: "DELETE", body: { revision: state.session.revision, confirm: true },
    });
    state.session = { ...state.session, ...data, dirty: true };
    state.buffer = discardBufferedRecord(state.buffer, recordBufferKey({ kind, id }));
    renderSession(); await loadRecords();
    showNotice("record-notice", data.valid ? "Record deleted from the draft." : "Record deleted; resolve validation diagnostics before saving.", "info");
  } catch (error) { showData("Delete record", { message: error.message, details: error.details }); }
}

function renderDiagnosticsAt(id, errors) {
  const list = byId(id); clear(list);
  for (const error of errors) list.append(element("li", { text: `${error.pointer || error.json_pointer || "/"}: ${error.message}` }));
}

function resetCreateForm() {
  byId("create-form").reset();
  renderDiagnosticsAt("create-errors", []);
  state.buffer = discardBufferedRecord(state.buffer, CREATE_FORM_BUFFER_KEY);
}

async function createRecord(event) {
  event.preventDefault();
  let record;
  try { record = JSON.parse(byId("create-json").value); }
  catch (error) { renderDiagnosticsAt("create-errors", [{ pointer: "/", message: error.message }]); return; }
  const kind = byId("create-kind").value.trim();
  const id = byId("create-id").value.trim();
  try {
    const spec = await api(`/api/forms/${encodeURIComponent(kind)}`);
    const identifierField = (spec.fields || []).find((field) => field.name === "id");
    if (identifierField && record.id === undefined) record.id = id;
    const checks = localShapeChecks(spec, record);
    renderDiagnosticsAt("create-errors", checks);
    if (checks.length) return;
    const data = await api("/api/draft/records", { method: "POST", body: { revision: state.session.revision, kind, identifier: id, record } });
    state.session = { ...state.session, ...data, dirty: true };
    resetCreateForm();
    renderSession(); byId("create-dialog").close(); await loadRecords(); await selectRecord(kind, id);
  } catch (error) { renderDiagnosticsAt("create-errors", error.details?.length ? error.details : [{ pointer: "/", message: error.message }]); }
}

function discoveryItems(data) {
  return data.draft?.matches || data.baseline?.matches || data.matches || [];
}

function renderQueryComparison(data) {
  const container = byId("query-comparison"); clear(container); container.hidden = false;
  const comparison = data.comparison || { available: false, reason: "baseline_only" };
  container.append(element("h3", { text: "Baseline versus draft" }));
  if (!comparison.available) {
    const unavailable = data.draft_unavailable;
    const revision = unavailable?.revision === undefined ? "" : ` Current draft r${unavailable.revision}.`;
    const lastValid = unavailable?.last_valid_revision === null || unavailable?.last_valid_revision === undefined ? "" : ` Last valid draft: r${unavailable.last_valid_revision}.`;
    container.append(element("p", { text: `Comparison unavailable (${unavailable?.reason || comparison.reason || "no valid draft"}).${revision}${lastValid}` }));
    if (unavailable?.diagnostics?.length) container.append(element("pre", { className: "json-view", text: jsonText(unavailable.diagnostics) }));
    else if (data.baseline?.diagnostics?.length) container.append(
      element("h4", { text: "Baseline discovery diagnostics" }),
      element("pre", { className: "json-view", text: jsonText(data.baseline.diagnostics) }),
    );
    return;
  }
  container.append(element("p", { text: `Baseline ${comparison.baseline_count} · draft ${comparison.draft_count} · ${comparison.changed_count} changed · ${comparison.unchanged_count} unchanged` }));
  const list = element("ol", { className: "comparison-list" });
  for (const change of comparison.changes || []) {
    list.append(element("li", {}, [
      element("strong", { text: `${change.status}: ${change.kind}:${change.identifier}` }),
      element("pre", { className: "json-view", text: jsonText(change) }),
    ]));
  }
  if (!(comparison.changes || []).length) list.append(element("li", { text: "No ranked-result changes." }));
  container.append(list);
  if (comparison.diagnostics_changed) container.append(
    element("h4", { text: "Discovery diagnostics changed" }),
    element("pre", { className: "json-view", text: jsonText(comparison.diagnostics) }),
  );
  else if (data.draft?.diagnostics?.length || data.baseline?.diagnostics?.length) container.append(
    element("h4", { text: "Discovery diagnostics" }),
    element("pre", { className: "json-view", text: jsonText(data.draft?.diagnostics || data.baseline.diagnostics) }),
  );
}

function renderQueryResults(data) {
  const list = byId("query-results"); clear(list);
  const resultSet = data.draft || data.baseline || data;
  for (const [index, result] of discoveryItems(data).entries()) {
    const id = result.id || result.identifier;
    const button = element("button", { type: "button", text: result.label || id });
    button.addEventListener("click", () => selectRecord(result.kind, id));
    const reasons = result.match_reasons || result.reasons || [];
    const reasonText = reasons.map((reason) => typeof reason === "string" ? reason : `${reason.field || "match"}: ${(reason.terms || []).join(", ")}`).join(" · ");
    const details = {
      matched_fields: result.matched_fields,
      matched_terms: result.matched_terms,
      unmatched_query_terms: result.unmatched_query_terms,
      match_reasons: reasons,
      diagnostics: result.diagnostics,
      origin: result.origin,
      qualifications: result.qualifications,
      profile_coverage: result.profile_coverage,
      active_revisions: result.active_revisions,
      implementation_bindings: result.implementation_bindings,
    };
    const metadata = element("details", { className: "result-metadata" }, [
      element("summary", { text: "Match, provenance, coverage, revisions, and bindings" }),
      element("pre", { className: "json-view", text: jsonText(details) }),
    ]);
    list.append(element("li", {}, [
      button,
      element("span", { className: "score", text: `rank ${index + 1} · score ${result.score ?? "—"} · ${result.kind}:${id}` }),
      element("p", { text: reasonText || "No match reasons returned." }),
      metadata,
    ]));
  }
  if (resultSet?.diagnostics?.length) showNotice("query-notice", `Discovery returned ${resultSet.diagnostics.length} diagnostic(s); inspect result metadata and comparison.`, "info");
}

async function runQuery(event) {
  event.preventDefault();
  showNotice("query-notice", "", "info");
  const body = {
    query: byId("query-text").value,
    limit: Number(byId("query-limit").value),
  };
  if (byId("query-profile").value) body.profile = byId("query-profile").value;
  const kinds = parseKinds(byId("query-kinds").value);
  if (kinds.length) body.kinds = kinds;
  if (byId("query-domain").value.trim()) body.domain = byId("query-domain").value.trim();
  try {
    const data = await api("/api/discover", { method: "POST", body });
    renderQueryResults(data);
    renderQueryComparison(data);
    if (data.draft_unavailable) showNotice("query-notice", "Draft comparison is unavailable; current baseline results are shown.", "info");
  } catch (error) { showNotice("query-notice", error.message); }
}

function showData(title, data) {
  byId("dialog-title").textContent = title;
  byId("dialog-data").textContent = jsonText(data);
  byId("data-dialog").showModal();
}

async function draftAction(path, title, { discardLocal = false } = {}) {
  try {
    const data = await api(path, { method: "POST", body: { revision: state.session.revision } });
    state.session = { ...state.session, ...data };
    state.buffer = discardLocal
      ? createDraftBuffer(data.revision || 0)
      : rebaseDraftBuffer(state.buffer, data.revision || 0);
    if (discardLocal) resetCreateForm();
    renderSession();
    showData(title, data);
    return data;
  } catch (error) { showData(title, { type: error.type, message: error.message, details: error.details }); }
}

async function boot() {
  try { await loadSession(); await loadRecords(); }
  catch (error) { showNotice("record-notice", error.message); }
  byId("filters").addEventListener("submit", (event) => {
    event.preventDefault();
    const params = new URLSearchParams(new FormData(event.currentTarget));
    for (const [key, value] of [...params]) if (!value) params.delete(key);
    loadRecords(params).catch((error) => showNotice("record-notice", error.message));
  });
  byId("apply-record").addEventListener("click", applyRecord);
  byId("record-editor").addEventListener("input", () => {
    bufferCurrentEditor();
    for (const { input } of state.enhancedControls) {
      input.dataset.enhancedDirty = "false";
    }
  });
  byId("load-more-records").addEventListener("click", renderNavigatorBatch);
  byId("delete-record").addEventListener("click", deleteRecord);
  byId("restore-record").addEventListener("click", () => {
    if (!state.selection) return;
    state.buffer = discardBufferedRecord(state.buffer, recordBufferKey(state.selection));
    renderSession();
    renderDiagnostics([]);
    renderRecord(state.record);
  });
  byId("query-form").addEventListener("submit", runQuery);
  byId("graph-depth").addEventListener("click", () => {
    if (!state.selection) return;
    state.graphDepth = state.graphDepth === 1 ? 2 : 1;
    selectRecord(state.selection.kind, state.selection.id, { history: "none", depth: state.graphDepth });
  });
  byId("new-record").addEventListener("click", () => byId("create-dialog").showModal());
  byId("cancel-create").addEventListener("click", () => byId("create-dialog").close());
  byId("create-form").addEventListener("submit", createRecord);
  trackCreateFormChanges({
    kind: byId("create-kind"),
    identifier: byId("create-id"),
    recordJson: byId("create-json"),
  }, (values) => {
    state.buffer = updateCreateFormBuffer(state.buffer, values);
    renderSession();
  });
  byId("show-diff").addEventListener("click", async () => {
    try { showData("Exact prospective source diff", await api("/api/draft/diff")); }
    catch (error) { showData("Draft diff", { message: error.message, details: error.details }); }
  });
  byId("validate-draft").addEventListener("click", () => draftAction("/api/draft/validate", "Draft validation"));
  byId("reset-draft").addEventListener("click", () => {
    if (!window.confirm("Discard all in-memory draft changes?")) return;
    draftAction("/api/draft/reset", "Draft reset", { discardLocal: true }).then(() => loadRecords());
  });
  byId("save-draft").addEventListener("click", async () => {
    const data = await draftAction("/api/draft/save", "Save result");
    if (!data?.saved) return;
    await loadRecords();
    if (state.selection) {
      await selectRecord(state.selection.kind, state.selection.id, { history: "none" });
    }
  });
  byId("shutdown").addEventListener("click", async () => {
    const discardUnsaved = hasUnsavedWork(state.session, state.buffer);
    if (discardUnsaved && !window.confirm("Discard the unsaved draft and unapplied editor changes, then shut down?")) return;
    try { await api("/api/shutdown", { method: "POST", body: { discard_unsaved: discardUnsaved } }); document.body.textContent = "The local curator has shut down."; }
    catch (error) { showData("Shutdown", { message: error.message }); }
  });
  byId("close-dialog").addEventListener("click", () => byId("data-dialog").close());
  window.addEventListener("popstate", (event) => {
    if (event.state?.kind && event.state?.id) selectRecord(event.state.kind, event.state.id, { history: "none" });
  });
}

if (typeof document !== "undefined") boot();
