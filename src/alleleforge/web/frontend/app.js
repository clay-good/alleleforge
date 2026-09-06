// AlleleForge served frontend (Phase 13).
// Implements the variant-first journey against the local API. No third-party
// scripts, no external calls: every fetch targets this same deployment.

"use strict";

const form = document.getElementById("design-form");
const statusEl = document.getElementById("status");
const reportFrame = document.getElementById("report");
const actions = document.getElementById("actions");
const submitBtn = document.getElementById("submit");

let lastRequest = null; // the last design request body, for the download buttons.

function readForm() {
  const populations = document.getElementById("populations").value.trim();
  const max = document.getElementById("max").value;
  return {
    variant: document.getElementById("variant").value.trim(),
    intent: document.getElementById("intent").value,
    populations: populations ? populations.split(",").map((p) => p.trim()) : null,
    max_per_chemistry: max ? Number(max) : null,
    run_offtarget: document.getElementById("offtarget").checked,
  };
}

function setStatus(message, isError) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", Boolean(isError));
}

async function design(event) {
  event.preventDefault();
  const body = readForm();
  if (!body.variant) {
    setStatus("Enter a variant first.", true);
    return;
  }
  lastRequest = body;
  submitBtn.disabled = true;
  actions.hidden = true;
  reportFrame.hidden = true;
  setStatus("Designing… (resolving variant, routing chemistries, scoring, off-target)");

  try {
    const res = await fetch("/api/design?format=html", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({ detail: res.statusText }));
      setStatus(`Error ${res.status}: ${detail.detail || res.statusText}`, true);
      return;
    }
    reportFrame.srcdoc = await res.text();
    reportFrame.hidden = false;
    actions.hidden = false;
    setStatus("Done. The interactive report is below.");
  } catch (err) {
    setStatus(`Request failed: ${err}`, true);
  } finally {
    submitBtn.disabled = false;
  }
}

