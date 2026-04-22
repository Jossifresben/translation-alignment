/* Translation Aligner — interactions
 * Hover a word → light up its alignment group across all three witnesses
 * Hover a variant token → light up the whole variant
 * Click a variant token or rail link → navigate to apparatus
 * Tweaks panel → toggled via ?tweaks=1, updates URL params on change
 */
(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // ── Alignment hover linking ────────────────────────────
  const toks = $$(".tok[data-align], .tok[data-variant]");
  const rows = $$(".align-row");
  const interGroups = $$(".inter-group");

  function clearActive() {
    $$(".tok.is-active").forEach(el => el.classList.remove("is-active"));
    $$(".tok.is-variant-active").forEach(el => el.classList.remove("is-variant-active"));
    $$(".align-row.is-active").forEach(el => el.classList.remove("is-active"));
    $$(".align-row.is-variant-active, .align-row.is-minor-variant-active, .align-row.is-major-variant-active")
      .forEach(el => el.classList.remove("is-variant-active", "is-minor-variant-active", "is-major-variant-active"));
    $$(".inter-group.is-active").forEach(el => el.classList.remove("is-active"));
  }

  function activateAlign(alignId) {
    if (!alignId) return;
    $$(`.tok[data-align="${alignId}"]`).forEach(el => el.classList.add("is-active"));
    $$(`.align-row[data-row="${alignId}"]`).forEach(el => el.classList.add("is-active"));
    $$(`.inter-group[data-row="${alignId}"]`).forEach(el => el.classList.add("is-active"));
  }

  function activateVariant(variantId) {
    if (!variantId) return;
    const variantTokens = $$(`.tok[data-variant="${variantId}"]`);
    variantTokens.forEach(el => el.classList.add("is-variant-active"));
    // Infer kind (minor vs major-family) from any variant token's class
    let kind = "major"; // default if v-* class missing
    for (const t of variantTokens) {
      if (t.classList.contains("v-minor")) { kind = "minor"; break; }
      if (t.classList.contains("v-major") || t.classList.contains("v-omitted") || t.classList.contains("v-added")) {
        kind = "major"; break;
      }
    }
    // Mark rows containing variant tokens with kind-tagged class
    $$(".align-row").forEach(row => {
      if (row.querySelector(`.tok[data-variant="${variantId}"]`)) {
        row.classList.add("is-variant-active");
        row.classList.add(kind === "minor" ? "is-minor-variant-active" : "is-major-variant-active");
      }
    });
  }

  function onEnter(e) {
    const el = e.target.closest(".tok, .inter-group");
    if (!el) return;
    clearActive();
    const a = el.dataset.align || el.dataset.row;
    const v = el.dataset.variant;
    if (a) activateAlign(a);
    if (v) activateVariant(v);
  }

  function onLeave(e) {
    const el = e.target.closest(".tok, .inter-group");
    if (!el) return;
    clearActive();
  }

  document.addEventListener("mouseover", onEnter);
  document.addEventListener("mouseout", onLeave);

  // ── Variants data (embedded by verse.html) ─────────────
  let VARIANTS_BY_ID = {};
  const variantsScript = document.getElementById("variants-data");
  if (variantsScript) {
    try {
      const arr = JSON.parse(variantsScript.textContent) || [];
      for (const v of arr) VARIANTS_BY_ID[v.id] = v;
    } catch (_e) { VARIANTS_BY_ID = {}; }
  }

  // ── Click a variant token → go to apparatus (plain click)
  //    Shift-click or info-icon click → inline popover  ──────
  document.addEventListener("click", (e) => {
    // If the click landed on the explicit info icon, open popover
    const info = e.target.closest(".variant-info");
    const tok = e.target.closest(".tok[data-variant]");
    const grp = e.target.closest(".inter-group[data-variant]");
    const target = info ? info.closest("[data-variant]") : (tok || grp);
    if (!target) return;
    const v = target.dataset.variant;
    if (e.shiftKey || info) {
      e.preventDefault();
      e.stopPropagation();
      showVariantPopover(target, v);
      return;
    }
    const params = new URLSearchParams(window.location.search);
    params.set("view", "apparatus");
    params.set("variant", v);
    const url = window.location.pathname + "?" + params.toString() + "#variant-" + v;
    window.location.href = url;
  });

  function closeVariantPopover() {
    const existing = document.getElementById("active-variant-popover");
    if (existing) existing.remove();
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function buildVariantPopoverHTML(variant) {
    // Title may be a string or a list of {label, text, dir, witness_id}
    let titleHTML = "";
    if (Array.isArray(variant.title)) {
      titleHTML = variant.title.map(p => {
        const dir = p.dir ? ` dir="${escapeHtml(p.dir)}"` : "";
        return `<div class="vp-title-line witness-${escapeHtml(p.witness_id || "")}">`
             + `<span class="vp-title-label">${escapeHtml(p.label || "")}</span>`
             + `<span class="vp-title-text"${dir}>${escapeHtml(p.text || "")}</span>`
             + `</div>`;
      }).join("");
    } else if (variant.title) {
      titleHTML = `<h4 class="vp-title">${escapeHtml(variant.title)}</h4>`;
    }

    // Sigla chips — we don't know the full witness list here, so render any
    // attested ones; the apparatus view has the authoritative layout.
    const attested = Array.isArray(variant.witnesses) ? variant.witnesses : [];
    const chipsHTML = attested.map(wid =>
      `<span class="sigil-chip attested">${escapeHtml(wid)}</span>`
    ).join("");

    const type = variant.type || "";
    const label = variant.label || "";
    const summary = variant.summary || "";

    const params = new URLSearchParams(window.location.search);
    params.set("view", "apparatus");
    params.set("variant", variant.id);
    const jumpHref = window.location.pathname + "?" + params.toString() + "#variant-" + variant.id;

    return `
      <header class="vp-head">
        <span class="variant-type ${escapeHtml(type)} vp-type">${escapeHtml(type)}</span>
        <span class="vp-label">${escapeHtml(label)}</span>
      </header>
      ${chipsHTML ? `<div class="vp-witnesses">${chipsHTML}</div>` : ""}
      ${titleHTML ? `<div class="vp-title-block">${titleHTML}</div>` : ""}
      ${summary ? `<p class="vp-summary">${escapeHtml(summary)}</p>` : ""}
      <div class="vp-footer">
        <a class="vp-jump" href="${escapeHtml(jumpHref)}">Open in apparatus ›</a>
        <span class="vp-hint">Esc to close</span>
      </div>
    `;
  }

  function showVariantPopover(anchor, variantId) {
    closeVariantPopover();
    const variant = VARIANTS_BY_ID[variantId];
    if (!variant) return;
    const pop = document.createElement("div");
    pop.id = "active-variant-popover";
    pop.className = "variant-popover";
    pop.innerHTML = buildVariantPopoverHTML(variant);
    document.body.appendChild(pop);
    const r = anchor.getBoundingClientRect();
    // Prefer placing below; flip above if near viewport bottom
    const popH = pop.offsetHeight;
    const viewportH = window.innerHeight;
    let top = window.scrollY + r.bottom + 6;
    if (r.bottom + popH + 12 > viewportH && r.top - popH - 12 > 0) {
      top = window.scrollY + r.top - popH - 6;
    }
    let left = window.scrollX + r.left;
    // Nudge within viewport horizontally
    const popW = pop.offsetWidth;
    const maxLeft = window.scrollX + window.innerWidth - popW - 12;
    if (left > maxLeft) left = Math.max(window.scrollX + 12, maxLeft);
    pop.style.top = top + "px";
    pop.style.left = left + "px";

    setTimeout(() => {
      document.addEventListener("click", function outside(e) {
        if (!pop.contains(e.target)) {
          closeVariantPopover();
          document.removeEventListener("click", outside);
        }
      });
    }, 0);
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeVariantPopover();
  });

  // ── Tweaks panel ───────────────────────────────────────
  const tweaks = $("#tweaks");
  const params = new URLSearchParams(window.location.search);
  if (params.get("tweaks") === "1") {
    if (tweaks) tweaks.hidden = false;
  }

  // Keyboard shortcut: `.` toggles tweaks
  document.addEventListener("keydown", (e) => {
    if (e.key === "." && !e.target.matches("input, textarea")) {
      if (tweaks) tweaks.hidden = !tweaks.hidden;
    }
  });

  // Tweak buttons update the URL (server re-renders)
  $$(".tweak-seg").forEach(seg => {
    const key = seg.dataset.tweak;
    seg.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-value]");
      if (!btn) return;
      e.preventDefault();
      const value = btn.dataset.value;
      const p = new URLSearchParams(window.location.search);
      if (key === "view") p.set("view", value);
      else if (key === "theme") p.set("theme", value);
      else if (key === "rail") p.set("rail", value);
      p.set("tweaks", "1");
      window.location.search = p.toString();
    });
  });

  // ── Keyboard nav for verses ────────────────────────────
  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, textarea, select")) return;
    const pagers = $$(".pager-btn");
    if (e.key === "ArrowLeft" && pagers[0]) window.location.href = pagers[0].href;
    if (e.key === "ArrowRight" && pagers[1]) window.location.href = pagers[1].href;
  });

  // ── Verse jump selector ────────────────────────────────
  const jumpForm = $(".verse-jump");
  const bookIndexScript = document.getElementById("book-index-data");
  let BOOK_INDEX = {};
  if (bookIndexScript) {
    try { BOOK_INDEX = JSON.parse(bookIndexScript.textContent); }
    catch (_e) { BOOK_INDEX = {}; }
  }
  if (jumpForm) {
    const chSel = jumpForm.querySelector('select[name="ch"]');
    const vSel  = jumpForm.querySelector('select[name="v"]');

    function rebuildVerseOptions(chapter, preferredVerse) {
      const verses = BOOK_INDEX[chapter] || [];
      const prev = preferredVerse != null ? String(preferredVerse) : vSel.value;
      vSel.innerHTML = "";
      for (const v of verses) {
        const opt = document.createElement("option");
        opt.value = String(v);
        opt.textContent = String(v);
        if (String(v) === prev) opt.selected = true;
        vSel.appendChild(opt);
      }
      if (!vSel.value && verses.length) vSel.value = String(verses[0]);
    }

    chSel.addEventListener("change", () => {
      rebuildVerseOptions(chSel.value, 1);
    });

    jumpForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const book = jumpForm.dataset.book || "mark";
      const view = jumpForm.dataset.view || "interlinear";
      const ch = chSel.value;
      const v = vSel.value;
      if (!ch || !v) return;
      const params = new URLSearchParams();
      if (view && view !== "interlinear") params.set("view", view);
      const qs = params.toString();
      window.location.href = `/verse/${book}/${ch}/${v}${qs ? "?" + qs : ""}`;
    });
  }
})();

