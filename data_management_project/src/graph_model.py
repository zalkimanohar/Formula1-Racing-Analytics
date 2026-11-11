"""Group task - Property graph model of Formula 1 and network analytics with NetworkX.

Property graph (labelled nodes and typed edges, all with properties):
    (:Driver)-[:RACED_IN {grid, classified_position, points, status_group, car_number}]->(:Race)
    (:Driver)-[:DROVE_FOR {first_season, last_season, races, points, wins}]->(:Constructor)
    (:Race)-[:HELD_AT]->(:Circuit)-[:LOCATED_IN]->(:Country)
    (:Driver)-[:HAS_NATIONALITY]->(:Country)<-[:REGISTERED_IN]-(:Constructor)
    (:Driver)-[:TEAMMATE_OF {races_together, seasons}]-(:Driver)      (derived projection)

Analytics run on the TEAMMATE_OF projection, built from cleaned data. Indianapolis 500 rounds are
excluded from the projection because there the 'constructor' is a chassis builder, not a team
(Component B issue B16), which would create false team-mate links.
"""
from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd

from src import config
from src import plot_style as ps

ps.apply()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

SEED = config.RANDOM_SEED
SOURCE = "Source: cleaned F1 results 1950-2025 (Component C output); NetworkX analysis."


def load() -> dict[str, pd.DataFrame]:
    return {
        "results": pd.read_csv(config.CLEAN_RESULTS_CSV),
        "races": pd.read_csv(config.CLEAN_RACES_CSV),
        "circuits": pd.read_csv(config.CLEAN_CIRCUITS_CSV),
        "drivers": pd.read_csv(config.CLEAN_DRIVERS_CSV),
        "constructors": pd.read_csv(config.CLEAN_CONSTRUCTORS_CSV),
    }


def props(row: pd.Series, keys) -> dict:
    """Node/edge properties without missing values (GEXF cannot store nulls)."""
    out = {}
    for k in keys:
        v = row[k]
        if pd.isna(v):
            continue
        out[k] = v.item() if hasattr(v, "item") else v
    return out


# --------------------------------------------------------------------------------------------
# Property graph
# --------------------------------------------------------------------------------------------
def build_property_graph(d: dict[str, pd.DataFrame]) -> nx.MultiDiGraph:
    res, races, circ, drv, con = d["results"], d["races"], d["circuits"], d["drivers"], d["constructors"]
    g = nx.MultiDiGraph(name="F1 property graph 1950-2025")
    used_races = races[races["has_results"]]
    countries = pd.concat([
        circ[["country_iso3", "country"]].rename(columns={"country_iso3": "iso", "country": "name"}),
        drv[["nationality_iso3", "nationality"]].rename(columns={"nationality_iso3": "iso", "nationality": "name"}),
        con[["nationality_iso3", "nationality"]].rename(columns={"nationality_iso3": "iso", "nationality": "name"}),
    ]).dropna().drop_duplicates("iso")
    for _, c in countries.iterrows():
        g.add_node(f"country:{c['iso']}", label="Country", iso_code=c["iso"], name=c["name"])
    for _, c in circ.iterrows():
        g.add_node(f"circuit:{c['circuit_id']}", label="Circuit",
                   **props(c, ["circuit_id", "circuit_name", "locality", "latitude", "longitude", "wikidata_qid"]))
        g.add_edge(f"circuit:{c['circuit_id']}", f"country:{c['country_iso3']}", key="LOCATED_IN", type="LOCATED_IN")
    for _, r in used_races.iterrows():
        g.add_node(f"race:{r['race_id']}", label="Race",
                   **props(r, ["race_id", "race_name", "race_date", "season", "round"]))
        g.add_edge(f"race:{r['race_id']}", f"circuit:{r['circuit_id']}", key="HELD_AT", type="HELD_AT")
    active_drivers = set(res["driver_id"])
    for _, p in drv[drv["driver_id"].isin(active_drivers)].iterrows():
        g.add_node(f"driver:{p['driver_id']}", label="Driver",
                   **props(p, ["driver_id", "full_name", "date_of_birth", "nationality_iso3", "wikidata_qid"]))
        if pd.notna(p["nationality_iso3"]):
            g.add_edge(f"driver:{p['driver_id']}", f"country:{p['nationality_iso3']}", key="HAS_NATIONALITY",
                       type="HAS_NATIONALITY")
    for _, c in con[con["constructor_id"].isin(set(res["constructor_id"]))].iterrows():
        g.add_node(f"constructor:{c['constructor_id']}", label="Constructor",
                   **props(c, ["constructor_id", "constructor_name", "nationality_iso3", "wikidata_qid"]))
        g.add_edge(f"constructor:{c['constructor_id']}", f"country:{c['nationality_iso3']}", key="REGISTERED_IN",
                   type="REGISTERED_IN")
    for _, r in res.iterrows():
        g.add_edge(f"driver:{r['driver_id']}", f"race:{r['race_id']}", key=r["result_id"], type="RACED_IN",
                   **props(r, ["grid_position", "classified_position", "points", "points_normalised",
                               "status_group", "car_number", "constructor_id"]))
    drove = (res.groupby(["driver_id", "constructor_id"])
             .agg(first_season=("season", "min"), last_season=("season", "max"), races=("race_id", "nunique"),
                  points=("points", "sum"), wins=("classified_position", lambda s: int((s == 1).sum())))
             .reset_index())
    for _, e in drove.iterrows():
        g.add_edge(f"driver:{e['driver_id']}", f"constructor:{e['constructor_id']}", key="DROVE_FOR",
                   type="DROVE_FOR", **props(e, ["first_season", "last_season", "races", "points", "wins"]))
    return g


