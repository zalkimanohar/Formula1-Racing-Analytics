"""Data-flow (architecture) diagram of the whole project, drawn from the generated outputs.

Zones follow the usual data-engineering layering: an immutable raw zone, a validated clean zone and
curated / serving products, with cross-cutting controls (schema contract, validation gates, lineage,
orchestration, tests) along the bottom.
"""
from __future__ import annotations

import pandas as pd

from src import config
from src import plot_style as ps

ps.apply()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT_DIR = config.OUTPUT_DIR / "architecture"
ZONE_COLORS = {"source": ps.NEUTRAL, "raw": ps.CATEGORICAL[3], "quality": ps.CATEGORICAL[1],
               "clean": ps.CATEGORICAL[0], "serve": ps.CATEGORICAL[2]}


def numbers() -> dict:
    issues = pd.read_csv(config.QUALITY_DIR / "quality_issues.csv")
    gates = pd.read_csv(config.CLEANING_DIR / "validation_report.csv")
    passed = pd.read_csv(config.QUALITY_DIR / "passed_checks.csv")
    clean = pd.read_csv(config.CLEAN_RESULTS_CSV)
    manifest = pd.read_csv(config.SOURCE_MANIFEST_CSV)
    edges = pd.read_csv(config.GRAPH_DIR / "property_graph_edge_counts.csv")["count"].sum()
    return {"files": len(manifest), "issues": len(issues), "dims": issues["dimension"].nunique(),
            "passed": len(passed), "gates": len(gates), "rows": len(clean), "cols": clean.shape[1],
            "edges": int(edges)}


def box(ax, x, y, w, h, title, body, zone, emphasis=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.012",
                                facecolor="#ffffff" if not emphasis else "#f1ecff",
                                edgecolor=ZONE_COLORS[zone], linewidth=1.3))
    ax.add_patch(FancyBboxPatch((x, y + h - 0.012), w, 0.012, boxstyle="square,pad=0",
                                facecolor=ZONE_COLORS[zone], edgecolor="none"))
    ax.text(x + 0.012, y + h - 0.03, title, fontsize=8.0, fontweight="bold", va="top", color=ps.INK)
    ax.text(x + 0.012, y + h - 0.07, body, fontsize=7.1, va="top", color=ps.INK_SECONDARY, linespacing=1.25)


def arrow(ax, x1, y1, x2, y2, rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=9, color=ps.INK_MUTED,
                                 linewidth=1.0, connectionstyle=f"arc3,rad={rad}", shrinkA=1, shrinkB=1))