/* --- Click-to-open tooltips (our enrichment overlay, alongside hover-linking) --- */
document.addEventListener("click", function (e) {
  // Ignore clicks on variant tokens — those navigate to apparatus.
  const tok = e.target.closest(".tok");
  if (!tok) return;
  if (tok.dataset.variant) return; // variant-click = navigate, not tooltip
  const alignId = tok.dataset.align;
  if (!alignId) return;

  // Locate witness + verse context
  const card = tok.closest("[data-witness]");
  const witness = card ? card.dataset.witness : null;
  const row = tok.closest(".align-row, .inter-group");
  const path = window.location.pathname.match(/\/verse\/(\w+)\/(\d+)\/(\d+)/);
  if (!path) return;
  const [, , ch, v] = path;

  // Token index within the current witness for this verse:
  // We derive from position among sibling .tok[data-align] in the same witness.
  // Simpler: each token has data-idx on it in our rendering layer — but for
  // the designer templates we don't emit data-idx. We fallback to skipping
  // the tooltip if we can't resolve the index.
  const idx = tok.dataset.idx;
  if (idx === undefined) return;

  let endpoint = null;
  if (witness === "grk") endpoint = `/tooltip/greek/${ch}/${v}/${idx}`;
  else if (witness === "syr") endpoint = `/tooltip/peshitta/${ch}/${v}/${idx}`;
  if (!endpoint) return;

  fetch(endpoint).then(r => r.status === 200 ? r.text() : "").then(html => {
    if (!html) return;
    showTooltip(tok, html);
  });
});

