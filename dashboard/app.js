/**
 * Memory chat dashboard with session auth and thread sidebar.
 */

const API_BASE = "";
const MOBILE_BREAKPOINT = 1024;
const THEME_STORAGE_KEY = "memory_theme_v1";
const LAST_USERNAME_STORAGE_KEY = "memory_last_username_v1";
const APPEARANCE_STORAGE_KEY = "memory_appearance_v1";
const COOLER_SETTINGS_STORAGE_KEY = "memory_cooler_settings_v1";
const AVAILABLE_THEMES = ["default", "gpt", "project", "white", "mist", "dawn", "black", "sunset"];
const THEME_META_COLORS = {
  default: "#060910",
  gpt: "#050b09",
  project: "#050919",
  white: "#f4f8ff",
  mist: "#eef8fb",
  dawn: "#fff5ea",
  black: "#040507",
  sunset: "#13090a",
};
const APPEARANCE_DEFAULTS = {
  accent: "#0a84ff",
  opacity: 92,
  intensity: 100,
  radius: 100,
  font: 100,
  compact: false,
};
const COOLER_SETTINGS_DEFAULTS = {
  coolerMode: false,
  intensity: "balanced",
};
const COOLER_INTENSITY_PRESETS = {
  subtle: { glow: 0.14, blur: 0.92, brightness: 1.0, particles: 0.025 },
  balanced: { glow: 0.24, blur: 1.0, brightness: 1.05, particles: 0.04 },
  vivid: { glow: 0.36, blur: 1.15, brightness: 1.1, particles: 0.06 },
};

function getClientId() {
  return "default";
}

const CLIENT_ID = getClientId();

const state = {
  user: null,
  authView: "choice",
  theme: "default",
  themePickerOpen: false,
  appearanceOpen: false,
  coolerOpen: false,
  coolerSettings: { ...COOLER_SETTINGS_DEFAULTS },
  threads: [],
  activeThreadId: null,
  sidebarOpen: window.innerWidth > MOBILE_BREAKPOINT,
  messagesRequestSeq: 0,
  suspendAutoScroll: false,
};

const AUTH_VIEW_IDS = {
  choice: "auth-view-choice",
  signin: "auth-view-signin",
  signup: "auth-view-signup",
};

const AUTH_MESSAGE_IDS = {
  choice: "auth-choice-message",
  signin: "auth-signin-message",
  signup: "auth-signup-message",
};

function updateViewportHeightVar() {
  const baseHeight = window.innerHeight || document.documentElement.clientHeight;
  const vv = window.visualViewport;
  const vh = vv ? Math.round(vv.height) : baseHeight;
  if (!vh) return;
  document.documentElement.style.setProperty("--app-height", `${vh}px`);
  const messages = document.getElementById("chat-messages");
  if (messages && isNearBottom(messages, 180)) {
    requestAnimationFrame(() => {
      messages.scrollTop = messages.scrollHeight;
      updateScrollBottomButton();
    });
  }
}

function isMobileViewport() {
  return window.innerWidth <= MOBILE_BREAKPOINT;
}

function isNearBottom(container, threshold = 120) {
  if (!container) return true;
  const remaining = container.scrollHeight - container.scrollTop - container.clientHeight;
  return remaining <= threshold;
}

function focusComposer(options = {}) {
  const input = document.getElementById("chat-input");
  if (!input) return;
  if (isMobileViewport() && !options.allowMobile) return;
  try {
    input.focus({ preventScroll: true });
  } catch (_) {
    input.focus();
  }
}

function normalizeThemeName(raw) {
  const value = String(raw || "").trim().toLowerCase();
  return AVAILABLE_THEMES.includes(value) ? value : "default";
}

function loadSavedTheme() {
  try {
    return normalizeThemeName(localStorage.getItem(THEME_STORAGE_KEY));
  } catch (_) {
    return "default";
  }
}

function loadSavedUsername() {
  try {
    return String(localStorage.getItem(LAST_USERNAME_STORAGE_KEY) || "").trim();
  } catch (_) {
    return "";
  }
}

function saveLastUsername(username) {
  const value = String(username || "").trim();
  if (!value) return;
  try {
    localStorage.setItem(LAST_USERNAME_STORAGE_KEY, value);
  } catch (_) {
    // Ignore storage write failures.
  }
}

function hydrateUsernameInputs() {
  const saved = loadSavedUsername();
  if (!saved) return;
  const signInInput = document.getElementById("signin-username");
  const signUpInput = document.getElementById("signup-username");
  if (signInInput && !signInInput.value.trim()) signInInput.value = saved;
  if (signUpInput && !signUpInput.value.trim()) signUpInput.value = saved;
}

function paintThemeSelection(theme) {
  const activeTheme = normalizeThemeName(theme);
  document.querySelectorAll(".theme-swatch[data-theme]").forEach((btn) => {
    const isActive = btn.dataset.theme === activeTheme;
    btn.classList.toggle("is-active", isActive);
    btn.setAttribute("aria-checked", isActive ? "true" : "false");
  });
}

function applyTheme(theme, options = {}) {
  const nextTheme = normalizeThemeName(theme);
  const shouldPersist = options.persist !== false;
  state.theme = nextTheme;
  document.body.dataset.theme = nextTheme;
  document.documentElement.style.colorScheme =
    (nextTheme === "white" || nextTheme === "mist" || nextTheme === "dawn") ? "light" : "dark";
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  if (themeMeta) {
    themeMeta.setAttribute("content", THEME_META_COLORS[nextTheme] || THEME_META_COLORS.default);
  }
  paintThemeSelection(nextTheme);
  if (!shouldPersist) return;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  } catch (_) {
    // Ignore storage write failures.
  }
}

function setThemePickerOpen(open) {
  const toolbar = document.getElementById("theme-toolbar");
  const toggleBtn = document.getElementById("theme-toggle-btn");
  if (!toolbar || !toggleBtn) return;
  const nextOpen = !!open;
  state.themePickerOpen = nextOpen;
  toolbar.classList.toggle("is-open", nextOpen);
  toggleBtn.setAttribute("aria-expanded", nextOpen ? "true" : "false");
  toggleBtn.setAttribute("aria-label", nextOpen ? "Close background picker" : "Open background picker");
}

function initThemePicker() {
  const toolbar = document.getElementById("theme-toolbar");
  const toggleBtn = document.getElementById("theme-toggle-btn");
  if (!toolbar || !toggleBtn) return;

  toggleBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    setAppearancePanelOpen(false);
    setThemePickerOpen(!state.themePickerOpen);
  });

  document.querySelectorAll(".theme-swatch[data-theme]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      applyTheme(btn.dataset.theme);
      setThemePickerOpen(false);
    });
  });

  document.addEventListener("click", (e) => {
    if (!toolbar.contains(e.target)) {
      setThemePickerOpen(false);
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      setThemePickerOpen(false);
    }
  });

  applyTheme(loadSavedTheme(), { persist: false });
  setThemePickerOpen(false);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function hexToRgb(hex) {
  const raw = String(hex || "").trim().replace("#", "");
  if (!/^[a-fA-F0-9]{6}$/.test(raw)) return [10, 132, 255];
  return [
    parseInt(raw.slice(0, 2), 16),
    parseInt(raw.slice(2, 4), 16),
    parseInt(raw.slice(4, 6), 16),
  ];
}

