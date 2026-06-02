// popup.js — controls the extension popup UI and persists settings

const $ = id => document.getElementById(id);

// ── State ─────────────────────────────────────────────────────────────────────
let settings = {
  mode:     "overlay",
  fontSize: 22,
  position: "bottom",
};

// ── Restore saved settings on open ───────────────────────────────────────────
chrome.storage.sync.get(
  ["mode", "fontSize", "position", "openaiKey", "anthropicKey"],
  (stored) => {
    if (stored.mode)     settings.mode     = stored.mode;
    if (stored.fontSize) settings.fontSize = stored.fontSize;
    if (stored.position) settings.position = stored.position;

    // Restore UI state
    applyModeUI(settings.mode);
    applyPosUI(settings.position);
    $("font-size").value    = settings.fontSize;
    $("size-preview").textContent = `${settings.fontSize}px`;

    if (stored.openaiKey)    $("openai-key").value    = stored.openaiKey;
    if (stored.anthropicKey) $("anthropic-key").value = stored.anthropicKey;
  }
);

// Restore toggle state
chrome.runtime.sendMessage({ type: "GET_STATE" }, (res) => {
  if (res?.active) setToggleUI(true);
});

// ── Main toggle ───────────────────────────────────────────────────────────────
$("main-toggle").addEventListener("change", async (e) => {
  const on = e.target.checked;

  if (on) {
    // Validate keys before starting
    const { openaiKey, anthropicKey } = await chrome.storage.sync.get(["openaiKey", "anthropicKey"]);
    if (!openaiKey || !anthropicKey) {
      showError("أدخل مفاتيح API أولاً ثم احفظها.");
      e.target.checked = false;
      return;
    }

    setStatus("connecting", "connecting...");

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    // Mount content script UI
    await chrome.tabs.sendMessage(tab.id, { type: "MOUNT" });
    await chrome.tabs.sendMessage(tab.id, { type: "SETTINGS_UPDATE", settings });

    // Start audio capture
    const res = await chrome.runtime.sendMessage({ type: "START_CAPTURE", tabId: tab.id });
    if (res?.ok) {
      setToggleUI(true);
      hideError();
    } else {
      showError(res?.error || "فشل في بدء الالتقاط.");
      e.target.checked = false;
      setStatus("inactive", "inactive");
    }

  } else {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    chrome.runtime.sendMessage({ type: "STOP_CAPTURE" });
    chrome.tabs.sendMessage(tab.id, { type: "UNMOUNT" });
    setToggleUI(false);
  }
});

// ── Mode buttons ──────────────────────────────────────────────────────────────
document.querySelectorAll(".mode-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    settings.mode = btn.dataset.mode;
    applyModeUI(settings.mode);
    saveSettings();
    pushSettingsToTab();

    // Show/hide position section for sidebar-only mode
    $("pos-section").style.display = settings.mode === "sidebar" ? "none" : "";
  });
});

function applyModeUI(mode) {
  document.querySelectorAll(".mode-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.mode === mode);
  });
  $("pos-section").style.display = mode === "sidebar" ? "none" : "";
}

// ── Position buttons ──────────────────────────────────────────────────────────
document.querySelectorAll(".pos-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    settings.position = btn.dataset.pos;
    applyPosUI(settings.position);
    saveSettings();
    pushSettingsToTab();
  });
});

function applyPosUI(pos) {
  document.querySelectorAll(".pos-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.pos === pos);
  });
}

// ── Font size slider ──────────────────────────────────────────────────────────
$("font-size").addEventListener("input", (e) => {
  settings.fontSize = parseInt(e.target.value);
  $("size-preview").textContent = `${settings.fontSize}px`;
  saveSettings();
  pushSettingsToTab();
});

// ── API key save ──────────────────────────────────────────────────────────────
$("save-keys").addEventListener("click", () => {
  const openaiKey    = $("openai-key").value.trim();
  const anthropicKey = $("anthropic-key").value.trim();

  if (!openaiKey || !anthropicKey) {
    showError("كلا المفتاحين مطلوبان.");
    return;
  }

  chrome.storage.sync.set({ openaiKey, anthropicKey }, () => {
    $("save-keys").textContent = "تم الحفظ ✓";
    setTimeout(() => { $("save-keys").textContent = "حفظ المفاتيح"; }, 1800);
    hideError();
  });
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function saveSettings() {
  chrome.storage.sync.set(settings);
}

async function pushSettingsToTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  chrome.tabs.sendMessage(tab.id, { type: "SETTINGS_UPDATE", settings }).catch(() => {});
}

function setToggleUI(on) {
  $("main-toggle").checked = on;
  if (on) {
    setStatus("active", "live · capturing audio");
    $("toggle-hint").textContent = "الترجمة الفورية نشطة";
  } else {
    setStatus("inactive", "inactive");
    $("toggle-hint").textContent = "اضغط لبدء الترجمة الفورية";
  }
}

function setStatus(state, text) {
  const dot = $("status-dot");
  dot.className = "dot" + (state === "active" ? " active" : state === "error" ? " error" : "");
  $("status-text").textContent = text;
}

function showError(msg) {
  const el = $("error-msg");
  el.textContent = msg;
  el.classList.add("visible");
}

function hideError() {
  $("error-msg").classList.remove("visible");
}