def schema_summary(g: nx.MultiDiGraph) -> tuple[pd.DataFrame, pd.DataFrame]:
    nodes = pd.Series(nx.get_node_attributes(g, "label")).value_counts().rename_axis("node_label").reset_index(name="count")
    edges = pd.Series([d["type"] for _, _, d in g.edges(data=True)]).value_counts().rename_axis("edge_type").reset_index(name="count")
    return nodes, edges


# --------------------------------------------------------------------------------------------
# Team-mate projection and analytics
# --------------------------------------------------------------------------------------------
def teammate_graph(res: pd.DataFrame, drivers: pd.DataFrame) -> nx.Graph:
    f1 = res[~res["is_indy500"]]
    pairs = f1[["race_id", "season", "constructor_id", "driver_id"]].drop_duplicates()
    m = pairs.merge(pairs, on=["race_id", "season", "constructor_id"], suffixes=("_a", "_b"))
    m = m[m["driver_id_a"] < m["driver_id_b"]]
    w = (m.groupby(["driver_id_a", "driver_id_b"])
         .agg(races_together=("race_id", "nunique"), seasons=("season", "nunique"),
              constructors=("constructor_id", lambda s: ", ".join(sorted(set(s)))))
         .reset_index())
    g = nx.Graph(name="F1 team-mate network (Indy 500 excluded)")
    career = (f1.groupby("driver_id")
              .agg(first_season=("season", "min"), last_season=("season", "max"), starts=("race_id", "nunique"),
                   points=("points", "sum"), wins=("classified_position", lambda s: int((s == 1).sum())))
              .reset_index())
    names = drivers.set_index("driver_id")["full_name"]
    for _, c in career.iterrows():
        g.add_node(c["driver_id"], name=str(names.get(c["driver_id"], c["driver_id"])),
                   first_season=int(c["first_season"]), last_season=int(c["last_season"]),
                   starts=int(c["starts"]), points=float(c["points"]), wins=int(c["wins"]))
    for _, e in w.iterrows():
        g.add_edge(e["driver_id_a"], e["driver_id_b"], weight=int(e["races_together"]),
                   distance=1.0 / int(e["races_together"]), seasons=int(e["seasons"]), constructors=e["constructors"])
    return g


