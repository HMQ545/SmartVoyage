const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const sessionListEl = document.getElementById("session-list");
const newSessionBtn = document.getElementById("new-session");

const SESSION_KEY = "smartvoyage_session_id";
let sessionId = localStorage.getItem(SESSION_KEY) || crypto.randomUUID();
localStorage.setItem(SESSION_KEY, sessionId);

/* ---------------- Markdown 渲染 ---------------- */

function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function inlineMd(s) {
    return escapeHtml(s)
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/\*([^*]+)\*/g, "<em>$1</em>")
        .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function renderMarkdownFallback(text) {
    const lines = text.split("\n");
    const out = [];
    let inCode = false, codeBuf = [], inList = false, listTag = "ul";
    const flushList = () => { if (inList) { out.push(`</${listTag}>`); inList = false; } };
    for (let line of lines) {
        if (line.trim().startsWith("```")) {
            if (inCode) { out.push("<pre><code>" + escapeHtml(codeBuf.join("\n")) + "</code></pre>"); inCode = false; codeBuf = []; }
            else { flushList(); inCode = true; }
            continue;
        }
        if (inCode) { codeBuf.push(line); continue; }
        const t = line.trim();
        if (!t) { flushList(); continue; }
        const h = t.match(/^(#{1,4})\s+(.*)$/);
        if (h) { flushList(); const lv = h[1].length; out.push(`<h${lv}>${inlineMd(h[2])}</h${lv}>`); continue; }
        if (/^---+$/.test(t)) { flushList(); out.push("<hr>"); continue; }
        if (/^>\s?/.test(t)) { flushList(); out.push(`<blockquote>${inlineMd(t.replace(/^>\s?/, ""))}</blockquote>`); continue; }
        const ul = t.match(/^[-*]\s+(.*)$/);
        if (ul) { if (!inList) { inList = true; listTag = "ul"; out.push("<ul>"); } out.push(`<li>${inlineMd(ul[1])}</li>`); continue; }
        const ol = t.match(/^\d+[.、]\s*(.*)$/);
        if (ol) { if (!inList) { inList = true; listTag = "ol"; out.push("<ol>"); } out.push(`<li>${inlineMd(ol[1])}</li>`); continue; }
        if (t.startsWith("|") && t.endsWith("|") && lines.includes(line) ) {
            const cells = t.split("|").slice(1, -1).map(c => inlineMd(c.trim()));
            if (/^[\s:|-]+$/.test(cells.join(""))) continue;
            out.push("<table><tr>" + cells.map(c => `<td>${c}</td>`).join("") + "</tr></table>");
            continue;
        }
        flushList();
        out.push(`<p>${inlineMd(t)}</p>`);
    }
    flushList();
    if (inCode) out.push("<pre><code>" + escapeHtml(codeBuf.join("\n")) + "</code></pre>");
    return out.join("\n");
}

function renderMarkdown(text) {
    if (window.marked && window.DOMPurify) {
        try {
            const html = window.marked.parse(text, { breaks: true, gfm: true });
            return window.DOMPurify.sanitize(html);
        } catch (e) { /* fall through */ }
    }
    return renderMarkdownFallback(text);
}

/* ---------------- DOM 工具 ---------------- */

function scrollBottom() {
    requestAnimationFrame(() => { chatEl.scrollTop = chatEl.scrollHeight; });
}

function addUser(text) {
    const el = document.createElement("div");
    el.className = "msg user";
    el.textContent = text;
    chatEl.appendChild(el);
    scrollBottom();
    return el;
}

function addBotContainer() {
    const wrap = document.createElement("div");
    wrap.className = "msg bot";
    const md = document.createElement("div");
    md.className = "md";
    const thinking = document.createElement("div");
    thinking.className = "thinking";
    thinking.textContent = "思考中...";
    wrap.append(md, thinking);
    chatEl.appendChild(wrap);
    scrollBottom();
    return { wrap, md, thinking };
}

function renderBotText(mdEl, text) {
    mdEl.innerHTML = text ? renderMarkdown(text) : "";
}

function addStepBox() {
    const box = document.createElement("div");
    box.className = "steps";
    const summary = document.createElement("div");
    summary.className = "step-title";
    summary.textContent = "🔧 工具调用过程";
    box.appendChild(summary);
    chatEl.appendChild(box);
    scrollBottom();
    return box;
}

function makeStepEl(tool, args) {
    const div = document.createElement("div");
    div.className = "step";
    const name = document.createElement("div");
    name.className = "tool-name";
    name.innerHTML = `🔧 ${escapeHtml(tool)} <span class="tool-status">进行中...</span>`;
    const argsPre = document.createElement("pre");
    argsPre.textContent = `参数: ${JSON.stringify(args, null, 2)}`;
    div.append(name, argsPre);
    return div;
}

/* ---------------- 会话管理 ---------------- */

async function refreshSessions() {
    try {
        const resp = await fetch("/api/sessions");
        const data = await resp.json();
        sessionListEl.innerHTML = "";
        (data.sessions || []).forEach((s) => {
            const item = document.createElement("div");
            item.className = "session-item" + (s.session_id === sessionId ? " active" : "");
            const title = document.createElement("div");
            title.className = "s-title";
            title.textContent = s.title || "新会话";
            title.title = s.title || "";
            const time = document.createElement("div");
            time.className = "s-time";
            time.textContent = (s.updated_at || "").slice(5, 16);
            const del = document.createElement("button");
            del.className = "s-del";
            del.textContent = "✕";
            del.title = "删除会话";
            del.addEventListener("click", (e) => {
                e.stopPropagation();
                deleteSession(s.session_id);
            });
            item.append(title, time, del);
            item.addEventListener("click", () => loadSession(s.session_id));
            sessionListEl.appendChild(item);
        });
    } catch (e) { /* 忽略列表刷新失败 */ }
}

async function loadSession(id) {
    try {
        const resp = await fetch(`/api/sessions/${encodeURIComponent(id)}`);
        if (!resp.ok) return;
        const data = await resp.json();
        sessionId = id;
        localStorage.setItem(SESSION_KEY, sessionId);
        chatEl.innerHTML = "";
        (data.messages || []).forEach((m) => {
            if (m.role === "user") {
                addUser(m.content);
            } else if (m.role === "assistant") {
                const { md } = addBotContainer();
                renderBotText(md, m.content);
                if (m.steps && m.steps.length) {
                    const box = addStepBox();
                    m.steps.forEach((s) => {
                        const el = makeStepEl(s.tool, s.args);
                        const res = document.createElement("pre");
                        res.textContent = `结果: ${s.result}`;
                        el.querySelector(".tool-status").textContent = "完成";
                        el.appendChild(res);
                        box.appendChild(el);
                    });
                }
            }
        });
        refreshSessions();
        scrollBottom();
    } catch (e) { /* 忽略 */ }
}

function newSession() {
    sessionId = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, sessionId);
    chatEl.innerHTML = "";
    refreshSessions();
    inputEl.focus();
}

async function deleteSession(id) {
    if (!confirm("确定删除该会话？")) return;
    try {
        await fetch(`/api/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
        if (id === sessionId) newSession(); else refreshSessions();
    } catch (e) { alert("删除失败：" + e.message); }
}

/* ---------------- 流式对话 ---------------- */

async function send() {
    const text = inputEl.value.trim();
    if (!text) return;
    inputEl.value = "";
    addUser(text);
    const { md, thinking, wrap } = addBotContainer();
    const stepsBox = addStepBox();
    sendBtn.disabled = true;

    let botText = "";
    let errorMsg = "";
    const stepEls = new Map();
    let stepIndex = 0;

    const handleEvent = (evt) => {
        if (evt.type === "tool_start") {
            const el = makeStepEl(evt.tool || "tool", evt.args || {});
            stepEls.set(stepIndex, el);
            stepIndex += 1;
            stepsBox.appendChild(el);
            scrollBottom();
        } else if (evt.type === "tool_end") {
            const el = stepEls.get(stepIndex - 1);
            if (el) {
                el.querySelector(".tool-status").textContent = "完成";
                const res = document.createElement("pre");
                res.textContent = `结果: ${evt.result}`;
                el.appendChild(res);
                scrollBottom();
            }
        } else if (evt.type === "content") {
            botText += evt.delta || "";
            renderBotText(md, botText);
            thinking.style.display = "none";
            scrollBottom();
        } else if (evt.type === "error") {
            errorMsg = evt.message || "服务异常";
        } else if (evt.type === "done") {
            if (evt.reply) {
                botText = evt.reply;
                renderBotText(md, botText);
            }
            if (errorMsg) {
                const err = document.createElement("div");
                err.className = "thinking";
                err.textContent = `⚠ ${errorMsg}`;
                wrap.appendChild(err);
            }
            thinking.style.display = "none";
            refreshSessions();
        }
    };

    try {
        const resp = await fetch("/api/chat/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId, message: text }),
        });
        if (!resp.ok || !resp.body) {
            const data = await resp.json().catch(() => ({}));
            throw new Error(data.detail || `HTTP ${resp.status}`);
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            let idx;
            while ((idx = buf.indexOf("\n\n")) >= 0) {
                const chunk = buf.slice(0, idx);
                buf = buf.slice(idx + 2);
                for (const line of chunk.split("\n")) {
                    if (!line.startsWith("data: ")) continue;
                    try { handleEvent(JSON.parse(line.slice(6))); }
                    catch (e) { /* 跳过无法解析的事件 */ }
                }
            }
        }
    } catch (err) {
        thinking.textContent = `请求失败：${err.message}`;
    } finally {
        sendBtn.disabled = false;
        inputEl.focus();
        scrollBottom();
    }
}

/* ---------------- 初始化 ---------------- */

newSessionBtn.addEventListener("click", newSession);
sendBtn.addEventListener("click", send);
inputEl.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });

refreshSessions();
loadSession(sessionId);