"""Build static/data.js for the dashboard from the cleaned, validated dataset.

Reads the outputs of data_management_project (cleaned tables, graph metrics, quality and FAIR
results) and writes compact aggregates as `window.F1 = {...}`.

    python build_web_data.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
# Repository layout: <repo>/dashboard next to <repo>/data_management_project.
# Submission ZIP layout: F1_DataManagement_Group/dashboard next to F1_DataManagement_Group/src.
PROJECT = HERE.parent / "data_management_project"
if not (PROJECT / "src" / "config.py").exists():
    PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT))

from src import config  # noqa: E402
from src.graph_model import teammate_graph  # noqa: E402

OUT = HERE / "static" / "data.js"

FAMILY_NAMES = {
    "ferrari": "Ferrari", "mclaren": "McLaren", "mercedes": "Mercedes", "red_bull": "Red Bull",
    "williams": "Williams", "lotus": "Lotus", "renault": "Renault", "brabham": "Brabham",
    "benetton": "Benetton", "tyrrell": "Tyrrell", "cooper": "Cooper", "brm": "BRM", "alfa": "Alfa Romeo",
    "maserati": "Maserati", "vanwall": "Vanwall", "matra": "Matra", "ligier": "Ligier", "brawn": "Brawn",
    "march": "March", "jordan": "Jordan", "kurtis_kraft": "Kurtis Kraft", "watson": "Watson",
}
# Stack order is part of the colour-safety design: the two blue teams (Williams, Red Bull) never touch.
MAIN_TEAMS = ["Ferrari", "Williams", "McLaren", "Lotus", "Red Bull", "Renault", "Mercedes"]


def family(constructor_id: str) -> str:
    base = constructor_id.replace("team_lotus", "lotus").split("-")[0]
    return FAMILY_NAMES.get(base, base.replace("_", " ").title())


def driver_code(family_name: str) -> str:
    letters = "".join(ch for ch in family_name.upper() if ch.isalpha())
    return (letters + "XXX")[:3]


def r(x, nd=4):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def build() -> dict:
    res = pd.read_csv(config.CLEAN_RESULTS_CSV)
    drivers = pd.read_csv(config.CLEAN_DRIVERS_CSV)
    circuits = pd.read_csv(config.CLEAN_CIRCUITS_CSV)
    res["team"] = res["constructor_id"].map(family)
    res["win"] = res["classified_position"] == 1
    res["podium"] = res["classified_position"] <= 3
    res["pole"] = res["grid_position"] == 1
    seasons = sorted(res["season"].unique().tolist())

    kpi = {
        "results": len(res), "seasons": len(seasons), "first": int(seasons[0]), "last": int(seasons[-1]),
        "gps": int(res["race_id"].nunique()), "drivers": int(res["driver_id"].nunique()),
        "constructors": int(res["constructor_id"].nunique()), "circuits": int(res["circuit_id"].nunique()),
        "countries": int(res["circuit_country_iso3"].nunique()),
        "first_race": res["race_date"].min(), "last_race": res["race_date"].max(),
    }

    # ---- eras: wins per team family per season -------------------------------------------
    wins = res[res["win"]].copy()
    wins["team_group"] = np.where(wins["team"].isin(MAIN_TEAMS), wins["team"], "Other")
    eras = (wins.groupby(["season", "team_group"]).size().unstack(fill_value=0)
            .reindex(index=seasons, fill_value=0).reindex(columns=MAIN_TEAMS + ["Other"], fill_value=0))
    team_totals = wins.groupby("team").size().sort_values(ascending=False)

    # ---- drivers: per-season stats for client-side range aggregation ------------------------
    ds = (res.groupby(["driver_id", "season"])
          .agg(starts=("race_id", "nunique"), wins=("win", "sum"), podiums=("podium", "sum"),
               poles=("pole", "sum"), points=("points", "sum"), score=("points_normalised", "sum"))
          .reset_index())
    main_team = (res.groupby(["driver_id", "team"]).size().reset_index(name="n")
                 .sort_values("n", ascending=False).drop_duplicates("driver_id").set_index("driver_id")["team"])
    dinfo = drivers.set_index("driver_id")
    driver_meta = {}
    for did in res["driver_id"].unique():
        row = dinfo.loc[did]
        driver_meta[did] = {"n": row["full_name"], "c": driver_code(str(row["family_name"])),
                            "nat": None if pd.isna(row["nationality_iso3"]) else row["nationality_iso3"],
                            "t": main_team.get(did, "Other")}
    driver_seasons = [[d, int(s), int(st), int(w), int(p), int(pl), r(pt, 2), r(sc, 3)]
                      for d, s, st, w, p, pl, pt, sc in ds.itertuples(index=False)]
    champions = (ds.sort_values(["season", "points", "wins"], ascending=[True, False, False])
                 .drop_duplicates("season")[["season", "driver_id"]])

    # ---- grid -> finish (sparse counts per season; finish 0 = not classified) ---------------
    gf = res[(res["grid_position"].between(1, 20)) & (~res["is_indy500"])].copy()
    cls = gf["classified_position"]
    gf["fin"] = np.select([cls.isna(), cls > 20], [0, 21], default=cls.fillna(0)).astype(int)
    grid_finish = (gf.groupby(["season", "grid_position", "fin"]).size().reset_index(name="n")
                   .astype(int).values.tolist())
    deep = (res[res["win"] & ~res["is_indy500"] & res["grid_position"].notna()]
            .sort_values(["grid_position", "season"], ascending=[False, True]).head(8))
    deep_wins = [[row.driver_name, row.race_name, int(row.season), int(row.grid_position)]
                 for row in deep.itertuples()]

    # ---- reliability: status groups per season ---------------------------------------------
    status_order = ["Finished", "Finished (lapped)", "Mechanical or technical failure", "Accident or collision",
                    "Did not start or withdrew", "Disqualified or excluded", "Driver health or safety",
                    "Retired (unspecified) or not classified"]
    st = (res.groupby(["season", "status_group"]).size().unstack(fill_value=0)
          .reindex(index=seasons, fill_value=0).reindex(columns=status_order, fill_value=0))

    # ---- circuits -----------------------------------------------------------------------------
    circ_rows = []
    by_circ = res.groupby("circuit_id")
    top_winner = (wins.groupby(["circuit_id", "driver_name"]).size().reset_index(name="w")
                  .sort_values(["circuit_id", "w"], ascending=[True, False]).drop_duplicates("circuit_id")
                  .set_index("circuit_id"))
    cinfo = circuits.set_index("circuit_id")
    for cid, g in by_circ:
        c = cinfo.loc[cid]
        if pd.isna(c["latitude"]):
            continue
        circ_rows.append({
            "id": cid, "n": c["circuit_name"], "loc": c["locality"], "country": c["country"],
            "lat": r(c["latitude"], 4), "lon": r(c["longitude"], 4),
            "seasons": sorted(g.drop_duplicates("race_id")["season"].astype(int).tolist()),
            "king": None if cid not in top_winner.index else
            [top_winner.loc[cid, "driver_name"], int(top_winner.loc[cid, "w"])],
        })

    # ---- team-mate network --------------------------------------------------------------------
    tg = teammate_graph(res, drivers)
    giant = tg.subgraph(max(nx.connected_components(tg), key=len)).copy()
    pos = nx.spring_layout(giant, weight="weight", seed=config.RANDOM_SEED,
                           k=0.9 / np.sqrt(giant.number_of_nodes()), iterations=200)
    metrics = pd.read_csv(config.GRAPH_DIR / "teammate_node_metrics.csv").set_index("driver_id")
    index = {n: i for i, n in enumerate(giant.nodes)}
    nodes = []
    for n in giant.nodes:
        m = metrics.loc[n]
        nodes.append([n, r(pos[n][0], 4), r(pos[n][1], 4), int(m["community"]), r(m["betweenness"], 5),
                      int(m["degree"]), int(m["first_season"]), int(m["last_season"]), int(m["wins"])])
    edges = [[index[a], index[b], int(d["weight"])] for a, b, d in giant.edges(data=True)]
    path = nx.shortest_path(giant, "fangio", "max_verstappen")
    communities = pd.read_csv(config.GRAPH_DIR / "communities.csv")
    net_metrics = pd.read_csv(config.GRAPH_DIR / "network_metrics.csv", index_col=0)["value"]

    # ---- data quality story ---------------------------------------------------------------------
    issues = pd.read_csv(config.QUALITY_DIR / "quality_issues.csv").set_index("issue_id")
    gates = pd.read_csv(config.CLEANING_DIR / "validation_report.csv")
    rda = pd.read_csv(config.FAIR_DIR / "rda_fair_summary.csv").set_index("area")
    fuji = pd.read_csv(config.FAIR_DIR / "fuji_summary.csv").set_index("resource")
    pid = pd.read_csv(config.FAIR_DIR / "pid_coverage.csv").set_index("entity_type")
    quality = {
        "issues": len(issues), "dimensions": int(issues["dimension"].nunique()),
        "disguised": int(issues.loc["B11", "affected_records"] + issues.loc["B04", "affected_records"]),
        "nulls": 18, "duplicates": int(issues.loc["B06", "affected_records"] + issues.loc["B07", "affected_records"]),
        "hidden_duplicates": int(issues.loc["B07", "affected_records"]),
        "shared_drives": int(issues.loc["B08", "affected_records"]), "status_raw": 136, "status_groups": 8,
        "gates": len(gates), "gates_passed": int((gates["result"] == "passed").sum()),
        "rda_before": float(rda.loc["Overall", "as_obtained_progress_percent"]),
        "rda_after": float(rda.loc["Overall", "curated_progress_percent"]),
        "fuji_github": float(fuji.loc["github_repository", "fair_percent"]),
        "fuji_kaggle": float(fuji.loc["kaggle_ergast_mirror", "fair_percent"]),
        "qid_drivers": float(pid.loc["driver", "qid_coverage_percent"]),
        "rows_raw": 25907, "rows_clean": len(res),
    }

    names = [f"{m['given_name']} {m['family_name']}" for m in config.TEAM]
    return {
        "team": ", ".join(names[:-1]) + " and " + names[-1],
        "kpi": kpi, "seasons": seasons,
        "eras": {"teams": MAIN_TEAMS + ["Other"], "rows": eras.values.tolist(),
                 "totals": {k: int(v) for k, v in team_totals.head(12).items()}},
        "drivers": driver_meta, "driverSeasons": driver_seasons,
        "champions": {int(s): d for s, d in champions.values},
        "gridFinish": grid_finish, "deepWins": deep_wins,
        "status": {"groups": status_order, "rows": st.values.tolist()},
        "circuits": circ_rows,
        "network": {"nodes": nodes, "edges": edges, "path": [index[p] for p in path],
                    "pathVia": [[family(c) for c in giant.edges[a, b]["constructors"].split(", ")]
                                for a, b in zip(path, path[1:])],
                    "communities": communities.to_dict("records"),
                    "metrics": {k: r(v, 4) for k, v in net_metrics.items()}},
        "quality": quality,
    }


def main() -> None:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=lambda o: o.item())
    OUT.write_text(f"window.F1 = {payload};\n", encoding="utf-8")
    print(f"[web] wrote {OUT.name}: {OUT.stat().st_size / 1e3:.0f} kB, "
          f"{len(data['driverSeasons'])} driver-seasons, {len(data['circuits'])} circuits, "
          f"{len(data['network']['nodes'])} network nodes, {len(data['network']['edges'])} edges")


if __name__ == "__main__":
    main()