def analytics(g: nx.Graph) -> tuple[pd.DataFrame, dict, list]:
    comps = sorted(nx.connected_components(g), key=len, reverse=True)
    giant = g.subgraph(comps[0]).copy()
    deg = nx.degree_centrality(g)
    btw = nx.betweenness_centrality(giant, normalized=True)
    pr = nx.pagerank(giant, weight="weight")
    communities = nx.community.louvain_communities(giant, weight="weight", seed=SEED, resolution=1.0)
    communities = sorted(communities, key=lambda c: np.median([giant.nodes[n]["first_season"] for n in c]))
    comm_of = {n: i + 1 for i, c in enumerate(communities) for n in c}
    modularity = nx.community.modularity(giant, communities, weight="weight")

    nodes = pd.DataFrame([{"driver_id": n, **g.nodes[n]} for n in g.nodes])
    nodes["degree"] = nodes["driver_id"].map(dict(g.degree()))
    nodes["degree_centrality"] = nodes["driver_id"].map(deg)
    nodes["betweenness"] = nodes["driver_id"].map(btw)
    nodes["pagerank"] = nodes["driver_id"].map(pr)
    nodes["community"] = nodes["driver_id"].map(comm_of).astype("Int64")
    nodes["in_giant_component"] = nodes["driver_id"].isin(comps[0])

    clustering = nx.average_clustering(giant)
    aspl = nx.average_shortest_path_length(giant)
    n, m = giant.number_of_nodes(), giant.number_of_edges()
    rng_clust, rng_aspl = [], []
    for i in range(5):
        rnd = nx.gnm_random_graph(n, m, seed=SEED + i)
        rnd = rnd.subgraph(max(nx.connected_components(rnd), key=len))
        rng_clust.append(nx.average_clustering(rnd))
        rng_aspl.append(nx.average_shortest_path_length(rnd))
    c_r, l_r = float(np.mean(rng_clust)), float(np.mean(rng_aspl))
    metrics = {
        "drivers_in_projection": g.number_of_nodes(),
        "teammate_links": g.number_of_edges(),
        "density": nx.density(g),
        "connected_components": len(comps),
        "giant_component_drivers": n,
        "giant_component_share": n / g.number_of_nodes(),
        "isolated_drivers": sum(1 for c in comps if len(c) == 1),
        "average_degree": 2 * g.number_of_edges() / g.number_of_nodes(),
        "average_clustering_giant": clustering,
        "average_shortest_path_giant": aspl,
        "diameter_giant": nx.diameter(giant),
        "random_graph_clustering": c_r,
        "random_graph_shortest_path": l_r,
        "small_world_sigma": (clustering / c_r) / (aspl / l_r),
        "louvain_communities": len(communities),
        "modularity": modularity,
        "degree_assortativity": nx.degree_assortativity_coefficient(giant),
    }
    community_rows = []
    for i, c in enumerate(communities, start=1):
        sub = nodes[nodes["community"] == i]
        top = sub.sort_values("pagerank", ascending=False).head(3)["name"].tolist()
        community_rows.append({"community": i, "drivers": len(c), "first_debut": int(sub["first_season"].min()),
                               "median_debut": float(sub["first_season"].median()),
                               "last_active": int(sub["last_season"].max()), "most_central_drivers": "; ".join(top)})
    return nodes, metrics, community_rows


def teammate_path(g: nx.Graph, source: str, target: str) -> list[dict]:
    path = nx.shortest_path(g, source, target)
    steps = []
    for a, b in zip(path, path[1:]):
        e = g.edges[a, b]
        steps.append({"from": g.nodes[a]["name"], "to": g.nodes[b]["name"], "constructors": e["constructors"],
                      "races_together": e["weight"]})
    return steps


