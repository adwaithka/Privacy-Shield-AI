/* ============================================================
   PRIVACY SHIELD AI — script.js v3.1

   Fixes vs v3.0:
     - Mode lock: switching to "Custom" while "Full auto" is active
       properly disables the target grid and vice-versa
     - Full auto-redact mode disables the custom target buttons entirely
     - Face-blur toggle wired to mask_face FormData field
     - Image redacted result shown inline + download as PNG
     - PDF redacted result download as PDF
     - analyzeBtn stays disabled until a file is actually chosen
============================================================ */

const API = "http://127.0.0.1:8000";

const ACCEPTED = new Set(["pdf","docx","txt","png","jpg","jpeg","webp","tiff","tif","bmp"]);
const IMAGES   = new Set(["png","jpg","jpeg","webp","tiff","tif","bmp"]);

/* ── DOM refs ── */
const dropZone     = document.getElementById("drop-zone");
const dzBody       = document.getElementById("dz-body");
const dzSelected   = document.getElementById("dz-selected");
const dzPreview    = document.getElementById("dz-preview");
const dzFilename   = document.getElementById("dz-filename");
const dzSize       = document.getElementById("dz-size");
const dzClear      = document.getElementById("dz-clear");
const fileInput    = document.getElementById("file-input");

const modeAll      = document.getElementById("mode-all");
const modeCustom   = document.getElementById("mode-custom");
const targetGrid   = document.getElementById("target-grid");
const maskNote     = document.getElementById("mask-note");
const faceToggle   = document.getElementById("face-toggle");

const analyzeBtn   = document.getElementById("analyze-btn");
const loadingState = document.getElementById("loading-state");
const loadingText  = document.getElementById("loading-text");
const loadingSub   = document.getElementById("loading-sub");
const errorBar     = document.getElementById("error-bar");
const errorMsg     = document.getElementById("error-msg");
const errorClose   = document.getElementById("error-close");

const results      = document.getElementById("results");
const rFilename    = document.getElementById("r-filename");
const rCount       = document.getElementById("r-count");
const rMasked      = document.getElementById("r-masked");
const dlBar        = document.getElementById("dl-bar");
const dlBtn        = document.getElementById("dl-btn");
const dlLabel      = document.getElementById("dl-label");
const imgCard      = document.getElementById("img-result-card");
const redactedImg  = document.getElementById("redacted-img");
const entTbody     = document.getElementById("ent-tbody");
const maskedTa     = document.getElementById("masked-ta");
const copyBtn      = document.getElementById("copy-btn");
const copyLabel    = document.getElementById("copy-label");

/* ── State ── */
let selectedFile = null;
let isImage      = false;
let maskMode     = "all";       // "all" | "custom"
let selectedKeys = new Set();
let targetData   = [];

/* ─── Load targets from backend ──────────────────────────────── */
async function loadTargets(retries = 5) {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const res = await fetch(`${API}/targets`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      targetData = (json.targets || []).filter(t => t.key !== "all");
      buildTargetGrid();
      return; // success
    } catch (_) {
      if (attempt < retries - 1) {
        await new Promise(r => setTimeout(r, 1500)); // wait 1.5s then retry
      }
    }
  }
  // All retries failed — build grid from hardcoded fallback so UI still works
  targetData = [
    {key:"name",        label:"Names"},
    {key:"email",       label:"Email addresses"},
    {key:"phone",       label:"Phone numbers"},
    {key:"address",     label:"Addresses & locations"},
    {key:"aadhaar",     label:"Aadhaar numbers"},
    {key:"pan",         label:"PAN numbers"},
    {key:"passport",    label:"Passport numbers"},
    {key:"ifsc",        label:"IFSC codes"},
    {key:"bank",        label:"Bank account numbers"},
    {key:"organization",label:"Organizations"},
    {key:"date",        label:"Dates & times"},
    {key:"url",         label:"URLs"},
    {key:"credit_card", label:"Credit card numbers"},
  ];
  buildTargetGrid();
}

function buildTargetGrid() {
  targetGrid.innerHTML = "";
  targetData.forEach(t => {
    const btn = document.createElement("button");
    btn.className = "target-btn";
    btn.dataset.key = t.key;
    btn.innerHTML = `<span class="t-check"></span>${t.label}`;
    btn.addEventListener("click", () => toggleTarget(t.key, btn));
    targetGrid.appendChild(btn);
  });
}

function toggleTarget(key, btn) {
  if (maskMode !== "custom") return;   // guard: grid is locked in "all" mode
  if (selectedKeys.has(key)) {
    selectedKeys.delete(key);
    btn.classList.remove("selected");
  } else {
    selectedKeys.add(key);
    btn.classList.add("selected");
  }
  updateNote();
}

