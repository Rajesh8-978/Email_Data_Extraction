const state = {
  mode: "text",
  analyzerResult: null,
  anonymizerResult: null,
};

const entityLabels = {
  BANKRUPTCY_NUMBER: "Bankruptcy number",
  BANKRUPT_NAME: "Bankrupt name",
  BANK_ACCOUNT_NUMBER: "Bank account",
  CREDITOR_NAME: "Creditor",
  DATE_TIME: "Date / time",
  EMAIL_ADDRESS: "Email address",
  EMAIL_DATE: "Email date",
  GOVERNMENT_AGENCY: "Government agency",
  JOB_TITLE: "Job title",
  LAW_FIRM: "Law firm",
  LOCATION: "Address / location",
  ORGANIZATION: "Organization",
  PASSPORT_NUMBER: "Passport number",
  PERSON: "Person",
  PHONE_NUMBER: "Phone number",
  SG_NRIC_FIN: "Singapore NRIC / FIN",
  SG_VEHICLE_NUMBER: "Vehicle number",
  URL: "URL",
};

const entityOrder = [
  "BANKRUPTCY_NUMBER",
  "BANKRUPT_NAME",
  "PERSON",
  "BANK_ACCOUNT_NUMBER",
  "CREDITOR_NAME",
  "EMAIL_ADDRESS",
  "PHONE_NUMBER",
  "SG_NRIC_FIN",
  "PASSPORT_NUMBER",
  "SG_VEHICLE_NUMBER",
  "LOCATION",
  "GOVERNMENT_AGENCY",
  "LAW_FIRM",
  "ORGANIZATION",
  "JOB_TITLE",
  "EMAIL_DATE",
  "DATE_TIME",
  "URL",
];

const els = {
  apiBase: document.querySelector("#apiBase"),
  textMode: document.querySelector("#textMode"),
  pdfMode: document.querySelector("#pdfMode"),
  textInputBlock: document.querySelector("#textInputBlock"),
  pdfInputBlock: document.querySelector("#pdfInputBlock"),
  textInput: document.querySelector("#textInput"),
  pdfInput: document.querySelector("#pdfInput"),
  emailMessageId: document.querySelector("#emailMessageId"),
  runAnalyzer: document.querySelector("#runAnalyzer"),
  runAnonymizer: document.querySelector("#runAnonymizer"),
  runBoth: document.querySelector("#runBoth"),
  status: document.querySelector("#status"),
  analyzerSummary: document.querySelector("#analyzerSummary"),
  anonymizerSummary: document.querySelector("#anonymizerSummary"),
  highlightedSource: document.querySelector("#highlightedSource"),
  highlightedAnonymized: document.querySelector("#highlightedAnonymized"),
  analyzerJson: document.querySelector("#analyzerJson"),
  anonymizerJson: document.querySelector("#anonymizerJson"),
  copyAnalyzer: document.querySelector("#copyAnalyzer"),
  copyAnonymizer: document.querySelector("#copyAnonymizer"),
};

init();

function init() {
  fetch("./ui.config.json")
    .then((response) => response.json())
    .then((config) => {
      els.apiBase.value = config.default_api_base || "http://localhost:5001";
    })
    .catch(() => {
      els.apiBase.value = "http://localhost:5001";
    });

  els.textMode.addEventListener("click", () => setMode("text"));
  els.pdfMode.addEventListener("click", () => setMode("pdf"));
  els.runAnalyzer.addEventListener("click", () => runAnalyzer());
  els.runAnonymizer.addEventListener("click", () => runAnonymizer());
  els.runBoth.addEventListener("click", () => runBoth());
  els.copyAnalyzer.addEventListener("click", () => copyJson(state.analyzerResult));
  els.copyAnonymizer.addEventListener("click", () => copyJson(state.anonymizerResult));
}

function setMode(mode) {
  state.mode = mode;
  const isText = mode === "text";
  els.textMode.classList.toggle("active", isText);
  els.pdfMode.classList.toggle("active", !isText);
  els.textInputBlock.classList.toggle("hidden", !isText);
  els.pdfInputBlock.classList.toggle("hidden", isText);
  clearResults();
}

