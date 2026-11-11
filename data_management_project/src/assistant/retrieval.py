"""Hybrid retrieval over the knowledge documents: BM25 keywords + semantic vectors, fused by rank.

Keyword retrieval always works (no model needed). When the cached document vectors exist and Ollama is
reachable, the question is embedded too and both rankings are merged with reciprocal rank fusion.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

import numpy as np

from src.assistant import llm
from src.assistant.facts import fold
from src.assistant.knowledge import load_documents, load_embeddings

STOPWORDS = set("""a an the of in on at to for from by with and or is are was were be been has have had do does did
what which who whom whose when where why how many much most more than that this these those it its his her their
there here about tell me show give list please can could would should will i you we they he she
el la los las un una unos unas de del en con por para y o que quien quienes cual cuales cuando donde como cuanto
cuantos cuantas mas menos es son fue fueron ser ha han tiene tienen tuvo se su sus al lo le les me mi dime""".split())
RRF_K = 60


SUFFIXES = ("ations", "ation", "ated", "ates", "ating", "ate", "ings", "ing", "ied", "ies", "ed", "es", "s")


def stem(t: str) -> str:
    """Light suffix stripping so that cleaned/cleaning/clean and validated/validation meet."""
    for suf in SUFFIXES:
        if len(t) > len(suf) + 3 and t.endswith(suf):
            return t[: -len(suf)] + ("y" if suf in ("ied", "ies") else "")
    return t


def tokens(text: str) -> list[str]:
    return [stem(t) for t in fold(text).split() if t not in STOPWORDS and len(t) > 1]


class BM25:
    def __init__(self, docs: list[dict], k1: float = 1.4, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.tf = [Counter(tokens(f"{d['title']} {d['title']} {d['text']}")) for d in docs]
        self.len = np.array([sum(c.values()) for c in self.tf], dtype=float)
        self.avg = float(self.len.mean())
        df: dict[str, int] = defaultdict(int)
        self.postings: dict[str, list[int]] = defaultdict(list)
        for i, c in enumerate(self.tf):
            for t in c:
                df[t] += 1
                self.postings[t].append(i)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> dict[int, float]:
        out: dict[int, float] = defaultdict(float)
        for t in set(tokens(query)):
            for i in self.postings.get(t, ()):
                f = self.tf[i][t]
                out[i] += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        return out


class Retriever:
    def __init__(self) -> None:
        self.docs = load_documents()
        self.bm25 = BM25(self.docs)
        self.vectors = load_embeddings(self.docs)
        if self.vectors is not None:
            self.vectors = self.vectors / np.linalg.norm(self.vectors, axis=1, keepdims=True)

    @property
    def semantic(self) -> bool:
        return self.vectors is not None

    def search(self, query: str, k: int = 4, kinds: set[str] | None = None, exclude: set[str] = frozenset()
               ) -> list[tuple[dict, dict]]:
        allowed = [i for i, d in enumerate(self.docs) if (not kinds or d["kind"] in kinds) and d["id"] not in exclude]
        allowed_set = set(allowed)
        kw = sorted(((s, i) for i, s in self.bm25.scores(query).items() if i in allowed_set), reverse=True)[:50]
        rankings = {"keyword": [i for _, i in kw]}
        if self.vectors is not None:
            try:
                q = np.asarray(llm.embed([f"search_query: {query}"], timeout=60)[0], dtype=np.float32)
                q /= np.linalg.norm(q)
                sims = self.vectors[allowed] @ q
                top = np.argsort(-sims)[:50]
                rankings["semantic"] = [allowed[j] for j in top]
            except OSError:
                pass
        fused: dict[int, float] = defaultdict(float)
        how: dict[int, dict] = defaultdict(dict)
        for name, ranked in rankings.items():
            for rank, i in enumerate(ranked, start=1):
                fused[i] += 1 / (RRF_K + rank)
                how[i][name] = rank
        best = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
        return [(self.docs[i], {"score": round(s, 4), **how[i]}) for i, s in best]
