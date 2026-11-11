"""Component B - Systematic profiling and data quality assessment of the raw F1 dataset.

Produces:
  * profile_tables.csv   - table-level structure (rows, columns, duplicates, candidate keys)
  * profile_columns.csv  - column-level profile (types, completeness, uniqueness, distributions)
  * quality_issues.csv / .md - the quality issue register: one row per rule with dimension,
    severity, evidence, root-cause hypothesis, downstream impact and the Component C step
    that resolves it (the contract between Components B and C)
  * quality_summary_by_dimension.csv
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from src import config

LAP_STATUS_RE = re.compile(r"^\+\d+ Laps?$")
NON_ISO_COUNTRY_NAMES = {"UK", "USA", "UAE", "Korea"}


@dataclass
class Issue:
    issue_id: str
    dimension: str
    table: str
    columns: str
    title: str
    affected_records: int
    table_rows: int
    is_error: bool
    severity: str
    evidence: str
    root_cause_hypothesis: str
    downstream_impact: str
    cleaning_step: str

    @property
    def affected_pct(self) -> float:
        return round(100 * self.affected_records / self.table_rows, 3) if self.table_rows else 0.0


def load_raw() -> dict[str, pd.DataFrame]:
    return {
        "results": pd.read_csv(config.RAW_RESULTS_CSV),
        "races": pd.read_csv(config.RAW_RACES_CSV),
        "circuits": pd.read_csv(config.RAW_CIRCUITS_CSV),
        "drivers": pd.read_csv(config.RAW_DRIVERS_CSV),
        "constructors": pd.read_csv(config.RAW_CONSTRUCTORS_CSV),
        "manifest": pd.read_csv(config.SOURCE_MANIFEST_CSV),
    }


# --------------------------------------------------------------------------------------------
# Structural profiling
# --------------------------------------------------------------------------------------------
def semantic_type(series: pd.Series) -> str:
    s = series.dropna()
    if s.empty:
        return "empty"
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_numeric_dtype(s):
        if pd.api.types.is_float_dtype(s) and np.all(np.mod(s, 1) == 0):
            return "integer (stored as float)"
        return "integer" if pd.api.types.is_integer_dtype(s) else "decimal"
    text = s.astype(str)
    if text.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        return "date (stored as text)"
    if text.str.match(r"^https?://").all():
        return "url"
    return "text"


def profile_columns(name: str, df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    n = len(df)
    for col in df.columns:
        s = df[col]
        non_null = int(s.notna().sum())
        distinct = int(s.nunique(dropna=True))
        top = s.value_counts(dropna=True).head(5)
        entry = {
            "table": name,
            "column": col,
            "pandas_dtype": str(s.dtype),
            "semantic_type": semantic_type(s),
            "rows": n,
            "non_null": non_null,
            "missing": n - non_null,
            "missing_pct": round(100 * (n - non_null) / n, 3) if n else 0,
            "distinct": distinct,
            "distinct_pct": round(100 * distinct / non_null, 3) if non_null else 0,
            "is_unique": bool(non_null == n and distinct == n),
            "top_values": "; ".join(f"{k} ({v})" for k, v in top.items()),
            "min": None, "max": None, "mean": None, "std": None, "zeros": None,
        }
        if pd.api.types.is_numeric_dtype(s) and non_null:
            entry.update(min=float(s.min()), max=float(s.max()), mean=round(float(s.mean()), 4),
                         std=round(float(s.std()), 4), zeros=int((s == 0).sum()))
        elif non_null and semantic_type(s).startswith("date"):
            entry.update(min=str(s.min()), max=str(s.max()))
        rows.append(entry)
    return pd.DataFrame(rows)


def profile_tables(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, df in tables.items():
        if name == "manifest":
            continue
        business = [c for c in df.columns if c not in ("source_file", "source_line")]
        rows.append({
            "table": name,
            "rows": len(df),
            "columns": len(business),
            "exact_duplicate_rows": int(df.duplicated(business).sum()),
            "rows_with_any_missing": int(df[business].isna().any(axis=1).sum()),
            "complete_rows_pct": round(100 * (1 - df[business].isna().any(axis=1).mean()), 3),
            "unique_columns": ", ".join(c for c in business if df[c].notna().all() and df[c].is_unique),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------
# Quality rules
# --------------------------------------------------------------------------------------------
def season_from_file(results: pd.DataFrame) -> pd.Series:
    return results["source_file"].str.extract(r"(\d{4})")[0].astype(int)


def line_ranges(df: pd.DataFrame) -> str:
    out = []
    for f, g in df.groupby("source_file"):
        lines = sorted(g["source_line"].astype(int))
        runs, start, prev = [], lines[0], lines[0]
        for x in lines[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            runs.append(f"{start}-{prev}" if prev != start else f"{start}")
            if x is not None:
                start = prev = x
        out.append(f"{f} line{'s' if len(lines) > 1 else ''} {', '.join(runs)}")
    return "; ".join(out)


def check_results(t: dict[str, pd.DataFrame]) -> list[Issue]:
    r = t["results"]
    races = t["races"]
    n = len(r)
    business = [c for c in r.columns if c not in ("source_file", "source_line")]
    issues: list[Issue] = []

    # ---- Completeness --------------------------------------------------------------------
    m = r["season"].isna()
    issues.append(Issue(
        "B01", "Completeness", "results", "season", "Season missing", int(m.sum()), n, True, "High",
        line_ranges(r[m]),
        "Field dropped while copying a block of rows (all affected rows belong to one race block).",
        "Rows cannot be joined to races/circuits and silently vanish from per-season aggregates and model training sets.",
        "C02"))
    m = r["round"].isna()
    issues.append(Issue(
        "B02", "Completeness", "results", "round", "Round missing", int(m.sum()), n, True, "High",
        line_ranges(r[m]),
        "Same corrupted block as B01 (1960 Italian GP).",
        "Race-level features (circuit, date) cannot be attached; orphaned facts in a star schema.",
        "C02"))
    m = r["number"].isna()
    issues.append(Issue(
        "B03", "Completeness", "results", "number", "Car number missing", int(m.sum()), n, False, "Low",
        f"all {int(m.sum())} rows have positionText 'W' (withdrawn entries): "
        f"{r.loc[m, 'positionText'].value_counts().to_dict()}",
        "Structurally missing (not applicable): a withdrawn entry was never assigned a race number.",
        "None if handled as nullable; imputing a number would invent facts.",
        "C01"))
    m = r["grid"] == 0
    issues.append(Issue(
        "B04", "Completeness", "results", "grid", "Disguised missing value: grid = 0 sentinel",
        int(m.sum()), n, True, "Medium",
        f"0 is not a grid slot; status of these rows: {r.loc[m, 'status'].value_counts().head(4).to_dict()}",
        "Source encodes 'pit-lane start / no grid slot' as 0 instead of null.",
        "Grid-vs-result models treat 0 as pole-better-than-pole; mean grid is biased low; correlation with "
        "finishing position is distorted.",
        "C05"))
    recent = r[season_from_file(r) >= 2014]
    entries = recent.groupby(["season", "round"]).size().rename("entries").reset_index()
    mode = entries.groupby("season")["entries"].agg(lambda s: s.mode().iloc[0]).rename("mode")
    entries = entries.join(mode, on="season")
    short = entries[entries["entries"] < entries["mode"]]
    evidence = []
    for _, row in short.iterrows():
        cur = set(r[(r["season"] == row["season"]) & (r["round"] == row["round"])]["driverId"])
        nb = set(r[(r["season"] == row["season"]) & r["round"].isin([row["round"] - 1, row["round"] + 1])]["driverId"])
        evidence.append(f"{int(row['season'])} R{int(row['round'])}: {int(row['entries'])}/{int(row['mode'])} entries, "
                        f"absent vs neighbouring rounds: {sorted(nb - cur)}")
    issues.append(Issue(
        "B05", "Completeness", "results", "(record level)",
        "Races with fewer entries than the season norm (2014+): verified, not data loss",
        int(len(short)), int(len(entries)), False, "Info",
        " | ".join(evidence) if evidence else "none",
        "Each gap matches a documented real-world absence (e.g. Marussia/Caterham missing late 2014, "
        "Stroll injured for the 2025 Spanish GP), not a lost record. Should still be confirmed against "
        "the official FIA classification before publication.",
        "None if verified; shows why record-count anomaly detection needs domain verification before imputation.",
        "None (verified as genuine)"))

    # ---- Uniqueness ------------------------------------------------------------------------
    m = r.duplicated(business, keep="first")
    issues.append(Issue(
        "B06", "Uniqueness", "results", "all", "Exact duplicate records", int(m.sum()), n, True, "High",
        f"duplicated copies at {line_ranges(r[m])}",
        "A block of rows was appended twice (copy/paste or a re-run of an append-only load).",
        "Double-counts points and wins, inflates sample weight of one race, leaks identical rows across "
        "train/test splits.",
        "C03"))
    key_missing = r["season"].isna() | r["round"].isna()
    filled = r.assign(season=season_from_file(r))
    filled["round"] = filled["round"].fillna(
        filled.merge(races[["season", "date", "round"]].drop_duplicates(), on=["season", "date"], how="left",
                     suffixes=("", "_ref"))["round_ref"])
    hidden = filled.duplicated(business, keep=False) & key_missing & ~r.duplicated(business, keep=False)
    issues.append(Issue(
        "B07", "Uniqueness", "results", "all", "Hidden duplicates masked by missing keys",
        int(hidden.sum()), n, True, "High",
        f"rows {line_ranges(r[hidden])} become exact copies of complete rows once season/round are restored",
        "The duplicated block of B06 was additionally damaged (keys blanked), so naive exact-match "
        "de-duplication misses it.",
        "Same as B06; also shows that cleaning order matters (repair keys before de-duplicating).",
        "C02 + C03"))
    dedup = r.drop_duplicates(business)
    nk = dedup.duplicated(["season", "round", "driverId"], keep=False) & dedup["season"].notna() & dedup["round"].notna()
    groups = dedup[nk].groupby(["season", "round", "driverId"])["number"].nunique()
    issues.append(Issue(
        "B08", "Uniqueness", "results", "season, round, driverId",
        "Natural-key collisions that are NOT errors (shared drives)", int(nk.sum()), n, False, "Info",
        f"{len(groups)} driver-race groups; car number differs in {int((groups > 1).sum())}/{len(groups)}; "
        f"seasons {int(dedup[nk]['season'].min())}-{int(dedup[nk]['season'].max())}",
        "Historic rule allowed a driver to take over a team-mate's car; each car is a separate classified entry.",
        "Naive de-duplication on (season, round, driver) would delete real history; the correct key "
        "includes the car number.",
        "C11 (flag is_shared_drive)"))

    # ---- Validity ----------------------------------------------------------------------------
    m = r["driverId"] != r["driverId"].str.strip().str.lower()
    issues.append(Issue(
        "B09", "Validity", "results", "driverId", "Identifier violates lowercase convention",
        int(m.sum()), n, True, "Medium", f"values {sorted(r.loc[m, 'driverId'].unique())} at {line_ranges(r[m])}",
        "Manual edit of identifiers (mixed case) in the source.",
        "Case-sensitive joins with other F1 sources fail; the same driver can appear as two entities.",
        "C04"))
    issues.append(Issue(
        "B10", "Validity", "results", "season, round, number, date",
        "Incorrect storage types (integers stored as floats, dates stored as text)", n, n, True, "Medium",
        "season/round/number inferred as float64 because of missing values; date is an untyped string",
        "JSON nulls force numeric columns to float when loaded; no schema was enforced at ingestion.",
        "Keys like 1960.0 break joins and string IDs; dates cannot be used for time-based splits without parsing.",
        "C01"))
    m = r["positionText"].isin(["R", "W", "D"])
    issues.append(Issue(
        "B11", "Validity", "results", "position, positionText",
        "'position' is filled for drivers who were not classified", int(m.sum()), n, True, "High",
        f"positionText codes R/W/D: {r.loc[m, 'positionText'].value_counts().to_dict()} all carry a numeric 'position'",
        "Source semantics: 'position' is the order of finishing incl. retirements, not the official result.",
        "Analyses that treat 'position' as the result (e.g. grid-vs-finish regressions, the project dashboard) "
        "count a retirement as e.g. 18th place, biasing targets for prediction models.",
        "C06"))

    # ---- Consistency -------------------------------------------------------------------------
    counts = r["status"].value_counts()
    tail = counts[counts / n < 0.01]
    issues.append(Issue(
        "B12", "Consistency", "results", "status", "Non-standard categorical values: free-text status",
        n, n, True, "Medium",
        f"{r['status'].nunique()} distinct values; {len(tail)} values each <1% of rows; mixes finishing margin "
        f"('+1 Lap' to '+46 Laps', 'Lapped') with causes ('Engine', 'Accident')",
        "Status is recorded verbatim from race reports over 75 years without a controlled vocabulary.",
        "One-hot encoding creates 136 sparse features; reliability analyses (DNF causes) cannot be aggregated.",
        "C07"))
    m = (r["positionText"] == "R") & (r["status"].str.match(LAP_STATUS_RE) | (r["status"] == "Finished"))
    issues.append(Issue(
        "B13", "Consistency", "results", "positionText, status",
        "Contradiction: retired ('R') but status says lapped finish", int(m.sum()), n, True, "Low",
        f"seasons {sorted(r.loc[m, 'season'].dropna().astype(int).unique().tolist())}",
        "Driver was running at the flag but covered <90% distance (not classified); status and code disagree.",
        "DNF-rate features are inconsistent depending on which field is used.",
        "C06 (flag status_position_conflict)"))
    m = r["raceName"] == r["raceName"].str.lower()
    issues.append(Issue(
        "B14", "Consistency", "results", "raceName",
        "Inconsistent text formatting (proper names stored in lowercase)", int(m.sum()), n, True, "Low",
        "raceName, circuitName, locality and driver names are lowercase while constructor names keep proper case",
        "A normalisation step lowercased some tables during an earlier export.",
        "Cosmetic for models but reduces readability, breaks exact matching with external sources (e.g. Wikidata labels).",
        "C10, C11"))
    winners = r[r["positionText"] == "1"]
    typical_win = winners.groupby("season")["points"].agg(lambda s: s.mode().iloc[0])
    eras = typical_win[typical_win.diff().fillna(1) != 0]
    frac = r[(r["points"] % 0.5) != 0]
    issues.append(Issue(
        "B15", "Consistency", "results", "points",
        "Points not comparable across eras (scoring rules changed)", int((r["points"] > 0).sum()), n, True, "Medium",
        f"points for a win range {winners['points'].min():g}-{winners['points'].max():g}; the typical winner score "
        f"changes in {len(eras)} seasons ({', '.join(f'{int(s)}: {v:g}' for s, v in eras.items())}); "
        f"{len(frac)} fractional values (shared drives / shared fastest lap, e.g. 8.14, 1.33)",
        "Not a recording error: FIA scoring systems changed (1950, 1960, 1961, 1991, 2003, 2010, 2014 double points, 2019 fastest lap).",
        "All-time rankings and models using raw points are dominated by the post-2010 era (25 points per win).",
        "C09"))

    # ---- Accuracy / plausibility ------------------------------------------------------------
    q1, q3 = r["laps"].quantile([0.25, 0.75])
    hi = q3 + 1.5 * (q3 - q1)
    m = r["laps"] > hi
    issues.append(Issue(
        "B16", "Accuracy", "results", "laps", "Statistical outliers that are valid (Indianapolis 500)",
        int(m.sum()), n, False, "Info",
        f"IQR upper fence {hi:g} laps; flagged rows by race: {r.loc[m, 'raceName'].value_counts().to_dict()}",
        "Indy 500 (200 laps, 1950-1960) counted for the championship under different rules.",
        "Removing them as 'outliers' would delete valid history; keeping them unflagged skews lap-based features.",
        "C08"))

    # ---- Integrity -------------------------------------------------------------------------
    keys = set(zip(races["season"], races["round"]))
    m = ~pd.Series([(s, rd) in keys for s, rd in zip(r["season"], r["round"])], index=r.index)
    issues.append(Issue(
        "B17", "Referential integrity", "results", "season, round", "Results that cannot be linked to a race",
        int(m.sum()), n, True, "High", line_ranges(r[m]),
        "Consequence of B01/B02.",
        "Inner joins drop these rows silently; left joins create rows without circuit/date.",
        "C02"))
    return issues


def check_reference(t: dict[str, pd.DataFrame]) -> list[Issue]:
    races, circ, drv, con, man, res = (t["races"], t["circuits"], t["drivers"], t["constructors"],
                                       t["manifest"], t["results"])
    issues: list[Issue] = []

    m = races.duplicated(keep="first")
    issues.append(Issue(
        "B18", "Uniqueness", "races", "all", "Duplicate race records", int(m.sum()), len(races), True, "Medium",
        f"duplicated (season, round): {[f'{s}-R{r}' for s, r in races.loc[m, ['season', 'round']].values]}",
        "Rows appended twice at the end of the file (rows 1174-1178).",
        "Join fan-out: every result of these races is duplicated after a join with races.",
        "C10"))
    exact = circ.duplicated(keep="first")
    orphan = circ["circuitId"].isna()
    issues.append(Issue(
        "B19", "Uniqueness", "circuits", "circuitId, url", "Duplicate circuits (exact copies and copies without ID)",
        int(exact.sum() + orphan.sum()), len(circ), True, "Medium",
        f"exact copies: {circ.loc[exact, 'circuitId'].tolist()}; ID missing but same url as existing circuit: "
        f"{circ.loc[orphan, 'circuitName'].tolist()}",
        "Circuits re-added during a merge without their key.",
        "Join fan-out on circuitId; a map aggregates the same circuit twice.",
        "C10"))
    full = drv["name.givenName"] + " " + drv["name.familyName"]
    m = full.duplicated(keep=False)
    issues.append(Issue(
        "B20", "Uniqueness", "drivers", "driverId", "Same person under two identifiers", int(m.sum()), len(drv),
        True, "Medium", f"{drv.loc[m, ['driverId', 'dateOfBirth']].to_dict('records')}",
        "A new driver was added twice by two ingestion runs with different ID conventions.",
        "Entity resolution error: career statistics split across two nodes in the graph.",
        "C10"))
    m = circ["country"].isin(NON_ISO_COUNTRY_NAMES)
    issues.append(Issue(
        "B21", "Validity", "circuits", "country", "Country names not in a standard vocabulary",
        int(m.sum()), len(circ), True, "Medium",
        f"{circ.loc[m, 'country'].value_counts().to_dict()} (ambiguous: 'Korea'); nationalities are free-text "
        f"demonyms incl. former states ('east german', 'rhodesian')",
        "Abbreviations typed by hand; no ISO 3166 codes in the source.",
        "Geo joins and choropleth maps fail (the dashboard map showed only 1 country); no interoperability.",
        "C10"))
    mc = circ[["lat", "long"]].isna().any(axis=1)
    issues.append(Issue(
        "B22", "Completeness", "circuits", "lat, long", "Missing coordinates", int(mc.sum()), len(circ), True, "Low",
        f"{circ.loc[mc, 'circuitId'].tolist()}", "New 2026 venue added before its coordinates were published.",
        "Circuit cannot be placed on a map or used in distance features.", "Documented (kept missing)"))
    md = drv[["dateOfBirth", "nationality", "url"]].isna().any(axis=1)
    mcon = con["url"].isna()
    issues.append(Issue(
        "B23", "Completeness", "drivers / constructors", "dateOfBirth, nationality, url",
        "Missing attributes for newest entities", int(md.sum() + mcon.sum()), len(drv) + len(con), True, "Low",
        f"drivers: {drv.loc[md, 'driverId'].tolist()}; constructors: {con.loc[mcon, 'constructorId'].tolist()}",
        "Timeliness: 2026 entrants/reserves were added before their profiles existed upstream.",
        "Age and nationality features are missing for recent drivers (none of them has a race result yet).",
        "Documented (kept missing)"))
    m = races["season"] > config.LAST_COMPLETE_SEASON
    issues.append(Issue(
        "B24", "Timeliness", "races", "season", "Reference calendar ahead of the results snapshot",
        int(m.sum()), len(races), False, "Low",
        f"{int(m.sum())} races of season {int(races.loc[m, 'season'].min())} without results; latest date {races['date'].max()}",
        "Calendar for the upcoming season is published before results exist; tables were exported at different times.",
        "Counting races per season or per circuit over-states 2026; an inner join hides the mismatch.",
        "C10 (flag has_results)"))
    schemes = pd.concat([drv["url"], con["url"], circ["url"], races["url"]]).dropna().str.extract(r"^(https?)://")[0]
    issues.append(Issue(
        "B25", "Consistency", "drivers / constructors", "url", "Mixed URL schemes (http vs https)",
        int((schemes == "http").sum()), int(schemes.notna().sum()), True, "Low",
        f"{schemes.value_counts().to_dict()} across all reference tables",
        "Links copied from different Wikipedia snapshots.",
        "Exact-match linking (e.g. to Wikidata) misses entities; mixed-content warnings in web apps.",
        "C10"))
    lower_names = int((drv["name.givenName"] == drv["name.givenName"].str.lower()).sum()
                      + (circ["circuitName"] == circ["circuitName"].str.lower()).sum())
    issues.append(Issue(
        "B26", "Consistency", "drivers / circuits", "name, circuitName, locality",
        "Proper names stored in lowercase", lower_names, len(drv) + len(circ), True, "Low",
        "e.g. 'carlo abate', 'circuit gilles villeneuve', 'montreal'; constructors use proper case ('McLaren')",
        "Same lowercasing step as B14.", "Readability and matching with external authority files.", "C10"))
    m = circ["circuitName"].str.contains("losail", na=False)
    issues.append(Issue(
        "B27", "Accuracy", "circuits", "circuitName", "Name differs from the official spelling",
        int(m.sum()), len(circ), True, "Low",
        "'losail international circuit' while the Wikipedia/official name is 'Lusail International Circuit'",
        "Legacy transliteration kept from an older source.", "Text matching against official sources fails.",
        "Documented (kept, alias noted)"))
    pretty = man[man["detected_format"] == "json_array_pretty_printed"]
    junk = man[man["detected_format"].isin(["os_metadata_file", "empty_file"])]
    issues.append(Issue(
        "B28", "Consistency", "source package", "file format", "Mixed file formats in one package",
        int(len(pretty) + len(junk)), len(man), True, "Low",
        f"{len(pretty)} sprint files are pretty-printed JSON arrays while all other JSON files are JSON Lines; "
        f"{len(junk)} non-data files (.DS_Store, empty .flag markers)",
        "Files produced by different scripts; macOS metadata zipped by accident.",
        "Generic loaders fail on part of the package; reproducibility depends on undocumented conventions.",
        "Step 0 (format detection in manifest)"))
    ret = res[res["positionText"] == "R"].assign(s=season_from_file(res[res["positionText"] == "R"]))
    generic_share = ret.groupby("s")["status"].apply(lambda s: s.eq("Retired").mean())
    late = generic_share[generic_share > 0.5].index
    first_late = int(late.min()) if len(late) else None
    m = ret["status"].eq("Retired") & (ret["s"] >= first_late if first_late else False)
    issues.append(Issue(
        "B29", "Consistency", "results", "status", "Retirement causes no longer recorded in recent seasons",
        int(m.sum()), len(res), True, "Medium",
        "share of retirements stored only as 'Retired': " +
        ", ".join(f"{s}: {v:.0%}" for s, v in generic_share.loc[2019:].items()) +
        f" (found when the reliability trend was visualised in the project dashboard)",
        f"Recording practice changed in the source from {first_late}: retirements are entered with the generic "
        "status 'Retired' instead of the cause (engine, accident, ...).",
        "Reliability trends and failure-cause models see a false collapse of mechanical failures and accidents "
        f"after {first_late - 1 if first_late else ''}; models trained across this boundary learn a spurious time effect.",
        "C07 (mapped to 'Retired (unspecified)'; cause analyses limited to earlier seasons)"))
    return issues


def passed_checks(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Rules that were tested and found no violation - evidence of what is trustworthy."""
    r, races, circ, drv, con = t["results"], t["races"], t["circuits"], t["drivers"], t["constructors"]
    joined = r.drop_duplicates(["season", "round"]).merge(races.drop_duplicates(), on=["season", "round"],
                                                          suffixes=("_r", "_x"))
    dob = r.merge(drv[["driverId", "dateOfBirth"]], on="driverId", how="left")
    age = (pd.to_datetime(dob["date"]) - pd.to_datetime(dob["dateOfBirth"], errors="coerce")).dt.days / 365.25
    num_text = pd.to_numeric(r["positionText"], errors="coerce")
    checks = [
        ("Referential integrity", "results.driverId exists in drivers", int((~r["driverId"].isin(drv["driverId"])).sum())),
        ("Referential integrity", "results.constructorId exists in constructors",
         int((~r["constructorId"].isin(con["constructorId"])).sum())),
        ("Referential integrity", "races.circuitId exists in circuits",
         int((~races["circuitId"].isin(circ["circuitId"].dropna())).sum())),
        ("Consistency", "results.date equals races.date for the same race", int((joined["date_r"] != joined["date_x"]).sum())),
        ("Consistency", "results.raceName equals races.raceName", int((joined["raceName_r"] != joined["raceName_x"]).sum())),
        ("Consistency", "numeric positionText equals position",
         int(((num_text != r["position"]) & num_text.notna()).sum())),
        ("Consistency", "year of date equals season (where season present)",
         int(((pd.to_datetime(r["date"]).dt.year != r["season"]) & r["season"].notna()).sum())),
        ("Validity", "no negative points, grid or laps", int(((r["points"] < 0) | (r["grid"] < 0) | (r["laps"] < 0)).sum())),
        ("Validity", "points > 0 only for rows with a position", int(((r["points"] > 0) & r["position"].isna()).sum())),
        ("Validity", "all dates parse as ISO 8601", int(pd.to_datetime(r["date"], errors="coerce").isna().sum())),
        ("Accuracy", "driver age at race between 16 and 60 years", int(((age < 16) | (age > 60)).sum())),
        ("Accuracy", "circuit coordinates within valid lat/long ranges",
         int(((circ["lat"].abs() > 90) | (circ["long"].abs() > 180)).sum())),
        ("Uniqueness", "driverId unique in drivers", int(drv["driverId"].duplicated().sum())),
        ("Uniqueness", "constructorId unique in constructors", int(con["constructorId"].duplicated().sum())),
    ]
    df = pd.DataFrame(checks, columns=["dimension", "rule", "violations"])
    df["result"] = np.where(df["violations"] == 0, "passed", "FAILED")
    return df