async function runBoth() {
  await runAnalyzer();
  await runAnonymizer();
}

async function runAnalyzer() {
  setStatus("Running analyzer...");
  try {
    const result = state.mode === "text"
      ? await postJson("/proxy/text/extracted-entities", textPayload())
      : await postForm("/proxy/pdf/extracted-entities");

    state.analyzerResult = result;
    renderAnalyzer(result);
    setStatus("Analyzer completed.");
  } catch (error) {
    showError("Analyzer failed", error, els.highlightedSource, els.analyzerJson);
  }
}

async function runAnonymizer() {
  setStatus("Running anonymizer...");
  try {
    const result = state.mode === "text"
      ? await postJson("/proxy/text/anonymized-text", textPayload())
      : await postForm("/proxy/pdf/anonymized-text");

    state.anonymizerResult = result;
    renderAnonymizer(result);
    setStatus("Anonymizer completed.");
  } catch (error) {
    showError("Anonymizer failed", error, els.highlightedAnonymized, els.anonymizerJson);
  }
}

function textPayload() {
  return {
    api_base: els.apiBase.value.trim(),
    text: els.textInput.value,
    language: "en",
  };
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

async function postForm(url) {
  const file = els.pdfInput.files[0];
  if (!file) {
    throw new Error("Please choose one PDF file first.");
  }

  const form = new FormData();
  form.append("api_base", els.apiBase.value.trim());
  form.append("file", file);
  form.append("language", "en");
  form.append("email_message_id", els.emailMessageId.value || "1");

  const response = await fetch(url, {
    method: "POST",
    body: form,
  });
  return parseResponse(response);
}

async function parseResponse(response) {
  const text = await response.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = {error: text || response.statusText};
  }

  if (!response.ok) {
    throw new Error(data.error || JSON.stringify(data));
  }
  return data;
}

function renderAnalyzer(result) {
  els.analyzerSummary.innerHTML = summaryChips(result);
  els.analyzerJson.textContent = JSON.stringify(result, null, 2);
  els.highlightedSource.innerHTML = groupedEntityHtml(result);
}

function renderAnonymizer(result) {
  els.anonymizerSummary.innerHTML = summaryChips(result);
  els.anonymizerJson.textContent = JSON.stringify(result, null, 2);

  const anonymizedText = result.anonymized_text || result.AnonymizedText || "";
  if (anonymizedText) {
    els.highlightedAnonymized.innerHTML = highlightAnonymizedText(anonymizedText);
  } else {
    els.highlightedAnonymized.innerHTML = `<span class="muted">No anonymized text returned.</span>`;
  }
}

function highlightOriginalText(text, entities) {
  const validEntities = entities
    .filter((item) => Number.isInteger(item.start) && Number.isInteger(item.end))
    .sort((a, b) => a.start - b.start || b.end - a.end);

  const nonOverlapping = [];
  let cursor = 0;
  for (const entity of validEntities) {
    if (entity.start < cursor) continue;
    nonOverlapping.push(entity);
    cursor = entity.end;
  }

  let html = "";
  cursor = 0;
  for (const entity of nonOverlapping) {
    html += escapeHtml(text.slice(cursor, entity.start));
    const value = text.slice(entity.start, entity.end);
    html += `<mark class="entity entity-source" title="${escapeHtml(entity.entity_type)}">${escapeHtml(value)}</mark>`;
    cursor = entity.end;
  }
  html += escapeHtml(text.slice(cursor));
  return html || `<span class="muted">No source text available.</span>`;
}

function highlightAnonymizedText(text) {
  const escaped = escapeHtml(text);
  return escaped
    .replace(/(&lt;[A-Z_]+&gt;)/g, '<mark class="entity entity-replace">$1</mark>')
    .replace(/([A-Za-z0-9+\/-]{1,4}\*{2,}[A-Za-z0-9\/-]{1,4})/g, '<mark class="entity entity-mask">$1</mark>');
}

