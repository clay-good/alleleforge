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

// The token this deployment requires, if it requires one. `null` on an open deployment,
// which is the default and the documented local one.
let apiToken = null;

/**
 * `fetch` for this deployment's API, carrying the token when one is needed.
 *
 * The gate is a header, and a browser cannot set one by itself: a token-protected
 * deployment served this page, showed its capabilities from the one endpoint the gate
 * lets through, and then answered every action with `401 missing or invalid API token`
 * — accurate, and nothing a person in a browser can act on. Every call goes through
 * here so a new one cannot be added that skips the header.
 */
function apiFetch(path, init = {}) {
  const headers = { ...(init.headers || {}) };
  if (apiToken) {
    headers["X-API-Token"] = apiToken;
  }
  return fetch(path, { ...init, headers });
}

/**
 * Reveal the token field when the deployment needs one, and remember what is typed.
 *
 * `sessionStorage`, not `localStorage`: the token is the operator's secret, and holding
 * it for the tab rather than the browser profile is the smaller promise. It never
 * reaches anything but this same origin.
 */
function setUpAuth(required) {
  const panel = document.getElementById("auth");
  const input = document.getElementById("api-token");
  if (!required) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  try {
    apiToken = sessionStorage.getItem("alleleforge-api-token") || null;
  } catch {
    apiToken = null; // storage can be disabled; the field still works for this page.
  }
  if (apiToken) {
    input.value = apiToken;
  }
  input.addEventListener("input", () => {
    apiToken = input.value.trim() || null;
    try {
      if (apiToken) {
        sessionStorage.setItem("alleleforge-api-token", apiToken);
      } else {
        sessionStorage.removeItem("alleleforge-api-token");
      }
    } catch {
      /* storage disabled; the token still applies to this page's requests. */
    }
  });
}

