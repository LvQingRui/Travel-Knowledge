const API = "";

let sessionId = null;
let isStreaming = false;

const $ = (sel) => document.querySelector(sel);
const messagesEl = $("#messages");
const queryInput = $("#queryInput");
const sendBtn = $("#sendBtn");
const sessionListEl = $("#sessionList");
const chatTitleEl = $("#chatTitle");
const sessionIdLabel = $("#sessionIdLabel");
const deleteCurrentBtn = $("#deleteCurrentBtn");

// ---- 初始化 ----
document.addEventListener("DOMContentLoaded", () => {
  loadSessions();
  bindEvents();
  updateDeleteButton();
});

function bindEvents() {
  sendBtn.addEventListener("click", sendMessage);
  $("#newChatBtn").addEventListener("click", startNewChat);
  deleteCurrentBtn.addEventListener("click", () => {
    if (sessionId) deleteSession(sessionId);
  });

  queryInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  queryInput.addEventListener("input", autoResize);

  document.querySelectorAll(".suggestion").forEach((btn) => {
    btn.addEventListener("click", () => {
      queryInput.value = btn.dataset.q;
      sendMessage();
    });
  });
}

function autoResize() {
  queryInput.style.height = "auto";
  queryInput.style.height = Math.min(queryInput.scrollHeight, 120) + "px";
}

// ---- 会话管理 ----
async function loadSessions() {
  try {
    const res = await fetch(`${API}/sessions`);
    const sessions = await res.json();
    renderSessionList(sessions);
  } catch (e) {
    console.error("加载会话失败", e);
  }
}

function renderSessionList(sessions) {
  if (!sessions.length) {
    sessionListEl.innerHTML = '<p class="empty-tip">暂无历史会话</p>';
    return;
  }

  sessionListEl.innerHTML = sessions
    .map(
      (s) => `
    <div class="session-item ${s.session_id === sessionId ? "active" : ""}"
         data-id="${s.session_id}">
      <span class="session-title" title="${escapeHtml(s.title)}">${escapeHtml(s.title || "新对话")}</span>
      <button class="session-delete" data-id="${s.session_id}" title="删除会话">×</button>
    </div>`
    )
    .join("");

  sessionListEl.querySelectorAll(".session-item").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (e.target.closest(".session-delete")) return;
      loadSession(el.dataset.id);
    });
  });

  sessionListEl.querySelectorAll(".session-delete").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteSession(btn.dataset.id);
    });
  });
}

async function deleteSession(id) {
  const session = sessionListEl.querySelector(`[data-id="${id}"] .session-title`);
  const title = session ? session.textContent : "该会话";
  if (!confirm(`确定删除「${title}」？此操作不可恢复。`)) return;

  try {
    const res = await fetch(`${API}/sessions/${id}`, { method: "DELETE" });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "删除失败");
    }
    if (sessionId === id) {
      startNewChat();
    } else {
      loadSessions();
    }
  } catch (e) {
    alert("删除失败：" + e.message);
  }
}

function updateDeleteButton() {
  deleteCurrentBtn.hidden = !sessionId;
}

async function loadSession(id) {
  try {
    const res = await fetch(`${API}/sessions/${id}`);
    const data = await res.json();
    sessionId = id;
    chatTitleEl.textContent = data.title || "对话";
    sessionIdLabel.textContent = `会话: ${id.slice(0, 8)}...`;
    updateDeleteButton();
    clearMessages();

    data.messages.forEach((msg) => {
      if (msg.role === "user") {
        appendMessage("user", msg.content);
      } else if (msg.role === "assistant") {
        appendMessage("assistant", msg.content, msg.citations);
      }
    });

    renderSessionList(await (await fetch(`${API}/sessions`)).json());
    updateDeleteButton();
  } catch (e) {
    console.error("加载会话详情失败", e);
  }
}

function startNewChat() {
  sessionId = null;
  chatTitleEl.textContent = "新对话";
  sessionIdLabel.textContent = "未开始会话";
  clearMessages();
  showWelcome();
  loadSessions();
  updateDeleteButton();
}

function clearMessages() {
  messagesEl.innerHTML = "";
}

