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

form.addEventListener("submit", design);
document
  .getElementById("download-pdf")
  .addEventListener("click", () => download("pdf", "alleleforge-report.pdf", "application/pdf"));
document
  .getElementById("download-json")
  .addEventListener("click", () => download("json", "alleleforge-report.json", "application/json"));
checkHealth();