function groupedEntityHtml(result) {
  const groupedResult = analyzerGroups(result);
  const rows = entityOrder
    .filter((key) => Array.isArray(groupedResult[key]) && groupedResult[key].length)
    .map((key) => entityGroupCard(key, groupedResult[key]));

  return rows.length
    ? `<div class="entity-board">${rows.join("")}</div>`
    : `<span class="muted">No entities returned.</span>`;
}

function analyzerGroups(result) {
  const output = {};

  for (const key of entityOrder) {
    if (Array.isArray(result[key])) {
      output[key] = result[key];
    }
  }

  if (result.grouped && typeof result.grouped === "object") {
    for (const [key, values] of Object.entries(result.grouped)) {
      if (!Array.isArray(values)) continue;
      output[key] = values
        .map((item) => item.normalized_value || item.value || item)
        .filter(Boolean);
    }
  }

  if (Array.isArray(result.entities)) {
    for (const item of result.entities) {
      const key = item.entity_type;
      const value = item.normalized_value || item.value;
      if (!key || !value) continue;
      output[key] = output[key] || [];
      output[key].push(value);
    }
  }

  for (const [key, values] of Object.entries(output)) {
    output[key] = [...new Set(values.map((value) => String(value)))];
  }

  return output;
}

function entityGroupCard(entityType, values) {
  const label = entityLabels[entityType] || entityType;
  const chips = values
    .map((value) => {
      const text = escapeHtml(String(value));
      return `<span class="value-chip ${entityClass(entityType)}" title="${escapeHtml(entityType)}">${text}</span>`;
    })
    .join("");

  return `
    <section class="entity-card">
      <div class="entity-card-head">
        <span>${escapeHtml(label)}</span>
        <small>${values.length}</small>
      </div>
      <div class="entity-card-values">${chips}</div>
    </section>
  `;
}

function entityClass(entityType) {
  if (["BANKRUPTCY_NUMBER", "BANK_ACCOUNT_NUMBER", "SG_NRIC_FIN", "PASSPORT_NUMBER", "SG_VEHICLE_NUMBER", "PHONE_NUMBER"].includes(entityType)) {
    return "entity-sensitive";
  }
  if (["BANKRUPT_NAME", "PERSON", "CREDITOR_NAME"].includes(entityType)) {
    return "entity-person";
  }
  if (["LOCATION", "GOVERNMENT_AGENCY", "LAW_FIRM", "ORGANIZATION"].includes(entityType)) {
    return "entity-business";
  }
  if (["EMAIL_ADDRESS", "URL"].includes(entityType)) {
    return "entity-contact";
  }
  return "entity-date";
}

function summaryChips(result) {
  const total = result.count ?? result.TotalEntitiesFound ?? result.anonymized_item_count ?? result.AnonymizedItemCount ?? 0;
  const source = result.SourceFileName ? `<span class="chip">${escapeHtml(result.SourceFileName)}</span>` : "";
  return `${source}<span class="chip">Total: ${total}</span>`;
}

function showError(title, error, targetBox, jsonBox) {
  setStatus(`${title}.`);
  const message = error instanceof Error ? error.message : String(error);
  targetBox.innerHTML = `<mark class="entity entity-error">${escapeHtml(message)}</mark>`;
  jsonBox.textContent = JSON.stringify({error: message}, null, 2);
}

function clearResults() {
  state.analyzerResult = null;
  state.anonymizerResult = null;
  els.analyzerSummary.innerHTML = "";
  els.anonymizerSummary.innerHTML = "";
  els.highlightedSource.textContent = "Run analyzer to see detected entities.";
  els.highlightedAnonymized.textContent = "Run anonymizer to see replaced and masked text.";
  els.analyzerJson.textContent = "";
  els.anonymizerJson.textContent = "";
  setStatus("Ready");
}

function setStatus(message) {
  els.status.textContent = message;
}

function copyJson(value) {
  if (!value) {
    setStatus("Nothing to copy yet.");
    return;
  }
  navigator.clipboard.writeText(JSON.stringify(value, null, 2));
  setStatus("JSON copied.");
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