function showWelcome() {
  messagesEl.innerHTML = `
    <div class="welcome">
      <h3>你好，我是旅游知识库助手</h3>
      <p>可以问我景点介绍、美食推荐、线路规划等问题，例如：</p>
      <div class="suggestions">
        <button class="suggestion" data-q="张家界有什么特色美食？">张家界有什么特色美食？</button>
        <button class="suggestion" data-q="三亚有哪些必去景点？">三亚有哪些必去景点？</button>
        <button class="suggestion" data-q="丽江古城最佳游览时间？">丽江古城最佳游览时间？</button>
      </div>
    </div>`;
  document.querySelectorAll(".suggestion").forEach((btn) => {
    btn.addEventListener("click", () => {
      queryInput.value = btn.dataset.q;
      sendMessage();
    });
  });
}

function removeWelcome() {
  const welcome = messagesEl.querySelector(".welcome");
  if (welcome) welcome.remove();
}

// ---- 发送消息（SSE 流式）----
async function sendMessage() {
  const query = queryInput.value.trim();
  if (!query || isStreaming) return;

  removeWelcome();
  appendMessage("user", query);
  queryInput.value = "";
  autoResize();
  setLoading(true);

  const assistantEl = appendMessage("assistant", "", null, true);
  const contentEl = assistantEl.querySelector(".message-content");
  let citations = [];

  try {
    const body = { query, top_k: 5 };
    if (sessionId) body.session_id = sessionId;

    const res = await fetch(`${API}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "请求失败");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop();

      for (const part of parts) {
        if (!part.trim()) continue;
        const event = parseSSE(part);
        if (!event) continue;

        if (event.type === "session") {
          sessionId = event.data.session_id;
          sessionIdLabel.textContent = `会话: ${sessionId.slice(0, 8)}...`;
          chatTitleEl.textContent = query.slice(0, 20);
          updateDeleteButton();
        } else if (event.type === "context") {
          citations = event.data.citations || [];
        } else if (event.type === "token") {
          contentEl.textContent += event.data.content;
          scrollToBottom();
        } else if (event.type === "error") {
          contentEl.textContent = "出错了：" + event.data.error;
        } else if (event.type === "done") {
          contentEl.classList.remove("streaming");
        }
      }
    }

    if (citations.length) {
      appendCitations(assistantEl, citations);
    }
    loadSessions();
  } catch (e) {
    contentEl.textContent = "请求失败：" + e.message;
    contentEl.classList.remove("streaming");
  } finally {
    setLoading(false);
    scrollToBottom();
  }
}

function parseSSE(raw) {
  const lines = raw.split("\n");
  let type = "message";
  let dataStr = "";
  for (const line of lines) {
    if (line.startsWith("event: ")) type = line.slice(7).trim();
    if (line.startsWith("data: ")) dataStr = line.slice(6);
  }
  if (!dataStr) return null;
  try {
    return { type, data: JSON.parse(dataStr) };
  } catch {
    return null;
  }
}

// ---- UI 辅助 ----
function appendMessage(role, content, citations = null, streaming = false) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.innerHTML = `
    <div class="message-avatar">${role === "user" ? "我" : "AI"}</div>
    <div class="message-body">
      <div class="message-content${streaming ? " streaming" : ""}">${escapeHtml(content)}</div>
    </div>`;
  messagesEl.appendChild(div);

  if (citations && citations.length) {
    appendCitations(div, citations);
  }
  scrollToBottom();
  return div;
}

function appendCitations(messageEl, citations) {
  const body = messageEl.querySelector(".message-body");
  const existing = body.querySelector(".citations");
  if (existing) existing.remove();

  const html = citations
    .map(
      (c) => `
    <div class="citation-item">
      <span class="citation-source">[${c.index}] ${escapeHtml(c.source_filename || c.recall_source || "来源")}</span>
      ${c.region ? ` · ${escapeHtml(c.region)}` : ""}
      <div class="citation-snippet">${escapeHtml(c.snippet || "")}</div>
    </div>`
    )
    .join("");

  const div = document.createElement("div");
  div.className = "citations";
  div.innerHTML = `<div class="citations-title">引用来源</div>${html}`;
  body.appendChild(div);
}

function setLoading(loading) {
  isStreaming = loading;
  sendBtn.disabled = loading;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