function loadSavedAppearance() {
  try {
    const raw = localStorage.getItem(APPEARANCE_STORAGE_KEY);
    if (!raw) return { ...APPEARANCE_DEFAULTS };
    const parsed = JSON.parse(raw);
    return {
      accent: /^#[a-fA-F0-9]{6}$/.test(parsed.accent || "") ? parsed.accent : APPEARANCE_DEFAULTS.accent,
      opacity: clamp(Number(parsed.opacity) || APPEARANCE_DEFAULTS.opacity, 40, 100),
      intensity: clamp(Number(parsed.intensity) || APPEARANCE_DEFAULTS.intensity, 30, 130),
      radius: clamp(Number(parsed.radius) || APPEARANCE_DEFAULTS.radius, 80, 140),
      font: clamp(Number(parsed.font) || APPEARANCE_DEFAULTS.font, 90, 120),
      compact: Boolean(parsed.compact),
    };
  } catch (_) {
    return { ...APPEARANCE_DEFAULTS };
  }
}

function applyAppearance(appearance, options = {}) {
  const next = {
    accent: appearance.accent,
    opacity: clamp(Number(appearance.opacity), 40, 100),
    intensity: clamp(Number(appearance.intensity), 30, 130),
    radius: clamp(Number(appearance.radius), 80, 140),
    font: clamp(Number(appearance.font), 90, 120),
    compact: Boolean(appearance.compact),
  };
  const [r, g, b] = hexToRgb(next.accent);
  const root = document.documentElement;
  root.style.setProperty("--accent-user", next.accent);
  root.style.setProperty("--accent-user-rgb", `${r}, ${g}, ${b}`);
  root.style.setProperty("--surface-opacity", String(next.opacity / 100));
  root.style.setProperty("--bg-intensity", String(next.intensity / 100));
  root.style.setProperty("--radius-factor", String(next.radius / 100));
  root.style.setProperty("--font-scale", String(next.font / 100));
  document.body.classList.toggle("compact-ui", next.compact);
  if (options.persist !== false) {
    try {
      localStorage.setItem(APPEARANCE_STORAGE_KEY, JSON.stringify(next));
    } catch (_) {
      // Ignore storage write failures.
    }
  }
}

function setAppearancePanelOpen(open) {
  const toolbar = document.getElementById("appearance-toolbar");
  const toggle = document.getElementById("appearance-toggle-btn");
  if (!toolbar || !toggle) return;
  const nextOpen = !!open;
  state.appearanceOpen = nextOpen;
  toolbar.classList.toggle("is-open", nextOpen);
  toggle.setAttribute("aria-expanded", nextOpen ? "true" : "false");
}

function syncAppearanceControls(appearance) {
  const accent = document.getElementById("appearance-accent");
  const opacity = document.getElementById("appearance-opacity");
  const intensity = document.getElementById("appearance-intensity");
  const radius = document.getElementById("appearance-radius");
  const font = document.getElementById("appearance-font");
  const compact = document.getElementById("appearance-compact");
  if (accent) accent.value = appearance.accent;
  if (opacity) opacity.value = String(appearance.opacity);
  if (intensity) intensity.value = String(appearance.intensity);
  if (radius) radius.value = String(appearance.radius);
  if (font) font.value = String(appearance.font);
  if (compact) compact.checked = Boolean(appearance.compact);
}

function readAppearanceFromControls() {
  return {
    accent: (document.getElementById("appearance-accent") || {}).value || APPEARANCE_DEFAULTS.accent,
    opacity: Number((document.getElementById("appearance-opacity") || {}).value || APPEARANCE_DEFAULTS.opacity),
    intensity: Number((document.getElementById("appearance-intensity") || {}).value || APPEARANCE_DEFAULTS.intensity),
    radius: Number((document.getElementById("appearance-radius") || {}).value || APPEARANCE_DEFAULTS.radius),
    font: Number((document.getElementById("appearance-font") || {}).value || APPEARANCE_DEFAULTS.font),
    compact: Boolean((document.getElementById("appearance-compact") || {}).checked),
  };
}

function initAppearanceStudio() {
  const toolbar = document.getElementById("appearance-toolbar");
  const toggle = document.getElementById("appearance-toggle-btn");
  const reset = document.getElementById("appearance-reset-btn");
  if (!toolbar || !toggle || !reset) return;

  const saved = loadSavedAppearance();
  syncAppearanceControls(saved);
  applyAppearance(saved, { persist: false });
  setAppearancePanelOpen(false);

  const onChange = () => applyAppearance(readAppearanceFromControls());
  ["appearance-accent", "appearance-opacity", "appearance-intensity", "appearance-radius", "appearance-font", "appearance-compact"]
    .map((id) => document.getElementById(id))
    .filter(Boolean)
    .forEach((el) => {
      el.addEventListener("input", onChange);
      el.addEventListener("change", onChange);
    });

  toggle.addEventListener("click", (e) => {
    e.stopPropagation();
    setThemePickerOpen(false);
    setAppearancePanelOpen(!state.appearanceOpen);
  });

  reset.addEventListener("click", () => {
    syncAppearanceControls(APPEARANCE_DEFAULTS);
    applyAppearance(APPEARANCE_DEFAULTS);
  });

  document.addEventListener("click", (e) => {
    if (!toolbar.contains(e.target)) setAppearancePanelOpen(false);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setAppearancePanelOpen(false);
  });
}

function normalizeCoolerIntensity(raw) {
  const value = String(raw || "").trim().toLowerCase();
  return Object.prototype.hasOwnProperty.call(COOLER_INTENSITY_PRESETS, value) ? value : "balanced";
}

function loadCoolerSettings() {
  try {
    const raw = localStorage.getItem(COOLER_SETTINGS_STORAGE_KEY);
    if (!raw) return { ...COOLER_SETTINGS_DEFAULTS };
    const parsed = JSON.parse(raw);
    return {
      coolerMode: Boolean(parsed.coolerMode),
      intensity: normalizeCoolerIntensity(parsed.intensity),
    };
  } catch (_) {
    return { ...COOLER_SETTINGS_DEFAULTS };
  }
}

function applyCoolerSettings(settings, options = {}) {
  const next = {
    coolerMode: Boolean(settings.coolerMode),
    intensity: normalizeCoolerIntensity(settings.intensity),
  };
  state.coolerSettings = next;
  const preset = COOLER_INTENSITY_PRESETS[next.intensity];
  const root = document.documentElement;
  root.style.setProperty("--cooler-glow", String(preset.glow));
  root.style.setProperty("--cooler-blur", String(preset.blur));
  root.style.setProperty("--cooler-brightness", String(preset.brightness));
  root.style.setProperty("--cooler-particles", String(preset.particles));
  root.style.setProperty("--glow", String(preset.glow));
  root.style.setProperty("--blur-strength", String(preset.blur));
  root.style.setProperty("--shadow-strength", next.intensity === "subtle" ? "0.85" : next.intensity === "vivid" ? "1.22" : "1");
  document.body.classList.toggle("cooler-mode", next.coolerMode);
  document.body.classList.toggle("cooler-vivid", next.coolerMode && next.intensity === "vivid");

  const switchBtn = document.getElementById("cooler-mode-toggle");
  if (switchBtn) {
    switchBtn.classList.toggle("is-on", next.coolerMode);
    switchBtn.setAttribute("aria-checked", next.coolerMode ? "true" : "false");
  }
  document.querySelectorAll(".cooler-segment[data-intensity]").forEach((btn) => {
    const active = btn.dataset.intensity === next.intensity;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-checked", active ? "true" : "false");
  });

  if (options.persist !== false) {
    try {
      localStorage.setItem(COOLER_SETTINGS_STORAGE_KEY, JSON.stringify(next));
    } catch (_) {
      // Ignore localStorage failures.
    }
  }
}

function setCoolerDrawerOpen(open) {
  const drawer = document.getElementById("cooler-settings-drawer");
  const btn = document.getElementById("cooler-settings-btn");
  if (!drawer || !btn) return;
  const nextOpen = !!open;
  state.coolerOpen = nextOpen;
  document.body.classList.toggle("cooler-open", nextOpen);
  drawer.setAttribute("aria-hidden", nextOpen ? "false" : "true");
  btn.setAttribute("aria-expanded", nextOpen ? "true" : "false");
}