# --------------------------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------------------------
def fig_schema(node_counts: pd.DataFrame, edge_counts: pd.DataFrame, path) -> None:
    nc = dict(zip(node_counts["node_label"], node_counts["count"]))
    ec = dict(zip(edge_counts["edge_type"], edge_counts["count"]))
    boxes = {
        "Driver": (0.17, 0.62, "driver_id, full_name,\ndate_of_birth, wikidata_qid"),
        "Race": (0.58, 0.62, "race_id, race_name,\nrace_date, season, round"),
        "Constructor": (0.17, 0.16, "constructor_id, name,\nwikidata_qid"),
        "Circuit": (0.86, 0.36, "circuit_id, name, lat/long,\nwikidata_qid"),
        "Country": (0.58, 0.10, "iso_code (ISO 3166),\nname"),
    }
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 0.92)
    ax.axis("off")
    w, h = 0.25, 0.17
    for i, (label, (x, y, attrs)) in enumerate(boxes.items()):
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.008,rounding_size=0.02",
                                    facecolor=ps.SURFACE, edgecolor=ps.CATEGORICAL[i], linewidth=1.8))
        ax.text(x, y + 0.045, f":{label}  ({nc.get(label, 0):,})", ha="center", va="center", fontsize=9.5,
                fontweight="semibold", color=ps.INK)
        ax.text(x, y - 0.025, attrs, ha="center", va="center", fontsize=7.2, color=ps.INK_SECONDARY)

    def arrow(start, end, text, label_xy):
        ax.annotate("", xy=end, xytext=start,
                    arrowprops=dict(arrowstyle="-|>", color=ps.INK_MUTED, lw=1.1, shrinkA=0, shrinkB=1))
        ax.text(*label_xy, text, ha="center", va="center", fontsize=7.2, color=ps.INK,
                bbox=dict(boxstyle="round,pad=0.25", facecolor=ps.SURFACE, edgecolor="none"))

    arrow((0.297, 0.64), (0.453, 0.64), f"RACED_IN ({ec.get('RACED_IN', 0):,})", (0.375, 0.675))
    ax.text(0.375, 0.585, "grid, position,\npoints, status", ha="center", va="center", fontsize=7, color=ps.INK_SECONDARY)
    arrow((0.17, 0.533), (0.17, 0.247), f"DROVE_FOR ({ec.get('DROVE_FOR', 0):,})\nfirst/last season, races,\npoints, wins",
          (0.17, 0.39))
    arrow((0.66, 0.533), (0.82, 0.447), f"HELD_AT ({ec.get('HELD_AT', 0):,})", (0.80, 0.525))
    arrow((0.80, 0.273), (0.707, 0.14), f"LOCATED_IN ({ec.get('LOCATED_IN', 0)})", (0.83, 0.20))
    arrow((0.26, 0.533), (0.56, 0.187), f"HAS_NATIONALITY ({ec.get('HAS_NATIONALITY', 0)})", (0.43, 0.36))
    arrow((0.297, 0.12), (0.453, 0.10), f"REGISTERED_IN ({ec.get('REGISTERED_IN', 0)})", (0.375, 0.05))
    ax.annotate("", xy=(0.23, 0.707), xytext=(0.11, 0.707),
                arrowprops=dict(arrowstyle="-", color=ps.CATEGORICAL[0], lw=1.2, shrinkA=0, shrinkB=0,
                                connectionstyle="arc3,rad=-1.2"))
    ax.text(0.17, 0.835, "TEAMMATE_OF (derived)\nraces_together, seasons", ha="center", va="bottom", fontsize=7.2,
            color=ps.INK)
    ps.titles(ax, "Property graph model: 5 node labels, 7 relationship types",
              "Counts are instances in the NetworkX graph built from the cleaned data.")
    ps.source_note(fig, SOURCE)
    ps.save(fig, path)