def draw(path) -> None:
    n = numbers()
    fig, ax = plt.subplots(figsize=(7.6, 4.7))
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.86)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    cols = [0.0, 0.197, 0.394, 0.591, 0.826]
    w = 0.178
    heads = [("Source", "source"), ("Raw zone (bronze)", "raw"), ("Quality (B)", "quality"),
             ("Clean zone (silver)", "clean"), ("Served (gold)", "serve")]
    for x, (label, zone) in zip(cols, heads):
        ax.text(x, 0.985, label, fontsize=8.6, fontweight="bold", va="top",
                color=ZONE_COLORS[zone] if zone != "source" else ps.INK_SECONDARY)

    top, mid, low = (0.75, 0.16), (0.53, 0.16), (0.31, 0.16)
    box(ax, cols[0], *top[:1], w, top[1], "Ergast / Jolpica", "public F1 API\nCC BY-NC-SA 4.0", "source")
    box(ax, cols[0], *mid[:1], w, mid[1], "racing_f1_data.zip", f"{n['files']} files, JSON + CSV\nSHA-256 pinned",
        "source")
    box(ax, cols[1], *top[:1], w, top[1], "Step 0: extract", "format detection\nlineage: file + line", "raw")
    box(ax, cols[1], *mid[:1], w, mid[1], "data/raw", "5 CSV tables\nvalues unchanged", "raw")
    box(ax, cols[2], *top[:1], w, top[1], "Profiling", f"{n['issues']} issues\n{n['dims']} dimensions",
        "quality")
    box(ax, cols[2], *mid[:1], w, mid[1], "Issue register", "contract B to C\nevidence + fix step", "quality")
    box(ax, cols[3], *top[:1], w, top[1], "Cleaning", "12 audited steps\nraw + register in", "clean")
    box(ax, cols[3], *mid[:1], w, mid[1], "Validation gates", f"{n['gates']} checks\nfail-fast", "clean")
    box(ax, cols[3], *low[:1], w, low[1], "data/cleaned", f"{n['rows']:,} x {n['cols']}\n+ 4 reference tables",
        "clean")
    serve = [("FAIR record (A)", "DataCite, PROV-O\nschema.org", False),
             ("Property graph", f"NetworkX\n{n['edges']:,} edges", False),
             ("Dashboard", "7 views + grounded\nLLM assistant", True),
             ("Report, slides", "generated\nfrom outputs", False)]
    sy = [0.79, 0.615, 0.44, 0.265]
    for y, (t, b, emph) in zip(sy, serve):
        box(ax, cols[4], y, 0.17, 0.135, t, b, "serve", emphasis=emph)

    arrow(ax, cols[0] + w / 2, top[0], cols[0] + w / 2, mid[0] + mid[1])
    arrow(ax, cols[0] + w, mid[0] + 0.08, cols[1], top[0] + 0.08)
    arrow(ax, cols[1] + w / 2, top[0], cols[1] + w / 2, mid[0] + mid[1])
    arrow(ax, cols[1] + w, mid[0] + 0.08, cols[2], top[0] + 0.08)
    arrow(ax, cols[2] + w / 2, top[0], cols[2] + w / 2, mid[0] + mid[1])
    arrow(ax, cols[2] + w, mid[0] + 0.08, cols[3], top[0] + 0.08)
    arrow(ax, cols[3] + w / 2, top[0], cols[3] + w / 2, mid[0] + mid[1])
    arrow(ax, cols[3] + w / 2, mid[0], cols[3] + w / 2, low[0] + low[1])
    for i, y in enumerate(sy):
        arrow(ax, cols[3] + w, low[0] + 0.125 - i * 0.03, cols[4], y + 0.0675)
    ax.text(cols[2], 0.47, "Feedback loop:\nissue B29 came from\nthe dashboard",
            fontsize=7.0, color=ps.CATEGORICAL[6], va="top", linespacing=1.25)

    ax.add_patch(FancyBboxPatch((0.0, 0.02), 0.996, 0.185, boxstyle="round,pad=0,rounding_size=0.012",
                                facecolor="#f4f3ef", edgecolor="none"))
    ax.text(0.015, 0.19, "Cross-cutting engineering controls", fontsize=8.2, fontweight="bold", va="top",
            color=ps.INK)
    controls = [("Schema as code", "schema.py, vocabularies.py:\none contract for C and A"),
                ("Orchestration", "run_all.py: one command,\nbyte-identical reruns"),
                ("Automated tests", "pytest on key decisions\n(order, keys, sentinels)"),
                ("Lineage", "file + line per row,\nchecksums, PROV-O")]
    for i, (t, b) in enumerate(controls):
        x = 0.015 + i * 0.248
        ax.text(x, 0.135, t, fontsize=7.6, fontweight="bold", va="top", color=ps.INK)
        ax.text(x, 0.098, b, fontsize=7.0, va="top", color=ps.INK_SECONDARY, linespacing=1.25)

    ps.titles(ax, "End-to-end data flow: from the raw archive to the dashboard",
              "Every arrow is code in run_all.py; each zone reads only the zone before it.")
    ps.source_note(fig, "Numbers read from the generated outputs; group project, Data Management 2026/27.")
    ps.save(fig, path)