def summarise(issues: list[Issue]) -> pd.DataFrame:
    df = pd.DataFrame([{**asdict(i), "affected_pct": i.affected_pct} for i in issues])
    return (df.groupby("dimension")
              .agg(issues=("issue_id", "count"),
                   errors=("is_error", "sum"),
                   not_errors=("is_error", lambda s: int((~s).sum())),
                   high_severity=("severity", lambda s: int((s == "High").sum())),
                   affected_records=("affected_records", "sum"))
              .reset_index()
              .sort_values("issues", ascending=False))


def to_markdown(df: pd.DataFrame) -> str:
    cols = ["issue_id", "dimension", "table", "title", "affected_records", "affected_pct", "severity",
            "is_error", "cleaning_step"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, row in df[cols].iterrows():
        lines.append("| " + " | ".join(str(v) for v in row.values) + " |")
    details = []
    for _, row in df.iterrows():
        details.append(f"\n### {row['issue_id']} - {row['title']}\n"
                       f"- **Dimension:** {row['dimension']} | **Table/columns:** {row['table']} / {row['columns']}\n"
                       f"- **Affected:** {row['affected_records']} of {row['table_rows']} ({row['affected_pct']}%) | "
                       f"**Severity:** {row['severity']} | **Error:** {row['is_error']}\n"
                       f"- **Evidence:** {row['evidence']}\n"
                       f"- **Root-cause hypothesis:** {row['root_cause_hypothesis']}\n"
                       f"- **Downstream impact (DS/AI):** {row['downstream_impact']}\n"
                       f"- **Resolved by:** {row['cleaning_step']}\n")
    return "# Data quality issue register\n\n" + "\n".join(lines) + "\n\n## Details\n" + "".join(details)


def run() -> dict:
    config.ensure_dirs()
    t = load_raw()
    tables = {k: v for k, v in t.items() if k != "manifest"}
    pd.concat([profile_columns(k, v) for k, v in tables.items()], ignore_index=True).to_csv(
        config.QUALITY_DIR / "profile_columns.csv", index=False)
    profile_tables(tables).to_csv(config.QUALITY_DIR / "profile_tables.csv", index=False)

    issues = check_results(t) + check_reference(t)
    register = pd.DataFrame([{**asdict(i), "affected_pct": i.affected_pct} for i in issues])
    register.to_csv(config.QUALITY_DIR / "quality_issues.csv", index=False)
    (config.QUALITY_DIR / "quality_issues.md").write_text(to_markdown(register), encoding="utf-8")
    by_dim = summarise(issues)
    by_dim.to_csv(config.QUALITY_DIR / "quality_summary_by_dimension.csv", index=False)
    passed_checks(t).to_csv(config.QUALITY_DIR / "passed_checks.csv", index=False)
    summary = {"issues": len(issues), "errors": int(register["is_error"].sum()),
               "dimensions": int(register["dimension"].nunique()),
               "high_severity": int((register["severity"] == "High").sum())}
    print("[component B] profiling:", summary)
    return summary


if __name__ == "__main__":
    run()
