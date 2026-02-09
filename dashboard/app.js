/**
 * ═══════════════════════════════════════════════════════════
 * MEMORY CHAT — Next-Level Chat Interface
 * Premium UX with smooth animations and interactions
 * ═══════════════════════════════════════════════════════════
 */

const API_BASE = "";  // Same origin when served by backend

// ═══════════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════════

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE || ""}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function smoothScrollToBottom(container, duration = 300) {
  const start = container.scrollTop;
  const end = container.scrollHeight - container.clientHeight;
  const distance = end - start;
  const startTime = performance.now();

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function scroll(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = easeOutCubic(progress);
    
    container.scrollTop = start + distance * eased;
    
    if (progress < 1) {
      requestAnimationFrame(scroll);
    }
  }

  requestAnimationFrame(scroll);
}

function typeWriterEffect(element, text, speed = 20) {
  return new Promise((resolve) => {
    let i = 0;
    element.textContent = '';
    
    function type() {
      if (i < text.length) {
        element.textContent += text.charAt(i);
        i++;
        setTimeout(type, speed);
      } else {
        resolve();
      }
    }
    
    type();
  });
}

// ═══════════════════════════════════════════════════════════
// MESSAGE LOADING & RENDERING
// ═══════════════════════════════════════════════════════════

async function loadMessages() {
  try {
    const data = await api("/api/messages");
    const container = document.getElementById("chat-messages");
    const welcome = document.getElementById("welcome");
    
    if (data.messages && data.messages.length > 0) {
      if (welcome) {
        welcome.style.animation = 'fadeOut 0.3s ease-out forwards';
        setTimeout(() => welcome.remove(), 300);
      }

      container.innerHTML = data.messages.map((m, index) => {
        const isUser = m.role === "user";
        const avatar = isUser ? "U" : "M";
        return `
          <div class="message ${m.role}" style="animation-delay: ${index * 0.05}s">
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">${escapeHtml(m.content)}</div>
          </div>
        `;
      }).join("");
      
      smoothScrollToBottom(container);
    }
  } catch (e) {
    console.error("Failed to load messages:", e);
    showNotification("Unable to load previous messages", "error");
  }
}

// ═══════════════════════════════════════════════════════════
// MESSAGE SENDING
// ═══════════════════════════════════════════════════════════

async function sendMessage(text) {
  const input = document.getElementById("chat-input");
  const btn = document.getElementById("send-btn");
  const container = document.getElementById("chat-messages");
  const welcome = document.getElementById("welcome");

  // Clear input immediately
  input.value = "";
  
  // Disable input
  input.disabled = true;
  btn.disabled = true;
  btn.style.transform = 'scale(0.9)';

  // Remove welcome with animation
  if (welcome) {
    welcome.style.animation = 'fadeOut 0.4s ease-out forwards';
    setTimeout(() => welcome.remove(), 400);
  }

  // Add user message with smooth entry
  const userMessage = document.createElement('div');
  userMessage.className = 'message user';
  userMessage.style.opacity = '0';
  userMessage.innerHTML = `
    <div class="message-avatar">U</div>
    <div class="message-content">${escapeHtml(text)}</div>
  `;
  container.appendChild(userMessage);
  
  // Trigger animation
  setTimeout(() => {
    userMessage.style.transition = 'all 0.4s cubic-bezier(0.22, 1, 0.36, 1)';
    userMessage.style.opacity = '1';
    userMessage.style.transform = 'translateY(0)';
  }, 10);
  
  smoothScrollToBottom(container);

  // Add loading message
  const loadingMessage = document.createElement('div');
  loadingMessage.className = 'message assistant loading';
  loadingMessage.style.opacity = '0';
  loadingMessage.innerHTML = `
    <div class="message-avatar">M</div>
    <div class="message-content">
      <span class="typing-dot">●</span>
      <span class="typing-dot">●</span>
      <span class="typing-dot">●</span>
    </div>
  `;
  container.appendChild(loadingMessage);
  
  setTimeout(() => {
    loadingMessage.style.transition = 'opacity 0.3s ease';
    loadingMessage.style.opacity = '1';
  }, 200);
  
  smoothScrollToBottom(container, 400);

  try {
    const data = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message: text }),
    });

    // Remove loading message with fade out
    loadingMessage.style.transition = 'opacity 0.2s ease';
    loadingMessage.style.opacity = '0';
    
    setTimeout(() => {
      loadingMessage.remove();
      
      // Add assistant message
      const assistantMessage = document.createElement('div');
      assistantMessage.className = 'message assistant';
      assistantMessage.style.opacity = '0';
      assistantMessage.innerHTML = `
        <div class="message-avatar">M</div>
        <div class="message-content">${escapeHtml(data.reply || "No response.")}</div>
      `;
      container.appendChild(assistantMessage);
      
      // Animate in
      setTimeout(() => {
        assistantMessage.style.transition = 'all 0.4s cubic-bezier(0.22, 1, 0.36, 1)';
        assistantMessage.style.opacity = '1';
        assistantMessage.style.transform = 'translateY(0)';
      }, 10);
      
      smoothScrollToBottom(container);
      
    }, 200);

  } catch (e) {
    loadingMessage.remove();
    
    const errorMessage = document.createElement('div');
    errorMessage.className = 'message assistant';
    errorMessage.style.opacity = '0';
    errorMessage.innerHTML = `
      <div class="message-avatar">M</div>
      <div class="message-content" style="color: #ff453a;">⚠️ Could not reach backend. Run: <code>python -m src.api</code></div>
    `;
    container.appendChild(errorMessage);
    
    setTimeout(() => {
      errorMessage.style.transition = 'opacity 0.3s ease';
      errorMessage.style.opacity = '1';
    }, 10);
    
    showNotification("Connection failed. Please check the backend.", "error");
  }

  // Re-enable input with smooth transition
  setTimeout(() => {
    input.disabled = false;
    btn.disabled = false;
    btn.style.transform = 'scale(1)';
    input.focus();
  }, 300);
}

