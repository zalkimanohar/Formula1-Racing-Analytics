"""Benchmark for the assistant: questions whose correct answers are computed here, directly from the
cleaned CSV with pandas (independently of src/assistant/facts.py), plus questions it must refuse.

    python -m src.assistant.evaluate          # evidence only: routing and retrieval (seconds)
    python -m src.assistant.evaluate --llm    # also the written answers of the local language model

Measures, per question: is the expected value in the evidence (routing/retrieval), is it in the written
answer, are all figures in the answer traceable to the evidence, is any evidence cited, and latency.
Results: outputs/assistant/evaluation.csv and evaluation_summary.json.
"""
from __future__ import annotations

import argparse
import json
import re
import time

import pandas as pd

from src import config
from src.assistant.facts import fold

OUT_DIR = config.OUTPUT_DIR / "assistant"
REFUSAL = re.compile(r"\b(not|no|does not|doesn't|cannot|can't|only|unavailable|missing|1950-2025|no se|no hay|"
                     r"solo)\b", re.I)


def ground_truth() -> list[dict]:
    r = pd.read_csv(config.CLEAN_RESULTS_CSV)
    d = pd.read_csv(config.CLEAN_DRIVERS_CSV).set_index("driver_id")["full_name"]
    champs = pd.read_csv(config.REFERENCE_DIR / "official_champions.csv").set_index("season")["champion_driver_id"]
    win = r["classified_position"] == 1
    pod = r["classified_position"] <= 3
    fam = r["constructor_id"].str.replace("team_lotus", "lotus").str.split("-").str[0]

    def family_name(driver_id: str) -> str:
        return d[driver_id].split()[-1]

    def winner(season: int, circuit: str) -> str:
        return family_name(r[(r["season"] == season) & (r["circuit_id"] == circuit) & win]["driver_id"].iloc[0])

    poles = r[r["grid_position"] == 1].groupby("driver_id").size().idxmax()
    team_wins = r[win].assign(f=fam[win]).groupby("f")["race_id"].nunique().idxmax()
    monaco_top = r[win & (r["circuit_id"] == "monaco")].groupby("driver_id").size().idxmax()
    hr = r[r["driver_id"].isin(["hamilton", "rosberg"]) & r["finish_category"].ne("Withdrawn")]
    both = hr[hr["driver_id"] == "hamilton"].merge(hr[hr["driver_id"] == "rosberg"], on="race_id")
    ahead = "Hamilton" if (both["position_order_x"] < both["position_order_y"]).mean() > 0.5 else "Rosberg"
    metrics = pd.read_csv(config.GRAPH_DIR / "teammate_node_metrics.csv")
    most_mates = metrics.sort_values("degree", ascending=False).iloc[0]["name"].split()[-1]
    issues = pd.read_csv(config.QUALITY_DIR / "quality_issues.csv")
    path = pd.read_csv(config.GRAPH_DIR / "shortest_teammate_path_fangio_verstappen.csv")
    from src.assistant.podium_model import podium_model     # the model's own estimate must reach the answer
    pole_prob = f"{100 * podium_model().probability('max_verstappen', 1):.0f}%"

    return [
        {"q": "How many Grands Prix has Lewis Hamilton won?", "expect": str(int((win & (r.driver_id == "hamilton")).sum())), "type": "driver"},
        {"q": "How many wins does Michael Schumacher have?", "expect": str(int((win & (r.driver_id == "michael_schumacher")).sum())), "type": "driver"},
        {"q": "Who won the 1988 World Championship?", "expect": family_name(champs[1988]), "type": "champion"},
        {"q": "Who won the 1964 World Championship?", "expect": family_name(champs[1964]), "type": "champion"},
        {"q": "Who was World Champion in 2016?", "expect": family_name(champs[2016]), "type": "champion"},
        {"q": "How many World Championships did Juan Manuel Fangio win?", "expect": str(int((champs == "fangio").sum())), "type": "champion"},
        {"q": "Who won the 2008 British Grand Prix?", "expect": winner(2008, "silverstone"), "type": "race"},
        {"q": "Who won the 2021 Abu Dhabi Grand Prix?", "expect": winner(2021, "yas_marina"), "type": "race"},
        {"q": "¿Quién ganó el Gran Premio de Mónaco de 2024?", "expect": winner(2024, "monaco"), "type": "race (Spanish)"},
        {"q": "How many podiums did Fernando Alonso get with Ferrari?",
         "expect": str(int((pod & (r.driver_id == "alonso") & (fam == "ferrari")).sum())), "type": "driver + team"},
        {"q": "¿Cuántas victorias consiguió Michael Schumacher con Ferrari?",
         "expect": str(int((win & (r.driver_id == "michael_schumacher") & (fam == "ferrari")).sum())), "type": "driver + team (Spanish)"},
        {"q": "How many races did Max Verstappen win in 2023?",
         "expect": str(int((win & (r.driver_id == "max_verstappen") & (r.season == 2023)).sum())), "type": "driver season"},
        {"q": "How did Red Bull do in 2023?",
         "expect": str(int(r[win & (fam == "red_bull") & (r.season == 2023)]["race_id"].nunique())), "type": "team season"},
        {"q": "Which team has won the most Grands Prix?", "expect": "Ferrari" if team_wins == "ferrari" else team_wins, "type": "ranking"},
        {"q": "Which driver has the most pole positions?", "expect": family_name(poles), "type": "ranking"},
        {"q": "How many Grands Prix has Monza hosted?", "expect": str(r[r.circuit_id == "monza"]["race_id"].nunique()), "type": "circuit"},
        {"q": "Who has won the most races at Monaco?", "expect": family_name(monaco_top), "type": "circuit ranking"},
        {"q": "Hamilton vs Rosberg: who finished ahead more often?", "expect": ahead, "type": "head to head"},
        {"q": "How many team-mate steps separate Fangio and Max Verstappen?", "expect": str(len(path)), "type": "graph"},
        {"q": "Which driver had the most different team-mates?", "expect": most_mates, "type": "graph"},
        {"q": "What is quality issue B29?", "expect": "2023", "type": "data quality"},
        {"q": "How many quality issues were found in the raw data?", "expect": str(len(issues)), "type": "data quality"},
        {"q": "What licence does the dataset use?", "expect": "CC BY-NC-SA", "type": "metadata"},
        {"q": "What are Max Verstappen's chances of a podium starting from pole?", "expect": pole_prob, "type": "model"},
        {"q": "Who won the 2030 World Championship?", "expect": None, "type": "must refuse"},
    ]