function readForm() {
  const populations = document.getElementById("populations").value.trim();
  const max = document.getElementById("max").value;
  const cellContext = document.getElementById("cell-context").value.trim();
  const track = document.getElementById("chromatin-track").value;
  const vector = document.getElementById("vector-scheme").value;
  return {
    variant: document.getElementById("variant").value.trim(),
    intent: document.getElementById("intent").value,
    populations: populations ? populations.split(",").map((p) => p.trim()) : null,
    max_per_chemistry: max ? Number(max) : null,
    run_offtarget: document.getElementById("offtarget").checked,
    // `null`, not `""`: an empty string is a cell line named "" and a track named "",
    // both of which the API would refuse. Blank means "not specified".
    cell_context: cellContext || null,
    chromatin_track: track || null,
    vector_scheme: vector || null,
    allow_ng: document.getElementById("allow-ng").checked,
    allow_spry: document.getElementById("allow-spry").checked,
    annotate_consequence: document.getElementById("annotate-consequence").checked,
    trained_efficiency: document.getElementById("trained-efficiency").checked,
    trained_outcome: document.getElementById("trained-outcome").checked,
    trained_base_outcome: document.getElementById("trained-base-outcome").checked,
    trained_prime: document.getElementById("trained-prime").checked,
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
    const res = await apiFetch("/api/design?format=html", {
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
    // The frame is a fixed height and the report is often tens of thousands of pixels
    // tall, with no cue on macOS that it scrolls. Say so, and point at the download.
    document.getElementById("report-note").hidden = false;
    actions.hidden = false;
    setStatus("Done. The interactive report is below.");
  } catch (err) {
    setStatus(`Request failed: ${err}`, true);
  } finally {
    submitBtn.disabled = false;
  }
}

async function download(format, filename, mime) {
  // Defence in depth behind the CSS fix: a download with nothing designed used to
  // return silently, so a button that should not have been visible also gave no reason
  // for doing nothing when it was pressed.
  if (!lastRequest) {
    setStatus("Run a design first — there is nothing to download yet.", true);
    return;
  }
  const res = await apiFetch(`/api/design?format=${format}`, {
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
    // Before anything else: without the token every other call on this page is a 401.
    setUpAuth(Boolean(h.auth_required));
    const ref = h.reference_loaded ? "reference loaded" : "no reference configured";
    // Which optional data sources this deployment has. A browser user cannot supply
    // them — they are operator-configured — so the status line is the only place they
    // can learn whether the ancestry labels they typed can be honoured at all. A
    // configured source that failed to load is named separately: a broken mount and a
    // deliberate absence are different facts.
    const sources = [];
    if (h.gnomad_loaded) sources.push("population sites");
    if (h.haplotypes_loaded) sources.push("haplotype panel");
    if (h.chromatin_tracks && h.chromatin_tracks.length) {
      sources.push(`tracks: ${h.chromatin_tracks.join("/")}`);
    }
    if (h.vep_enabled) sources.push("VEP consequence (external)");
    // Which models scored the numbers is as much a fact about the deployment as which
    // data it searched, and a client cannot tell a trained-model run from a baseline one
    // by looking at the menu.
    if (h.trained_models && h.trained_models.length) {
      sources.push(`trained: ${h.trained_models.join("/")}`);
    }
    // The disclaimer promised that no sequence data leaves this deployment. That is the
    // sentence a reader checks before pasting a patient variant, and enabling the VEP
    // annotation makes it false — so the page says what this deployment actually does,
    // the way the API description does.
    if (h.vep_enabled) {
      document.getElementById("transmission").innerHTML =
        "<strong>Compute is local, but this deployment can send a variant off it</strong> " +
        "\u2014 ticking \u201cannotate the predicted consequence\u201d sends that variant, " +
        "chromosome, position and both alleles, to an external VEP server.";
    }
    const errors = Object.keys(h.source_errors || {});
    const basis = sources.length ? sources.join(" · ") : "reference-only";
    const broken = errors.length ? ` · configured but unreadable: ${errors.join(", ")}` : "";
    document.getElementById("health").textContent =
      `AlleleForge ${h.version} · ${ref} · ${basis}${broken}`;
    // The status line already named this deployment's tracks and the form could not
    // select one, so the page listed a capability it could not use. The names are
    // operator-configured, hence read from health rather than hard-coded.
    const names = h.chromatin_tracks || [];
    for (const id of ["chromatin-track", "batch-chromatin-track"]) {
      const select = document.getElementById(id);
      for (const name of names) {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        select.appendChild(option);
      }
      select.disabled = names.length === 0;
    }
    // Enabled only where the operator turned it on. A checkbox that looks available and
    // silently 422s is worse than one that is visibly greyed out, and the label says
    // which of the two a greyed box means.
    for (const id of ["annotate-consequence", "batch-annotate-consequence"]) {
      document.getElementById(id).disabled = !h.vep_enabled;
    }
    // Same operator-enables/client-chooses split as VEP, and the same reason for reading
    // it from health: which trained models a deployment can run is its own fact, and a
    // checkbox that looks available and silently 422s is worse than a greyed-out one.
    const trained = h.trained_models || [];
    for (const field of ["trained_efficiency", "trained_outcome", "trained_base_outcome", "trained_prime"]) {
      const id = field.replace(/_/g, "-");
      for (const prefix of ["", "batch-"]) {
        document.getElementById(prefix + id).disabled = !trained.includes(field);
      }
    }
  } catch {
    document.getElementById("health").textContent = "API unreachable";
  }
}

// --- tabs -------------------------------------------------------------------

function showTab(name) {
  for (const tab of ["single", "batch", "offtarget"]) {
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

let lastBatch = null; // the last batch response, for the JSON download.
let lastBatchRequest = null; // the body that produced it, for renderings the server makes.

function readBatchForm() {
  const variants = document
    .getElementById("batch-variants")
    .value.split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));
  const populations = document.getElementById("batch-populations").value.trim();
  const max = document.getElementById("batch-max").value;
  const cellContext = document.getElementById("batch-cell-context").value.trim();
  const track = document.getElementById("batch-chromatin-track").value;
  return {
    variants,
    intent: document.getElementById("batch-intent").value,
    populations: populations ? populations.split(",").map((p) => p.trim()) : null,
    max_per_chemistry: max ? Number(max) : null,
    run_offtarget: document.getElementById("batch-offtarget").checked,
    cell_context: cellContext || null,
    chromatin_track: track || null,
    allow_ng: document.getElementById("batch-allow-ng").checked,
    allow_spry: document.getElementById("batch-allow-spry").checked,
    annotate_consequence: document.getElementById("batch-annotate-consequence").checked,
    trained_efficiency: document.getElementById("batch-trained-efficiency").checked,
    trained_outcome: document.getElementById("batch-trained-outcome").checked,
    trained_base_outcome: document.getElementById("batch-trained-base-outcome").checked,
    trained_prime: document.getElementById("batch-trained-prime").checked,
  };
}

// Everything rendered through innerHTML below is built from *user input*: a cohort's
// `item_id` is a raw line from the pasted variant list, `error` is an exception message
// that quotes it back, and the off-target panel echoes the spacer and the ancestry
// labels. All of those were once inserted unescaped, and a line like
// `<img src=x onerror=...>` executed in the page. Escape at the boundary — and in one
// place, because two panels with two escapers is one escaper that will fall behind.
const esc = (v) =>
  String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const cell = (v) => (v === null || v === undefined ? "—" : esc(v));

function renderBatch(data) {
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
      // `offtarget_sources` is `{}` when none did. That is no longer always the case
      // over HTTP: the operator can configure a population source and a haplotype panel
      // (the status line above says which), so this reads "reference-only" for a
      // deployment that has none rather than for the web shell as such. Either way an
      // empty ancestry picture means "not measured", not "clean".
      // What a clinical database asserts, when one did. This is the reason a row was
      // requested by accession rather than by coordinates, and it reached the CLI's
      // summary table and the API response while the page — the audience with no
      // terminal to fall back to — had no column for it.
      const clinical = cell(s.clinical_significance);
      // Never a bare estimate — the rule this table already follows for efficiency, and
      // `bystander_burden` is a calibrated prediction too. It is the unintended-edit
      // burden of the recommended reagent, which is exactly what a triage scan is for.
      let bystander = "—";
      if (typeof s.best_bystander_burden === "number") {
        bystander = s.best_bystander_burden.toFixed(2);
        if (
          typeof s.best_bystander_burden_low === "number" &&
          typeof s.best_bystander_burden_high === "number"
        ) {
          bystander += ` [${s.best_bystander_burden_low.toFixed(2)}, ${s.best_bystander_burden_high.toFixed(2)}]`;
        }
      }
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
          ? `<td>${cell(s.best_chemistry)}</td><td>${eff}</td><td>${bystander}</td><td>${worst}</td><td>${spec}</td><td>${basis}</td><td>${caveats}</td><td>${cell(s.n_candidates)}</td>`
          : `<td colspan="8" class="err">${cell(it.error)}</td>`;
      // The first column was headed "variant" and held `item_id` — the string that was
      // typed. Normalization moves an indel under left-alignment, and an accession or an
      // rsID names no locus at all, so the header was making a claim the cell could not
      // keep. Input and resolved variant are two columns now, as they are in the TSV.
      return `<tr class="${it.status}"><td>${esc(it.item_id)}</td><td>${cell(s.variant)}</td><td>${clinical}</td><td>${it.status}</td>${detail}</tr>`;
    })
    .join("");
  batchResults.innerHTML = `
    <table class="results">
      <thead><tr><th>input</th><th>variant</th><th>ClinVar</th><th>status</th><th>best</th><th>efficiency</th>
        <th>bystander burden</th><th>worst off-target</th><th>specificity</th><th>off-target basis</th>
        <th>caveats</th><th>candidates</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

/**
 * Poll a submitted job until it is done or failed.
 *
 * Returns `{ result }` or `{ error }`. `onState` is called with the job's state on
 * every poll that is still running, so the status line says something other than the
 * same sentence for the whole run.
 *
 * The deadline is generous but finite: a page that polls forever on a server that has
 * forgotten the job (a restart drops in-flight records, which the job manager's own
 * docstring says) shows "running" until the tab is closed.
 */
async function awaitJob(jobId, onState) {
  const deadline = Date.now() + 60 * 60 * 1000;
  let delay = 250;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, delay));
    delay = Math.min(delay * 1.5, 2000);
    const res = await apiFetch(`/api/jobs/${jobId}`);
    if (!res.ok) {
      return { error: `job ${jobId} could not be polled (${res.status})` };
    }
    const status = await res.json();
    if (status.state === "done") {
      return { result: status.result };
    }
    if (status.state === "error") {
      return { error: status.error || "the job failed without a reason" };
    }
    onState(status.state);
  }
  return { error: "the job did not finish within an hour" };
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
    // Submitted as a job, not held on one connection. A cohort is the long operation
    // here — a three-hundred-variant run measured 3m 40s — and a browser or a proxy in
    // front of the server closes an idle request long before that, so the blocking
    // endpoint fails exactly on the cohorts this panel exists for. `/api/jobs/batch`
    // returns immediately with an id and the poll below carries the state.
    const submitted = await apiFetch("/api/jobs/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!submitted.ok) {
      const detail = await submitted.json().catch(() => ({ detail: submitted.statusText }));
      batchStatus.textContent =
        `Error ${submitted.status}: ${detail.detail || submitted.statusText}`;
      batchStatus.classList.add("error");
      return;
    }
    const jobId = (await submitted.json()).job_id;
    const finished = await awaitJob(jobId, (state) => {
      batchStatus.textContent =
        `Designing ${body.variants.length} variant(s) — ${state}…`;
    });
    if (finished.error) {
      batchStatus.textContent = `Error: ${finished.error}`;
      batchStatus.classList.add("error");
      return;
    }
    lastBatch = finished.result;
    lastBatchRequest = body;
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
  if (!lastBatch) {
    // The cohort panel has its own status line; `setStatus` writes to the
    // single-variant one, which is not even on screen when this button is.
    batchStatus.textContent = "Run a cohort first — there is nothing to download yet.";
    batchStatus.classList.add("error");
    return;
  }
  const blob = new Blob([JSON.stringify(lastBatch, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "alleleforge-cohort.json";
  a.click();
  URL.revokeObjectURL(url);
}

async function downloadBatchTsv() {
  if (!lastBatchRequest) {
    batchStatus.textContent = "Run a cohort first — there is nothing to download yet.";
    batchStatus.classList.add("error");
    return;
  }
  // Asked of the endpoint rather than assembled here: the column set and its order are
  // the shared ones, and a second implementation in the browser is exactly how two
  // tables of the same numbers come to disagree about their columns.
  const res = await apiFetch("/api/batch?format=tsv", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(lastBatchRequest),
  });
  if (!res.ok) {
    batchStatus.textContent = `Download failed: ${res.status}`;
    batchStatus.classList.add("error");
    return;
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = "alleleforge-cohort.tsv";
  a.click();
  URL.revokeObjectURL(url);
}


// --- off-target (check a spacer) --------------------------------------------
//
// The page could only run an off-target search *inside* a design. `aforge offtarget`
// is a first-class command and `POST /api/offtarget` a first-class endpoint, so the one
// audience with no terminal could not ask the commonest off-target question: here is a
// guide I already have — where else does it cut?

const otForm = document.getElementById("offtarget-form");
const otStatus = document.getElementById("ot-status");
const otResults = document.getElementById("ot-results");

function otNumber(id) {
  const value = document.getElementById(id).value.trim();
  return value === "" ? undefined : Number(value);
}

function otBody() {
  const populations = document
    .getElementById("ot-populations")
    .value.split(",")
    .map((p) => p.trim())
    .filter(Boolean);
  const scorer = document.getElementById("ot-scorer").value.trim();
  const chrom = document.getElementById("ot-chrom").value.trim();
  const start = otNumber("ot-start");
  const end = otNumber("ot-end");
  // Built from four fields rather than parsed from one string: the API takes a
  // structured locus, and a text box here would mean a second coordinate parser.
  // Sent only when all three parts are given — a half-filled locus is a mistake, and
  // silently dropping it would leave the guide counted against itself with no sign.
  const onTarget =
    chrom && start !== undefined && end !== undefined
      ? { chrom, start, end, strand: document.getElementById("ot-strand").value }
      : null;
  const body = {
    spacer: document.getElementById("ot-spacer").value.trim(),
    pam: document.getElementById("ot-pam").value.trim() || "NGG",
    mismatches: otNumber("ot-mismatches"),
    dna_bulges: otNumber("ot-dna-bulges"),
    rna_bulges: otNumber("ot-rna-bulges"),
    cfd_threshold: otNumber("ot-cfd"),
    mit_threshold: otNumber("ot-mit"),
    maf: otNumber("ot-maf"),
    populations: populations.length ? populations : null,
    scorer: scorer || null,
    on_target: onTarget,
  };
  return body;
}

function ancestryTable(worst, burden) {
  // Both, side by side, and never only the first. A CFD score is a property of the
  // sequence and not of who carries it, so the per-ancestry *worst score* is usually
  // identical across ancestries — it is the frequency-weighted burden that carries the
  // reference-bias finding this search exists to reproduce. Showing the worst score
  // alone reads as "risk is spread evenly", which is the opposite of the finding.
  const names = [...new Set([...Object.keys(worst || {}), ...Object.keys(burden || {})])].sort();
  if (!names.length) return "";
  const rows = names
    .map(
      (a) =>
        `<tr><td>${esc(a)}</td><td>${cell(worst?.[a]?.toFixed?.(3))}</td>` +
        `<td>${cell(burden?.[a]?.toFixed?.(4))}</td></tr>`,
    )
    .join("");
  return (
    "<table><caption>By ancestry</caption><thead><tr><th>ancestry</th>" +
    "<th>worst score</th><th>expected burden</th></tr></thead>" +
    `<tbody>${rows}</tbody></table>`
  );
}

function renderOffTarget(data) {
  const burden =
    data.expected_burden === null || data.expected_burden === undefined
      ? "—"
      : data.expected_burden.toFixed(4);
  const onTarget = data.on_target_excluded
    ? ""
    : "<p class=\"warn\">The on-target locus was <strong>not</strong> excluded, so the " +
      "guide's own site is counted against it. Give it above to exclude it.</p>";
  otResults.innerHTML =
    `<h3>Spacer ${esc(data.report.spacer)} / PAM ${esc(data.report.pam)}</h3>` +
    "<table><tbody>" +
    `<tr><th>sites</th><td>${cell(data.n_sites)}</td></tr>` +
    `<tr><th>worst score</th><td>${cell(data.worst_score?.toFixed?.(3))}</td></tr>` +
    `<tr><th>specificity</th><td>${cell(data.specificity?.toFixed?.(3))}</td></tr>` +
    `<tr><th>expected burden</th><td>${esc(burden)}</td></tr>` +
    `<tr><th>scoring matrix</th><td>${cell(data.effective_matrix)}</td></tr>` +
    "</tbody></table>" +
    onTarget +
    ancestryTable(data.ancestry_stratification, data.ancestry_expected_burden) +
    // Every number above is conditional on the budget and the cut-offs, and the
    // sentence that states them travels with the result on every other surface.
    `<p class="note">${esc(data.search_description)}</p>` +
    `<p class="note">${esc(data.coordinate_system)}</p>` +
    `<p class="disclaimer">${esc(data.disclaimer)}</p>`;
}

async function runOffTarget(event) {
  event.preventDefault();
  otResults.innerHTML = "";
  otStatus.textContent = "Searching…";
  otStatus.classList.remove("error");
  try {
    const res = await apiFetch("/api/offtarget", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(otBody()),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({ detail: res.statusText }));
      otStatus.textContent = `Error ${res.status}: ${detail.detail || res.statusText}`;
      otStatus.classList.add("error");
      return;
    }
    renderOffTarget(await res.json());
    otStatus.textContent = "";
  } catch (err) {
    otStatus.textContent = `Request failed: ${err}`;
    otStatus.classList.add("error");
  }
}

form.addEventListener("submit", design);
batchForm.addEventListener("submit", runBatch);
document.getElementById("tab-single").addEventListener("click", () => showTab("single"));
document.getElementById("tab-batch").addEventListener("click", () => showTab("batch"));
document.getElementById("tab-offtarget").addEventListener("click", () => showTab("offtarget"));
otForm.addEventListener("submit", runOffTarget);
document.getElementById("batch-download-json").addEventListener("click", downloadBatch);
document.getElementById("batch-download-tsv").addEventListener("click", downloadBatchTsv);
document
  .getElementById("download-pdf")
  .addEventListener("click", () => download("pdf", "alleleforge-report.pdf", "application/pdf"));
document
  .getElementById("download-json")
  .addEventListener("click", () => download("json", "alleleforge-report.json", "application/json"));

document
  .getElementById("download-html")
  .addEventListener("click", () =>
    // The same document the frame renders, as a standalone file: it is self-contained
    // (styles and charts inlined), so a reader can open it full-height, keep it, or
    // send it to someone without this deployment.
    download("html", "alleleforge-report.html", "text/html"),
  );
document
  .getElementById("download-tsv")
  .addEventListener("click", () =>
    download("tsv", "alleleforge-menu.tsv", "text/tab-separated-values"),
  );
checkHealth();