function updateNote() {
  if (maskMode === "all") {
    maskNote.textContent = "All detected PII will be redacted automatically.";
    return;
  }
  if (selectedKeys.size === 0) {
    maskNote.textContent = "Select at least one category to mask.";
    return;
  }
  const labels = [...selectedKeys].map(k => {
    const t = targetData.find(x => x.key === k);
    return t ? t.label : k;
  });
  maskNote.textContent = `Will mask: ${labels.join(", ")}.`;
}

/* ── Mode switch ── */
modeAll.addEventListener("click", () => {
  if (maskMode === "all") return;
  maskMode = "all";
  modeAll.classList.add("active");
  modeCustom.classList.remove("active");
  targetGrid.hidden = true;
  // Visually disable (but don't destroy) the target buttons
  targetGrid.querySelectorAll(".target-btn").forEach(b => b.setAttribute("disabled", "true"));
  updateNote();
});

modeCustom.addEventListener("click", () => {
  if (maskMode === "custom") return;
  maskMode = "custom";
  modeCustom.classList.add("active");
  modeAll.classList.remove("active");
  targetGrid.hidden = false;
  targetGrid.querySelectorAll(".target-btn").forEach(b => b.removeAttribute("disabled"));
  updateNote();
});

/* ─── File helpers ────────────────────────────────────────────── */
function ext(name) { return (name.split(".").pop() || "").toLowerCase(); }
function fmtSize(n) { return n > 1048576 ? `${(n/1048576).toFixed(1)} MB` : `${Math.round(n/1024)} KB`; }

function setFile(file) {
  const e = ext(file.name);
  if (!ACCEPTED.has(e)) {
    showError(`".${e}" files are not supported. Upload PDF, DOCX, TXT, or an image.`);
    return;
  }
  if (file.size > 20 * 1024 * 1024) {
    showError("File exceeds 20 MB limit.");
    return;
  }
  selectedFile = file;
  isImage = IMAGES.has(e);
  hideError();

  dzBody.hidden    = true;
  dzSelected.hidden = false;
  dzFilename.textContent = file.name;
  dzSize.textContent     = fmtSize(file.size);

  if (isImage) {
    const url = URL.createObjectURL(file);
    dzPreview.innerHTML = `<img src="${url}" alt="preview" />`;
  } else {
    dzPreview.innerHTML = `
      <div class="dz-doc-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
      </div>`;
  }

  analyzeBtn.disabled = false;
}

function clearFile() {
  selectedFile = null; isImage = false;
  fileInput.value = "";
  dzBody.hidden    = false;
  dzSelected.hidden = true;
  dzPreview.innerHTML = "";
  analyzeBtn.disabled = true;
}

/* ── Drop zone events ── */
dropZone.addEventListener("click", e => {
  if (e.target.closest(".dz-clear") || e.target.closest("label")) return;
  fileInput.click();
});
dropZone.addEventListener("keydown", e => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
});
fileInput.addEventListener("change", () => { if (fileInput.files.length) setFile(fileInput.files[0]); });
dzClear.addEventListener("click", e => { e.stopPropagation(); clearFile(); });

["dragenter","dragover"].forEach(ev =>
  dropZone.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); dropZone.classList.add("drag-over"); })
);
dropZone.addEventListener("dragleave", e => {
  e.preventDefault(); e.stopPropagation();
  if (!dropZone.contains(e.relatedTarget)) dropZone.classList.remove("drag-over");
});
dropZone.addEventListener("drop", e => {
  e.preventDefault(); e.stopPropagation();
  dropZone.classList.remove("drag-over");
  if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
});

/* ─── Error helpers ───────────────────────────────────────────── */
function showError(msg) {
  errorMsg.textContent = msg;
  errorBar.hidden = false;
  errorBar.classList.add("anim-in");
}
function hideError() {
  errorBar.hidden = true;
  errorBar.classList.remove("anim-in");
}
errorClose.addEventListener("click", hideError);

/* ─── Loading ─────────────────────────────────────────────────── */
function setLoading(on) {
  loadingState.hidden  = !on;
  analyzeBtn.disabled  =  on;
  fileInput.disabled   =  on;
  dropZone.style.pointerEvents = on ? "none" : "";
  dropZone.style.opacity       = on ? "0.5"  : "";
  if (on) {
    loadingState.classList.add("anim-in");
    if (isImage) {
      loadingText.textContent = "Running OCR + face detection…";
      loadingSub.textContent  = "Tesseract + OpenCV — may take 10–20 s";
    } else {
      loadingText.textContent = "Scanning document…";
      loadingSub.textContent  = "Running entity recognition pipeline";
    }
  }
}

/* ─── Analyze ─────────────────────────────────────────────────── */
analyzeBtn.addEventListener("click", analyze);

