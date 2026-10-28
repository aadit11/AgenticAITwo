// Phase 8. POST /api/chat and read the SSE stream with fetch.

const STARTERS = [
  "What does PEP 8 say about imports?",
  "How many PEPs in the table have status Final?",
  "Show the function format_pep_reference in code_bundle/pep_tools/references.py and explain it.",
];

const messages = [];
const transcript = document.querySelector("#transcript");
const traceList = document.querySelector("#trace");
const form = document.querySelector("#ask");
const queryBox = document.querySelector("#query");
const sendButton = document.querySelector("#send");
const statusLine = document.querySelector("#status");
const starters = document.querySelector("#starters");

STARTERS.forEach((question) => {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = question;
  button.addEventListener("click", () => {
    queryBox.value = question;
    queryBox.focus();
  });
  starters.appendChild(button);
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = queryBox.value.trim();
  if (!query || sendButton.disabled) return;
  ask(query);
});

function ask(query) {
  const history = messages.map((message) => ({ role: message.role, content: message.content }));
  messages.push({ role: "user", content: query });
  const assistant = { role: "assistant", content: "" };
  messages.push(assistant);
  queryBox.value = "";
  const userNode = renderUser(query);
  const view = renderAssistant();
  transcript.append(userNode, view.article);
  transcript.scrollTop = transcript.scrollHeight;
  sendButton.disabled = true;
  statusLine.textContent = "Working";
  readStream(query, history, assistant, view).finally(() => {
    sendButton.disabled = false;
    statusLine.textContent = "";
    queryBox.focus();
  });
}

function renderUser(text) {
  const article = document.createElement("article");
  article.className = "bubble user";
  article.textContent = text;
  return article;
}

function renderAssistant() {
  const article = document.createElement("article");
  article.className = "bubble assistant";
  const answer = document.createElement("p");
  answer.className = "answer";
  const routes = document.createElement("ul");
  routes.className = "routes";
  const chips = document.createElement("div");
  chips.className = "chips";
  const detail = document.createElement("div");
  detail.className = "detail";
  detail.hidden = true;
  article.append(answer, routes, chips, detail);
  return { article, answer, routes, chips, detail, openId: "" };
}

async function readStream(query, history, assistant, view) {
  let response;
  try {
    response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, history }),
    });
  } catch (error) {
    addTrace("request", "error", "The browser could not reach the server.");
    return;
  }
  if (!response.ok || !response.body) {
    addTrace("request", "error", `The server returned ${response.status}.`);
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const chunk = await reader.read();
    buffer += decoder.decode(chunk.value || new Uint8Array(), { stream: !chunk.done });
    buffer = consume(buffer, (kind, payload) => applyEvent(kind, payload, assistant, view));
    if (chunk.done) break;
  }
  consume(`${buffer}\n\n`, (kind, payload) => applyEvent(kind, payload, assistant, view));
}

function consume(buffer, onEvent) {
  const frames = buffer.split("\n\n");
  const rest = frames.pop() || "";
  frames.forEach((frame) => {
    const trimmed = frame.trim();
    if (!trimmed || trimmed.startsWith(":")) return;
    let kind = "message";
    const dataLines = [];
    trimmed.split("\n").forEach((line) => {
      if (line.startsWith("event:")) kind = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
    });
    if (!dataLines.length) return;
    try {
      onEvent(kind, JSON.parse(dataLines.join("\n")));
    } catch (error) {
      addTrace("page", "error", "A stream frame was not valid JSON.");
    }
  });
  return rest;
}

function applyEvent(kind, payload, assistant, view) {
  if (kind === "token") {
    assistant.content += payload.text || "";
    view.answer.textContent = assistant.content;
  } else if (kind === "trace") {
    addTrace(payload.node, payload.event, payload.detail);
  } else if (kind === "route") {
    addRoute(view.routes, payload);
  } else if (kind === "citation") {
    addChip(view, payload);
  } else if (kind === "error") {
    const recovered = payload.recovered ? "recovered" : "not recovered";
    addTrace(payload.agent || "error", "error", `${payload.message || "A worker failed."} (${recovered})`);
  }
  transcript.scrollTop = transcript.scrollHeight;
  traceList.scrollTop = traceList.scrollHeight;
}

const TRACE_TITLES = {
  "plan enter": "Planner",
  "plan exit": "Plan",
  "plan fallback": "Planner fallback",
  "plan model": "Planner model",
  "supervisor route": "Supervisor",
  "supervisor skip": "Supervisor skipped a step",
  "research enter": "Research",
  "research retrieve": "Corpus search",
  "research tool": "Research web search",
  "research exit": "Research finished",
  "research model": "Research model",
  "data enter": "Data",
  "data query": "PEP table query",
  "data exit": "Data finished",
  "data model": "Data model",
  "code enter": "Code",
  "code read": "Code file",
  "code exit": "Code finished",
  "code model": "Code model",
  "summary enter": "Summary",
  "summary tool": "Summary web tool",
  "summary exit": "Summary finished",
  "summary model": "Summary model",
  "planner model": "Planner model",
  "graph error": "Graph stopped",
};

function addTrace(node, event, detail) {
  const item = document.createElement("li");
  if (event === "error") item.className = "error";
  const name = document.createElement("span");
  name.className = "node";
  const key = `${node || "graph"} ${event || ""}`.trim();
  name.textContent = TRACE_TITLES[key] || key;
  const body = document.createElement("p");
  body.className = "trace-detail";
  body.textContent = detail || "";
  item.append(name, body);
  traceList.appendChild(item);
}

function addRoute(list, payload) {
  const item = document.createElement("li");
  item.className = "route";
  const reason = payload.reason || "";
  item.textContent = [payload.agent, payload.provider, payload.model, reason].filter(Boolean).join(" · ");
  list.appendChild(item);
}

function addChip(view, payload) {
  const chunkId = payload.chunk_id || payload.source || "citation";
  if (view.chips.querySelector(`[data-chunk-id="${cssEscape(chunkId)}"]`)) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "chip";
  button.dataset.chunkId = chunkId;
  button.textContent = chunkId;
  button.setAttribute("aria-pressed", "false");
  button.addEventListener("click", () => toggleCitation(view, button, payload));
  view.chips.appendChild(button);
}

function toggleCitation(view, button, payload) {
  const chunkId = button.dataset.chunkId;
  const opening = view.openId !== chunkId;
  view.chips.querySelectorAll(".chip").forEach((chip) => chip.setAttribute("aria-pressed", "false"));
  if (!opening) {
    view.openId = "";
    view.detail.hidden = true;
    view.detail.replaceChildren();
    return;
  }
  view.openId = chunkId;
  button.setAttribute("aria-pressed", "true");
  view.detail.hidden = false;
  view.detail.replaceChildren(
    line("Chunk", payload.chunk_id),
    line("Title", payload.title),
    line("Section", payload.section),
    line("Score", payload.score),
    line("Excerpt", payload.excerpt, true),
  );
}

function line(label, value, excerpt) {
  const paragraph = document.createElement("p");
  if (excerpt) paragraph.className = "excerpt";
  const strong = document.createElement("strong");
  strong.textContent = `${label}: `;
  paragraph.append(strong, document.createTextNode(value == null || value === "" ? "—" : String(value)));
  return paragraph;
}

function cssEscape(value) {
  if (window.CSS && CSS.escape) return CSS.escape(value);
  return String(value).replace(/"/g, '\\"');
}
