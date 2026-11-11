"""HTTP service for the assistant (served zone).

    python -m src.assistant.api            # http://127.0.0.1:8000  (docs at /docs)

Endpoints
    GET  /health     readiness, language-model status, knowledge-base size, podium-model metrics
    GET  /examples   suggested questions
    POST /ask        {"question": "..."} -> NDJSON stream: plan, evidence, tokens, check, done
    POST /chat       {"prompt": "...", "run_training": false} -> one JSON object; same contract as the
                     Graphic-LlmRag prototype, so its Streamlit page (dashboard/sections/rq6_graphic_llm_rag.py)
                     works unchanged on top of this grounded engine
Port 8000 is the prototype's port; override with F1_ASSISTANT_PORT.
"""
from __future__ import annotations

import json
import os
import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.assistant import llm

PORT = int(os.environ.get("F1_ASSISTANT_PORT", "8000"))
EXAMPLES = [
    "How many Grands Prix has Lewis Hamilton won, and with which teams?",
    "Who won the 1988 World Championship, and who scored more points?",
    "What are Charles Leclerc's chances of a podium starting from P4?",
    "How is Juan Manuel Fangio connected to Max Verstappen through team-mates?",
    "Which circuit has hosted the most Grands Prix?",
    "What is quality issue B29 and how was it handled?",
    "¿Cuántas victorias consiguió Michael Schumacher con Ferrari?",
    "Who won the 2021 Abu Dhabi Grand Prix?",
]

app = FastAPI(title="F1 data assistant", version="1.0.0",
              description="Grounded question answering over the validated F1 dataset (served zone).")
app.add_middleware(CORSMiddleware, allow_origin_regex=r"^(null|https?://(localhost|127\.0\.0\.1)(:\d+)?)$",
                   allow_methods=["GET", "POST"], allow_headers=["*"])

_state: dict = {"engine": None, "error": None, "started": time.time()}


def _load() -> None:
    try:
        from src.assistant.engine import engine
        _state["engine"] = engine()
        status = llm.status()
        if status.get("chat_model_ready"):
            llm.warm_up()
    except Exception as exc:  # noqa: BLE001 - reported through /health
        _state["error"] = f"{type(exc).__name__}: {exc}"


@app.on_event("startup")
def _startup() -> None:
    threading.Thread(target=_load, daemon=True).start()


class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)
    use_llm: bool = True


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=500)
    run_training: bool = False


def _not_ready() -> JSONResponse:
    return JSONResponse({"status": "loading" if not _state["error"] else "error", "error": _state["error"]},
                        status_code=503)


@app.get("/health")
def health() -> dict:
    e = _state["engine"]
    out = {"status": "ready" if e else ("error" if _state["error"] else "loading"), "error": _state["error"],
           "llm": llm.status()}
    if e:
        card = e.model.card
        out.update({"documents": len(e.retriever.docs), "semantic_search": e.retriever.semantic,
                    "engine_load_seconds": e.load_seconds,
                    "podium_model": {"name": card["selected_model"], "test": card["test_metrics"],
                                     "baseline_test": card["baseline_test_metrics"]},
                    "data_sha256": e.store.sha["results"][:16]})
    return out


@app.get("/examples")
def examples() -> dict:
    return {"questions": EXAMPLES}


@app.post("/ask")
def ask(req: AskRequest):
    e = _state["engine"]
    if not e:
        return _not_ready()

    def stream():
        for event in e.answer(req.question, use_llm=req.use_llm):
            yield json.dumps(event, ensure_ascii=False, default=str) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/chat")
def chat(req: ChatRequest):
    e = _state["engine"]
    if not e:
        return _not_ready()
    out = e.ask(req.prompt)
    evidence = out.get("evidence", {}).get("items", [])
    used_model = any(item["kind"] == "model" for item in evidence)
    card = e.model.card
    context = "\n\n".join(f"[{i['id']}] {i['title']}\n" + "\n".join(f"- {line}" for line in i["lines"]) +
                          f"\n  source: {i['source'].get('dataset')} ({i['source'].get('filter')})" for i in evidence)
    check = out.get("check", {})
    note = (f"\n\n_Figures checked against the evidence: {check.get('verified', 0)} of {check.get('numbers', 0)}"
            + (f"; not found: {', '.join(check['unverified'])}" if check.get("unverified") else "") + "._")
    plan = out.get("plan", {})
    return {
        "query": req.prompt,
        "detected_intent": {"target": ", ".join(plan.get("intents", [])) or "general",
                            "task": "podium probability" if used_model else "grounded answer",
                            "entities": [x["name"] for x in plan.get("entities", [])]},
        "winning_model": card["selected_model"] if used_model else llm.CHAT_MODEL,
        "model_score": card["test_metrics"]["roc_auc"] if used_model else "n/a",
        "retrieved_context": context,
        "context_summary": context[:300],
        "llm_response": out.get("answer", "") + (note if check else ""),
        "mode": out.get("done", {}).get("mode"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
