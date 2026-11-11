/* Ask the data - client for the local assistant service (data_management_project/src/assistant/api.py).
   The service streams NDJSON events: plan, evidence, token..., answer (fallback), check, done. */
(() => {
  "use strict";

  const API = (window.F1_ASSISTANT_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const form = $("#ask-form"), input = $("#ask-input"), btn = $("#ask-btn");
  const answerEl = $("#ask-answer"), checkEl = $("#ask-check"), evList = $("#ask-evidence"), statusEl = $("#ask-status");
  const steps = [...document.querySelectorAll(".ask-steps li")];
  if (!form) return;

  const FALLBACK_EXAMPLES = [
    "How many Grands Prix has Lewis Hamilton won, and with which teams?",
    "Who won the 1988 World Championship, and who scored more points?",
    "What are Charles Leclerc's chances of a podium starting from P4?",
    "How is Juan Manuel Fangio connected to Max Verstappen through team-mates?",
    "What is quality issue B29 and how was it handled?",
    "¿Cuántas victorias consiguió Michael Schumacher con Ferrari?",
  ];
  const KIND = { fact: "Exact figures", graph: "Team-mate network", model: "Podium model", document: "Knowledge document" };
  const START_HINT = "Start it with <code>python -m src.assistant.api</code> in <code>data_management_project</code> " +
    "(the Streamlit app starts it for you).";
  let health = null, busy = false, pollTimer = null;

  // ---------------------------------------------------------------- service status
  function setStatus(state, html) {
    statusEl.dataset.state = state;
    statusEl.querySelector("span").innerHTML = html;
  }

  async function fetchJSON(path, ms = 2500) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), ms);
    try {
      const r = await fetch(API + path, { signal: ctrl.signal });
      return { ok: r.ok, status: r.status, body: await r.json() };
    } finally { clearTimeout(t); }
  }

  async function checkHealth() {
    let next = 4000;
    try {
      const { body } = await fetchJSON("/health");
      health = body;
      if (body.status === "ready") {
        const llm = body.llm || {};
        const docs = (body.documents || 0).toLocaleString("en-GB");
        if (llm.chat_model_ready) {
          setStatus("ready", `Assistant ready: ${esc(llm.chat_model)} on this computer, ${docs} knowledge documents, ` +
            `${body.semantic_search ? "keyword and semantic search" : "keyword search"}.`);
        } else {
          setStatus("partial", `Assistant ready without a language model: answers show the evidence only. ` +
            `Install Ollama and run <code>ollama pull ${esc(llm.chat_model || "llama3")}</code> for written answers.`);
        }
        next = 30000;
      } else if (body.status === "loading") {
        setStatus("loading", "The assistant is loading the validated data, the team-mate network and the podium model.");
      } else {
        setStatus("offline", `The assistant failed to start: ${esc(body.error || "unknown error")}`);
        next = 15000;
      }
    } catch (e) {
      health = null;
      setStatus("offline", `The assistant is not running. ${START_HINT}`);
      next = 6000;
    }
    clearTimeout(pollTimer);
    pollTimer = setTimeout(checkHealth, next);
  }

  // ---------------------------------------------------------------- examples
  async function loadExamples() {
    let list = FALLBACK_EXAMPLES;
    try { const { body } = await fetchJSON("/examples"); if (body.questions) list = body.questions; } catch (e) { /* keep fallback */ }
    $("#ask-examples").innerHTML = list.map((q) => `<button type="button" class="ask-chip">${esc(q)}</button>`).join("");
  }
  $("#ask-examples").addEventListener("click", (e) => {
    const b = e.target.closest(".ask-chip");
    if (!b || busy) return;
    input.value = b.textContent;
    ask(b.textContent);
  });

  // ---------------------------------------------------------------- rendering
  function inline(s) {
    return s
      .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\[((?:S\d+)(?:\s*,\s*S\d+)*)\]/g, (_, ids) =>
        ids.split(/\s*,\s*/).map((id) => `<button type="button" class="cite" data-s="${id}" aria-label="Show evidence ${id}">${id}</button>`).join(""));
  }

  function md(text) {
    let html = "", list = false;
    for (const raw of esc(text).split(/\n/)) {
      const l = raw.trim();
      const item = l.match(/^(?:[-*•]|\d+[.)])\s+(.*)$/);
      if (item) { if (!list) { html += "<ul>"; list = true; } html += `<li>${inline(item[1])}</li>`; continue; }
      if (list) { html += "</ul>"; list = false; }
      if (l) html += `<p>${inline(l)}</p>`;
    }
    return html + (list ? "</ul>" : "");
  }

  function renderEvidence(items) {
    if (!items.length) { evList.innerHTML = `<li class="ev-empty">No evidence matched this question.</li>`; return; }
    evList.innerHTML = items.map((e) => {
      const s = e.source || {};
      const rows = [
        ["File", s.dataset && `<code>${esc(s.dataset)}</code>`],
        ["Filter", s.filter && `<code>${esc(s.filter)}</code>`],
        ["Rows", s.rows != null && Number(s.rows).toLocaleString("en-GB")],
        ["SHA-256", s.sha256 && `<code>${esc(s.sha256)}…</code>`],
        ["Raw lines", s.lineage && s.lineage.length && esc(s.lineage.join(", "))],
        ["Found by", s.retrieval && esc(Object.entries(s.retrieval).filter(([k]) => k !== "score").map(([k, v]) => `${k} rank ${v}`).join(", "))],
      ].filter(([, v]) => v);
      return `<li class="ev" id="ev-${esc(e.id)}" data-kind="${esc(e.kind)}">
        <div class="ev-head"><b>${esc(e.id)}</b><span>${KIND[e.kind] || esc(e.kind)}</span></div>
        <h3>${esc(e.title)}</h3>
        <ul>${e.lines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>
        <details><summary>Where this comes from</summary><dl>${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl></details>
      </li>`;
    }).join("");
  }

  function flash(id) {
    const card = document.getElementById(`ev-${id}`);
    if (!card) return;
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    card.classList.remove("flash"); void card.offsetWidth; card.classList.add("flash");
    setTimeout(() => card.classList.remove("flash"), 1600);
  }
  answerEl.addEventListener("click", (e) => { const c = e.target.closest(".cite"); if (c) flash(c.dataset.s); });

  function stepTo(i) {
    steps.forEach((li, k) => { li.classList.toggle("on", k === i); li.classList.toggle("done", k < i || i === 4); });
  }

  function renderCheck(c, done, evidenceSeconds) {
    const parts = [];
    if (!c.numbers) parts.push(`<span class="ok">No figures in this answer to check.</span>`);
    else if (!c.unverified.length) parts.push(`<span class="ok">All ${c.numbers} figures in the answer were found in the evidence.</span>`);
    else parts.push(`<span class="warn">${c.verified} of ${c.numbers} figures found in the evidence. Not found: ${esc(c.unverified.join(", "))}. Treat these with care.</span>`);
    if (c.cited && c.cited.length) parts.push(`<span class="meta">Cites ${c.cited.join(", ")} of ${c.blocks} evidence blocks.</span>`);
    if (done) {
      const st = done.stats || {};
      const llmTxt = done.mode === "llm"
        ? `written by ${esc(st.model || "the language model")} on this computer (read ${st.prompt_tokens || "?"} tokens in ${st.prompt_seconds ?? "?"} s, wrote ${st.answer_tokens || "?"} in ${st.answer_seconds ?? "?"} s)`
        : "evidence only, no language model";
      parts.push(`<span class="meta">Evidence in ${evidenceSeconds ?? "?"} s, complete answer in ${done.seconds} s, ${llmTxt}.</span>`);
    }
    checkEl.innerHTML = parts.join("");
    checkEl.hidden = false;
  }

  // ---------------------------------------------------------------- asking
  async function ask(question) {
    question = question.trim();
    if (question.length < 2 || busy) return;
    busy = true; btn.disabled = true; btn.textContent = "Working";
    checkEl.hidden = true; stepTo(0);
    evList.innerHTML = `<li class="ev-empty">Gathering evidence…</li>`;
    const head = `<p class="ask-question">${esc(question)}</p>`;
    const t0 = performance.now();
    let text = "", evSeconds = null, firstToken = false, done = null, check = null, fallbackNote = "";
    const waiting = () => `${head}<p class="ask-wait">${health && health.llm && health.llm.chat_model_ready ? "Llama 3 is reading the evidence" : "Preparing the answer"}: <b>${((performance.now() - t0) / 1000).toFixed(0)} s</b></p><div class="ask-bar"></div>`;
    answerEl.innerHTML = waiting();
    const timer = setInterval(() => { if (!firstToken && !done) answerEl.innerHTML = waiting(); }, 1000);
    try {
      const r = await fetch(API + "/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
      if (r.status === 503) throw new Error("loading");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const reader = r.body.getReader(), dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done: end } = await reader.read();
        if (end) break;
        buf += dec.decode(value, { stream: true });
        let nl;
        while ((nl = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1);
          if (!line) continue;
          const ev = JSON.parse(line);
          if (ev.type === "plan") stepTo(1);
          else if (ev.type === "evidence") { renderEvidence(ev.items); evSeconds = ev.seconds; stepTo(2); }
          else if (ev.type === "token") {
            if (!firstToken) { firstToken = true; stepTo(2); }
            text += ev.text;
            answerEl.innerHTML = head + md(text) + `<span class="caret" aria-hidden="true"></span>`;
          } else if (ev.type === "answer") {
            text = ev.text;
            fallbackNote = ev.reason === "no evidence" ? "" :
              `<p class="ask-note">Shown from the evidence directly: ${esc(ev.reason)}.</p>`;
          } else if (ev.type === "check") { check = ev; stepTo(3); }
          else if (ev.type === "done") done = ev;
        }
      }
      answerEl.innerHTML = head + md(text || "No answer was produced.") + fallbackNote;
      if (check) renderCheck(check, done, evSeconds);
      stepTo(4);
    } catch (e) {
      stepTo(-1);
      evList.innerHTML = `<li class="ev-empty">Nothing yet.</li>`;
      answerEl.innerHTML = head + (e.message === "loading"
        ? `<p class="ask-note">The assistant is still loading. Try again in a few seconds.</p>`
        : `<p class="ask-note">The assistant could not be reached. ${START_HINT}</p>`);
      checkHealth();
    } finally {
      clearInterval(timer);
      busy = false; btn.disabled = false; btn.textContent = "Ask";
    }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); ask(input.value); });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(input.value); } });

  loadExamples();
  checkHealth();
})();