async function download(format, filename, mime) {
  if (!lastRequest) return;
  const res = await fetch(`/api/design?format=${format}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(lastRequest),
  });
  if (!res.ok) {
    setStatus(`Download failed: ${res.status}`, true);
    return;
  }
  const blob = format === "json" ? new Blob([await res.text()], { type: mime }) : await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const h = await res.json();
    const ref = h.reference_loaded ? "reference loaded" : "no reference configured";
    document.getElementById("health").textContent = `AlleleForge ${h.version} · ${ref}`;
  } catch {
    document.getElementById("health").textContent = "API unreachable";
  }
}

// --- tabs -------------------------------------------------------------------

function showTab(name) {
  for (const tab of ["single", "batch"]) {
    const isActive = tab === name;
    document.getElementById(`tab-${tab}`).classList.toggle("active", isActive);
    document.getElementById(`tab-${tab}`).setAttribute("aria-selected", String(isActive));
    document.getElementById(`panel-${tab}`).hidden = !isActive;
  }
}

// --- batch (cohort) ---------------------------------------------------------

const batchForm = document.getElementById("batch-form");
const batchStatus = document.getElementById("batch-status");
const batchResults = document.getElementById("batch-results");
const batchActions = document.getElementById("batch-actions");
const batchSubmit = document.getElementById("batch-submit");

let lastBatch = null; // the last batch response, for the download button.

function readBatchForm() {
  const variants = document
    .getElementById("batch-variants")
    .value.split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));
  const populations = document.getElementById("batch-populations").value.trim();
  const max = document.getElementById("batch-max").value;
  return {
    variants,
    intent: document.getElementById("batch-intent").value,
    populations: populations ? populations.split(",").map((p) => p.trim()) : null,
    max_per_chemistry: max ? Number(max) : null,
    run_offtarget: document.getElementById("batch-offtarget").checked,
  };
}

function renderBatch(data) {
  // Everything here is interpolated into innerHTML, and a cohort row is built from
  // *user input*: `item_id` is a raw line from the pasted variant list, and `error` is
  // an exception message that quotes it back. Both were inserted unescaped, so a line
  // like `<img src=x onerror=...>` executed in the page. Escape at the boundary.
  const esc = (v) =>
    String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const cell = (v) => (v === null || v === undefined ? "—" : esc(v));
  const rows = data.items
    .map((it) => {
      const s = it.summary || {};
      // Never a bare estimate: the interval and the out-of-distribution flag travel
      // with the number here as they do everywhere else. This table is the surface
      // aimed at people who will not open a terminal, and it is scanned to decide
      // which variants deserve a closer look — the moment a lone number is trusted.
      let eff = "—";
      if (typeof s.best_efficiency === "number") {
        eff = s.best_efficiency.toFixed(2);
        if (typeof s.best_efficiency_low === "number" && typeof s.best_efficiency_high === "number") {
          eff += ` [${s.best_efficiency_low.toFixed(2)}, ${s.best_efficiency_high.toFixed(2)}]`;
        }
        if (s.best_efficiency_in_distribution === false) {
          eff += ' <span class="err">OOD</span>';
        }
      }
      // A worst-case score alone is the most reassuring number the system can make
      // and the least interpretable: it is conditional on the aggregate specificity
      // the scan is summarized by, and on whether any population source backed it.
      // `offtarget_sources` is `{}` when none did — which over HTTP is always, since
      // no file-backed source can be supplied to this deployment — and an empty
      // ancestry picture means "not measured", not "clean".
      const worst = typeof s.worst_offtarget === "number" ? s.worst_offtarget.toFixed(3) : "—";
      const spec =
        typeof s.best_specificity === "number" ? s.best_specificity.toFixed(3) : "—";
      const sources = s.offtarget_sources;
      const backed = sources && Object.keys(sources).length > 0;
      const basis = backed
        ? esc(Object.keys(sources).join(", "))
        : '<span class="err">reference-only</span>';
      const flagged = Array.isArray(s.best_caveats) ? s.best_caveats : [];
      const caveats = flagged.length ? `<span class="err">${flagged.map(esc).join(", ")}</span>` : "—";
      const detail =
        it.status === "ok"
          ? `<td>${cell(s.best_chemistry)}</td><td>${eff}</td><td>${worst}</td><td>${spec}</td><td>${basis}</td><td>${caveats}</td><td>${cell(s.n_candidates)}</td>`
          : `<td colspan="7" class="err">${cell(it.error)}</td>`;
      return `<tr class="${it.status}"><td>${esc(it.item_id)}</td><td>${it.status}</td>${detail}</tr>`;
    })
    .join("");
  batchResults.innerHTML = `
    <table class="results">
      <thead><tr><th>variant</th><th>status</th><th>best</th><th>efficiency</th>
        <th>worst off-target</th><th>specificity</th><th>off-target basis</th>
        <th>caveats</th><th>candidates</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

async function runBatch(event) {
  event.preventDefault();
  const body = readBatchForm();
  if (body.variants.length === 0) {
    batchStatus.textContent = "Enter at least one variant.";
    batchStatus.classList.add("error");
    return;
  }
  batchStatus.classList.remove("error");
  batchSubmit.disabled = true;
  batchActions.hidden = true;
  batchResults.innerHTML = "";
  batchStatus.textContent = `Designing ${body.variants.length} variant(s)…`;

  try {
    const res = await fetch("/api/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({ detail: res.statusText }));
      batchStatus.textContent = `Error ${res.status}: ${detail.detail || res.statusText}`;
      batchStatus.classList.add("error");
      return;
    }
    lastBatch = await res.json();
    renderBatch(lastBatch);
    batchActions.hidden = false;
    batchStatus.textContent =
      `Done: ${lastBatch.succeeded} ok, ${lastBatch.failed} failed of ${lastBatch.total}.`;
  } catch (err) {
    batchStatus.textContent = `Request failed: ${err}`;
    batchStatus.classList.add("error");
  } finally {
    batchSubmit.disabled = false;
  }
}

function downloadBatch() {
  if (!lastBatch) return;
  const blob = new Blob([JSON.stringify(lastBatch, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "alleleforge-cohort.json";
  a.click();
  URL.revokeObjectURL(url);
}

form.addEventListener("submit", design);
batchForm.addEventListener("submit", runBatch);
document.getElementById("tab-single").addEventListener("click", () => showTab("single"));
document.getElementById("tab-batch").addEventListener("click", () => showTab("batch"));
document.getElementById("batch-download-json").addEventListener("click", downloadBatch);
document
  .getElementById("download-pdf")
  .addEventListener("click", () => download("pdf", "alleleforge-report.pdf", "application/pdf"));
document
  .getElementById("download-json")
  .addEventListener("click", () => download("json", "alleleforge-report.json", "application/json"));
checkHealth();