// ═══════════════════════════════════════════════════════════
// NOTIFICATION SYSTEM
// ═══════════════════════════════════════════════════════════

function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.textContent = message;
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 12px 20px;
    background: ${type === 'error' ? '#ff453a' : '#0a84ff'};
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
    notification.style.opacity = '1';
    notification.style.transform = 'translateY(0)';
  }, 10);
  
  setTimeout(() => {
    notification.style.opacity = '0';
    notification.style.transform = 'translateY(-20px)';
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

// ═══════════════════════════════════════════════════════════
// INPUT HANDLING
// ═══════════════════════════════════════════════════════════

function handleInput(e) {
  const btn = document.getElementById("send-btn");
  const hasText = e.target.value.trim().length > 0;
  
  btn.disabled = !hasText;
  btn.style.transition = 'all 0.3s cubic-bezier(0.22, 1, 0.36, 1)';
  btn.style.opacity = hasText ? '1' : '0.4';
  btn.style.transform = hasText ? 'scale(1)' : 'scale(0.9)';
}

function handleSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  
  if (text && !input.disabled) {
    sendMessage(text);
  }
}

function handleKeyDown(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    const text = e.target.value.trim();
    if (text && !e.target.disabled) {
      sendMessage(text);
    }
  }
}

// ═══════════════════════════════════════════════════════════
// TYPING INDICATOR ANIMATION
// ═══════════════════════════════════════════════════════════

function addTypingIndicatorStyles() {
  const style = document.createElement('style');
  style.textContent = `
    .typing-dot {
      display: inline-block;
      margin: 0 2px;
      animation: typingBounce 1.4s infinite ease-in-out;
      opacity: 0.5;
    }
    
    .typing-dot:nth-child(1) {
      animation-delay: 0s;
    }
    
    .typing-dot:nth-child(2) {
      animation-delay: 0.2s;
    }
    
    .typing-dot:nth-child(3) {
      animation-delay: 0.4s;
    }
    
    @keyframes typingBounce {
      0%, 60%, 100% {
        transform: translateY(0);
        opacity: 0.5;
      }
      30% {
        transform: translateY(-6px);
        opacity: 1;
      }
    }
    
    @keyframes fadeOut {
      to {
        opacity: 0;
        transform: scale(0.95) translateY(-10px);
      }
    }
  `;
  document.head.appendChild(style);
}

// ═══════════════════════════════════════════════════════════
// EASTER EGGS & ENHANCEMENTS
// ═══════════════════════════════════════════════════════════

function addKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K to focus input
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      document.getElementById('chat-input').focus();
    }
  });
}

function enhanceScrollBehavior() {
  const container = document.getElementById('chat-messages');
  let isUserScrolling = false;
  let scrollTimeout;
  
  container.addEventListener('scroll', () => {
    isUserScrolling = true;
    clearTimeout(scrollTimeout);
    
    scrollTimeout = setTimeout(() => {
      isUserScrolling = false;
    }, 150);
  });
  
  // Auto-scroll only if user is near bottom
  const observer = new MutationObserver(() => {
    if (!isUserScrolling) {
      const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
      if (isNearBottom) {
        smoothScrollToBottom(container);
      }
    }
  });
  
  observer.observe(container, { childList: true, subtree: true });
}

// ═══════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════

function init() {
  // Add custom styles
  addTypingIndicatorStyles();
  
  // Load previous messages
  loadMessages();

  // Set up event listeners
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  
  form.addEventListener("submit", handleSubmit);
  input.addEventListener("input", handleInput);
  input.addEventListener("keydown", handleKeyDown);
  
  // Enhanced features
  addKeyboardShortcuts();
  enhanceScrollBehavior();
  
  // Focus input on load
  setTimeout(() => input.focus(), 500);
  
  // Add subtle entrance animation to input
  const inputArea = document.querySelector('.input-area');
  inputArea.style.opacity = '0';
  inputArea.style.transform = 'translateY(20px)';
  
  setTimeout(() => {
    inputArea.style.transition = 'all 0.6s cubic-bezier(0.22, 1, 0.36, 1)';
    inputArea.style.opacity = '1';
    inputArea.style.transform = 'translateY(0)';
  }, 300);
  
  console.log('%c✨ Memory Chat Loaded', 'color: #0a84ff; font-size: 16px; font-weight: bold;');
  console.log('%cKeyboard shortcuts: Ctrl/Cmd + K to focus input', 'color: #8e8e93; font-size: 12px;');
}

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", init);