function showTooltip(anchor, html) {
  const existing = document.getElementById("active-tooltip");
  if (existing) existing.remove();
  const tip = document.createElement("div");
  tip.id = "active-tooltip";
  tip.className = "tooltip";
  tip.innerHTML = html;
  document.body.appendChild(tip);
  const r = anchor.getBoundingClientRect();
  tip.style.left = (window.scrollX + r.left) + "px";
  tip.style.top  = (window.scrollY + r.bottom + 4) + "px";
  setTimeout(() => {
    document.addEventListener("click", function handler(e) {
      if (!tip.contains(e.target) && !anchor.contains(e.target)) {
        tip.remove();
        document.removeEventListener("click", handler);
      }
    });
  }, 0);
}

/* --- Search palette (⌘K / Ctrl+K) --- */
(function () {
  const overlay = document.getElementById("search-overlay");
  const input = document.getElementById("search-input");
  const results = document.getElementById("search-results");
  const trigger = document.getElementById("search-trigger");
  if (!overlay || !input || !results) return;

  let activeIdx = 0;
  let lastResults = [];
  let debounceTimer = null;

  function open() {
    overlay.hidden = false;
    requestAnimationFrame(() => input.focus());
    input.select();
  }
  function close() {
    overlay.hidden = true;
    results.innerHTML = "";
    lastResults = [];
    activeIdx = 0;
  }

  if (trigger) trigger.addEventListener("click", open);

  document.addEventListener("keydown", (e) => {
    const isMac = navigator.platform.toUpperCase().indexOf("MAC") >= 0;
    if ((isMac && e.metaKey && e.key === "k") || (!isMac && e.ctrlKey && e.key === "k")) {
      e.preventDefault();
      open();
      return;
    }
    if (overlay.hidden) return;
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (e.key === "ArrowDown") { e.preventDefault(); moveActive(+1); return; }
    if (e.key === "ArrowUp")   { e.preventDefault(); moveActive(-1); return; }
    if (e.key === "Enter" && lastResults[activeIdx]) {
      e.preventDefault();
      navigateTo(lastResults[activeIdx]);
    }
  });

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(runSearch, 120);
  });

  function runSearch() {
    const q = input.value.trim();
    if (!q) { results.innerHTML = ""; lastResults = []; return; }
    fetch("/search?q=" + encodeURIComponent(q) + "&limit=25")
      .then(r => r.json())
      .then(data => renderResults(data.results || []))
      .catch(() => renderResults([]));
  }

  function renderResults(list) {
    lastResults = list;
    activeIdx = 0;
    if (!list.length) {
      results.innerHTML = '<li class="empty">No matches.</li>';
      return;
    }
    results.innerHTML = list.map((r, i) =>
      `<li class="search-result${i === 0 ? ' active' : ''}" data-idx="${i}">
         <span class="sr-ref">${r.ref}</span>
         <span class="sr-snippet">${escapeHtml(r.snippet || "")}</span>
         <span class="sr-kind">${r.kind}</span>
       </li>`
    ).join("");
    results.querySelectorAll(".search-result").forEach(li => {
      li.addEventListener("click", () => {
        const i = parseInt(li.dataset.idx, 10);
        navigateTo(lastResults[i]);
      });
    });
  }

  function moveActive(delta) {
    const items = results.querySelectorAll(".search-result");
    if (!items.length) return;
    items[activeIdx]?.classList.remove("active");
    activeIdx = (activeIdx + delta + items.length) % items.length;
    items[activeIdx].classList.add("active");
    items[activeIdx].scrollIntoView({ block: "nearest" });
  }

  function navigateTo(r) {
    close();
    window.location.href = `/verse/mark/${r.chapter}/${r.verse}`;
  }

  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
    }[c]));
  }
})();
