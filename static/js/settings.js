/* Settings panel behavior. Three concerns:
   1. Interface language: server-roundtrip (sets cookie, redirects to /<lang>/path).
   2. Verse glosses: localStorage; toggles .gloss-row[hidden] live.
   3. Theme: localStorage; toggles document <html data-theme="..."> + <body class="dark">.

   Also: open/close panel (click cog, Esc, click outside).
*/
(function () {
  const trigger = document.getElementById("settings-trigger");
  const panel = document.getElementById("settings-panel");
  if (!trigger || !panel) return;   // panel not on this page (404 etc.)

  const SUPPORTED = ["en", "es", "zh-Hans", "zh-Hant"];
  const STORAGE_GLOSSES = "gloss_langs";
  const STORAGE_THEME = "theme";

  // ---- Open / close ----
  const closeBtn = panel.querySelector(".settings-close");
  function open()  { panel.hidden = false; }
  function close() { panel.hidden = true; }
  trigger.addEventListener("click", () => panel.hidden ? open() : close());
  if (closeBtn) closeBtn.addEventListener("click", close);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) close();
  });
  document.addEventListener("mousedown", (e) => {
    if (panel.hidden) return;
    if (e.target.closest("#settings-panel")) return;
    if (e.target.closest("#settings-trigger")) return;
    close();
  });

  // ---- Cookie + storage helpers ----
  function getCookie(name) {
    const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : null;
  }
  function setCookie(name, val, days) {
    const d = new Date();
    d.setTime(d.getTime() + (days || 365) * 86400000);
    document.cookie = name + "=" + encodeURIComponent(val) +
      ";expires=" + d.toUTCString() + ";path=/;SameSite=Lax";
  }
  function readGlosses() {
    try {
      const raw = localStorage.getItem(STORAGE_GLOSSES);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (e) { /* fall through */ }
    // Default: just the chrome lang.
    return [getCookie("lang") || "en"];
  }
  function writeGlosses(list) {
    try { localStorage.setItem(STORAGE_GLOSSES, JSON.stringify(list)); }
    catch (e) { /* ignore quota errors */ }
  }

  // ---- Initialize form state from storage ----
  const currentLang    = getCookie("lang") || "en";
  const currentTheme   = localStorage.getItem(STORAGE_THEME) || "light";
  const currentGlosses = readGlosses();

  panel.querySelectorAll('input[name="interface_lang"]').forEach((el) => {
    el.checked = (el.value === currentLang);
  });
  panel.querySelectorAll('input[name="gloss_lang"]').forEach((el) => {
    el.checked = currentGlosses.includes(el.value);
  });
  panel.querySelectorAll('input[name="theme"]').forEach((el) => {
    el.checked = (el.value === currentTheme);
  });

  // ---- Apply current state on page load ----
  applyTheme(currentTheme);
  applyGlosses(currentGlosses);

  // ---- Wire change handlers ----
  panel.querySelectorAll('input[name="interface_lang"]').forEach((el) => {
    el.addEventListener("change", () => {
      if (!el.checked) return;
      const newLang = el.value;
      setCookie("lang", newLang, 365);
      // Redirect to the matching path-prefix.
      const path = window.location.pathname;
      const stripped = stripLangPrefix(path);
      const next = (newLang === "en") ? stripped : ("/" + newLang + stripped);
      window.location.href = next + window.location.search + window.location.hash;
    });
  });

  panel.querySelectorAll('input[name="gloss_lang"]').forEach((el) => {
    el.addEventListener("change", () => {
      const checked = Array.from(
        panel.querySelectorAll('input[name="gloss_lang"]:checked')
      ).map((x) => x.value);
      writeGlosses(checked);
      applyGlosses(checked);
    });
  });

  panel.querySelectorAll('input[name="theme"]').forEach((el) => {
    el.addEventListener("change", () => {
      if (!el.checked) return;
      localStorage.setItem(STORAGE_THEME, el.value);
      applyTheme(el.value);
    });
  });

  function applyGlosses(list) {
    const rows = document.querySelectorAll(".gloss-row");
    rows.forEach((r) => {
      const lang = r.getAttribute("data-lang");
      r.hidden = !list.includes(lang);
    });
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.body.classList.toggle("dark", theme === "dark");
  }

  function stripLangPrefix(path) {
    for (const lang of SUPPORTED) {
      if (lang === "en") continue;
      if (path === "/" + lang || path.startsWith("/" + lang + "/")) {
        return path.slice(("/" + lang).length) || "/";
      }
    }
    return path;
  }
})();