def fig_network(g: nx.Graph, nodes: pd.DataFrame, path) -> None:
    giant = g.subgraph(nodes.loc[nodes["in_giant_component"], "driver_id"]).copy()
    pos = nx.spring_layout(giant, weight="weight", seed=SEED, k=0.9 / np.sqrt(giant.number_of_nodes()), iterations=150)
    comm = nodes.set_index("driver_id")["community"]
    sizes = comm.loc[list(giant.nodes)].value_counts()
    top = list(sizes.index[:7])
    colour = {c: ps.CATEGORICAL[i] for i, c in enumerate(sorted(top))}
    fig, ax = plt.subplots(figsize=(7.6, 6.2))
    ax.axis("off")
    nx.draw_networkx_edges(giant, pos, ax=ax, width=0.25, edge_color=ps.GRID, alpha=0.9)
    btw = nodes.set_index("driver_id")["betweenness"]
    node_list = list(giant.nodes)
    nx.draw_networkx_nodes(giant, pos, ax=ax, nodelist=node_list,
                           node_size=[8 + 900 * btw[n] for n in node_list],
                           node_color=[colour.get(comm[n], ps.NEUTRAL) for n in node_list],
                           linewidths=0.4, edgecolors=ps.SURFACE)
    label_ids = btw.loc[node_list].sort_values(ascending=False).head(10).index
    xs = np.array([p[0] for p in pos.values()])
    ys = np.array([p[1] for p in pos.values()])
    char_w, line_h = 0.0085 * (xs.max() - xs.min()), 0.035 * (ys.max() - ys.min())
    placed: list[tuple[float, float, float]] = []
    for n in label_ids:
        x, y = pos[n]
        name = giant.nodes[n]["name"]
        half = len(name) * char_w / 2
        ly = y + line_h
        while any(abs(ly - py) < line_h and abs(x - px) < half + ph for px, py, ph in placed):
            ly += line_h
        placed.append((x, ly, half))
        if ly - y > line_h * 1.5:
            ax.plot([x, x], [y, ly - line_h * 0.4], color=ps.INK_MUTED, lw=0.6)
        ax.text(x, ly, name, fontsize=7, ha="center", va="center", color=ps.INK,
                bbox=dict(boxstyle="round,pad=0.15", facecolor=ps.SURFACE, edgecolor="none", alpha=0.9))
    era = nodes.groupby("community")["first_season"].median()
    handles = [plt.Line2D([], [], marker="o", ls="", color=colour[c], markersize=6,
                          label=f"Community {c} (median debut {era[c]:.0f})") for c in sorted(top)]
    handles.append(plt.Line2D([], [], marker="o", ls="", color=ps.NEUTRAL, markersize=6, label="Smaller communities"))
    ax.legend(handles=handles, loc="lower right", fontsize=7.5)
    ps.titles(ax, "The team-mate network is organised by era",
              f"{giant.number_of_nodes()} drivers in the giant component; colour = Louvain community, "
              f"size = betweenness; top-10 bridges labelled.")
    ps.source_note(fig, SOURCE)
    ps.save(fig, path)


def fig_centrality(nodes: pd.DataFrame, path) -> pd.DataFrame:
    top = nodes.sort_values("betweenness", ascending=False).head(12).iloc[::-1]
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 4.0), sharey=True)
    y = np.arange(len(top))
    axes[0].barh(y, top["betweenness"], height=0.62, color=ps.CATEGORICAL[0])
    axes[0].set_yticks(y, top["name"])
    axes[0].set_xlabel("Betweenness centrality")
    axes[1].barh(y, top["degree"], height=0.62, color=ps.CATEGORICAL[0])
    axes[1].set_xlabel("Degree (distinct team-mates)")
    for ax in axes:
        ax.grid(axis="y", visible=False)
    for yi, v in zip(y, top["betweenness"]):
        axes[0].text(v, yi, f" {v:.3f}", va="center", fontsize=7.5, color=ps.INK_SECONDARY)
    for yi, v in zip(y, top["degree"]):
        axes[1].text(v, yi, f" {v}", va="center", fontsize=7.5, color=ps.INK_SECONDARY)
    ps.titles(axes[0], "Bridges between eras: top 12 drivers by betweenness",
              "Long careers across many teams connect otherwise separate generations.")
    ps.source_note(fig, SOURCE)
    fig.tight_layout()
    ps.save(fig, path)
    return top.iloc[::-1][["name", "first_season", "last_season", "degree", "betweenness", "pagerank", "community"]]