async function analyze() {
  if (!selectedFile) return;
  hideError();
  results.hidden = true;
  setLoading(true);

  // Build mask_targets
  let targetsVal;
  if (maskMode === "all") {
    targetsVal = "all";
  } else {
    targetsVal = selectedKeys.size > 0
      ? JSON.stringify([...selectedKeys])
      : "all";
  }

  const fd = new FormData();
  fd.append("file",         selectedFile);
  fd.append("mask_targets", targetsVal);
  fd.append("mask_face",    faceToggle.checked ? "true" : "false");
  const maskQr = maskMode === "all" || selectedKeys.has("qr_code");
  fd.append("mask_qr",      maskQr ? "true" : "false");

  try {
    const resp = await fetch(`${API}/analyze`, { method: "POST", body: fd });

    if (!resp.ok) {
      let detail = `Server error ${resp.status}`;
      try { const j = await resp.json(); if (j.detail) detail = j.detail; } catch (_) {}
      throw new Error(detail);
    }

    const data = await resp.json();
    renderResults(data);

  } catch (err) {
    if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
      showError(`Cannot reach backend at ${API}. Is uvicorn running?  →  uvicorn app:app --reload`);
    } else {
      showError(err.message || "An unexpected error occurred.");
    }
  } finally {
    setLoading(false);
  }
}

/* ─── Render results ──────────────────────────────────────────── */
function renderResults(data) {
  if (!data || typeof data !== "object") { showError("Invalid response from server."); return; }

  rFilename.textContent = data.filename || selectedFile.name;
  rCount.textContent    = data.entities_found ?? (data.entities?.length ?? 0);

  const targets = data.mask_targets || [];
  rMasked.textContent = targets.includes("all") ? "All PII"
    : targets.length ? targets.join(", ") : "All PII";

  /* ── Download / preview ── */
  dlBar.hidden   = true;
  imgCard.hidden = true;

  if (data.redacted_image_b64) {
    const blob = b64Blob(data.redacted_image_b64, "image/png");
    const url  = URL.createObjectURL(blob);
    redactedImg.src  = url;
    imgCard.hidden   = false;
    const safeName   = (data.filename || "image").replace(/\.[^.]+$/, "");
    dlBtn.href       = url;
    dlBtn.download   = `${safeName}_redacted.png`;
    dlLabel.textContent = "Redacted image ready";
    dlBar.hidden     = false;
    dlBar.classList.add("anim-in");
  } else if (data.redacted_pdf_b64) {
    const blob = b64Blob(data.redacted_pdf_b64, "application/pdf");
    const url  = URL.createObjectURL(blob);
    const safeName = (data.filename || "document").replace(/\.[^.]+$/, "");
    dlBtn.href       = url;
    dlBtn.download   = `${safeName}_redacted.pdf`;
    dlLabel.textContent = "Redacted PDF ready";
    dlBar.hidden     = false;
    dlBar.classList.add("anim-in");
  }

  /* ── Entity table ── */
  entTbody.innerHTML = "";
  const entities = data.entities || [];

  if (entities.length === 0) {
    entTbody.innerHTML = `<tr><td colspan="3" style="text-align:center;color:var(--slate-500);padding:24px;font-size:.83rem;">No entities detected</td></tr>`;
  } else {
    entities.forEach((ent, i) => {
      const tr = document.createElement("tr");
      tr.style.animationDelay = `${i * 25}ms`;
      tr.classList.add("anim-in");
      const score   = typeof ent.score === "number" ? ent.score : parseFloat(ent.score) || 0;
      const typeKey = (ent.type || "UNKNOWN").replace(/[^A-Z0-9_]/gi, "_").toUpperCase();
      tr.innerHTML = `
        <td><span class="ent-badge ent-badge--${typeKey}">${esc(ent.type || "UNKNOWN")}</span></td>
        <td><span class="ent-text">${esc(ent.text || "—")}</span></td>
        <td>
          <div class="score-wrap">
            <div class="score-bar"><div class="score-fill" style="width:${Math.round(score*100)}%"></div></div>
            <span class="score-val" style="color:${scoreColor(score)}">${score.toFixed(2)}</span>
          </div>
        </td>`;
      entTbody.appendChild(tr);
    });
  }

  /* ── Masked text ── */
  maskedTa.value = data.masked_text || "(No redacted text returned)";

  /* ── Show results ── */
  results.hidden = false;
  results.classList.add("anim-in");
  setTimeout(() => results.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
}

/* ─── Utilities ───────────────────────────────────────────────── */
function esc(s) {
  return String(s)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
function scoreColor(s) {
  return s >= .9 ? "var(--green-400)" : s >= .7 ? "var(--amber-400)" : "var(--red-400)";
}
function b64Blob(b64, mime) {
  const bytes = atob(b64);
  const arr   = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
  return new Blob([arr], { type: mime });
}

/* ─── Copy ────────────────────────────────────────────────────── */
copyBtn.addEventListener("click", async () => {
  const text = maskedTa.value;
  if (!text) return;
  try { await navigator.clipboard.writeText(text); }
  catch (_) { maskedTa.select(); document.execCommand("copy"); }
  copyLabel.textContent = "Copied!";
  setTimeout(() => { copyLabel.textContent = "Copy"; }, 2000);
});

/* ─── Init ────────────────────────────────────────────────────── */
loadTargets();
updateNote();