function buildShareableThemeLink() {
  try {
    const url = new URL(window.location.href);
    const data = {
      c: state.coolerSettings.coolerMode ? 1 : 0,
      i: state.coolerSettings.intensity,
      t: state.theme,
    };
    url.searchParams.set("theme_pack", btoa(JSON.stringify(data)));
    return url.toString();
  } catch (_) {
    return window.location.href;
  }
}

function applyThemePackFromUrl() {
  try {
    const url = new URL(window.location.href);
    const raw = url.searchParams.get("theme_pack");
    if (!raw) return;
    const data = JSON.parse(atob(raw));
    if (typeof data.t === "string") {
      applyTheme(data.t);
    }
    applyCoolerSettings({
      coolerMode: Boolean(data.c),
      intensity: normalizeCoolerIntensity(data.i),
    });
  } catch (_) {
    // Ignore malformed theme links.
  }
}

function initCoolerSettings() {
  const openBtn = document.getElementById("cooler-settings-btn");
  const closeBtn = document.getElementById("cooler-close-btn");
  const overlay = document.getElementById("cooler-overlay");
  const modeToggle = document.getElementById("cooler-mode-toggle");
  const intensityGroup = document.getElementById("cooler-intensity-group");
  const saveBtn = document.getElementById("cooler-save-btn");
  const resetBtn = document.getElementById("cooler-reset-btn");
  const shareBtn = document.getElementById("cooler-share-btn");
  if (!openBtn || !closeBtn || !overlay || !modeToggle || !intensityGroup || !saveBtn || !resetBtn || !shareBtn) return;

  const saved = loadCoolerSettings();
  applyCoolerSettings(saved, { persist: false });
  setCoolerDrawerOpen(false);

  openBtn.addEventListener("click", () => {
    setAppearancePanelOpen(false);
    setThemePickerOpen(false);
    setCoolerDrawerOpen(true);
  });
  closeBtn.addEventListener("click", () => setCoolerDrawerOpen(false));
  overlay.addEventListener("click", () => setCoolerDrawerOpen(false));

  modeToggle.addEventListener("click", () => {
    applyCoolerSettings({
      ...state.coolerSettings,
      coolerMode: !state.coolerSettings.coolerMode,
    }, { persist: false });
  });

  intensityGroup.addEventListener("click", (e) => {
    const btn = e.target.closest(".cooler-segment[data-intensity]");
    if (!btn) return;
    applyCoolerSettings({
      ...state.coolerSettings,
      intensity: btn.dataset.intensity,
    }, { persist: false });
  });

  saveBtn.addEventListener("click", () => {
    applyCoolerSettings(state.coolerSettings);
    showNotification("Theme saved", "info");
  });

  resetBtn.addEventListener("click", () => {
    applyCoolerSettings(COOLER_SETTINGS_DEFAULTS);
    showNotification("Theme reset", "info");
  });

  shareBtn.addEventListener("click", async () => {
    const link = buildShareableThemeLink();
    try {
      await navigator.clipboard.writeText(link);
      showNotification("Theme link copied", "info");
    } catch (_) {
      showNotification("Could not copy theme link", "error");
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setCoolerDrawerOpen(false);
  });
}

function getUserAvatarLetter() {
  const name = (state.user && state.user.username ? String(state.user.username) : "").trim();
  if (!name) return "U";
  return name.charAt(0).toUpperCase();
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function truncateText(text, max = 48) {
  const value = String(text || "").trim();
  if (value.length <= max) return value;
  return `${value.slice(0, max - 3).trimEnd()}...`;
}

function toTitleCase(text) {
  return String(text || "")
    .split(" ")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function cleanSentenceForTitle(raw) {
  const value = String(raw || "")
    .replace(/[`"'()[\]{}]/g, " ")
    .replace(/[^\w\s-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return value;
}

function buildSmartTitle(source, fallback = "Start a New Conversation") {
  const cleaned = cleanSentenceForTitle(source);
  if (!cleaned) return fallback;
  const stopwords = new Set([
    "a", "an", "and", "are", "be", "can", "for", "from", "get", "give", "help", "i", "in",
    "is", "it", "me", "my", "of", "on", "or", "please", "show", "tell", "that", "the", "to",
    "we", "what", "when", "where", "which", "with", "you", "your",
  ]);
  const words = cleaned
    .split(" ")
    .map((w) => w.toLowerCase())
    .filter((w) => w.length > 1 && !stopwords.has(w));
  const picked = words.length ? words : cleaned.split(" ").map((w) => w.toLowerCase());
  const compact = picked.slice(0, 6).join(" ").trim();
  const finalTitle = toTitleCase(compact);
  if (!finalTitle || /^new chat$/i.test(finalTitle)) return fallback;
  const count = finalTitle.split(" ").filter(Boolean).length;
  if (count < 3) {
    const padded = toTitleCase(picked.slice(0, 3).join(" "));
    return padded || fallback;
  }
  return finalTitle;
}

function looksGenericTitle(title) {
  const value = String(title || "").trim().toLowerCase();
  return !value || ["new chat", "chat", "conversation", "start", "hello", "hi", "hey"].includes(value);
}

function resolveThreadTitle(thread) {
  const fallback = "Start a New Conversation";
  const baseTitle = String((thread && thread.title) || "").trim();
  const source = String((thread && (thread.last_user_message || thread.last_message)) || "").trim();
  if (!source && !baseTitle) return fallback;
  if (!looksGenericTitle(baseTitle) && baseTitle.split(" ").length <= 6) {
    return toTitleCase(baseTitle);
  }
  return buildSmartTitle(source, fallback);
}

function formatThreadTime(ts) {
  const normalized = normalizeServerTimestamp(ts);
  if (!normalized) return "";
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

function getThreadIdFromUrl() {
  try {
    const url = new URL(window.location.href);
    const raw = url.searchParams.get("thread_id");
    if (!raw) return null;
    const id = Number(raw);
    return Number.isFinite(id) && id > 0 ? id : null;
  } catch (_) {
    return null;
  }
}

function setThreadIdInUrl(threadId) {
  try {
    const url = new URL(window.location.href);
    if (threadId) {
      url.searchParams.set("thread_id", String(threadId));
    } else {
      url.searchParams.delete("thread_id");
    }
    window.history.replaceState({}, "", url.toString());
  } catch (_) {
    // Ignore history update issues.
  }
}

async function shareThread(threadId) {
  const id = Number(threadId);
  if (!id) return;
  const thread = state.threads.find((t) => Number(t.id) === id);
  const safeTitle = (thread && thread.title) ? thread.title : "Memory chat";
  let shareUrl = window.location.href;
  try {
    const url = new URL(window.location.href);
    url.searchParams.set("thread_id", String(id));
    shareUrl = url.toString();
  } catch (_) {}

  if (navigator.share) {
    try {
      await navigator.share({
        title: `Chat: ${safeTitle}`,
        text: `Open chat: ${safeTitle}`,
        url: shareUrl,
      });
      showNotification("Chat shared", "info");
      return;
    } catch (_) {
      // Fallback to copy.
    }
  }
  try {
    await copyToClipboard(shareUrl);
    showNotification("Chat link copied", "info");
  } catch (_) {
    showNotification("Could not copy chat link", "error");
  }
}

async function copyToClipboard(text) {
  const value = String(text ?? "");
  if (!value) return;
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const ta = document.createElement("textarea");
  ta.value = value;
  ta.setAttribute("readonly", "true");
  ta.style.position = "absolute";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.select();
  const ok = document.execCommand("copy");
  ta.remove();
  if (!ok) throw new Error("copy_failed");
}

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE || ""}${path}`, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-Client-ID": CLIENT_ID,
      ...options.headers,
    },
    ...options,
  });
  const raw = await res.text();
  let data = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch (_) {
    data = { raw };
  }
  if (!res.ok) {
    const err = new Error(data.error || raw || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function smoothScrollToBottom(container, duration = 220) {
  const start = container.scrollTop;
  const end = container.scrollHeight - container.clientHeight;
  const distance = end - start;
  if (distance <= 0) return;
  const startTime = performance.now();
  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }
  function scroll(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    container.scrollTop = start + distance * easeOutCubic(progress);
    if (progress < 1) requestAnimationFrame(scroll);
  }
  requestAnimationFrame(scroll);
}

function animateAssistantText(element, text, onStep) {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reducedMotion || text.length > 320) {
    element.textContent = text;
    if (onStep) onStep();
    return;
  }
  let index = 0;
  const step = text.length > 180 ? 2 : 1;
  function tick() {
    index += step;
    element.textContent = text.slice(0, index);
    if (onStep && index % 6 === 0) onStep();
    if (index < text.length) {
      setTimeout(() => requestAnimationFrame(tick), 8);
    } else if (onStep) {
      onStep();
    }
  }
  tick();
}

function normalizeServerTimestamp(ts) {
  if (!ts) return "";
  const raw = String(ts).trim();
  if (!raw) return "";
  const hasTimezone = /(?:Z|[+\-]\d{2}:\d{2})$/i.test(raw);
  if (hasTimezone) return raw;
  if (/^\d{4}-\d{2}-\d{2}T/.test(raw)) return `${raw}Z`;
  return raw;
}

function formatMessageTime(ts) {
  const normalized = normalizeServerTimestamp(ts);
  if (!normalized) return "";
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function createMessageElement(role, content, createdAt, opts = {}) {
  const message = document.createElement("div");
  message.className = `message ${role}${opts.loading ? " loading" : ""}`;
  const avatar = role === "user" ? getUserAvatarLetter() : "M";
  const timeText = formatMessageTime(createdAt || new Date().toISOString());
  if (opts.loading) {
    message.innerHTML = `<div class="message-avatar">${avatar}</div><div class="message-body"><div class="message-content"><span class="typing-indicator" aria-label="Assistant is thinking"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></span></div></div>`;
    return message;
  }
  const actionRow =
    role === "user"
      ? `<div class="message-meta-row"><div class="message-meta">${timeText}</div><button type="button" class="message-copy-btn" aria-label="Copy your message">Copy</button></div>`
      : `<div class="message-meta">${timeText}</div>`;
  message.innerHTML = `
    <div class="message-avatar">${avatar}</div>
    <div class="message-body">
      <div class="message-content">${escapeHtml(content || "")}</div>
      ${actionRow}
    </div>
  `;
  return message;
}

function showNotification(message, type = "info") {
  const notification = document.createElement("div");
  notification.className = `notification ${type}`;
  notification.textContent = message;
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 12px 20px;
    background: ${type === "error" ? "#ff453a" : "#0a84ff"};
    color: white;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 500;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    z-index: 10000;
    opacity: 0;
    transform: translateY(-20px);
    transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
  `;
  document.body.appendChild(notification);
  setTimeout(() => {
    notification.style.opacity = "1";
    notification.style.transform = "translateY(0)";
  }, 10);
  setTimeout(() => {
    notification.style.opacity = "0";
    notification.style.transform = "translateY(-20px)";
    setTimeout(() => notification.remove(), 300);
  }, 2600);
}

function triggerRipple(event, element) {
  if (!element) return;
  const rect = element.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height) * 0.92;
  const ripple = document.createElement("span");
  ripple.className = "tap-ripple";
  ripple.style.width = `${size}px`;
  ripple.style.height = `${size}px`;
  ripple.style.left = `${event.clientX - rect.left - size / 2}px`;
  ripple.style.top = `${event.clientY - rect.top - size / 2}px`;
  element.appendChild(ripple);
  setTimeout(() => ripple.remove(), 520);
}

function supports3DEffects() {
  return (
    window.matchMedia("(hover: hover) and (pointer: fine)").matches &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function bind3DTilt(target) {
  if (!target || target.dataset.tiltBound === "1") return;
  target.dataset.tiltBound = "1";

  target.addEventListener("pointermove", (event) => {
    if (!supports3DEffects()) return;
    const rect = target.getBoundingClientRect();
    const px = (event.clientX - rect.left) / rect.width;
    const py = (event.clientY - rect.top) / rect.height;
    const rx = (0.5 - py) * 7.5;
    const ry = (px - 0.5) * 9;
    target.style.setProperty("--tilt-rx", `${rx.toFixed(2)}deg`);
    target.style.setProperty("--tilt-ry", `${ry.toFixed(2)}deg`);
  });

  target.addEventListener("pointerenter", () => {
    if (!supports3DEffects()) return;
    target.classList.add("is-tilting");
  });

  target.addEventListener("pointerleave", () => {
    target.classList.remove("is-tilting");
    target.style.setProperty("--tilt-rx", "0deg");
    target.style.setProperty("--tilt-ry", "0deg");
  });
}

function refresh3DTargets() {
  if (!supports3DEffects()) return;
  document.querySelectorAll(".thread-item, .welcome-card, .welcome-badge").forEach(bind3DTilt);
}

function clearAuthMessages() {
  Object.values(AUTH_MESSAGE_IDS).forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = "";
    el.className = "auth-message";
  });
}

function setAuthMessage(view, text, type = "") {
  const el = document.getElementById(AUTH_MESSAGE_IDS[view]);
  if (!el) return;
  el.textContent = text || "";
  el.className = `auth-message${type ? ` ${type}` : ""}`;
}

function setAuthBusy(busy) {
  document.querySelectorAll("#auth-screen input, #auth-screen button").forEach((el) => {
    el.disabled = busy;
  });
}

function focusAuthView(view) {
  if (view === "signin") {
    document.getElementById("signin-username").focus();
    return;
  }
  if (view === "signup") {
    document.getElementById("signup-username").focus();
    return;
  }
  const demoBtn = document.getElementById("go-demo");
  if (demoBtn) {
    demoBtn.focus();
    return;
  }
  document.getElementById("go-signin").focus();
}

function showAuthView(view, opts = {}) {
  if (!AUTH_VIEW_IDS[view]) return;
  state.authView = view;
  Object.entries(AUTH_VIEW_IDS).forEach(([name, id]) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (name === view) {
      el.classList.remove("is-hidden");
    } else {
      el.classList.add("is-hidden");
    }
  });
  if (opts.clearMessages) clearAuthMessages();
  if (opts.message) setAuthMessage(view, opts.message, opts.type || "");
  setTimeout(() => focusAuthView(view), 0);
}

function applySidebarState() {
  const app = document.getElementById("chat-app");
  const overlay = document.getElementById("sidebar-overlay");
  if (!app || !overlay) return;

  if (isMobileViewport()) {
    app.classList.remove("sidebar-collapsed");
    app.classList.toggle("sidebar-mobile-open", state.sidebarOpen);
    overlay.classList.toggle("is-hidden", !state.sidebarOpen);
  } else {
    app.classList.remove("sidebar-mobile-open");
    overlay.classList.add("is-hidden");
    app.classList.toggle("sidebar-collapsed", !state.sidebarOpen);
  }
}

function setSidebarOpen(open) {
  state.sidebarOpen = !!open;
  applySidebarState();
}

function toggleSidebar() {
  setSidebarOpen(!state.sidebarOpen);
}

function toggleApp(authenticated) {
  const authScreen = document.getElementById("auth-screen");
  const chatApp = document.getElementById("chat-app");
  document.body.classList.toggle("chat-open", !!authenticated);
  if (authenticated) {
    authScreen.classList.add("is-hidden");
    chatApp.classList.remove("is-hidden");
    state.sidebarOpen = !isMobileViewport();
    applySidebarState();
    focusComposer({ allowMobile: false });
  } else {
    chatApp.classList.add("is-hidden");
    authScreen.classList.remove("is-hidden");
  }
}

function setUserUI(user) {
  const userPill = document.getElementById("user-pill");
  userPill.textContent = `@${user.username}`;
}

function setServiceStatus(mode = "active") {
  const indicator = document.querySelector(".status-indicator");
  const statusText = indicator ? indicator.querySelector(".status-text") : null;
  if (!indicator || !statusText) return;
  if (mode === "degraded") {
    indicator.classList.add("degraded");
    statusText.textContent = "Limited";
    return;
  }
  indicator.classList.remove("degraded");
  statusText.textContent = "Active";
}

function updateHeaderThreadUI() {
  const welcomeSub = document.getElementById("welcome-sub");
  const input = document.getElementById("chat-input");

  if (welcomeSub) {
    welcomeSub.textContent = "Start a conversation and your important context will be carried forward.";
  }

  if (input) {
    input.placeholder = "Type a message…";
  }
}

function updateScrollBottomButton() {
  const container = document.getElementById("chat-messages");
  const btn = document.getElementById("scroll-bottom-btn");
  if (!container || !btn) return;
  const remaining = container.scrollHeight - container.scrollTop - container.clientHeight;
  btn.classList.toggle("is-hidden", remaining < 160);
}

function renderThreadLoadingState() {
  const container = document.getElementById("chat-messages");
  if (!container) return;
  state.suspendAutoScroll = true;
  container.classList.add("thread-switching");
  container.innerHTML = `
    <div class="thread-loading" aria-live="polite" aria-label="Loading messages">
      <div class="thread-loading-line w-72"></div>
      <div class="thread-loading-line w-56"></div>
      <div class="thread-loading-line w-64"></div>
    </div>
  `;
  updateScrollBottomButton();
}

function renderMessages(messages, options = {}) {
  const { animate = false, scroll = "instant" } = options;
  const container = document.getElementById("chat-messages");
  const welcome = document.getElementById("welcome");
  if (!container) return;
  const suspendDuringRender = !animate;
  if (suspendDuringRender) state.suspendAutoScroll = true;
  container.classList.remove("thread-switching");
  if (messages && messages.length > 0) {
    if (welcome) welcome.remove();
    container.innerHTML = "";
    messages.forEach((m, index) => {
      const node = createMessageElement(m.role, m.content, m.created_at);
      if (animate) {
        node.style.animationDelay = `${index * 0.03}s`;
      } else {
        node.classList.add("static");
      }
      container.appendChild(node);
    });
    if (scroll === "smooth") {
      smoothScrollToBottom(container, 220);
    } else if (scroll === "instant") {
      container.scrollTop = container.scrollHeight;
    }
  } else if (!welcome) {
    container.innerHTML = `
      <div class="welcome" id="welcome">
        <div class="welcome-badge">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
            <path d="M2 17l10 5 10-5"></path>
            <path d="M2 12l10 5 10-5"></path>
          </svg>
        </div>
        <h1 class="welcome-title">Memory Workspace</h1>
        <p class="welcome-sub" id="welcome-sub">Start a conversation and your important context will be carried forward.</p>
        <div class="welcome-highlights" aria-label="Workspace highlights">
          <div class="welcome-card">
            <span class="welcome-card-title">Partitioned Memory</span>
            <span class="welcome-card-sub">User, thread, and category aware retrieval.</span>
          </div>
          <div class="welcome-card">
            <span class="welcome-card-title">Smart Titles</span>
            <span class="welcome-card-sub">Chats auto-name from meaningful user intent.</span>
          </div>
          <div class="welcome-card">
            <span class="welcome-card-title">Low-Latency Recall</span>
            <span class="welcome-card-sub">Fast context injection with ranked top-k memory.</span>
          </div>
        </div>
      </div>
    `;
  }
  refresh3DTargets();
  updateHeaderThreadUI();
  if (suspendDuringRender) {
    requestAnimationFrame(() => {
      state.suspendAutoScroll = false;
      updateScrollBottomButton();
    });
  } else {
    updateScrollBottomButton();
  }
}

function sortThreadsInPlace() {
  state.threads.sort((a, b) => {
    const ta = new Date(normalizeServerTimestamp(a.updated_at || a.created_at || "")).getTime() || 0;
    const tb = new Date(normalizeServerTimestamp(b.updated_at || b.created_at || "")).getTime() || 0;
    return tb - ta;
  });
}

function upsertThread(thread) {
  if (!thread || typeof thread.id !== "number") return;
  const idx = state.threads.findIndex((t) => t.id === thread.id);
  if (idx >= 0) {
    state.threads[idx] = { ...state.threads[idx], ...thread };
  } else {
    state.threads.unshift(thread);
  }
  sortThreadsInPlace();
}

function renderThreadList() {
  const list = document.getElementById("thread-list");
  if (!list) return;

  if (!state.threads.length) {
    list.innerHTML = `<div class="thread-empty">No chats yet. Start a new one.</div>`;
    return;
  }

  list.innerHTML = state.threads
    .map((thread, index) => {
      const active = thread.id === state.activeThreadId;
      const resolvedTitle = resolveThreadTitle(thread);
      const title = escapeHtml(resolvedTitle);
      const time = formatThreadTime(thread.last_message_at || thread.updated_at);
      const count = Number(thread.message_count || 0);
      const previewSource = String(thread.last_message || "No messages yet").replace(/\s+/g, " ").trim();
      const preview = escapeHtml(previewSource || "No messages yet");
      const meta = [time, count > 0 ? `${count} msg${count === 1 ? "" : "s"}` : "empty"]
        .filter(Boolean)
        .join(" · ");
      return `
        <div class="thread-item${active ? " active" : ""}" style="--thread-index:${index}">
          <button class="thread-main" type="button" data-thread-id="${thread.id}" aria-label="Open ${title}">
            <div class="thread-title-row"><span class="thread-title">${title}</span></div>
            <div class="thread-meta">${escapeHtml(meta)}</div>
            <div class="thread-preview">${preview}</div>
          </button>
          <div class="thread-actions">
            <button class="thread-more-btn" type="button" data-thread-id="${thread.id}" aria-label="Open actions for ${title}">•••</button>
            <div class="thread-menu" role="menu" aria-label="Thread actions">
              <button class="thread-menu-item thread-menu-share" type="button" data-thread-id="${thread.id}" role="menuitem">
                Share chat
              </button>
              <button class="thread-menu-item thread-menu-delete" type="button" data-thread-id="${thread.id}" role="menuitem">
                Delete chat
              </button>
            </div>
          </div>
        </div>
      `;
    })
    .join("");
  refresh3DTargets();
}

async function loadThreads(options = {}) {
  const { preferThreadId = null, preserveSelection = true } = options;
  const data = await api("/api/threads");
  state.threads = (data.threads || []).filter((t) => !t.is_temporary);

  if (!state.threads.length) {
    const created = await api("/api/threads", {
      method: "POST",
      body: JSON.stringify({ temporary: false }),
    });
    state.threads = created.thread ? [created.thread].filter((t) => !t.is_temporary) : [];
  }

  let nextId = null;
  if (preferThreadId) {
    nextId = Number(preferThreadId);
  } else if (preserveSelection && state.activeThreadId) {
    nextId = state.activeThreadId;
  }

  if (!nextId || !state.threads.some((t) => t.id === nextId)) {
    nextId = state.threads[0] ? state.threads[0].id : null;
  }

  state.activeThreadId = nextId;
  setThreadIdInUrl(state.activeThreadId);
  renderThreadList();
  updateHeaderThreadUI();
  await loadMessages();
}

async function createThread() {
  const data = await api("/api/threads", {
    method: "POST",
    body: JSON.stringify({ temporary: false }),
  });
  if (!data.thread) return;
  if (data.thread.is_temporary) return;
  upsertThread(data.thread);
  state.activeThreadId = data.thread.id;
  setThreadIdInUrl(state.activeThreadId);
  renderThreadList();
  renderMessages([]);
  updateHeaderThreadUI();
  if (isMobileViewport()) setSidebarOpen(false);
  focusComposer({ allowMobile: false });
}

async function selectThread(threadId) {
  const id = Number(threadId);
  if (!id || state.activeThreadId === id) {
    if (isMobileViewport()) setSidebarOpen(false);
    return;
  }
  state.activeThreadId = id;
  setThreadIdInUrl(state.activeThreadId);
  renderThreadList();
  updateHeaderThreadUI();
  renderThreadLoadingState();
  await loadMessages();
  if (isMobileViewport()) setSidebarOpen(false);
}

async function deleteThread(threadId) {
  const id = Number(threadId);
  if (!id) return;
  const data = await api(`/api/threads/${id}`, { method: "DELETE" });
  state.threads = (data.threads || []).filter((t) => !t.is_temporary);
  state.activeThreadId = data.next_thread_id || (state.threads[0] ? state.threads[0].id : null);
  if (state.activeThreadId && !state.threads.some((t) => t.id === state.activeThreadId)) {
    state.activeThreadId = state.threads[0] ? state.threads[0].id : null;
  }
  setThreadIdInUrl(state.activeThreadId);
  renderThreadList();
  updateHeaderThreadUI();
  await loadMessages();
  showNotification("Chat deleted", "info");
}

async function loadMessages() {
  if (!state.user || !state.activeThreadId) {
    renderMessages([]);
    return;
  }
  const threadId = Number(state.activeThreadId);
  const requestSeq = ++state.messagesRequestSeq;
  try {
    const data = await api(`/api/messages?thread_id=${encodeURIComponent(threadId)}`);
    if (requestSeq !== state.messagesRequestSeq || threadId !== Number(state.activeThreadId)) {
      return;
    }
    if (data.thread) upsertThread(data.thread);
    renderThreadList();
    renderMessages(data.messages || [], {
      animate: false,
      scroll: "instant",
    });
  } catch (e) {
    if (requestSeq !== state.messagesRequestSeq || threadId !== Number(state.activeThreadId)) {
      return;
    }
    if (e.status === 401) {
      state.user = null;
      state.threads = [];
      state.activeThreadId = null;
      toggleApp(false);
      showAuthView("choice", {
        clearMessages: true,
        message: "Session required. Choose Sign In or Sign Up.",
        type: "error",
      });
      return;
    }
    renderMessages([], { animate: false, scroll: "instant" });
    showNotification("Unable to load messages", "error");
  }
}

async function sendMessage(text) {
  if (!state.user) {
    toggleApp(false);
    showAuthView("choice", { message: "Please sign in first.", type: "error" });
    return;
  }
  if (!state.activeThreadId) {
    showNotification("Create or select a chat first", "error");
    return;
  }

  const input = document.getElementById("chat-input");
  const btn = document.getElementById("send-btn");
  const container = document.getElementById("chat-messages");
  const welcome = document.getElementById("welcome");
  const threadIdAtSend = Number(state.activeThreadId);

  input.value = "";
  autoResizeComposer(input);
  input.disabled = true;
  btn.disabled = true;

  if (welcome) welcome.remove();

  const userMessage = createMessageElement("user", text, new Date().toISOString());
  container.appendChild(userMessage);
  smoothScrollToBottom(container, 240);

  const loadingMessage = createMessageElement("assistant", "", null, { loading: true });
  container.appendChild(loadingMessage);
  smoothScrollToBottom(container, 240);

  try {
    const data = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        message: text,
        thread_id: threadIdAtSend,
      }),
    });

    if (data.thread) {
      upsertThread(data.thread);
    } else {
      upsertThread({
        id: threadIdAtSend,
        updated_at: new Date().toISOString(),
      });
    }
    renderThreadList();
    if (threadIdAtSend !== Number(state.activeThreadId)) {
      return;
    }

    loadingMessage.remove();

    const assistantMessage = createMessageElement("assistant", "", new Date().toISOString());
    const replyText = data.reply || "No response.";
    const degradedReply = Boolean(data.degraded) || /temporarily unavailable|can't connect to the ai/i.test(replyText);
    setServiceStatus(degradedReply ? "degraded" : "active");
    container.appendChild(assistantMessage);
    const content = assistantMessage.querySelector(".message-content");
    animateAssistantText(content, replyText, () => smoothScrollToBottom(container, 160));
    smoothScrollToBottom(container, 280);
    updateHeaderThreadUI();
  } catch (e) {
    if (threadIdAtSend !== Number(state.activeThreadId)) {
      return;
    }
    loadingMessage.remove();
    if (e.status === 401) {
      state.user = null;
      state.threads = [];
      state.activeThreadId = null;
      toggleApp(false);
      showAuthView("choice", {
        clearMessages: true,
        message: "Session expired. Sign in again.",
        type: "error",
      });
      return;
    }
    const errorMessage = createMessageElement(
      "assistant",
      "Could not reach backend.",
      new Date().toISOString()
    );
    setServiceStatus("degraded");
    const errContent = errorMessage.querySelector(".message-content");
    if (errContent) errContent.style.color = "#ff7b72";
    container.appendChild(errorMessage);
    showNotification("Message failed", "error");
  } finally {
    input.disabled = false;
    autoResizeComposer(input);
    btn.disabled = input.value.trim().length === 0;
    focusComposer({ allowMobile: true });
    updateScrollBottomButton();
  }
}

function handleInput(e) {
  autoResizeComposer(e.target);
  const btn = document.getElementById("send-btn");
  const hasText = e.target.value.trim().length > 0;
  btn.disabled = !hasText;
  btn.classList.toggle("is-ready", hasText);
}

function handleSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (text && !input.disabled) sendMessage(text);
}

function handleKeyDown(e) {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    const text = e.target.value.trim();
    if (text && !e.target.disabled) sendMessage(text);
  }
}

function autoResizeComposer(inputEl) {
  if (!inputEl) return;
  inputEl.style.height = "auto";
  const nextHeight = Math.min(inputEl.scrollHeight, 128);
  inputEl.style.height = `${Math.max(nextHeight, 22)}px`;
}

function addTypingIndicatorStyles() {
  const style = document.createElement("style");
  style.textContent = `
    .typing-indicator {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      line-height: 1;
    }
    .typing-dot {
      width: 7px;
      height: 7px;
      border-radius: 999px;
      background: rgba(220, 226, 244, 0.88);
      display: block;
      animation: typingPulse 1.2s infinite ease-in-out;
      opacity: 0.35;
      transform: translateY(0);
    }
    .typing-dot:nth-child(1) { animation-delay: 0s; }
    .typing-dot:nth-child(2) { animation-delay: 0.18s; }
    .typing-dot:nth-child(3) { animation-delay: 0.36s; }
    @keyframes typingPulse {
      0%, 80%, 100% { transform: translateY(0); opacity: 0.32; }
      40% { transform: translateY(-3px); opacity: 1; }
    }
  `;
  document.head.appendChild(style);
}

function addKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (state.user) {
        focusComposer({ allowMobile: true });
      } else {
        focusAuthView(state.authView);
      }
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b" && state.user) {
      e.preventDefault();
      toggleSidebar();
    }
  });
}

function enhanceScrollBehavior() {
  const container = document.getElementById("chat-messages");
  const scrollBtn = document.getElementById("scroll-bottom-btn");
  if (!container) return;
  let isUserScrolling = false;
  let scrollTimeout;

  container.addEventListener("scroll", () => {
    isUserScrolling = true;
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(() => {
      isUserScrolling = false;
    }, 150);
    updateScrollBottomButton();
  });

  const observer = new MutationObserver(() => {
    updateScrollBottomButton();
    if (state.suspendAutoScroll) return;
    if (!isUserScrolling) {
      if (isNearBottom(container, 100)) smoothScrollToBottom(container);
    }
  });
  observer.observe(container, { childList: true, subtree: true });

  if (scrollBtn) {
    scrollBtn.addEventListener("click", () => smoothScrollToBottom(container, 220));
  }
}

async function loginWithCredentials(username, password) {
  const data = await api("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  saveLastUsername(username);
  state.user = data.user;
  setUserUI(data.user);
  clearAuthMessages();
  toggleApp(true);
  await loadThreads({ preferThreadId: data.default_thread_id, preserveSelection: false });
}

async function registerWithCredentials(username, password) {
  const data = await api("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  saveLastUsername(username);
  state.user = data.user;
  setUserUI(data.user);
  clearAuthMessages();
  toggleApp(true);
  showNotification("Account created", "info");
  await loadThreads({ preferThreadId: data.default_thread_id, preserveSelection: false });
}

async function loginWithDemoAccount() {
  const data = await api("/api/auth/demo", {
    method: "POST",
    body: JSON.stringify({}),
  });
  state.user = data.user;
  setUserUI(data.user);
  clearAuthMessages();
  toggleApp(true);
  showNotification("Live demo ready", "info");
  await loadThreads({ preferThreadId: data.default_thread_id, preserveSelection: false });
}

async function handleDemoLogin() {
  setAuthBusy(true);
  setAuthMessage("choice", "Starting live demo...");
  try {
    await loginWithDemoAccount();
  } catch (err) {
    setAuthMessage("choice", err.message || "Could not start demo.", "error");
  } finally {
    setAuthBusy(false);
  }
}

async function handleSignInSubmit(e) {
  e.preventDefault();
  const username = document.getElementById("signin-username").value.trim();
  const password = document.getElementById("signin-password").value.trim();
  if (!username || !password) {
    setAuthMessage("signin", "Username and password are required.", "error");
    return;
  }
  setAuthBusy(true);
  setAuthMessage("signin", "Signing in...");
  try {
    await loginWithCredentials(username, password);
  } catch (err) {
    setAuthMessage("signin", err.message || "Sign in failed.", "error");
  } finally {
    setAuthBusy(false);
  }
}

async function handleSignUpSubmit(e) {
  e.preventDefault();
  const username = document.getElementById("signup-username").value.trim();
  const password = document.getElementById("signup-password").value.trim();
  const confirm = document.getElementById("signup-confirm-password").value.trim();
  if (!username || !password || !confirm) {
    setAuthMessage("signup", "All fields are required.", "error");
    return;
  }
  if (password !== confirm) {
    setAuthMessage("signup", "Passwords do not match.", "error");
    return;
  }
  setAuthBusy(true);
  setAuthMessage("signup", "Creating account...");
  try {
    await registerWithCredentials(username, password);
  } catch (err) {
    setAuthMessage("signup", err.message || "Sign up failed.", "error");
  } finally {
    setAuthBusy(false);
  }
}

async function handleLogout() {
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch (_) {
    // Ignore network errors while clearing local UI state.
  }
  applySignedOutState("Logged out.", "success");
}

function applySignedOutState(message = "", type = "success") {
  state.user = null;
  state.threads = [];
  state.activeThreadId = null;
  setThreadIdInUrl(null);
  document.getElementById("signin-password").value = "";
  document.getElementById("signup-password").value = "";
  document.getElementById("signup-confirm-password").value = "";
  toggleApp(false);
  renderMessages([]);
  renderThreadList();
  showAuthView("choice", { clearMessages: true, message, type });
}

function setDeleteAccountModalOpen(open) {
  const overlay = document.getElementById("delete-account-overlay");
  if (!overlay) return;
  const shouldOpen = Boolean(open);
  overlay.hidden = !shouldOpen;
  document.body.classList.toggle("danger-modal-open", shouldOpen);
  if (shouldOpen) {
    const input = document.getElementById("delete-account-confirm-input");
    if (input) input.focus();
  }
}

function resetDeleteAccountModal() {
  const confirmInput = document.getElementById("delete-account-confirm-input");
  const passwordInput = document.getElementById("delete-account-password-input");
  const consentInput = document.getElementById("delete-account-consent-input");
  const error = document.getElementById("delete-account-error");
  const confirmBtn = document.getElementById("delete-account-confirm-btn");
  if (confirmInput) confirmInput.value = "";
  if (passwordInput) passwordInput.value = "";
  if (consentInput) consentInput.checked = false;
  if (error) error.textContent = "";
  if (confirmBtn) confirmBtn.disabled = true;
}

function updateDeleteAccountActionState() {
  const confirmInput = document.getElementById("delete-account-confirm-input");
  const passwordInput = document.getElementById("delete-account-password-input");
  const consentInput = document.getElementById("delete-account-consent-input");
  const confirmBtn = document.getElementById("delete-account-confirm-btn");
  if (!confirmBtn) return;
  const ready =
    String((confirmInput && confirmInput.value) || "").trim().toUpperCase() === "DELETE" &&
    String((passwordInput && passwordInput.value) || "").trim().length > 0 &&
    Boolean(consentInput && consentInput.checked);
  confirmBtn.disabled = !ready;
}

function openDeleteAccountModal() {
  resetDeleteAccountModal();
  setDeleteAccountModalOpen(true);
}

function closeDeleteAccountModal() {
  setDeleteAccountModalOpen(false);
}

async function handleDeleteAccountConfirm() {
  const confirmInput = document.getElementById("delete-account-confirm-input");
  const passwordInput = document.getElementById("delete-account-password-input");
  const error = document.getElementById("delete-account-error");
  const confirmBtn = document.getElementById("delete-account-confirm-btn");
  const consentInput = document.getElementById("delete-account-consent-input");
  const confirmation = String((confirmInput && confirmInput.value) || "").trim();
  const password = String((passwordInput && passwordInput.value) || "").trim();
  if (error) error.textContent = "";

  if (confirmation.toUpperCase() !== "DELETE") {
    if (error) error.textContent = "Type DELETE to confirm.";
    return;
  }
  if (!password) {
    if (error) error.textContent = "Password is required.";
    return;
  }
  if (!Boolean(consentInput && consentInput.checked)) {
    if (error) error.textContent = "Please acknowledge the warning first.";
    return;
  }
  if (confirmBtn && confirmBtn.disabled) return;

  if (confirmBtn) confirmBtn.disabled = true;
  try {
    await api("/api/auth/account", {
      method: "DELETE",
      body: JSON.stringify({
        confirmation: "DELETE",
        password,
      }),
    });
    closeDeleteAccountModal();
    applySignedOutState("Account deleted permanently.", "success");
    showNotification("Account deleted", "info");
  } catch (err) {
    if (error) error.textContent = err.message || "Could not delete account.";
  } finally {
    if (confirmBtn) confirmBtn.disabled = false;
  }
}

async function bootstrapAuthState() {
  try {
    const data = await api("/api/auth/me");
    if (data.authenticated && data.user) {
      state.user = data.user;
      setUserUI(data.user);
      toggleApp(true);
      const preferredFromUrl = getThreadIdFromUrl();
      await loadThreads({
        preferThreadId: preferredFromUrl || data.default_thread_id,
        preserveSelection: false,
      });
      return;
    }
  } catch (_) {
    // Fallback to auth choice.
  }
  state.user = null;
  state.threads = [];
  state.activeThreadId = null;
  toggleApp(false);
  showAuthView("choice", { clearMessages: true });
}

function initThreadInteractions() {
  const threadList = document.getElementById("thread-list");
  const newChatBtn = document.getElementById("new-chat-btn");
  const sidebarToggleBtn = document.getElementById("sidebar-toggle-btn");
  const sidebarCollapseBtn = document.getElementById("sidebar-collapse-btn");
  const sidebarOverlay = document.getElementById("sidebar-overlay");
  const closeThreadMenus = (exceptItem = null) => {
    document.querySelectorAll(".thread-item.menu-open").forEach((item) => {
      if (item !== exceptItem) item.classList.remove("menu-open");
    });
  };

  if (threadList) {
    threadList.addEventListener("click", async (e) => {
      const shareMenuBtn = e.target.closest(".thread-menu-share");
      if (shareMenuBtn) {
        e.preventDefault();
        e.stopPropagation();
        const threadId = Number(shareMenuBtn.dataset.threadId);
        closeThreadMenus();
        await shareThread(threadId);
        return;
      }

      const deleteMenuBtn = e.target.closest(".thread-menu-delete");
      if (deleteMenuBtn) {
        e.preventDefault();
        e.stopPropagation();
        const threadId = Number(deleteMenuBtn.dataset.threadId);
        closeThreadMenus();
        try {
          await deleteThread(threadId);
        } catch (err) {
          showNotification(err.message || "Failed to delete chat", "error");
        }
        return;
      }

      const moreBtn = e.target.closest(".thread-more-btn");
      if (moreBtn) {
        e.preventDefault();
        e.stopPropagation();
        const threadItem = moreBtn.closest(".thread-item");
        if (!threadItem) return;
        const willOpen = !threadItem.classList.contains("menu-open");
        closeThreadMenus(threadItem);
        threadItem.classList.toggle("menu-open", willOpen);
        return;
      }

      closeThreadMenus();
      const openBtn = e.target.closest(".thread-main");
      if (!openBtn) return;
      triggerRipple(e, openBtn);
      const threadId = Number(openBtn.dataset.threadId);
      try {
        await selectThread(threadId);
      } catch (err) {
        showNotification(err.message || "Failed to load chat", "error");
      }
    });
  }

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".thread-actions")) {
      closeThreadMenus();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeThreadMenus();
    }
  });

  newChatBtn.addEventListener("click", async (e) => {
    triggerRipple(e, newChatBtn);
    try {
      await createThread();
    } catch (err) {
      showNotification(err.message || "Could not create chat", "error");
    }
  });

  sidebarToggleBtn.addEventListener("click", () => toggleSidebar());
  sidebarCollapseBtn.addEventListener("click", () => setSidebarOpen(false));
  sidebarOverlay.addEventListener("click", () => setSidebarOpen(false));

  window.addEventListener("resize", () => {
    updateViewportHeightVar();
    if (!state.user) return;
    if (!isMobileViewport() && state.sidebarOpen === false) {
      // Keep explicit collapsed state on desktop.
      applySidebarState();
      return;
    }
    if (isMobileViewport() && state.sidebarOpen === true) {
      applySidebarState();
      return;
    }
    applySidebarState();
  });
}

function initMessageActions() {
  const container = document.getElementById("chat-messages");
  if (!container) return;
  container.addEventListener("click", async (e) => {
    const copyBtn = e.target.closest(".message-copy-btn");
    if (!copyBtn) return;
    const message = copyBtn.closest(".message.user");
    const content = message ? message.querySelector(".message-content") : null;
    const text = content ? content.textContent || "" : "";
    if (!text.trim()) return;
    try {
      await copyToClipboard(text);
      copyBtn.textContent = "Copied";
      showNotification("Message copied", "info");
      setTimeout(() => {
        copyBtn.textContent = "Copy";
      }, 1100);
    } catch (_) {
      showNotification("Could not copy message", "error");
    }
  });
}

function init() {
  updateViewportHeightVar();
  closeDeleteAccountModal();
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", updateViewportHeightVar);
    window.visualViewport.addEventListener("scroll", updateViewportHeightVar);
  }
  window.addEventListener("orientationchange", () => {
    setTimeout(updateViewportHeightVar, 140);
  });
  initThemePicker();
  initAppearanceStudio();
  initCoolerSettings();
  applyThemePackFromUrl();
  addTypingIndicatorStyles();
  addKeyboardShortcuts();
  enhanceScrollBehavior();
  setServiceStatus("active");

  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("send-btn");
  const logoutBtn = document.getElementById("logout-btn");
  const openDeleteAccountBtn = document.getElementById("open-delete-account-btn");
  const drawerDeleteAccountBtn = document.getElementById("drawer-delete-account-btn");
  const deleteAccountOverlay = document.getElementById("delete-account-overlay");
  const deleteAccountCancelBtn = document.getElementById("delete-account-cancel-btn");
  const deleteAccountConfirmBtn = document.getElementById("delete-account-confirm-btn");
  const deleteAccountConfirmInput = document.getElementById("delete-account-confirm-input");
  const deleteAccountPasswordInput = document.getElementById("delete-account-password-input");
  const deleteAccountConsentInput = document.getElementById("delete-account-consent-input");

  const goSignIn = document.getElementById("go-signin");
  const goSignUp = document.getElementById("go-signup");
  const goDemo = document.getElementById("go-demo");
  const signInBack = document.getElementById("signin-back");
  const signUpBack = document.getElementById("signup-back");
  const signInForm = document.getElementById("signin-form");
  const signUpForm = document.getElementById("signup-form");
  hydrateUsernameInputs();

  form.addEventListener("submit", handleSubmit);
  input.addEventListener("input", handleInput);
  input.addEventListener("keydown", handleKeyDown);
  input.addEventListener("focus", () => {
    document.body.classList.add("composer-focused");
    setTimeout(updateViewportHeightVar, 40);
    setTimeout(updateViewportHeightVar, 180);
  });
  input.addEventListener("blur", () => {
    document.body.classList.remove("composer-focused");
    setTimeout(updateViewportHeightVar, 100);
  });
  autoResizeComposer(input);
  sendBtn.disabled = true;
  logoutBtn.addEventListener("click", handleLogout);
  if (openDeleteAccountBtn) openDeleteAccountBtn.addEventListener("click", openDeleteAccountModal);
  if (drawerDeleteAccountBtn) drawerDeleteAccountBtn.addEventListener("click", () => {
    setCoolerDrawerOpen(false);
    openDeleteAccountModal();
  });
  if (deleteAccountCancelBtn) deleteAccountCancelBtn.addEventListener("click", closeDeleteAccountModal);
  if (deleteAccountConfirmBtn) deleteAccountConfirmBtn.addEventListener("click", handleDeleteAccountConfirm);
  [deleteAccountConfirmInput, deleteAccountPasswordInput, deleteAccountConsentInput].filter(Boolean).forEach((el) => {
    el.addEventListener("input", updateDeleteAccountActionState);
    el.addEventListener("change", updateDeleteAccountActionState);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter") e.preventDefault();
    });
  });
  updateDeleteAccountActionState();
  if (deleteAccountOverlay) {
    deleteAccountOverlay.addEventListener("click", (e) => {
      if (e.target === deleteAccountOverlay) {
        closeDeleteAccountModal();
      }
    });
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !document.getElementById("delete-account-overlay")?.hidden) {
      closeDeleteAccountModal();
    }
  });

  if (goDemo) goDemo.addEventListener("click", handleDemoLogin);
  goSignIn.addEventListener("click", () => showAuthView("signin", { clearMessages: true }));
  goSignUp.addEventListener("click", () => showAuthView("signup", { clearMessages: true }));
  signInBack.addEventListener("click", () => showAuthView("choice", { clearMessages: true }));
  signUpBack.addEventListener("click", () => showAuthView("choice", { clearMessages: true }));
  signInForm.addEventListener("submit", handleSignInSubmit);
  signUpForm.addEventListener("submit", handleSignUpSubmit);

  initThreadInteractions();
  initMessageActions();
  refresh3DTargets();
  bootstrapAuthState();
}

document.addEventListener("DOMContentLoaded", init);
