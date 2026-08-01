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

const state = {
  session: null,
  selection: null,
  record: null,
  formSpec: null,
  graph: null,
  buffer: createDraftBuffer(),
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
  );
  byId("save-draft").disabled = !session.editable || !session.dirty || session.valid === false;
  byId("validate-draft").disabled = !session.editable;
  byId("reset-draft").disabled = !session.editable || !session.dirty;
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
  const data = await api(`/api/records?${params.toString()}`);
  const records = data.records || data.items || [];
  byId("record-total").textContent = String(data.total ?? records.length);
  const list = byId("record-list");
  clear(list);
  const kinds = new Set();
  for (const item of records) {
    const identity = recordIdentity(item);
    kinds.add(identity.kind);
    const button = element("button", { type: "button" }, [
      element("span", { className: "record-label", text: item.label || identity.id }),
      element("span", { className: "record-meta", text: `${identity.kind} · ${identity.id}` }),
    ]);
    button.addEventListener("click", () => selectRecord(identity.kind, identity.id));
    list.append(element("li", {}, [button]));
  }
  const select = byId("filter-kind");
  if (select.options.length === 1) {
    for (const kind of [...kinds].sort()) select.append(element("option", { value: kind, text: kind }));
  }
}

function jsonText(value) {
  return value === undefined ? "Not provided" : JSON.stringify(value, null, 2);
}

function editableAuthored(data) {
  return data.authored || data.record || data.contribution || null;
}

function renderRecord(data) {
  const identity = state.selection;
  const authored = editableAuthored(data);
  byId("record-kind").textContent = identity.kind;
  byId("record-title").textContent = data.label || authored?.label || identity.id;
  byId("record-state").textContent = data.draft_state || (data.editable ? "editable" : "read only");
  byId("authored-record").textContent = jsonText(authored);
  byId("layered-record").textContent = jsonText(data.effective || data.layers || data);
  const summary = byId("record-summary");
  clear(summary);
  const facts = [
    ["Stable ID", identity.id], ["Kind", identity.kind],
    ["Origin", data.origin], ["Module", data.module || data.module_id],
    ["Profile", data.profile || data.target_profile], ["Lifecycle", data.lifecycle],
  ];
  for (const [term, description] of facts) {
    if (description === undefined || description === null) continue;
    summary.append(element("div", {}, [element("dt", { text: term }), element("dd", { text: String(description) })]));
  }
  const canEdit = Boolean(data.editable && state.session?.editable && authored);
  byId("editor-section").hidden = !canEdit;
  if (canEdit) {
    byId("record-editor").value = jsonText(authored);
    renderEnhancedFields(state.formSpec, authored);
  }
}

function renderEnhancedFields(spec, authored) {
  const container = byId("enhanced-fields"); clear(container);
  if (!spec?.enhanced) return;
  for (const field of spec.fields || []) {
    if (field.control === "json" || field.immutable) continue;
    let input;
    if (field.control === "select") {
      input = element("select");
      for (const value of field.enum || []) input.append(element("option", { value, text: value }));
    } else if (field.control === "textarea") input = element("textarea");
    else input = element("input", { type: field.control === "number" ? "number" : field.control === "checkbox" ? "checkbox" : "text" });
    if (field.control === "checkbox") input.checked = Boolean(authored[field.name]);
    else input.value = authored[field.name] ?? "";
    input.addEventListener("change", () => {
      let record;
      try { record = JSON.parse(byId("record-editor").value); } catch { return; }
      if (field.control === "checkbox") record[field.name] = input.checked;
      else if (field.control === "number") record[field.name] = Number(input.value);
      else record[field.name] = input.value;
      byId("record-editor").value = jsonText(record);
    });
    const children = [element("span", { text: field.label }), input];
    const help = field.warning || field.help;
    if (help) children.push(element("small", { text: help }));
    container.append(element("label", {}, children));
  }
}

