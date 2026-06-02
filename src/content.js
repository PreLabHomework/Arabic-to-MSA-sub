// content.js
// Injected into youtube.com/watch* pages.
// Creates: overlay subtitles (on video) + sidebar panel, togglable via popup.

(function () {
  if (window.__msaSubsLoaded) return;
  window.__msaSubsLoaded = true;

  // ── State ───────────────────────────────────────────────────────────────────
  let mode        = "overlay"; // "overlay" | "sidebar" | "both"
  let fontSize    = 22;        // px
  let position    = "bottom";  // "bottom" | "top"
  let subtitleTimeout = null;

  // ── DOM elements ────────────────────────────────────────────────────────────
  let overlayEl   = null;
  let sidebarEl   = null;
  let sidebarText = null;

  // ── Build overlay (on-video subtitle bar) ────────────────────────────────────
  function createOverlay() {
    if (overlayEl) return;

    overlayEl = document.createElement("div");
    overlayEl.id = "msa-overlay";
    overlayEl.setAttribute("dir", "rtl");

    // Mount inside the YouTube player container so it scales with fullscreen
    const player = document.querySelector("#movie_player") || document.body;
    player.appendChild(overlayEl);
  }

  // ── Build sidebar panel ──────────────────────────────────────────────────────
  function createSidebar() {
    if (sidebarEl) return;

    sidebarEl = document.createElement("div");
    sidebarEl.id = "msa-sidebar";

    const header = document.createElement("div");
    header.className = "msa-sidebar-header";
    header.innerHTML = `
      <span class="msa-sidebar-title">ترجمة فصحى</span>
      <span class="msa-sidebar-badge">MSA</span>
    `;

    sidebarText = document.createElement("div");
    sidebarText.className = "msa-sidebar-text";
    sidebarText.setAttribute("dir", "rtl");
    sidebarText.textContent = "في انتظار الكلام...";

    sidebarEl.appendChild(header);
    sidebarEl.appendChild(sidebarText);
    document.body.appendChild(sidebarEl);
  }

  // ── Show a subtitle ──────────────────────────────────────────────────────────
  function showSubtitle(text) {
    if (!text) return;

    // Overlay
    if (overlayEl && (mode === "overlay" || mode === "both")) {
      overlayEl.textContent = text;
      overlayEl.classList.add("msa-visible");
      overlayEl.style.fontSize = `${fontSize}px`;
      overlayEl.style[position === "top" ? "top" : "bottom"] = position === "top" ? "8%" : "10%";
      overlayEl.style[position === "top" ? "bottom" : "top"] = "auto";
    }

    // Sidebar
    if (sidebarText && (mode === "sidebar" || mode === "both")) {
      sidebarText.textContent = text;
      sidebarText.classList.add("msa-flash");
      setTimeout(() => sidebarText.classList.remove("msa-flash"), 400);
    }

    // Auto-hide overlay after 5s of silence
    clearTimeout(subtitleTimeout);
    subtitleTimeout = setTimeout(() => {
      overlayEl?.classList.remove("msa-visible");
    }, 5000);
  }

  // ── Apply settings from storage ──────────────────────────────────────────────
  function applySettings(settings) {
    mode     = settings.mode     ?? "overlay";
    fontSize = settings.fontSize ?? 22;
    position = settings.position ?? "bottom";

    // Show/hide elements based on mode
    if (overlayEl) {
      overlayEl.style.display = (mode === "sidebar") ? "none" : "";
    }
    if (sidebarEl) {
      sidebarEl.style.display = (mode === "overlay") ? "none" : "";
    }
  }

  // ── Message listener ─────────────────────────────────────────────────────────
  chrome.runtime.onMessage.addListener((msg) => {
    switch (msg.type) {
      case "SUBTITLE":
        showSubtitle(msg.text);
        break;

      case "SETTINGS_UPDATE":
        applySettings(msg.settings);
        break;

      case "MOUNT":
        createOverlay();
        createSidebar();
        chrome.storage.sync.get(
          ["mode", "fontSize", "position"],
          (s) => applySettings(s)
        );
        break;

      case "UNMOUNT":
        overlayEl?.remove();
        sidebarEl?.remove();
        overlayEl = sidebarEl = sidebarText = null;
        break;
    }
  });

  // ── Load settings on init ────────────────────────────────────────────────────
  chrome.storage.sync.get(["mode", "fontSize", "position"], (s) => {
    applySettings(s);
  });

})();
