"""Knowledge base for retrieval: one short document per driver, team, circuit, season, quality issue,
validation gate group, metadata file and project stage, all generated from the validated outputs.

    python -m src.assistant.knowledge            # rebuild the documents (fast, no network)
    python -m src.assistant.knowledge --embed    # also compute semantic vectors with Ollama (optional)

Vectors are cached by document hash in data/reference/assistant_embeddings/, so they survive
`run_all.py --from-scratch` and are only recomputed for documents whose text changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re

import numpy as np
import pandas as pd

from src import config
from src.assistant import llm
from src.assistant.facts import store

OUT_DIR = config.OUTPUT_DIR / "assistant"
DOCS_JSONL = OUT_DIR / "knowledge_documents.jsonl"
EMB_DIR = config.REFERENCE_DIR / "assistant_embeddings"


def _doc(kind: str, key: str, title: str, text: str, source: str) -> dict:
    text = re.sub(r"\s+", " ", text).strip()
    return {"id": f"{kind}:{key}", "kind": kind, "title": title, "text": text, "source": source,
            "sha": hashlib.sha256(f"{title}\n{text}".encode()).hexdigest()[:16]}


def _md_sections(path, kind: str, source: str, min_len: int = 120) -> list[dict]:
    if not path.exists():
        return []
    docs, title, buf = [], path.stem, []
    for line in path.read_text(encoding="utf-8").splitlines() + ["# end"]:
        if line.startswith("#"):
            body = " ".join(buf).strip()
            if len(body) >= min_len:
                docs.append(_doc(kind, f"{path.stem}:{len(docs)}", f"{path.stem}: {title}", body[:1500], source))
            title, buf = line.lstrip("# ").strip(), []
        else:
            buf.append(line.strip("|- ").replace("|", ";"))
    return docs


def build_documents() -> list[dict]:
    s = store()
    docs: list[dict] = []
    res = s.results
    for did in res["driver_id"].unique():
        ev = s.driver_career(did)
        docs.append(_doc("driver", did, ev.title, " ".join(ev.lines), ev.source["dataset"]))
    for fam in res["family"].unique():
        ev = s.team_profile(fam)
        docs.append(_doc("team", fam, ev.title, " ".join(ev.lines), ev.source["dataset"]))
    for cid in res["circuit_id"].unique():
        ev = s.circuit_profile(cid)
        docs.append(_doc("circuit", cid, ev.title, " ".join(ev.lines), ev.source["dataset"]))
    for year in sorted(res["season"].unique()):
        ev = s.season_summary(int(year))
        docs.append(_doc("season", str(year), ev.title, " ".join(ev.lines), ev.source["dataset"]))

    issues = pd.read_csv(config.QUALITY_DIR / "quality_issues.csv")
    for _, row in issues.iterrows():
        ev = s.quality_overview(row["issue_id"])
        docs.append(_doc("quality", row["issue_id"], ev.title, " ".join(ev.lines),
                         "outputs/component_b_quality/quality_issues.csv"))
    ev = s.quality_overview()
    docs.append(_doc("quality", "overview", ev.title, " ".join(ev.lines), ev.source["dataset"]))
    gates = pd.read_csv(config.CLEANING_DIR / "validation_report.csv")
    for i in range(0, len(gates), 12):
        chunk = gates.iloc[i:i + 12]
        docs.append(_doc("validation", str(i // 12), f"Validation gates {i + 1}-{i + len(chunk)}",
                         " ".join(f"{g.gate}: {g.result}." for g in chunk.itertuples()),
                         "outputs/component_c_cleaning/validation_report.csv"))
    audit = pd.read_csv(config.CLEANING_DIR / "audit_log.csv")
    for step, grp in audit.groupby(audit.columns[0]):
        docs.append(_doc("cleaning", str(step), f"Cleaning step {step}",
                         " ".join(" ".join(str(v) for v in r if pd.notna(v)) for r in grp.head(8).itertuples(index=False)),
                         "outputs/component_c_cleaning/audit_log.csv"))
    ddict = pd.read_csv(config.FAIR_DIR / "data_dictionary.csv")
    for _, row in ddict.iterrows():
        docs.append(_doc("dictionary", str(row.iloc[0]) + ":" + str(row.iloc[1]), f"Column {row.iloc[1]}",
                         " ".join(f"{k}: {v}." for k, v in row.items() if pd.notna(v)),
                         "outputs/component_a_fair/data_dictionary.csv"))
    for path in (config.FAIR_DIR / "component_a_summary.md", config.FAIR_DIR / "fair_gaps.md",
                 config.FAIR_DIR / "LICENSE-DATA.md", config.QUALITY_DIR / "quality_issues.md",
                 config.CLEANING_DIR / "audit_log.md", config.PROJECT_ROOT / "README.md"):
        docs += _md_sections(path, "project", str(path.relative_to(config.PROJECT_ROOT)).replace("\\", "/"))
    from src.assistant.graph_tools import graph
    ev = graph().overview()
    docs.append(_doc("graph", "overview", ev.title, " ".join(ev.lines), "outputs/graph/network_metrics.csv"))
    for c in graph().communities.reset_index().itertuples():
        docs.append(_doc("graph", f"community:{c.community}", f"Team-mate community {c.community}",
                         f"Community {c.community}: {c.drivers} drivers, debuts {c.first_debut}-{c.last_active}, "
                         f"median debut {c.median_debut:.0f}; most central drivers: {c.most_central_drivers}",
                         "outputs/graph/communities.csv"))
    card_path = OUT_DIR / "podium_model_card.json"
    if card_path.exists():
        card = json.loads(card_path.read_text(encoding="utf-8"))
        docs.append(_doc("model", "podium", "Podium probability model (model card)",
                         f"{card['task']}. Unit: {card['unit']}. Split: {card['split']}. Selected: "
                         f"{card['selected_model']} by {card['selection_rule']}. Test metrics: {card['test_metrics']}. "
                         f"Grid-only baseline: {card['baseline_test_metrics']}. Leakage guard: {card['leakage_guard']}. "
                         f"Most important features: {list(card['feature_importance_test'])[:4]}.",
                         "outputs/assistant/podium_model_card.json"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(DOCS_JSONL, "w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    return docs


def load_documents() -> list[dict]:
    if not DOCS_JSONL.exists():
        return build_documents()
    with open(DOCS_JSONL, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def _emb_path(model: str):
    return EMB_DIR / f"{model.replace(':', '_').replace('/', '_')}.npz"


def load_embeddings(docs: list[dict], model: str = llm.EMBED_MODEL) -> np.ndarray | None:
    """Matrix aligned with `docs`, or None when some documents have no cached vector yet."""
    path = _emb_path(model)
    if not path.exists():
        return None
    cache = np.load(path)
    index = {sha: i for i, sha in enumerate(cache["sha"])}
    if any(d["sha"] not in index for d in docs):
        return None
    return cache["vec"][[index[d["sha"]] for d in docs]]


def embed_documents(docs: list[dict], model: str = llm.EMBED_MODEL, batch: int = 16) -> np.ndarray:
    path = _emb_path(model)
    EMB_DIR.mkdir(parents=True, exist_ok=True)
    shas, vecs = [], []
    if path.exists():
        cache = np.load(path)
        shas, vecs = list(cache["sha"]), list(cache["vec"])
    known = set(shas)
    todo = [d for d in docs if d["sha"] not in known]
    for i in range(0, len(todo), batch):
        part = todo[i:i + batch]
        out = llm.embed([f"search_document: {d['title']}. {d['text'][:1200]}" for d in part], model=model)
        shas += [d["sha"] for d in part]
        vecs += [np.asarray(v, dtype=np.float32) for v in out]
        np.savez_compressed(path, sha=np.array(shas), vec=np.vstack(vecs))
        print(f"[knowledge] embedded {min(i + batch, len(todo))}/{len(todo)}", flush=True)
    return load_embeddings(docs, model)


def run(embed: bool = False) -> list[dict]:
    docs = build_documents()
    kinds = pd.Series([d["kind"] for d in docs]).value_counts()
    print(f"[knowledge] {len(docs)} documents: " + ", ".join(f"{k} {v}" for k, v in kinds.items()))
    if embed:
        embed_documents(docs)
    has = load_embeddings(docs) is not None
    print(f"[knowledge] semantic vectors: {'complete' if has else 'not computed (keyword retrieval only)'}")
    return docs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--embed", action="store_true")
    run(embed=ap.parse_args().embed)