async function selectRecord(kind, id) {
  state.selection = { kind, id };
  state.formSpec = null;
  showNotice("record-notice", "", "info");
  try {
    const path = `/api/records/${encodeURIComponent(kind)}/${encodeURIComponent(id)}`;
    const [record, graph] = await Promise.all([api(path), api(`/api/graph/${encodeURIComponent(kind)}/${encodeURIComponent(id)}?depth=1`)]);
    state.record = record;
    state.graph = graph;
    state.formSpec = record.form || record.form_spec || null;
    renderRecord(record);
    renderConnections(graph);
    history.pushState({ kind, id }, "", `#${encodeURIComponent(kind)}:${encodeURIComponent(id)}`);
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
  const checks = localShapeChecks(state.formSpec, replacement);
  renderDiagnostics(checks);
  if (checks.length) return;
  const { kind, id } = state.selection;
  try {
    const data = await api(`/api/draft/records/${encodeURIComponent(kind)}/${encodeURIComponent(id)}`, {
      method: "PUT", body: { revision: state.session.revision, record: replacement },
    });
    state.session = { ...state.session, ...data, dirty: true };
    state.buffer = bufferRecord({ ...state.buffer, revision: state.session.revision }, `${kind}:${id}`, replacement);
    renderSession();
    await selectRecord(kind, id);
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
    renderSession(); await loadRecords();
    showNotice("record-notice", data.valid ? "Record deleted from the draft." : "Record deleted; resolve validation diagnostics before saving.", "info");
  } catch (error) { showData("Delete record", { message: error.message, details: error.details }); }
}

function renderDiagnosticsAt(id, errors) {
  const list = byId(id); clear(list);
  for (const error of errors) list.append(element("li", { text: `${error.pointer || error.json_pointer || "/"}: ${error.message}` }));
}

async function createRecord(event) {
  event.preventDefault();
  let record;
  try { record = JSON.parse(byId("create-json").value); }
  catch (error) { renderDiagnosticsAt("create-errors", [{ pointer: "/", message: error.message }]); return; }
  const kind = byId("create-kind").value.trim();
  const id = byId("create-id").value.trim();
  try {
    const data = await api("/api/draft/records", { method: "POST", body: { revision: state.session.revision, kind, identifier: id, record } });
    state.session = { ...state.session, ...data, dirty: true };
    renderSession(); byId("create-dialog").close(); await loadRecords(); await selectRecord(kind, id);
  } catch (error) { renderDiagnosticsAt("create-errors", error.details?.length ? error.details : [{ pointer: "/", message: error.message }]); }
}

function discoveryItems(data) {
  return data.draft?.matches || data.baseline?.matches || data.matches || [];
}

async function runQuery(event) {
  event.preventDefault();
  showNotice("query-notice", "", "info");
  const body = {
    query: byId("query-text").value,
    limit: Number(byId("query-limit").value),
  };
  if (byId("query-profile").value) body.profile = byId("query-profile").value;
  try {
    const data = await api("/api/discover", { method: "POST", body });
    const list = byId("query-results"); clear(list);
    for (const result of discoveryItems(data)) {
      const id = result.id || result.identifier;
      const button = element("button", { type: "button", text: result.label || id });
      button.addEventListener("click", () => selectRecord(result.kind, id));
      const reasons = result.match_reasons || result.reasons || [];
      const reasonText = reasons.map((reason) => typeof reason === "string" ? reason : `${reason.field || "match"}: ${(reason.terms || []).join(", ")}`).join(" · ");
      list.append(element("li", {}, [button, element("span", { className: "score", text: `score ${result.score ?? "—"}` }), element("p", { text: reasonText })]));
    }
    if (data.draft_unavailable) showNotice("query-notice", "Draft comparison is unavailable; baseline results are shown.", "info");
  } catch (error) { showNotice("query-notice", error.message); }
}

function showData(title, data) {
  byId("dialog-title").textContent = title;
  byId("dialog-data").textContent = jsonText(data);
  byId("data-dialog").showModal();
}

async function draftAction(path, title) {
  try {
    const data = await api(path, { method: "POST", body: { revision: state.session.revision } });
    state.session = { ...state.session, ...data };
    renderSession();
    showData(title, data);
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
  byId("delete-record").addEventListener("click", deleteRecord);
  byId("restore-record").addEventListener("click", () => renderRecord(state.record));
  byId("query-form").addEventListener("submit", runQuery);
  byId("new-record").addEventListener("click", () => byId("create-dialog").showModal());
  byId("cancel-create").addEventListener("click", () => byId("create-dialog").close());
  byId("create-form").addEventListener("submit", createRecord);
  byId("show-diff").addEventListener("click", async () => {
    try { showData("Exact prospective source diff", await api("/api/draft/diff")); }
    catch (error) { showData("Draft diff", { message: error.message, details: error.details }); }
  });
  byId("validate-draft").addEventListener("click", () => draftAction("/api/draft/validate", "Draft validation"));
  byId("reset-draft").addEventListener("click", () => {
    if (!window.confirm("Discard all in-memory draft changes?")) return;
    draftAction("/api/draft/reset", "Draft reset").then(() => loadRecords());
  });
  byId("save-draft").addEventListener("click", () => draftAction("/api/draft/save", "Save result"));
  byId("shutdown").addEventListener("click", async () => {
    if (state.session?.dirty && !window.confirm("Discard the unsaved draft and shut down?")) return;
    try { await api("/api/shutdown", { method: "POST", body: { discard_unsaved: Boolean(state.session?.dirty) } }); document.body.textContent = "The local curator has shut down."; }
    catch (error) { showData("Shutdown", { message: error.message }); }
  });
  byId("close-dialog").addEventListener("click", () => byId("data-dialog").close());
  window.addEventListener("popstate", (event) => {
    if (event.state?.kind && event.state?.id) selectRecord(event.state.kind, event.state.id);
  });
}

if (typeof document !== "undefined") boot();
