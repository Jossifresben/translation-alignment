(function () {
  "use strict";

  // --- Click-to-open tooltips on .tok elements ---
  document.addEventListener("click", function (e) {
    const tok = e.target.closest(".tok");
    if (!tok) return;
    const tid = tok.dataset.tradition;
    const idx = tok.dataset.idx;
    const card = document.querySelector(".verse-card");
    if (!card) return;
    const ch = card.dataset.chapter;
    const v = card.dataset.verse;

    let endpoint = null;
    if (tid === "greek_nt") endpoint = `/tooltip/greek/${ch}/${v}/${idx}`;
    else if (tid === "peshitta") endpoint = `/tooltip/peshitta/${ch}/${v}/${idx}`;
    if (!endpoint) return;

    fetch(endpoint).then(r => {
      if (r.status !== 200) return "";
      return r.text();
    }).then(html => {
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
      }, { once: false });
    }, 0);
  }

  // --- Keyboard shortcuts ---
  document.addEventListener("keydown", function (e) {
    const tag = e.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA") return;
    switch (e.key) {
      case "ArrowRight": clickLink(".nav-next"); break;
      case "ArrowLeft":  clickLink(".nav-prev"); break;
      case "Escape":     closeTooltip(); break;
    }
  });

  function clickLink(selector) {
    const el = document.querySelector(selector);
    if (el && el.tagName === "A") el.click();
  }

  function closeTooltip() {
    const tip = document.getElementById("active-tooltip");
    if (tip) tip.remove();
  }
})();
