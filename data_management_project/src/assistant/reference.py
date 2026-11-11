"""Official Drivers' World Champions, reconciled with the points in the cleaned dataset.

The results table holds points per race, not the official standings: until 1990 only a driver's best
results counted (dropped scores), and from 2021 sprint points are not part of the Grand Prix results.
The champion of each season is therefore taken from Wikidata (season item -> P1346 "winner"), resolved
through the English Wikipedia season article, and compared with the driver who scored the most Grand Prix
points in our data. Disagreements are expected and explained (1964, 1988: dropped scores). Seasons with no
winner statement in Wikidata fall back to the points leader and are flagged.

The table is cached in data/reference/official_champions.csv, so later runs work offline.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

import pandas as pd

from src import config

CHAMPIONS_CSV = config.REFERENCE_DIR / "official_champions.csv"
USER_AGENT = ("F1-DataManagement-StudentProject/1.0 "
              "(educational use; https://github.com/zalkimanohar/Formula1-Racing-Analytics)")
TITLE_PATTERNS = ("{y} Formula One World Championship", "{y} Formula One season")
DROPPED_SCORES_NOTE = ("Official champion under the dropped-scores rule (only the best results counted); "
                       "another driver scored more points in total.")


def _get(url: str, params: dict) -> dict:
    request = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except OSError:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def _season_qids(seasons: range) -> dict[int, str]:
    found: dict[int, str] = {}
    for pattern in TITLE_PATTERNS:
        titles = [pattern.format(y=y) for y in seasons if y not in found]
        for i in range(0, len(titles), 50):
            q = _get("https://en.wikipedia.org/w/api.php",
                     {"action": "query", "titles": "|".join(titles[i:i + 50]), "prop": "pageprops",
                      "ppprop": "wikibase_item", "redirects": 1, "format": "json"})["query"]
            back = {r["to"]: r["from"] for r in q.get("redirects", [])}
            for n in q.get("normalized", []):
                back.setdefault(n["to"], n["from"])
            for page in q["pages"].values():
                title = back.get(page["title"], page["title"])
                qid = page.get("pageprops", {}).get("wikibase_item")
                if qid:
                    found[int(title[:4])] = qid
    return found


def _winners(qids: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for i in range(0, len(qids), 50):
        entities = _get("https://www.wikidata.org/w/api.php",
                        {"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]), "props": "claims",
                         "format": "json"})["entities"]
        for qid, entity in entities.items():
            out[qid] = [c["mainsnak"]["datavalue"]["value"]["id"] for c in entity.get("claims", {}).get("P1346", [])
                        if "datavalue" in c["mainsnak"]]
    return out


def build_official_champions(refresh: bool = False) -> pd.DataFrame:
    if CHAMPIONS_CSV.exists() and not refresh:
        return pd.read_csv(CHAMPIONS_CSV)
    seasons = range(config.FIRST_SEASON, config.LAST_COMPLETE_SEASON + 1)
    season_qid = _season_qids(seasons)
    winners = _winners(sorted(set(season_qid.values())))
    drivers = pd.read_csv(config.CLEAN_DRIVERS_CSV).dropna(subset=["wikidata_qid"])
    driver_of_qid = drivers.set_index("wikidata_qid")["driver_id"]
    results = pd.read_csv(config.CLEAN_RESULTS_CSV)
    totals = (results.groupby(["season", "driver_id"])["points"].sum().reset_index()
              .sort_values(["season", "points"], ascending=[True, False]))
    leader = totals.drop_duplicates("season").set_index("season")
    rows = []
    for y in seasons:
        qid = season_qid.get(y)
        matched = [driver_of_qid[w] for w in winners.get(qid, []) if w in driver_of_qid.index] if qid else []
        points_leader = leader.loc[y, "driver_id"]
        if len(matched) == 1:
            champion, method = matched[0], "Wikidata P1346 (winner) of the season item"
        else:
            champion, method = points_leader, "Grand Prix points leader (no winner statement in Wikidata)"
        champion_points = float(totals[(totals["season"] == y) & (totals["driver_id"] == champion)]["points"].sum())
        agrees = champion == points_leader
        rows.append({"season": y, "champion_driver_id": champion, "method": method,
                     "season_wikidata_qid": qid or "", "gp_points_champion": champion_points,
                     "gp_points_leader_driver_id": points_leader,
                     "gp_points_leader": float(leader.loc[y, "points"]), "agrees_with_points_leader": agrees,
                     "note": "" if agrees else DROPPED_SCORES_NOTE if y <= 1990 else
                     "Differs from the Grand Prix points leader (sprint points are not in the results table)."})
    table = pd.DataFrame(rows)
    table.to_csv(CHAMPIONS_CSV, index=False)
    return table


def champions() -> pd.DataFrame:
    return build_official_champions(refresh=False)


if __name__ == "__main__":
    t = build_official_champions(refresh=True)
    print(t["method"].value_counts().to_string())
    print(t[~t["agrees_with_points_leader"]].to_string(index=False))