def draw_assistant(path) -> bool:
    """Architecture of the ask-the-data assistant, with the measured results (replaces the prototype sketch)."""
    import json
    a = config.OUTPUT_DIR / "assistant"
    needed = [a / "podium_model_card.json", a / "evaluation_evidence_summary.json", a / "knowledge_documents.jsonl"]
    if not all(p.exists() for p in needed):
        return False
    card = json.loads(needed[0].read_text(encoding="utf-8"))
    route = json.loads(needed[1].read_text(encoding="utf-8"))
    llm_path = a / "evaluation_llm_summary.json"
    llm = json.loads(llm_path.read_text(encoding="utf-8")) if llm_path.exists() else {}
    docs = sum(1 for _ in open(needed[2], encoding="utf-8"))

    fig, ax = plt.subplots(figsize=(7.6, 4.7))
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.86)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    heads = [(0.0, "Users", "serve"), (0.205, "Service", "source"), (0.41, "Evidence (code, not the LLM)", "clean"),
             (0.655, "Writing and checking", "quality"), (0.862, "Result", "serve")]
    for x, label, zone in heads:
        ax.text(x, 0.985, label, fontsize=8.4, fontweight="bold", va="top",
                color=ZONE_COLORS[zone] if zone != "source" else ps.INK_SECONDARY)
    w, h = 0.175, 0.135
    box(ax, 0.0, 0.70, w, h, "Dashboard: Ask", "question in English\nor Spanish, streamed", "serve", emphasis=True)
    box(ax, 0.0, 0.45, w, h, "Classic dashboard", "page RQ6 (prototype)\ncalls POST /chat", "serve")
    box(ax, 0.205, 0.70, w, h, "FastAPI, port 8000", "/ask (stream), /chat,\n/health, /examples", "source")
    box(ax, 0.205, 0.45, w, h, "Understand", "drivers, teams, circuits,\nseasons, intent", "source")
    ev = [("Exact facts (pandas)", "data/cleaned: file,\nSHA-256, raw line"),
          ("Team-mate graph", "NetworkX: chains,\nteam-mates, communities"),
          ("Podium model", f"{card['selected_model'].replace('_', ' ')}, time split,\n"
                           f"test ROC AUC {card['test_metrics']['roc_auc']:.3f}"),
          ("Knowledge base", f"{docs:,} documents, BM25\n(+ vectors if computed)")]
    ey = [0.775, 0.615, 0.455, 0.295]
    for y, (t, b) in zip(ey, ev):
        box(ax, 0.41, y, 0.205, h, t, b, "clean")
    box(ax, 0.655, 0.70, 0.18, h, "Llama 3 8B, local", "Ollama; evidence only,\ncites [S1], [S2]", "quality")
    box(ax, 0.655, 0.45, 0.18, h, "Figure check", "every number looked\nup in the evidence", "quality")
    box(ax, 0.862, 0.575, 0.134, h, "Answer", "with cited evidence\nand provenance", "serve", emphasis=True)

    arrow(ax, w, 0.70 + h / 2, 0.205, 0.70 + h / 2)
    arrow(ax, w, 0.45 + h / 2, 0.205, 0.70 + 0.02, rad=0.15)
    arrow(ax, 0.205 + w / 2, 0.70, 0.205 + w / 2, 0.45 + h)
    for y in ey:
        arrow(ax, 0.205 + w, 0.45 + h / 2, 0.41, y + h / 2)
        arrow(ax, 0.615, y + h / 2, 0.655, 0.70 + h / 2)
    arrow(ax, 0.655 + 0.09, 0.70, 0.655 + 0.09, 0.45 + h)
    arrow(ax, 0.835, 0.45 + h / 2, 0.862, 0.575 + h / 2)

    ax.add_patch(FancyBboxPatch((0.0, 0.02), 0.996, 0.205, boxstyle="round,pad=0,rounding_size=0.012",
                                facecolor="#f4f3ef", edgecolor="none"))
    ax.text(0.015, 0.21, f"Measured on {route['questions']} benchmark questions (answers computed independently "
                         "from the cleaned CSV)", fontsize=8.0, fontweight="bold", va="top", color=ps.INK)
    stats = [(f"{route['evidence_contains_expected']}/{route['questions']}", "evidence holds\nthe answer")]
    if llm:
        stats += [(f"{llm['answer_contains_expected']}/{llm['questions']}", "written answers\ncorrect"),
                  (f"{llm['figures_verified']}/{llm['figures_total']}", "figures traced\nto evidence"),
                  (f"{llm['median_total_seconds']:.0f} s", "median answer time\n(laptop CPU)")]
    stats.append((f"{card['test_metrics']['log_loss']:.3f}", f"podium log loss vs\n{card['baseline_test_metrics']['log_loss']:.3f} grid only"))
    for i, (num, lab) in enumerate(stats):
        x = 0.015 + i * 0.198
        ax.text(x, 0.15, num, fontsize=12, fontweight="bold", va="top", color=ps.CATEGORICAL[0])
        ax.text(x, 0.085, lab, fontsize=6.9, va="top", color=ps.INK_SECONDARY, linespacing=1.2)
    ps.titles(ax, "Ask the data: grounded answers, no invented numbers",
              "The language model only phrases the evidence; every figure comes from code and is checked afterwards.")
    ps.source_note(fig, "Idea and first prototype: Manohar Zalki (Graphic-LlmRag); results in outputs/assistant/.")
    ps.save(fig, path)
    return True


def run() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    draw(OUT_DIR / "fig_e1_data_flow.png")
    print("[architecture] data-flow diagram written")
    if draw_assistant(OUT_DIR / "fig_e2_assistant.png"):
        print("[architecture] assistant diagram written")


if __name__ == "__main__":
    run()
