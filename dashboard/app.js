/**
 * Memory chat dashboard with session auth and thread sidebar.
 */

const API_BASE = "";
const MOBILE_BREAKPOINT = 1024;
const CLIENT_ID_STORAGE_KEY = "memory_client_id_v1";
const THEME_STORAGE_KEY = "memory_theme_v1";
const AVAILABLE_THEMES = ["default", "gpt", "project", "white", "sunset"];
const THEME_META_COLORS = {
  default: "#060910",
  gpt: "#050b09",
  project: "#050919",
  white: "#f4f8ff",
  sunset: "#13090a",
};

function createClientId() {
  if (window.crypto && window.crypto.getRandomValues) {
    const bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  }
  return `client_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function getClientId() {
  const valid = /^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$/;
  try {
    const existing = (localStorage.getItem(CLIENT_ID_STORAGE_KEY) || "").trim();
    if (valid.test(existing)) return existing;
    const created = createClientId();
    localStorage.setItem(CLIENT_ID_STORAGE_KEY, created);
    return created;
  } catch (_) {
    return "default";
  }
}

const CLIENT_ID = getClientId();

const state = {
  user: null,
  authView: "choice",
  theme: "default",
  themePickerOpen: false,
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
  const vh = window.innerHeight || document.documentElement.clientHeight;
  if (!vh) return;
  document.documentElement.style.setProperty("--app-height", `${vh}px`);
}

function isMobileViewport() {
  return window.innerWidth <= MOBILE_BREAKPOINT;
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
  document.documentElement.style.colorScheme = nextTheme === "white" ? "light" : "dark";
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
  message.innerHTML = `
    <div class="message-avatar">${avatar}</div>
    <div class="message-body">
      <div class="message-content">${escapeHtml(content || "")}</div>
      <div class="message-meta">${timeText}</div>
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
    document.getElementById("chat-input").focus();
  } else {
    chatApp.classList.add("is-hidden");
    authScreen.classList.remove("is-hidden");
  }
}

function setUserUI(user) {
  const userPill = document.getElementById("user-pill");
  userPill.textContent = `@${user.username}`;
}

function updateHeaderThreadUI() {
  const welcomeSub = document.getElementById("welcome-sub");
  const input = document.getElementById("chat-input");

  if (welcomeSub) {
    welcomeSub.textContent = "Start a conversation — I'll remember what you share.";
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
        <h1 class="welcome-title">Welcome to the chat box</h1>
        <p class="welcome-sub" id="welcome-sub">Start a conversation — I'll remember what you share.</p>
      </div>
    `;
  }
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
    .map((thread) => {
      const active = thread.id === state.activeThreadId;
      const title = escapeHtml(thread.title || "New chat");
      const time = formatThreadTime(thread.last_message_at || thread.updated_at);
      const count = Number(thread.message_count || 0);
      const previewSource = thread.last_message || "No messages yet";
      const preview = escapeHtml(truncateText(previewSource, 42));
      const meta = [time, count > 0 ? `${count} msg${count === 1 ? "" : "s"}` : "empty"]
        .filter(Boolean)
        .join(" · ");
      return `
        <div class="thread-item${active ? " active" : ""}">
          <button class="thread-main" type="button" data-thread-id="${thread.id}" aria-label="Open ${title}">
            <div class="thread-title-row"><span class="thread-title">${title}</span></div>
            <div class="thread-meta">${escapeHtml(meta)}${preview ? ` · ${preview}` : ""}</div>
          </button>
          <div class="thread-actions">
            <button class="thread-more-btn" type="button" data-thread-id="${thread.id}" aria-label="Open actions for ${title}">...</button>
            <div class="thread-menu" role="menu" aria-label="Thread actions">
              <button class="thread-menu-item thread-menu-delete" type="button" data-thread-id="${thread.id}" role="menuitem">
                Delete chat
              </button>
            </div>
          </div>
        </div>
      `;
    })
    .join("");
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
  renderThreadList();
  renderMessages([]);
  updateHeaderThreadUI();
  if (isMobileViewport()) setSidebarOpen(false);
  document.getElementById("chat-input").focus();
}

async function selectThread(threadId) {
  const id = Number(threadId);
  if (!id || state.activeThreadId === id) {
    if (isMobileViewport()) setSidebarOpen(false);
    return;
  }
  state.activeThreadId = id;
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
    const errContent = errorMessage.querySelector(".message-content");
    if (errContent) errContent.style.color = "#ff7b72";
    container.appendChild(errorMessage);
    showNotification("Message failed", "error");
  } finally {
    input.disabled = false;
    autoResizeComposer(input);
    btn.disabled = input.value.trim().length === 0;
    input.focus();
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
        document.getElementById("chat-input").focus();
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
      const isNearBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight < 100;
      if (isNearBottom) smoothScrollToBottom(container);
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
  state.user = data.user;
  setUserUI(data.user);
  clearAuthMessages();
  toggleApp(true);
  showNotification("Account created", "info");
  await loadThreads({ preferThreadId: data.default_thread_id, preserveSelection: false });
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
  state.user = null;
  state.threads = [];
  state.activeThreadId = null;
  document.getElementById("signin-password").value = "";
  document.getElementById("signup-password").value = "";
  document.getElementById("signup-confirm-password").value = "";
  toggleApp(false);
  renderMessages([]);
  renderThreadList();
  showAuthView("choice", { clearMessages: true, message: "Logged out.", type: "success" });
}

async function bootstrapAuthState() {
  try {
    const data = await api("/api/auth/me");
    if (data.authenticated && data.user) {
      state.user = data.user;
      setUserUI(data.user);
      toggleApp(true);
      await loadThreads({ preferThreadId: data.default_thread_id, preserveSelection: false });
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

  newChatBtn.addEventListener("click", async () => {
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

function init() {
  updateViewportHeightVar();
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", updateViewportHeightVar);
  }
  initThemePicker();
  addTypingIndicatorStyles();
  addKeyboardShortcuts();
  enhanceScrollBehavior();

  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("send-btn");
  const logoutBtn = document.getElementById("logout-btn");

  const goSignIn = document.getElementById("go-signin");
  const goSignUp = document.getElementById("go-signup");
  const signInBack = document.getElementById("signin-back");
  const signUpBack = document.getElementById("signup-back");
  const signInForm = document.getElementById("signin-form");
  const signUpForm = document.getElementById("signup-form");

  form.addEventListener("submit", handleSubmit);
  input.addEventListener("input", handleInput);
  input.addEventListener("keydown", handleKeyDown);
  autoResizeComposer(input);
  sendBtn.disabled = true;
  logoutBtn.addEventListener("click", handleLogout);

  goSignIn.addEventListener("click", () => showAuthView("signin", { clearMessages: true }));
  goSignUp.addEventListener("click", () => showAuthView("signup", { clearMessages: true }));
  signInBack.addEventListener("click", () => showAuthView("choice", { clearMessages: true }));
  signUpBack.addEventListener("click", () => showAuthView("choice", { clearMessages: true }));
  signInForm.addEventListener("submit", handleSignInSubmit);
  signUpForm.addEventListener("submit", handleSignUpSubmit);

  initThreadInteractions();
  bootstrapAuthState();
}

document.addEventListener("DOMContentLoaded", init);