def contains(text: str, expected: str) -> bool:
    if expected.endswith("%"):
        return re.search(rf"(?<![\d.]){re.escape(expected[:-1])}\s*%", text) is not None
    if re.fullmatch(r"\d+", expected):
        return re.search(rf"(?<![\d.]){expected}(?![\d])", text) is not None
    return fold(expected) in fold(text)


def evaluate_case(eng, case: dict, use_llm: bool) -> dict:
    t0 = time.perf_counter()
    out = eng.ask(case["q"], use_llm=use_llm)
    items = out.get("evidence", {}).get("items", [])
    ev_text = " ".join(i["title"] + " " + " ".join(i["lines"]) for i in items)
    answer = out.get("answer", "")
    check = out.get("check", {})
    exp = case["expect"]
    row = {"question": case["q"], "type": case["type"], "expected": exp if exp is not None else "(refuse)",
           "evidence_blocks": len(items), "evidence_kinds": ",".join(i["kind"] for i in items),
           "in_evidence": contains(ev_text, exp) if exp else "outside this range" in ev_text,
           "mode": out.get("done", {}).get("mode"),
           "evidence_seconds": out.get("evidence", {}).get("seconds"),
           "total_seconds": round(time.perf_counter() - t0, 1)}
    if use_llm:
        row.update({"in_answer": contains(answer, exp) if exp else bool(REFUSAL.search(answer)),
                    "figures": check.get("numbers", 0), "figures_verified": check.get("verified", 0),
                    "all_figures_verified": not check.get("unverified"), "cites_evidence": bool(check.get("cited")),
                    "answer": " ".join(answer.split())[:600]})
    print(f"[{'ok' if row['in_evidence'] else 'MISS'}] {case['q']} -> {row.get('answer', '')[:120]}", flush=True)
    return row


def summarise(df: pd.DataFrame, use_llm: bool) -> dict:
    summary = {"questions": len(df), "evidence_contains_expected": int(df["in_evidence"].sum()),
               "median_evidence_seconds": float(df["evidence_seconds"].median())}
    if use_llm:
        written = df["mode"] == "llm"
        summary.update({"answers_written_by_model": int(written.sum()),
                        "answer_contains_expected": int(df["in_answer"].sum()),
                        "answers_with_all_figures_verified": int(df["all_figures_verified"].sum()),
                        "figures_total": int(df["figures"].sum()), "figures_verified": int(df["figures_verified"].sum()),
                        "answers_citing_evidence": int(df["cites_evidence"].sum()),
                        "median_total_seconds": float(df.loc[written, "total_seconds"].median()),
                        "hardware_note": "measured on a laptop CPU (no GPU); times depend on the machine"})
    return summary


def run(use_llm: bool = False, retry: bool = False) -> pd.DataFrame:
    """retry: re-ask only the questions whose stored answer was not written by the model."""
    from src.assistant.engine import engine
    eng = engine()
    name = "evaluation_llm" if use_llm else "evaluation_evidence"
    cases = ground_truth()
    path = OUT_DIR / f"{name}.csv"
    if retry and path.exists():
        df = pd.read_csv(path)
        failed = (df["mode"] != "llm") | df["answer"].fillna("").str.startswith("**")
        for i in df.index[failed]:
            case = next(c for c in cases if c["q"] == df.at[i, "question"])
            for k, v in evaluate_case(eng, case, use_llm).items():
                df.at[i, k] = v
    else:
        df = pd.DataFrame([evaluate_case(eng, c, use_llm) for c in cases])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    summary = summarise(df, use_llm)
    (OUT_DIR / f"{name}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--retry", action="store_true", help="re-ask only answers the model did not write")
    a = ap.parse_args()
    run(use_llm=a.llm, retry=a.retry)
