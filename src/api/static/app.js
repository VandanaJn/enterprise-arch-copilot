"use strict";

// Minimal chat client for the copilot's SSE API. No framework, no build step.
// EventSource can't POST, so we stream POST /chat via fetch + ReadableStream and
// parse the SSE frames ourselves.

const messagesEl = document.getElementById("messages");
const emptyEl = document.getElementById("empty-state");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const newChatBtn = document.getElementById("new-chat");

const THREAD_KEY = "eac_thread_id";
let threadId = sessionStorage.getItem(THREAD_KEY) || null;
let streaming = false;

// --- rendering ---------------------------------------------------------------

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Escape first, then apply a light, safe formatting pass over our own patterns:
// markdown headings, bold, and [doc-id] citation chips.
function renderAnswer(text) {
  let html = escapeHtml(text);
  html = html.replace(/^#{1,4}\s*(.+)$/gm, '<span class="h">$1</span>');
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(
    /\[([0-9a-z]+(?:-[0-9a-z]+)+)\](?!\()/g,
    '<span class="cite">[$1]</span>'
  );
  return html;
}

function hideEmpty() {
  if (emptyEl) emptyEl.style.display = "none";
}

function addTurn(role) {
  hideEmpty();
  const turn = document.createElement("div");
  turn.className = `turn ${role}`;
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = role === "user" ? "You" : "EA";
  const body = document.createElement("div");
  body.style.minWidth = "0";
  const chips = document.createElement("div");
  chips.className = "chips";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  body.appendChild(chips);
  body.appendChild(bubble);
  turn.appendChild(who);
  turn.appendChild(body);
  messagesEl.appendChild(turn);
  scrollToBottom();
  return { chips, bubble };
}

function addUser(text) {
  const { chips, bubble } = addTurn("user");
  chips.remove();
  bubble.textContent = text;
}

function addChip(chips, name, args) {
  const chip = document.createElement("span");
  chip.className = "chip";
  const argStr = args && Object.keys(args).length ? ` (${summarizeArgs(args)})` : "";
  chip.innerHTML = `<span class="k">${escapeHtml(name)}</span>${escapeHtml(argStr)}`;
  chips.appendChild(chip);
}

function summarizeArgs(args) {
  const parts = [];
  for (const [k, v] of Object.entries(args)) {
    const val = typeof v === "string" ? v : JSON.stringify(v);
    parts.push(`${k}=${val.length > 40 ? val.slice(0, 40) + "…" : val}`);
  }
  return parts.join(", ");
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// --- SSE over fetch ----------------------------------------------------------

// SSE allows CRLF, LF, or CR line endings, so match a blank line in any of them
// rather than assuming "\n\n" (sse-starlette's default framing is CRLF).
const FRAME_SEP = /\r\n\r\n|\n\n|\r\r/;

async function* readSSE(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let match;
    while ((match = FRAME_SEP.exec(buffer)) !== null) {
      const frame = buffer.slice(0, match.index);
      buffer = buffer.slice(match.index + match[0].length);
      const evt = parseFrame(frame);
      if (evt) yield evt;
    }
  }
}

function parseFrame(frame) {
  let event = "message";
  const dataLines = [];
  for (const line of frame.split(/\r\n|\n|\r/)) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

async function sendMessage(text) {
  streaming = true;
  sendBtn.disabled = true;
  addUser(text);
  const { chips, bubble } = addTurn("assistant");
  bubble.classList.add("cursor");
  let raw = "";

  try {
    const resp = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, thread_id: threadId }),
    });
    if (!resp.ok || !resp.body) {
      throw new Error(`HTTP ${resp.status}`);
    }

    for await (const { event, data } of readSSE(resp)) {
      if (event === "token") {
        raw += data.text || "";
        bubble.innerHTML = renderAnswer(raw);
        scrollToBottom();
      } else if (event === "tool_call") {
        addChip(chips, data.name || "tool", data.args);
        scrollToBottom();
      } else if (event === "done") {
        if (data.thread_id) {
          threadId = data.thread_id;
          sessionStorage.setItem(THREAD_KEY, threadId);
        }
        bubble.innerHTML = renderAnswer(data.text || raw || "(no response)");
      } else if (event === "error") {
        bubble.classList.add("error");
        bubble.textContent = `Error: ${data.message || "request failed"}`;
      }
    }
  } catch (err) {
    bubble.classList.add("error");
    bubble.textContent = `Error: ${err.message}`;
  } finally {
    bubble.classList.remove("cursor");
    if (!chips.children.length) chips.remove();
    streaming = false;
    sendBtn.disabled = false;
    scrollToBottom();
  }
}

// --- thread restore ----------------------------------------------------------

async function restoreThread() {
  if (!threadId) return;
  try {
    const resp = await fetch(`/threads/${encodeURIComponent(threadId)}/messages`);
    if (!resp.ok) return;
    const body = await resp.json();
    for (const m of body.messages || []) {
      if (m.role === "user") {
        addUser(m.content);
      } else {
        const { chips, bubble } = addTurn("assistant");
        chips.remove();
        bubble.innerHTML = renderAnswer(m.content);
      }
    }
  } catch {
    /* fresh start if restore fails */
  }
}

// --- events ------------------------------------------------------------------

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || streaming) return;
  input.value = "";
  input.style.height = "auto";
  sendMessage(text);
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
});

newChatBtn.addEventListener("click", () => {
  if (streaming) return;
  sessionStorage.removeItem(THREAD_KEY);
  threadId = null;
  messagesEl.innerHTML = "";
  if (emptyEl) {
    messagesEl.appendChild(emptyEl);
    emptyEl.style.display = "";
  }
});

document.querySelectorAll(".example").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (streaming) return;
    sendMessage(btn.textContent.trim());
  });
});

restoreThread();
