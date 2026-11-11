"""Local language model through the Ollama HTTP API (no Python package needed, nothing leaves the machine).

Defaults follow the original prototype (Llama 3). Override with environment variables:
    F1_ASSISTANT_MODEL=llama3.2:3b       lighter model for laptops with little memory
    F1_ASSISTANT_EMBED_MODEL=nomic-embed-text
    OLLAMA_HOST=http://127.0.0.1:11434
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterator

_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
OLLAMA_URL = (_host if _host.startswith("http") else f"http://{_host}").rstrip("/").replace("0.0.0.0", "127.0.0.1")
CHAT_MODEL = os.environ.get("F1_ASSISTANT_MODEL", "llama3")
EMBED_MODEL = os.environ.get("F1_ASSISTANT_EMBED_MODEL", "nomic-embed-text")
OPTIONS = {"temperature": 0.1, "num_ctx": 4096, "num_predict": 450, "seed": 42}
KEEP_ALIVE = "30m"


def _request(path: str, body: dict | None = None, timeout: float = 600):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{OLLAMA_URL}{path}", data=data,
                                 headers={"Content-Type": "application/json"} if data else {})
    return urllib.request.urlopen(req, timeout=timeout)


def _has(models: list[str], wanted: str) -> bool:
    base = wanted if ":" in wanted else f"{wanted}:latest"
    return any(m == wanted or m == base for m in models)


def status(timeout: float = 3.0, attempts: int = 2) -> dict:
    """Is Ollama up and are the models pulled? Retried once: a busy server can miss one short request."""
    for attempt in range(attempts):
        try:
            with _request("/api/tags", timeout=timeout) as r:
                models = [m["name"] for m in json.loads(r.read())["models"]]
            with _request("/api/version", timeout=timeout) as r:
                version = json.loads(r.read()).get("version")
            break
        except (urllib.error.URLError, OSError, ValueError) as exc:
            if attempt + 1 == attempts:
                return {"online": False, "error": str(exc), "chat_model": CHAT_MODEL, "embed_model": EMBED_MODEL,
                        "chat_model_ready": False, "embed_model_ready": False}
            time.sleep(1.5)
    return {"online": True, "version": version, "models": models, "chat_model": CHAT_MODEL,
            "embed_model": EMBED_MODEL, "chat_model_ready": _has(models, CHAT_MODEL),
            "embed_model_ready": _has(models, EMBED_MODEL)}


def embed(texts: list[str], model: str = EMBED_MODEL, timeout: float = 900) -> list[list[float]]:
    with _request("/api/embed", {"model": model, "input": texts, "keep_alive": KEEP_ALIVE}, timeout=timeout) as r:
        return json.loads(r.read())["embeddings"]


def chat_stream(system: str, prompt: str, model: str = CHAT_MODEL, timeout: float = 900) -> Iterator[dict]:
    """Yields {"text": ...} pieces, then one {"done": True, "stats": {...}}."""
    body = {"model": model, "stream": True, "keep_alive": KEEP_ALIVE, "options": OPTIONS,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
    with _request("/api/chat", body, timeout=timeout) as r:
        for raw in r:
            if not raw.strip():
                continue
            msg = json.loads(raw)
            if msg.get("error"):
                raise RuntimeError(msg["error"])
            piece = msg.get("message", {}).get("content", "")
            if piece:
                yield {"text": piece}
            if msg.get("done"):
                ns = 1e9
                yield {"done": True, "stats": {
                    "model": msg.get("model", model),
                    "prompt_tokens": msg.get("prompt_eval_count", 0),
                    "prompt_seconds": round(msg.get("prompt_eval_duration", 0) / ns, 1),
                    "answer_tokens": msg.get("eval_count", 0),
                    "answer_seconds": round(msg.get("eval_duration", 0) / ns, 1),
                    "load_seconds": round(msg.get("load_duration", 0) / ns, 1)}}


def warm_up(model: str = CHAT_MODEL) -> None:
    """Load the model into memory so the first question does not pay the loading time."""
    try:
        with _request("/api/generate", {"model": model, "prompt": "", "keep_alive": KEEP_ALIVE}, timeout=600):
            pass
    except (urllib.error.URLError, OSError):
        pass
