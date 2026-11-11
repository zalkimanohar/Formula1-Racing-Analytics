"""Team-mate network queries for the assistant (graph retrieval).

Reuses the projection built by src.graph_model (drivers linked when they drove for the same constructor
in the same Grand Prix, Indy 500 excluded) and the metrics it already wrote to outputs/graph/.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache

import networkx as nx
import pandas as pd

from src import config
from src.assistant.facts import Evidence, family_of, store
from src.graph_model import teammate_graph


class TeamMateGraph:
    def __init__(self) -> None:
        s = store()
        self.g = teammate_graph(s.results, s.drivers.reset_index())
        self.metrics = pd.read_csv(config.GRAPH_DIR / "teammate_node_metrics.csv").set_index("driver_id")
        self.network = pd.read_csv(config.GRAPH_DIR / "network_metrics.csv", index_col=0)["value"]
        self.communities = pd.read_csv(config.GRAPH_DIR / "communities.csv").set_index("community")
        path = config.GRAPH_DIR / "teammate_node_metrics.csv"
        self.src = {"dataset": "team-mate network built from data/cleaned/f1_race_results_clean.csv "
                               "(src/graph_model.py); metrics in outputs/graph/teammate_node_metrics.csv",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:12]}

    def name(self, did: str) -> str:
        return self.g.nodes[did]["name"] if did in self.g else store().driver_name(did)

    def path(self, a: str, b: str) -> Evidence:
        na, nb = self.name(a), self.name(b)
        src = {**self.src, "filter": f"shortest path {a} -> {b}", "rows": 0, "lineage": []}
        if a not in self.g or b not in self.g:
            return Evidence("graph", f"Team-mate chain {na} - {nb}",
                            [f"{na if a not in self.g else nb} is not in the team-mate network (no team-mate in a "
                             f"Grand Prix outside the Indy 500)."], src)
        try:
            nodes = nx.shortest_path(self.g, a, b)
        except nx.NetworkXNoPath:
            return Evidence("graph", f"Team-mate chain {na} - {nb}",
                            [f"No chain of team-mates connects {na} and {nb}: they are in different components."], src)
        hops = []
        for x, y in zip(nodes, nodes[1:]):
            e = self.g.edges[x, y]
            teams = ", ".join(dict.fromkeys(store().team_name(family_of(t)) for t in e["constructors"].split(", ")))
            hops.append(f"{self.name(x)} -> {self.name(y)}: team-mates at {teams} in {e['weight']} races")
        n_paths = sum(1 for _ in nx.all_shortest_paths(self.g, a, b)) if len(nodes) <= 7 else None
        lines = [f"Shortest team-mate chain from {na} to {nb}: {len(nodes) - 1} step(s)"] + hops
        if n_paths:
            lines.append(f"Number of different shortest chains of this length: {n_paths}")
        if len(nodes) == 2:
            lines.insert(0, f"{na} and {nb} were direct team-mates.")
        src["rows"] = len(nodes)
        src["path"] = [self.name(n) for n in nodes]
        return Evidence("graph", f"Team-mate chain {na} - {nb}", lines, src)

    def teammates(self, a: str, top: int = 10) -> Evidence:
        na = self.name(a)
        src = {**self.src, "filter": f"neighbours of {a}", "rows": 0, "lineage": []}
        if a not in self.g:
            return Evidence("graph", f"Team-mates of {na}", [f"{na} has no team-mates in the network."], src)
        nb = sorted(self.g[a].items(), key=lambda kv: -kv[1]["weight"])
        m = self.metrics.loc[a]
        rank_btw = int((self.metrics["betweenness"] > m["betweenness"]).sum()) + 1
        rank_deg = int((self.metrics["degree"] > m["degree"]).sum()) + 1
        comm = self.communities.loc[int(m["community"])] if pd.notna(m["community"]) else None
        lines = [f"{na} had {len(nb)} different team-mates (rank {rank_deg} of {len(self.metrics)} drivers by number "
                 f"of team-mates)",
                 "Most races together: " + "; ".join(f"{self.name(o)} {e['weight']} races" for o, e in nb[:top]),
                 f"Betweenness centrality rank: {rank_btw} of {len(self.metrics)} (how often {na} lies on the shortest "
                 f"chains between other drivers)"]
        if comm is not None:
            lines.append(f"Community {int(m['community'])} of {int(self.network['louvain_communities'])} (Louvain): "
                         f"{int(comm['drivers'])} drivers, debut years {int(comm['first_debut'])}-"
                         f"{int(comm['last_active'])}, most central: {comm['most_central_drivers']}")
        src["rows"] = len(nb)
        return Evidence("graph", f"Team-mates of {na}", lines, src)

    def most_connected(self, top: int = 8) -> Evidence:
        m = self.metrics
        by_deg = m.sort_values("degree", ascending=False).head(top)
        by_btw = m.sort_values("betweenness", ascending=False).head(5)
        lines = ["Drivers with the most different team-mates: " + "; ".join(
                     f"{r['name']} {int(r['degree'])}" for _, r in by_deg.iterrows()),
                 "Strongest bridges between generations (betweenness centrality): " + "; ".join(
                     f"{r['name']} {r['betweenness']:.3f}" for _, r in by_btw.iterrows())]
        return Evidence("graph", "Most connected drivers in the team-mate network", lines,
                        {**self.src, "filter": "rank by degree and betweenness", "rows": len(m),
                         "lineage": ["outputs/graph/teammate_node_metrics.csv"]})

    def overview(self) -> Evidence:
        n = self.network
        top = self.metrics.sort_values("betweenness", ascending=False).head(5)
        lines = [f"Team-mate network: {int(n['drivers_in_projection'])} drivers, {int(n['teammate_links'])} team-mate "
                 f"links, {int(n['connected_components'])} components; the largest holds "
                 f"{int(n['giant_component_drivers'])} drivers ({100 * n['giant_component_share']:.1f}%)",
                 f"Small world: clustering {n['average_clustering_giant']:.3f} vs {n['random_graph_clustering']:.3f} in a "
                 f"random graph of the same size; average chain length {n['average_shortest_path_giant']:.2f} vs "
                 f"{n['random_graph_shortest_path']:.2f}; sigma {n['small_world_sigma']:.1f}",
                 f"Louvain communities: {int(n['louvain_communities'])}, modularity {n['modularity']:.2f}",
                 "Highest betweenness (bridges between generations): " + "; ".join(
                     f"{r['name']} {r['betweenness']:.3f}" for _, r in top.iterrows())]
        return Evidence("graph", "Team-mate network overview", lines,
                        {**self.src, "filter": "whole network", "rows": int(n["drivers_in_projection"]),
                         "lineage": ["outputs/graph/network_metrics.csv"]})


@lru_cache(maxsize=1)
def graph() -> TeamMateGraph:
    return TeamMateGraph()
