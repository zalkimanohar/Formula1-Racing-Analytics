"""Exact facts from the cleaned dataset, each returned with its provenance.

Every number the assistant shows is computed here with pandas from data/cleaned/ (never by the language
model). Each fact block carries the file, its SHA-256, the filter, the number of rows and the raw-file
lines (source_file:source_line) it came from, so any figure can be traced back to the original archive.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from functools import lru_cache

import pandas as pd

from src import config
from src.assistant import reference

POINTS_NOTE = "Grand Prix points as awarded at the time; sprint points are not in the results table"
FAMILY_NAMES = {
    "ferrari": "Ferrari", "mclaren": "McLaren", "mercedes": "Mercedes", "red_bull": "Red Bull",
    "williams": "Williams", "lotus": "Lotus", "renault": "Renault", "brabham": "Brabham",
    "benetton": "Benetton", "tyrrell": "Tyrrell", "cooper": "Cooper", "brm": "BRM", "alfa": "Alfa Romeo",
    "maserati": "Maserati", "vanwall": "Vanwall", "matra": "Matra", "ligier": "Ligier", "brawn": "Brawn",
    "march": "March", "jordan": "Jordan", "kurtis_kraft": "Kurtis Kraft", "watson": "Watson",
}
TEAM_ALIASES = {"red bull racing": "red_bull", "scuderia ferrari": "ferrari", "mercedes amg": "mercedes",
                "team lotus": "lotus", "racing bulls": "rb", "toro rosso": "toro_rosso", "alpha tauri": "alphatauri",
                "aston martin": "aston_martin", "alpine": "alpine", "sauber": "sauber", "haas": "haas"}
# Family names that are also everyday words: only matched when written with a capital letter.
COMMON_WORDS = {"may", "love", "ward", "rose", "hall", "bell", "brown", "hill", "hunt", "rich", "power", "young",
                "king", "long", "bird", "fry", "miles", "wing", "grand", "price", "field", "black", "white", "green",
                "walker", "parker", "brooks", "march", "watson", "ferrari", "james", "jones", "johnson", "will",
                "gay", "hart", "west", "russell", "stewart", "moss", "lee", "pace", "piper", "hope", "driver",
                "best", "race", "won", "win", "team", "most", "can", "more", "fast", "start", "pole", "ahead"}
GIVEN_NAME_MIN_STARTS = 100
YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-2]\d)\b")


@dataclass
class Evidence:
    kind: str                      # fact | graph | model | document
    title: str
    lines: list[str]
    source: dict = field(default_factory=dict)
    id: str = ""

    def to_prompt(self) -> str:
        return f"[{self.id}] {self.title}\n" + "\n".join(f"- {line}" for line in self.lines)

    def to_dict(self) -> dict:
        return asdict(self)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def family_of(constructor_id: str) -> str:
    return constructor_id.replace("team_lotus", "lotus").split("-")[0]


def fmt_points(x: float) -> str:
    return f"{x:g}"


def pct(a: float, b: float) -> str:
    return f"{100 * a / b:.1f}%" if b else "n/a"


@dataclass
class Entity:
    type: str        # driver | team | circuit | race | year
    id: str
    name: str
    start: int       # position in the folded question, for ordering
    alternatives: list[str] = field(default_factory=list)


class DataStore:
    """Loads the validated tables once and answers fact queries."""

    def __init__(self) -> None:
        self.files = {"results": config.CLEAN_RESULTS_CSV, "drivers": config.CLEAN_DRIVERS_CSV,
                      "constructors": config.CLEAN_CONSTRUCTORS_CSV, "circuits": config.CLEAN_CIRCUITS_CSV,
                      "races": config.CLEAN_RACES_CSV}
        self.sha = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in self.files.items()}
        r = pd.read_csv(config.CLEAN_RESULTS_CSV)
        r["win"] = r["classified_position"].eq(1).fillna(False).astype(bool)
        r["podium"] = r["classified_position"].le(3).fillna(False).astype(bool)
        r["pole"] = r["grid_position"].eq(1).fillna(False).astype(bool)
        r["started"] = r["finish_category"].ne("Withdrawn")
        r["family"] = r["constructor_id"].map(family_of)
        self.results = r
        self.drivers = pd.read_csv(config.CLEAN_DRIVERS_CSV).set_index("driver_id")
        self.constructors = pd.read_csv(config.CLEAN_CONSTRUCTORS_CSV).set_index("constructor_id")
        self.circuits = pd.read_csv(config.CLEAN_CIRCUITS_CSV).set_index("circuit_id")
        self.races = pd.read_csv(config.CLEAN_RACES_CSV)
        self.champions = reference.champions().set_index("season")
        champ_rows = r.merge(self.champions["champion_driver_id"].rename("driver_id").reset_index(),
                             on=["season", "driver_id"])
        # team of each champion = the family that earned most of his points that season
        self.champion_team = {int(y): g.groupby("family")["points"].sum().idxmax()
                              for y, g in champ_rows.groupby("season")}
        self.starts_by_driver = r[r["started"]].groupby("driver_id").size()
        self._build_index()

    # ------------------------------------------------------------------ names and provenance
    def driver_name(self, did: str) -> str:
        return str(self.drivers.loc[did, "full_name"]) if did in self.drivers.index else did

    def team_name(self, fam: str) -> str:
        if fam in FAMILY_NAMES:
            return FAMILY_NAMES[fam]
        names = self.results.loc[self.results["family"] == fam, "constructor_name"]
        return str(names.mode().iloc[0]) if len(names) else fam

    def circuit_name(self, cid: str) -> str:
        return str(self.circuits.loc[cid, "circuit_name"]) if cid in self.circuits.index else cid

    def source(self, rows: pd.DataFrame, filter_text: str, table: str = "results") -> dict:
        lineage = []
        if "source_file" in rows.columns and len(rows):
            ordered = rows.sort_values(["season", "round"]) if "round" in rows.columns else rows
            picks = ordered.iloc[[0, -1]] if len(ordered) > 1 else ordered
            lineage = [f"{f}:{int(n)}" for f, n in zip(picks["source_file"], picks["source_line"])]
        path = self.files[table]
        return {"dataset": f"data/cleaned/{path.name}", "sha256": self.sha[table][:12], "filter": filter_text,
                "rows": int(len(rows)), "lineage": lineage}

    # ------------------------------------------------------------------ entity resolution
    def _build_index(self) -> None:
        idx: dict[str, list[tuple[str, str]]] = {}

        def add(phrase: str, etype: str, eid: str) -> None:
            key = fold(phrase)
            if len(key) >= 3 and (etype, eid) not in idx.setdefault(key, []):
                idx[key].append((etype, eid))

        for did, row in self.drivers.iterrows():
            add(row["full_name"], "driver", did)
            add(row["family_name"], "driver", did)
            add(did.replace("_", " "), "driver", did)
        given = self.drivers.assign(starts=self.starts_by_driver.reindex(self.drivers.index).fillna(0))
        given = given[given["starts"] >= GIVEN_NAME_MIN_STARTS].groupby("given_name")
        for name, grp in given:
            if len(grp) == 1:
                add(name, "driver", grp.index[0])
        for fam in self.results["family"].unique():
            add(self.team_name(fam), "team", fam)
        for cid, name in self.constructors["constructor_name"].items():
            add(str(name).replace("&amp;", "&"), "team", family_of(cid))
        for alias, fam in TEAM_ALIASES.items():
            add(alias, "team", fam)
        generic = {"circuit", "circuito", "circuit", "de", "di", "del", "of", "the", "autodromo", "autodrom",
                   "nazionale", "internacional", "international", "street", "park", "raceway", "speedway", "grand",
                   "prix", "motor", "racing", "race", "course", "national", "city", "la", "le", "do", "das", "and"}
        country_count = self.circuits["country"].value_counts()
        for cid, row in self.circuits.iterrows():
            add(row["circuit_name"], "circuit", cid)
            add(row["locality"], "circuit", cid)
            add(cid.replace("_", " "), "circuit", cid)
            short = " ".join(t for t in fold(row["circuit_name"]).split() if t not in generic)
            if short:
                add(short, "circuit", cid)
            if country_count[row["country"]] == 1:      # e.g. Monaco, Bahrain, Singapore
                add(row["country"], "circuit", cid)
        for name in self.races["race_name"].unique():
            add(name, "race", name)
            add(name.replace(" Grand Prix", " GP"), "race", name)
        self.index = idx
        self.max_ngram = max(len(k.split()) for k in idx)

    def _pick(self, key: str, cands: list[tuple[str, str]], context: str) -> tuple[str, str, list[str]]:
        teamish = re.search(r"\b(team|constructor|equipo|escuderia|scuderia|car|coche)\b", context)
        types = {t for t, _ in cands}
        if "team" in types and "driver" in types:
            single = len(key.split()) == 1
            if teamish or single:
                cands = [c for c in cands if c[0] == "team"]
            else:
                cands = [c for c in cands if c[0] == "driver"]
        if len({t for t, _ in cands}) > 1:   # e.g. circuit locality vs race name: prefer circuit
            order = {"driver": 0, "team": 1, "circuit": 2, "race": 3}
            cands = sorted(cands, key=lambda c: order[c[0]])
        etype = cands[0][0]
        same = [c for c in cands if c[0] == etype]
        if etype == "driver" and len(same) > 1:
            same = sorted(same, key=lambda c: -int(self.starts_by_driver.get(c[1], 0)))
            return etype, same[0][1], [self.driver_name(c[1]) for c in same[1:]]
        return etype, same[0][1], []

    def resolve(self, question: str) -> list[Entity]:
        raw_tokens = re.findall(r"[^\W_]+", unicodedata.normalize("NFC", question))
        tokens = [fold(t) for t in raw_tokens]
        capital = [t[:1].isupper() for t in raw_tokens]
        context = fold(question)
        used = [False] * len(tokens)
        found: list[Entity] = []
        for n in range(min(self.max_ngram, len(tokens)), 0, -1):
            for i in range(len(tokens) - n + 1):
                if any(used[i:i + n]):
                    continue
                key = " ".join(tokens[i:i + n])
                cands = self.index.get(key)
                if not cands:
                    continue
                if n == 1 and key in COMMON_WORDS and not capital[i]:
                    continue
                etype, eid, alts = self._pick(key, cands, context)
                name = {"driver": self.driver_name, "team": self.team_name,
                        "circuit": self.circuit_name}.get(etype, lambda x: x)(eid)
                found.append(Entity(etype, eid, name, i, alts))
                used[i:i + n] = [True] * n
        for m in YEAR_RE.finditer(question):
            y = int(m.group(1))
            if config.FIRST_SEASON <= y <= config.LAST_COMPLETE_SEASON:
                found.append(Entity("year", str(y), str(y), 10_000 + m.start()))
        out, seen = [], set()
        for e in sorted(found, key=lambda e: e.start):
            if (e.type, e.id) not in seen:
                seen.add((e.type, e.id))
                out.append(e)
        return out

    # ------------------------------------------------------------------ fact blocks
    def _summary(self, rows: pd.DataFrame, team: bool = False) -> dict:
        """Driver totals count every result row; team totals count each race (or podium place) once, so a car
        shared by two drivers in the 1950s is not counted twice."""
        started = rows[rows["started"]]
        if team:
            wins = rows.loc[rows["win"], "race_id"].nunique()
            podiums = len(rows.loc[rows["podium"], ["race_id", "classified_position"]].drop_duplicates())
            poles = rows.loc[rows["pole"], "race_id"].nunique()
        else:
            wins, podiums, poles = int(rows["win"].sum()), int(rows["podium"].sum()), int(rows["pole"].sum())
        return {"entries": len(rows), "starts": len(started), "wins": int(wins), "podiums": int(podiums),
                "poles": int(poles), "points": float(rows["points"].sum()), "races": rows["race_id"].nunique()}

    def titles_of(self, did: str) -> list[int]:
        return sorted(int(s) for s in self.champions.index[self.champions["champion_driver_id"] == did])

    def driver_career(self, did: str) -> Evidence:
        rows = self.results[self.results["driver_id"] == did]
        d = self.drivers.loc[did]
        s = self._summary(rows)
        titles = self.titles_of(did)
        teams = (rows.groupby("family")["season"].agg(["min", "max"]).sort_values("min"))
        team_txt = "; ".join(f"{self.team_name(f)} {a}-{b}" if a != b else f"{self.team_name(f)} {a}"
                             for f, (a, b) in teams.iterrows())
        wins = rows[rows["win"]].sort_values(["season", "round"])
        per_season = rows.groupby("season")["points"].sum()
        lines = [f"Driver: {d['full_name']} ({d['nationality']}, born {d['date_of_birth']})",
                 f"Seasons: {int(rows['season'].min())}-{int(rows['season'].max())} ({rows['season'].nunique()} seasons)",
                 f"Race entries: {s['entries']}; starts: {s['starts']}",
                 f"Wins: {s['wins']} ({pct(s['wins'], s['starts'])} of starts); podiums: {s['podiums']}; "
                 f"started from pole (grid 1): {s['poles']}",
                 f"Career points: {fmt_points(s['points'])} ({POINTS_NOTE})",
                 f"World Championships: {len(titles)}" + (f" ({', '.join(map(str, titles))})" if titles else ""),
                 f"Teams: {team_txt}",
                 f"Best season by points: {int(per_season.idxmax())} with {fmt_points(per_season.max())} points"]
        if len(wins):
            first, last = wins.iloc[0], wins.iloc[-1]
            lines.append(f"First win: {first['race_name']} {int(first['season'])}; "
                         f"most recent win: {last['race_name']} {int(last['season'])}")
        retired = int((rows["finish_category"] == "Retired").sum())
        lines.append(f"Retirements: {retired} ({pct(retired, s['starts'])} of starts)")
        return Evidence("fact", f"Career of {d['full_name']}", lines,
                        self.source(rows, f"driver_id == '{did}'"))

    def driver_with_team(self, did: str, fam: str) -> Evidence:
        rows = self.results[(self.results["driver_id"] == did) & (self.results["family"] == fam)]
        name, team = self.driver_name(did), self.team_name(fam)
        if rows.empty:
            return Evidence("fact", f"{name} with {team}", [f"{name} never drove for {team}."],
                            self.source(rows, f"driver_id == '{did}' and constructor family == '{fam}'"))
        s = self._summary(rows)
        seasons = sorted(rows["season"].unique())
        titles = [y for y in self.titles_of(did) if self.champion_team.get(y) == fam]
        wins = rows[rows["win"]].sort_values(["season", "round"])
        lines = [f"{name} with {team}: seasons {', '.join(map(str, seasons))}; {s['entries']} entries, {s['starts']} starts",
                 f"Wins: {s['wins']}; podiums: {s['podiums']}; started from pole: {s['poles']}",
                 f"Points: {fmt_points(s['points'])} ({POINTS_NOTE})",
                 f"World Championships won with {team}: {len(titles)}" + (f" ({', '.join(map(str, titles))})" if titles else "")]
        if len(wins):
            lines.append(f"First win with {team}: {wins.iloc[0]['race_name']} {int(wins.iloc[0]['season'])}; "
                         f"last: {wins.iloc[-1]['race_name']} {int(wins.iloc[-1]['season'])}")
        return Evidence("fact", f"{name} with {team}", lines,
                        self.source(rows, f"driver_id == '{did}' and constructor family == '{fam}'"))

    def driver_season(self, did: str, year: int) -> Evidence:
        season = self.results[self.results["season"] == year]
        rows = season[season["driver_id"] == did]
        name = self.driver_name(did)
        if rows.empty:
            return Evidence("fact", f"{name} in {year}", [f"{name} has no race entries in {year}."],
                            self.source(rows, f"driver_id == '{did}' and season == {year}"))
        s = self._summary(rows)
        totals = season.groupby("driver_id")["points"].sum().sort_values(ascending=False)
        rank = int((totals > totals[did]).sum()) + 1
        teams = ", ".join(self.team_name(f) for f in rows["family"].unique())
        wins = rows[rows["win"]].sort_values("round")["race_name"].tolist()
        champ = self.champions.loc[year, "champion_driver_id"] if year in self.champions.index else None
        best = rows["classified_position"].min()
        lines = [f"{name} in {year} with {teams}: {s['entries']} entries, {s['starts']} starts",
                 f"Wins: {s['wins']}; podiums: {s['podiums']}; started from pole: {s['poles']}",
                 f"Points: {fmt_points(s['points'])} ({POINTS_NOTE}); rank {rank} of {len(totals)} by these points",
                 f"Best finish: {'P' + str(int(best)) if pd.notna(best) else 'not classified'}"]
        if wins:
            lines.append("Races won: " + ", ".join(wins))
        lines.append(f"{year} World Champion: {self.driver_name(champ)}" +
                     (" (this driver)" if champ == did else "") if champ else "")
        return Evidence("fact", f"{name} in the {year} season", [x for x in lines if x],
                        self.source(rows, f"driver_id == '{did}' and season == {year}"))

    def season_summary(self, year: int) -> Evidence:
        rows = self.results[self.results["season"] == year]
        races = rows.drop_duplicates("race_id").sort_values("round")
        totals = rows.groupby("driver_id")["points"].sum().sort_values(ascending=False)
        wins = rows[rows["win"]].groupby("driver_id").size().sort_values(ascending=False)
        team_wins = rows[rows["win"]].groupby("family").size().sort_values(ascending=False)
        c = self.champions.loc[year]
        lines = [f"Season {year}: {len(races)} Grands Prix, from the {races.iloc[0]['race_name']} "
                 f"({races.iloc[0]['race_date']}) to the {races.iloc[-1]['race_name']} ({races.iloc[-1]['race_date']})",
                 f"World Champion: {self.driver_name(c['champion_driver_id'])} "
                 f"(source: {c['method']}" + (f", {c['season_wikidata_qid']}" if isinstance(c['season_wikidata_qid'], str)
                                              and c['season_wikidata_qid'] else "") + ")"]
        if isinstance(c["note"], str) and c["note"]:
            lines.append(f"Note: {c['note']} Most points in total: {self.driver_name(c['gp_points_leader_driver_id'])} "
                         f"({fmt_points(c['gp_points_leader'])}) vs champion {fmt_points(c['gp_points_champion'])}")
        lines.append("Top 5 by points: " + "; ".join(f"{self.driver_name(d)} {fmt_points(p)}"
                                                     for d, p in totals.head(5).items()) + f" ({POINTS_NOTE})")
        lines.append("Most wins: " + "; ".join(f"{self.driver_name(d)} {n}" for d, n in wins.head(5).items()))
        lines.append("Wins by team: " + "; ".join(f"{self.team_name(f)} {n}" for f, n in team_wins.items()))
        return Evidence("fact", f"The {year} season", lines, self.source(rows, f"season == {year}"))

    def team_profile(self, fam: str) -> Evidence:
        rows = self.results[self.results["family"] == fam]
        name = self.team_name(fam)
        s = self._summary(rows, team=True)
        by_driver = rows[rows["win"]].groupby("driver_id").size().sort_values(ascending=False)
        champs = [(y, self.driver_name(self.champions.loc[y, "champion_driver_id"]))
                  for y, f in sorted(self.champion_team.items()) if f == fam]
        ids = ", ".join(sorted(rows["constructor_id"].unique()))
        lines = [f"Team: {name} (constructor records grouped: {ids})",
                 f"Seasons: {int(rows['season'].min())}-{int(rows['season'].max())}; Grands Prix entered: {s['races']}; "
                 f"car entries: {s['entries']}",
                 f"Wins: {s['wins']}; podiums: {s['podiums']}; pole starts: {s['poles']}",
                 f"Points scored by its drivers: {fmt_points(s['points'])} ({POINTS_NOTE})",
                 "Drivers with most wins for the team: " + "; ".join(f"{self.driver_name(d)} {n}"
                                                                    for d, n in by_driver.head(5).items()),
                 f"Drivers' titles won with this team: {len(champs)}" +
                 (" (" + ", ".join(f"{y} {n}" for y, n in champs) + ")" if champs else "")]
        return Evidence("fact", f"Team history: {name}", lines, self.source(rows, f"constructor family == '{fam}'"))

    def team_season(self, fam: str, year: int) -> Evidence:
        season = self.results[self.results["season"] == year]
        rows = season[season["family"] == fam]
        name = self.team_name(fam)
        if rows.empty:
            return Evidence("fact", f"{name} in {year}", [f"{name} has no entries in {year}."],
                            self.source(rows, f"constructor family == '{fam}' and season == {year}"))
        s = self._summary(rows, team=True)
        totals = season.groupby("family")["points"].sum().sort_values(ascending=False)
        rank = int((totals > totals[fam]).sum()) + 1
        drivers = rows.groupby("driver_id")["points"].sum().sort_values(ascending=False)
        lines = [f"{name} in {year}: {s['races']} Grands Prix, drivers: " +
                 ", ".join(f"{self.driver_name(d)} ({fmt_points(p)} pts)" for d, p in drivers.items()),
                 f"Wins: {s['wins']}; podiums: {s['podiums']}; pole starts: {s['poles']}",
                 f"Points of its drivers: {fmt_points(s['points'])}; rank {rank} of {len(totals)} teams by these points "
                 f"({POINTS_NOTE}; the official constructors' table used other rules before 1979)"]
        return Evidence("fact", f"{name} in {year}", lines,
                        self.source(rows, f"constructor family == '{fam}' and season == {year}"))

    def circuit_profile(self, cid: str) -> Evidence:
        rows = self.results[self.results["circuit_id"] == cid]
        c = self.circuits.loc[cid]
        races = rows.drop_duplicates("race_id")
        winners = rows[rows["win"]]
        top_d = winners.groupby("driver_id").size().sort_values(ascending=False).head(3)
        top_t = winners.groupby("family").size().sort_values(ascending=False).head(3)
        pole_win = rows[rows["win"] & rows["pole"]]["race_id"].nunique()
        lines = [f"Circuit: {c['circuit_name']}, {c['locality']}, {c['country']}",
                 f"Grands Prix held: {len(races)} ({int(races['season'].min())}-{int(races['season'].max())}); "
                 f"events: {', '.join(sorted(races['race_name'].unique()))}",
                 "Most wins (drivers): " + "; ".join(f"{self.driver_name(d)} {n}" for d, n in top_d.items()),
                 "Most wins (teams): " + "; ".join(f"{self.team_name(f)} {n}" for f, n in top_t.items()),
                 f"Won from pole position: {pole_win} of {len(races)} races ({pct(pole_win, len(races))})"]
        return Evidence("fact", f"Circuit history: {c['circuit_name']}", lines,
                        self.source(rows, f"circuit_id == '{cid}'"))

    def race_result(self, year: int, circuit: str | None = None, race_name: str | None = None) -> Evidence:
        rows = self.results[self.results["season"] == year]
        rows = rows[rows["circuit_id"] == circuit] if circuit else rows[rows["race_name"] == race_name]
        label = race_name or (self.circuit_name(circuit) if circuit else "race")
        if rows.empty:
            return Evidence("fact", f"{label} {year}", [f"No Grand Prix matching {label} in {year}."],
                            self.source(rows, f"season == {year}"))
        lines = []
        for race_id, race in rows.groupby("race_id"):
            race = race.sort_values("position_order")
            podium = race[race["podium"]].sort_values("classified_position")
            pole = race[race["pole"]]
            first = race.iloc[0]
            lines.append(f"{first['race_name']} {year} (round {int(first['round'])}, {first['race_date']}, "
                         f"{first['circuit_name']}): " + "; ".join(
                             f"P{int(p['classified_position'])} {p['driver_name']} ({p['constructor_name']})"
                             for _, p in podium.iterrows()))
            if len(pole):
                lines.append(f"Started from pole: {pole.iloc[0]['driver_name']}; winner started from grid "
                             f"{int(podium.iloc[0]['grid_position']) if len(podium) and pd.notna(podium.iloc[0]['grid_position']) else 'n/a'}")
            lines.append(f"Entries: {len(race)}; classified finishers: {int(race['classified_position'].notna().sum())}")
        return Evidence("fact", f"Result: {label} {year}", lines,
                        self.source(rows, f"season == {year} and " + (f"circuit_id == '{circuit}'" if circuit
                                                                      else f"race_name == '{race_name}'")))

    def event_history(self, race_name: str) -> Evidence:
        rows = self.results[self.results["race_name"] == race_name]
        races = rows.drop_duplicates("race_id")
        winners = rows[rows["win"]]
        top_d = winners.groupby("driver_id").size().sort_values(ascending=False).head(3)
        last = winners.sort_values(["season", "round"]).tail(3)
        lines = [f"{race_name}: held {len(races)} times ({int(races['season'].min())}-{int(races['season'].max())}) at "
                 f"{races['circuit_id'].nunique()} circuit(s): " + ", ".join(sorted(races['circuit_name'].unique())),
                 "Most wins: " + "; ".join(f"{self.driver_name(d)} {n}" for d, n in top_d.items()),
                 "Latest winners: " + "; ".join(f"{int(r['season'])} {r['driver_name']}" for _, r in last.iterrows())]
        return Evidence("fact", f"Event history: {race_name}", lines, self.source(rows, f"race_name == '{race_name}'"))

    def head_to_head(self, a: str, b: str) -> Evidence:
        r = self.results[self.results["started"]]
        ra, rb = r[r["driver_id"] == a], r[r["driver_id"] == b]
        both = ra.merge(rb, on="race_id", suffixes=("_a", "_b"))
        mates = both[both["constructor_id_a"] == both["constructor_id_b"]]
        ahead_a = int((both["position_order_a"] < both["position_order_b"]).sum())
        na, nb = self.driver_name(a), self.driver_name(b)
        sa, sb = self._summary(self.results[self.results["driver_id"] == a]), \
            self._summary(self.results[self.results["driver_id"] == b])
        ta, tb = self.titles_of(a), self.titles_of(b)
        titles = lambda t: f"{len(t)} World Championship{'s' if len(t) != 1 else ''}"  # noqa: E731
        lines = [f"Career {na}: {sa['starts']} starts, {sa['wins']} wins, {sa['podiums']} podiums, {sa['poles']} pole starts, "
                 f"{fmt_points(sa['points'])} points, {titles(ta)}",
                 f"Career {nb}: {sb['starts']} starts, {sb['wins']} wins, {sb['podiums']} podiums, {sb['poles']} pole starts, "
                 f"{fmt_points(sb['points'])} points, {titles(tb)}",
                 f"Races both started: {len(both)}; finished ahead: {na} {ahead_a}, {nb} {len(both) - ahead_a}"]
        if len(mates):
            ahead_m = int((mates["position_order_a"] < mates["position_order_b"]).sum())
            seasons = sorted(mates["season_a"].unique())
            lines.append(f"Team-mates in {len(mates)} races ({', '.join(map(str, seasons))}, "
                         f"{', '.join(sorted(mates['constructor_name_a'].unique()))}): "
                         f"{na} ahead {ahead_m}, {nb} ahead {len(mates) - ahead_m}")
        else:
            lines.append("They were never team-mates.")
        rows = self.results[self.results["driver_id"].isin([a, b])]
        return Evidence("fact", f"{na} vs {nb}", lines, self.source(rows, f"driver_id in ('{a}', '{b}')"))

    METRICS = {"wins": "win", "podiums": "podium", "poles": "pole", "points": "points", "starts": "started"}

    def leaderboard(self, metric: str, by: str = "driver", year: int | None = None, fam: str | None = None,
                    circuit: str | None = None, top: int = 10) -> Evidence:
        rows = self.results
        scope = []
        if year:
            rows, _ = rows[rows["season"] == year], scope.append(f"season == {year}")
        if fam:
            rows, _ = rows[rows["family"] == fam], scope.append(f"constructor family == '{fam}'")
        if circuit:
            rows, _ = rows[rows["circuit_id"] == circuit], scope.append(f"circuit_id == '{circuit}'")
        key = "driver_id" if by == "driver" else "family"
        col = self.METRICS[metric]
        if by != "driver" and metric in ("wins", "poles"):
            table = rows[rows[col]].groupby(key)["race_id"].nunique()
        elif by != "driver" and metric == "podiums":
            table = rows[rows[col]].drop_duplicates(["race_id", "classified_position"]).groupby(key).size()
        else:
            table = rows.groupby(key)[col].sum()
        table = table.sort_values(ascending=False).head(top)
        namer = self.driver_name if by == "driver" else self.team_name
        where = " and ".join(scope) or "all seasons 1950-2025"
        label = {"wins": "wins", "podiums": "podiums", "poles": "starts from pole", "points": "points",
                 "starts": "starts"}[metric]
        lines = [f"{'Drivers' if by == 'driver' else 'Teams'} with most {label} ({where}):"]
        lines += [f"{i}. {namer(k)}: {fmt_points(v)}" for i, (k, v) in enumerate(table.items(), start=1)]
        if metric == "points":
            lines.append(f"Points are {POINTS_NOTE}; scoring systems changed over time, so totals favour recent eras")
        return Evidence("fact", f"Ranking: most {label} ({where})", lines, self.source(rows, where))

    def champions_list(self, fam: str | None = None) -> Evidence:
        ch = self.champions.reset_index()
        counts = ch.groupby("champion_driver_id").size().sort_values(ascending=False)
        lines = ["Most Drivers' World Championships: " + "; ".join(
            f"{self.driver_name(d)} {n}" for d, n in counts.head(8).items())]
        recent = ch.sort_values("season").tail(10)
        lines.append("Champions 2016-2025: " + "; ".join(f"{int(r.season)} {self.driver_name(r.champion_driver_id)}"
                                                       for r in recent.itertuples()))
        lines.append("Seasons where the champion did not score the most points (dropped-scores rule): " + "; ".join(
            f"{int(r.season)} {self.driver_name(r.champion_driver_id)} ({fmt_points(r.gp_points_champion)}) vs "
            f"{self.driver_name(r.gp_points_leader_driver_id)} ({fmt_points(r.gp_points_leader)})"
            for r in ch[~ch["agrees_with_points_leader"]].itertuples()))
        src = {"dataset": "data/reference/official_champions.csv", "sha256": hashlib.sha256(
            reference.CHAMPIONS_CSV.read_bytes()).hexdigest()[:12], "filter": "all seasons", "rows": len(ch),
               "lineage": ["Wikidata P1346 via the English Wikipedia season articles (73 seasons); "
                           "points leader for 2018, 2022, 2024"]}
        return Evidence("fact", "World Champions 1950-2025", lines, src)

    def quality_overview(self, issue_id: str | None = None) -> Evidence:
        issues = pd.read_csv(config.QUALITY_DIR / "quality_issues.csv")
        resolution = pd.read_csv(config.CLEANING_DIR / "issue_resolution.csv").set_index("issue_id")
        gates = pd.read_csv(config.CLEANING_DIR / "validation_report.csv")
        if issue_id:
            row = issues[issues["issue_id"] == issue_id].iloc[0]
            res = resolution.loc[issue_id]
            lines = [f"{issue_id} ({row['dimension']}, severity {row['severity']}): {row['title']}",
                     f"Affected records: {row['affected_records']} of {row['table_rows']} ({row['affected_pct']}%) in "
                     f"table {row['table']}, columns {row['columns']}",
                     f"Evidence: {row['evidence']}", f"Likely cause: {row['root_cause_hypothesis']}",
                     f"Impact if not fixed: {row['downstream_impact']}",
                     f"Resolution: {res['resolution']} (cleaning step {res['cleaning_step']}; affected records before "
                     f"cleaning {fmt_points(float(res['before']))}, after {fmt_points(float(res['after']))})"]
            path = config.QUALITY_DIR / "quality_issues.csv"
            return Evidence("fact", f"Quality issue {issue_id}", lines,
                            {"dataset": "outputs/component_b_quality/quality_issues.csv",
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:12],
                             "filter": f"issue_id == '{issue_id}'", "rows": 1, "lineage": [str(row["evidence"])[:120]]})
        by_dim = issues.groupby("dimension").size().sort_values(ascending=False)
        high = issues[issues["severity"] == "High"]
        lines = [f"Quality register: {len(issues)} issues ({int(issues['is_error'].sum())} errors) across "
                 f"{issues['dimension'].nunique()} dimensions: " + "; ".join(f"{d} {n}" for d, n in by_dim.items()),
                 "High severity: " + "; ".join(f"{r.issue_id} {r.title}" for r in high.itertuples()),
                 f"Validation gates after cleaning: {int((gates['result'] == 'passed').sum())} of {len(gates)} passed",
                 "Resolution: " + "; ".join(f"{k} {v}" for k, v in resolution["resolution"].value_counts().items())]
        path = config.QUALITY_DIR / "quality_issues.csv"
        return Evidence("fact", "Data quality register", lines,
                        {"dataset": "outputs/component_b_quality/quality_issues.csv",
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:12], "filter": "all issues",
                         "rows": len(issues), "lineage": ["outputs/component_c_cleaning/validation_report.csv"]})

    def dataset_overview(self) -> Evidence:
        r = self.results
        lines = [f"Cleaned results table: {len(r)} rows x {len(r.columns) - 5} columns, seasons "
                 f"{int(r['season'].min())}-{int(r['season'].max())}, {r['race_id'].nunique()} Grands Prix, "
                 f"{r['driver_id'].nunique()} drivers, {r['constructor_id'].nunique()} constructor records, "
                 f"{r['circuit_id'].nunique()} circuits",
                 f"SHA-256 of f1_race_results_clean.csv: {self.sha['results'][:16]}...",
                 "Source: Jolpica-F1 / Ergast archive (racing_f1_data.zip), licence CC BY-NC-SA 4.0; code MIT",
                 "Every row keeps source_file and source_line, pointing to the raw JSON line it came from"]
        return Evidence("fact", "About the dataset", lines, self.source(r, "all rows"))


@lru_cache(maxsize=1)
def store() -> DataStore:
    return DataStore()