def fig_communities(community_rows: list[dict], path) -> pd.DataFrame:
    df = pd.DataFrame(community_rows).sort_values("median_debut", ascending=False)
    df = df[df["drivers"] >= 10]
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    y = np.arange(len(df))
    ax.hlines(y, df["first_debut"], df["last_active"], color=ps.CATEGORICAL[0], lw=2)
    ax.scatter(df["median_debut"], y, s=40, color=ps.CATEGORICAL[0], zorder=3, edgecolor=ps.SURFACE, linewidth=2)
    for yi, (_, r) in zip(y, df.iterrows()):
        ax.text(r["last_active"] + 1, yi, f"{r['drivers']} drivers · {r['most_central_drivers'].split('; ')[0]}",
                va="center", fontsize=7.5, color=ps.INK_SECONDARY)
    ax.set_yticks(y, [f"Community {c}" for c in df["community"]])
    ax.set_xlim(1948, 2060)
    ax.set_xticks(range(1950, 2030, 10))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Season (line: first debut to last season active; dot: median debut)")
    ps.titles(ax, "Communities found without any date information line up with eras",
              "Louvain communities of the team-mate network (>= 10 drivers); label = most central driver (PageRank).")
    ps.source_note(fig, SOURCE)
    ps.save(fig, path)
    return df


def run() -> dict:
    config.ensure_dirs()
    d = load()
    pg = build_property_graph(d)
    node_counts, edge_counts = schema_summary(pg)
    tg = teammate_graph(d["results"], d["drivers"])
    nodes, metrics, community_rows = analytics(tg)

    nodes.to_csv(config.GRAPH_DIR / "teammate_node_metrics.csv", index=False)
    pd.DataFrame([metrics]).T.rename(columns={0: "value"}).to_csv(config.GRAPH_DIR / "network_metrics.csv")
    pd.DataFrame(community_rows).to_csv(config.GRAPH_DIR / "communities.csv", index=False)
    node_counts.to_csv(config.GRAPH_DIR / "property_graph_node_counts.csv", index=False)
    edge_counts.to_csv(config.GRAPH_DIR / "property_graph_edge_counts.csv", index=False)
    path = teammate_path(tg, "fangio", "max_verstappen")
    pd.DataFrame(path).to_csv(config.GRAPH_DIR / "shortest_teammate_path_fangio_verstappen.csv", index=False)

    for n, attrs in tg.nodes(data=True):
        row = nodes.set_index("driver_id").loc[n]
        attrs.update(betweenness=float(row["betweenness"]) if pd.notna(row["betweenness"]) else 0.0,
                     pagerank=float(row["pagerank"]) if pd.notna(row["pagerank"]) else 0.0,
                     community=int(row["community"]) if pd.notna(row["community"]) else 0)
    nx.write_gexf(tg, config.GRAPH_DIR / "f1_teammate_network.gexf")
    nx.write_gexf(pg, config.GRAPH_DIR / "f1_property_graph.gexf")

    fig_schema(node_counts, edge_counts, config.GRAPH_FIG_DIR / "fig_g1_property_graph_model.png")
    fig_network(tg, nodes, config.GRAPH_FIG_DIR / "fig_g2_teammate_network.png")
    fig_centrality(nodes, config.GRAPH_FIG_DIR / "fig_g3_centrality.png").to_csv(
        config.GRAPH_DIR / "top_betweenness.csv", index=False)
    fig_communities(community_rows, config.GRAPH_FIG_DIR / "fig_g4_communities_by_era.png")
    summary = {**{k: (round(v, 4) if isinstance(v, float) else v) for k, v in metrics.items()},
               "property_graph_nodes": pg.number_of_nodes(), "property_graph_edges": pg.number_of_edges(),
               "fangio_to_verstappen_hops": len(path)}
    print("[graph] summary:", summary)
    return summary


if __name__ == "__main__":
    run()
