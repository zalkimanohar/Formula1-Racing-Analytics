"""Component C - Reproducible cleaning pipeline with an audit log.

Every step responds to issues in the Component B register (outputs/component_b_quality/
quality_issues.csv) and records before/after statistics. The step order is deliberate: keys are
repaired (C02) BEFORE de-duplication (C03), otherwise 11 duplicates whose keys were blanked would
survive. The pipeline ends with validation gates; if any gate fails the run stops and no file
is published as "clean".

Run:  python -m src.cleaning     (from the project root, after src.build_raw_dataset)
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from src import config, schema
from src import vocabularies as voc

BUSINESS_COLUMNS = ["date", "raceName", "round", "season", "url", "constructorId", "driverId", "grid",
                    "laps", "number", "points", "position", "positionText", "status"]


# --------------------------------------------------------------------------------------------
# Audit log
# --------------------------------------------------------------------------------------------
@dataclass
class StepRecord:
    step_id: str
    step_name: str
    issues_addressed: str
    table: str
    rows_before: int
    rows_after: int
    rows_removed: int
    cells_changed: int
    columns_added: str
    missing_before: int
    missing_after: int
    details: str
    duration_ms: int


def _norm(value):
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return str(value)


def cells_changed(before: pd.DataFrame, after: pd.DataFrame, rename: dict) -> int:
    """Count cells whose value differs, aligning rows by index and columns through `rename`."""
    idx = before.index.intersection(after.index)
    total = 0
    for col in before.columns:
        target = rename.get(col, col)
        if target not in after.columns:
            continue
        b = before.loc[idx, col].map(_norm)
        a = after.loc[idx, target].map(_norm)
        same = (b == a) | (b.isna() & a.isna())
        total += int((~same).sum())
    return total


class Audit:
    def __init__(self) -> None:
        self.records: list[StepRecord] = []

    def log(self, step_id, name, issues, table, before, after, details, started, rename=None):
        rename = rename or {}
        pairs = [(c, rename.get(c, c)) for c in before.columns if rename.get(c, c) in after.columns]
        mapped = {a for _, a in pairs}
        rec = StepRecord(
            step_id=step_id, step_name=name, issues_addressed=issues, table=table,
            rows_before=len(before), rows_after=len(after), rows_removed=len(before) - len(after),
            cells_changed=cells_changed(before, after, rename),
            columns_added=", ".join(c for c in after.columns if c not in mapped),
            missing_before=int(before[[b for b, _ in pairs]].isna().sum().sum()),
            missing_after=int(after[[a for _, a in pairs]].isna().sum().sum()),
            details=details, duration_ms=int((time.perf_counter() - started) * 1000))
        self.records.append(rec)
        print(f"  [{step_id}] {name}: rows {rec.rows_before}->{rec.rows_after}, cells changed {rec.cells_changed}")

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(r) for r in self.records])


# --------------------------------------------------------------------------------------------
# Results table steps
# --------------------------------------------------------------------------------------------
def c01_enforce_types(r: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = r.copy()
    before = {c: str(r[c].dtype) for c in r.columns}
    for col in ("season", "round", "number", "grid", "laps", "position", "source_line"):
        values = pd.to_numeric(out[col], errors="raise")
        if not np.all(np.mod(values.dropna(), 1) == 0):
            raise ValueError(f"{col} has non-integer values")
        out[col] = values.astype("Int64")
    out["points"] = pd.to_numeric(out["points"], errors="raise").astype("float64")
    out["date"] = pd.to_datetime(out["date"], format="%Y-%m-%d", errors="raise")
    for col in ("source_file", "raceName", "url", "constructorId", "driverId", "positionText", "status"):
        out[col] = out[col].astype("string")
    changed = [f"{c}: {before[c]}->{out[c].dtype}" for c in out.columns if before[c] != str(out[c].dtype)]
    return out, "; ".join(changed)


def c02_repair_keys(r: pd.DataFrame, races_raw: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = r.copy()
    file_season = out["source_file"].str.extract(r"(\d{4})")[0].astype("Int64")
    miss_season = out["season"].isna()
    if (out.loc[~miss_season, "season"] != file_season[~miss_season]).any():
        raise ValueError("season disagrees with source file name; cannot use file name as key source")
    out.loc[miss_season, "season"] = file_season[miss_season]
    if (out["date"].dt.year != out["season"]).any():
        raise ValueError("restored season disagrees with race date")

    ref = races_raw.drop_duplicates()[["season", "date", "raceName", "round"]].copy()
    ref["date"] = pd.to_datetime(ref["date"])
    ref["season"] = ref["season"].astype("Int64")
    if ref.duplicated(["season", "date", "raceName"]).any():
        raise ValueError("races lookup key (season, date, raceName) is not unique")
    miss_round = out["round"].isna()
    looked_up = out.loc[miss_round, ["season", "date", "raceName"]].merge(
        ref, on=["season", "date", "raceName"], how="left")["round"].to_numpy()
    if pd.isna(looked_up).any():
        raise ValueError("some missing rounds could not be resolved from races.csv")
    out.loc[miss_round, "round"] = pd.array(looked_up, dtype="Int64")
    return out, (f"season restored for {int(miss_season.sum())} rows from source file name (cross-checked with "
                 f"race date); round restored for {int(miss_round.sum())} rows by exact lookup in races.csv on "
                 f"(season, date, raceName). Deterministic lookup, no statistical imputation.")


def c03_remove_duplicates(r: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    dup = r.duplicated(BUSINESS_COLUMNS, keep="first")
    removed = r[dup]
    out = r[~dup].copy()
    key = ["season", "round", "driverId", "number"]
    if out.duplicated(key, keep=False).any():
        raise ValueError("natural key (season, round, driverId, number) still not unique after de-duplication")
    where = "; ".join(f"{f}: {len(g)} rows" for f, g in removed.groupby("source_file"))
    return out, (f"removed {int(dup.sum())} exact duplicates on all 14 business columns (keep first occurrence) "
                 f"[{where}]; natural key (season, round, driverId, number) verified unique. Shared drives "
                 f"(same driver, different car) are intentionally kept.")


def c04_standardise_ids(r: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = r.copy()
    changed = {}
    for col in ("driverId", "constructorId"):
        new = out[col].str.strip().str.lower()
        diff = new != out[col]
        changed[col] = sorted(out.loc[diff, col].unique().tolist())
        out[col] = new
    return out, f"trimmed and lower-cased identifiers; changed values: {changed}"


def c05_grid_sentinel(r: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = r.copy()
    sentinel = out["grid"] == 0
    out["grid_position_missing"] = sentinel.astype("boolean")
    out["grid"] = out["grid"].mask(sentinel)
    return out, (f"grid value 0 (pit-lane start / no grid slot) replaced by missing for {int(sentinel.sum())} rows; "
                 f"boolean flag grid_position_missing keeps the information")


def c06_classification(r: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = r.copy()
    numeric = out["positionText"].str.fullmatch(r"\d+")
    unknown = sorted(set(out.loc[~numeric, "positionText"]) - set(voc.FINISH_CATEGORY_BY_CODE))
    if unknown:
        raise ValueError(f"unmapped positionText codes: {unknown}")
    out["classified_position"] = out["position"].where(numeric).astype("Int64")
    out["finish_category"] = np.where(numeric, "Classified",
                                      out["positionText"].map(voc.FINISH_CATEGORY_BY_CODE).astype(object))
    out["finish_category"] = out["finish_category"].astype("string")
    lapped = out["status"].str.match(voc.LAPPED_RE.pattern) | (out["status"] == "Finished")
    out["status_position_conflict"] = ((out["positionText"] == "R") & lapped).astype("boolean")
    counts = out["finish_category"].value_counts().to_dict()
    return out, (f"classified_position kept only where positionText is numeric ({int(numeric.sum())} rows), "
                 f"set missing for {int((~numeric).sum())} non-classified rows; finish_category {counts}; "
                 f"{int(out['status_position_conflict'].sum())} R-vs-lapped conflicts flagged (positionText trusted)")


def c07_status(r: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = r.copy()
    groups = out["status"].map(voc.status_group)
    unmapped = sorted(out.loc[groups.isna(), "status"].unique().tolist())
    if unmapped:
        raise ValueError(f"unmapped status values: {unmapped}")
    out["status_group"] = groups.astype("string")
    return out, (f"{out['status'].nunique()} free-text values mapped to {out['status_group'].nunique()} groups "
                 f"(exhaustive mapping, raw value kept): {out['status_group'].value_counts().to_dict()}")


def c08_outliers(r: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = r.copy()
    q1, q3 = out["laps"].quantile([0.25, 0.75])
    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    out["laps_outlier_iqr"] = ((out["laps"] < lo) | (out["laps"] > hi)).astype("boolean")
    out["is_indy500"] = (out["raceName"] == "indianapolis 500").astype("boolean")
    flagged = out["laps_outlier_iqr"]
    overlap = int((flagged & out["is_indy500"]).sum())
    return out, (f"IQR fences [{lo:g}, {hi:g}] laps; {int(flagged.sum())} rows flagged, {overlap} of them are "
                 f"Indianapolis 500 entries; {int(out['is_indy500'].sum())} Indy 500 rows flagged in total. "
                 f"Rows are KEPT: the values are valid domain extremes, not errors.")


def c09_points(r: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = r.copy()
    race_max = out.groupby(["season", "round"])["points"].transform("max")
    if (race_max <= 0).any():
        raise ValueError("a race awards no points; normalisation undefined")
    out["points_normalised"] = (out["points"] / race_max).round(6)
    return out, ("points_normalised = points / highest points awarded in the same race; raw points kept. "
                 f"Winner share = 1.0 in every race; mean share {out['points_normalised'].mean():.4f}")


# --------------------------------------------------------------------------------------------
# Reference tables (C10)
# --------------------------------------------------------------------------------------------
def https(url: pd.Series) -> pd.Series:
    return url.str.replace(r"^http://", "https://", regex=True)


def load_crosswalk() -> pd.DataFrame | None:
    path = config.REFERENCE_DIR / "wikidata_crosswalk.csv"
    if not path.exists():
        return None
    cw = pd.read_csv(path)
    cw = cw[cw["wikidata_qid"].notna()].copy()
    cw["wikipedia_url"] = https(cw["wikipedia_url"].astype(str).str.strip())
    return cw


def attach_qid(df: pd.DataFrame, entity_type: str, crosswalk: pd.DataFrame | None) -> pd.DataFrame:
    if crosswalk is None:
        df["wikidata_qid"] = pd.Series(pd.NA, index=df.index, dtype="string")
        return df
    cw = crosswalk[crosswalk["entity_type"] == entity_type][["wikipedia_url", "wikidata_qid"]].drop_duplicates(
        "wikipedia_url")
    out = df.merge(cw, on="wikipedia_url", how="left", validate="many_to_one")
    out.index = df.index
    out["wikidata_qid"] = out["wikidata_qid"].astype("string")
    return out


def c10_races(races_raw: pd.DataFrame, results_keys: set) -> tuple[pd.DataFrame, str]:
    dup = races_raw.duplicated(keep="first")
    out = races_raw[~dup].copy()
    out["season"] = out["season"].astype("Int64")
    out["round"] = out["round"].astype("Int64")
    out["race_id"] = out["season"].astype(str) + "_" + out["round"].astype(str).str.zfill(2)
    out["race_name"] = out["raceName"].map(voc.smart_title).astype("string")
    out["race_date"] = pd.to_datetime(out["date"], format="%Y-%m-%d")
    out["circuit_id"] = out["circuitId"].astype("string")
    out["wikipedia_url"] = https(out["url"]).astype("string")
    out["has_results"] = pd.Series([(s, r) in results_keys for s, r in zip(out["season"], out["round"])],
                                   index=out.index, dtype="boolean")
    if out["race_id"].duplicated().any():
        raise ValueError("race_id not unique after de-duplication")
    out = out[["race_id", "season", "round", "race_name", "race_date", "circuit_id", "wikipedia_url", "has_results"]]
    return out, (f"removed {int(dup.sum())} exact duplicate races; title-cased names; https "
                                        f"URLs; has_results=False for {int((~out['has_results']).sum())} races "
                                        f"(future {int(out.loc[~out['has_results'], 'season'].min())} calendar)")


def c10_circuits(circ_raw: pd.DataFrame, crosswalk) -> tuple[pd.DataFrame, str]:
    exact = circ_raw.duplicated(keep="first")
    out = circ_raw[~exact].copy()
    orphan = out["circuitId"].isna()
    known_urls = set(out.loc[~orphan, "url"])
    redundant = orphan & out["url"].isin(known_urls)
    if (orphan & ~redundant).any():
        raise ValueError("circuit without ID that does not duplicate a known circuit - needs manual review")
    out = out[~redundant].copy()
    bad_country = sorted(set(out["country"].replace(voc.COUNTRY_NAME_FIXES)) - set(voc.COUNTRY_ISO3))
    if bad_country:
        raise ValueError(f"unmapped circuit countries: {bad_country}")
    out["country_std"] = out["country"].replace(voc.COUNTRY_NAME_FIXES)
    res = pd.DataFrame({
        "circuit_id": out["circuitId"].astype("string"),
        "circuit_name": out["circuitName"].map(voc.smart_title).astype("string"),
        "locality": out["locality"].map(voc.smart_title).astype("string"),
        "country": out["country_std"].astype("string"),
        "country_iso3": out["country_std"].map(voc.COUNTRY_ISO3).astype("string"),
        "latitude": out["lat"].astype("float64"),
        "longitude": out["long"].astype("float64"),
        "wikipedia_url": https(out["url"]).astype("string"),
    })
    res = attach_qid(res, "circuit", crosswalk)
    if res["circuit_id"].duplicated().any():
        raise ValueError("circuit_id not unique")
    fixed = int(out["country"].isin(voc.COUNTRY_NAME_FIXES).sum())
    return res, (
        f"removed {int(exact.sum())} exact duplicates and {int(redundant.sum())} ID-less copies of known circuits; "
        f"{fixed} country abbreviations expanded; ISO 3166-1 alpha-3 codes added for all {len(res)} circuits; "
        f"title-cased names; coordinates of {int(res['latitude'].isna().sum())} circuit(s) left missing (no source)")


def c10_drivers(drv_raw: pd.DataFrame, crosswalk) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    out = drv_raw.copy()
    out["driverId"] = out["driverId"].str.strip().str.lower()
    out["full_key"] = out["name.givenName"] + " " + out["name.familyName"]
    out["completeness"] = out[["dateOfBirth", "nationality", "url"]].notna().sum(axis=1)
    aliases = []
    for _, grp in out[out["full_key"].duplicated(keep=False)].groupby("full_key"):
        if grp["dateOfBirth"].dropna().nunique() > 1:
            raise ValueError(f"same name, different birth dates: {grp['driverId'].tolist()} - not the same person")
        keep = grp.sort_values("completeness", ascending=False).iloc[0]["driverId"]
        for drop_id in grp["driverId"]:
            if drop_id != keep:
                aliases.append({"alias_driver_id": drop_id, "canonical_driver_id": keep,
                                "reason": "same full name; alias record has no birth date or nationality"})
    alias_df = pd.DataFrame(aliases, columns=["alias_driver_id", "canonical_driver_id", "reason"])
    out = out[~out["driverId"].isin(alias_df["alias_driver_id"])].copy()
    unknown = sorted(set(out["nationality"].dropna()) - set(voc.NATIONALITY_ISO))
    if unknown:
        raise ValueError(f"unmapped driver nationalities: {unknown}")
    res = pd.DataFrame({
        "driver_id": out["driverId"].astype("string"),
        "given_name": out["name.givenName"].map(voc.smart_title).astype("string"),
        "family_name": out["name.familyName"].map(voc.smart_title).astype("string"),
        "full_name": out["full_key"].map(voc.smart_title).astype("string"),
        "date_of_birth": pd.to_datetime(out["dateOfBirth"], format="%Y-%m-%d"),
        "nationality": out["nationality"].map(voc.smart_title).astype("string"),
        "nationality_iso3": out["nationality"].map(voc.NATIONALITY_ISO).astype("string"),
        "wikipedia_url": https(out["url"]).astype("string"),
    })
    res = attach_qid(res, "driver", crosswalk)
    if res["driver_id"].duplicated().any():
        raise ValueError("driver_id not unique")
    return res, alias_df, (
        f"lower-cased 3 IDs ('Cannoc', 'scott_Brown', 'Changy'); merged {len(alias_df)} duplicate person "
        f"({alias_df.to_dict('records')}); nationality mapped to ISO codes (ISO 3166-3 for East Germany and "
        f"Rhodesia); title-cased names; https URLs")


def c10_constructors(con_raw: pd.DataFrame, crosswalk) -> tuple[pd.DataFrame, str]:
    unknown = sorted(set(con_raw["nationality"].dropna()) - set(voc.NATIONALITY_ISO))
    if unknown:
        raise ValueError(f"unmapped constructor nationalities: {unknown}")
    res = pd.DataFrame({
        "constructor_id": con_raw["constructorId"].str.strip().str.lower().astype("string"),
        "constructor_name": con_raw["name"].astype("string"),
        "nationality": con_raw["nationality"].map(voc.smart_title).astype("string"),
        "nationality_iso3": con_raw["nationality"].map(voc.NATIONALITY_ISO).astype("string"),
        "wikipedia_url": https(con_raw["url"]).astype("string"),
    })
    res = attach_qid(res, "constructor", crosswalk)
    return res, "nationality mapped to ISO codes; https URLs; names already in proper case (kept)"


# --------------------------------------------------------------------------------------------
# Integration (C11) and validation (C12)
# --------------------------------------------------------------------------------------------
def c11_integrate(r, races, circuits, drivers, constructors) -> tuple[pd.DataFrame, str]:
    n0 = len(r)
    df = r.copy()
    df["race_id"] = df["season"].astype(str) + "_" + df["round"].astype(str).str.zfill(2)
    df = df.merge(races[["race_id", "race_name", "race_date", "circuit_id"]], on="race_id", how="left",
                  validate="many_to_one")
    df = df.merge(circuits[["circuit_id", "circuit_name", "locality", "country", "country_iso3"]]
                  .rename(columns={"locality": "circuit_locality", "country": "circuit_country",
                                   "country_iso3": "circuit_country_iso3"}),
                  on="circuit_id", how="left", validate="many_to_one")
    df = df.merge(drivers[["driver_id", "full_name", "nationality_iso3"]]
                  .rename(columns={"driver_id": "driverId", "full_name": "driver_name",
                                   "nationality_iso3": "driver_nationality_iso3"}),
                  on="driverId", how="left", validate="many_to_one")
    df = df.merge(constructors[["constructor_id", "constructor_name", "nationality_iso3"]]
                  .rename(columns={"constructor_id": "constructorId",
                                   "nationality_iso3": "constructor_nationality_iso3"}),
                  on="constructorId", how="left", validate="many_to_one")
    if len(df) != n0:
        raise ValueError("join changed the number of rows (fan-out or loss)")
    df.index = r.index
    if (df["race_date"] != df["date"]).any():
        raise ValueError("race date from races table disagrees with results date")

    race = ["season", "round"]
    driver_twice = df.duplicated(race + ["driverId"], keep=False)
    car_shared = df["number"].notna() & df.duplicated(race + ["number"], keep=False)
    df["is_shared_drive"] = (driver_twice | car_shared).astype("boolean")
    car = df["number"].astype("string").fillna("NA")
    df["result_id"] = df["race_id"] + "_" + df["driverId"] + "_" + car

    df = df.rename(columns={"driverId": "driver_id", "constructorId": "constructor_id", "number": "car_number",
                            "grid": "grid_position", "laps": "laps_completed", "position": "position_order",
                            "positionText": "position_text", "status": "status_raw"})
    df = df[schema.column_names()]
    return df, (f"joined races, circuits, drivers and constructors (many-to-one, validated; {n0} rows in = "
                f"{len(df)} rows out); is_shared_drive flags {int(df['is_shared_drive'].sum())} rows; "
                f"result_id built from race_id + driver_id + car_number")


def c12_validate(df, races, circuits, drivers, constructors) -> pd.DataFrame:
    gates = []

    def gate(name, ok, detail=""):
        gates.append({"gate": name, "result": "passed" if ok else "FAILED", "detail": detail})

    gate("columns match schema (names and order)", list(df.columns) == schema.column_names())
    for col in schema.RESULTS_COLUMNS:
        if not col.nullable and col.name in df:
            n = int(df[col.name].isna().sum())
            gate(f"no missing values in required column {col.name}", n == 0, f"{n} missing")
        if col.allowed_values:
            bad = sorted(set(df[col.name].dropna()) - set(col.allowed_values))
            gate(f"{col.name} uses controlled vocabulary", not bad, str(bad))
    gate("result_id unique", df["result_id"].is_unique)
    gate("natural key (season, round, driver_id, car_number) unique",
         not df.duplicated(list(schema.RESULTS_NATURAL_KEY)).any())
    gate("no exact duplicate records", not df.drop(columns=["result_id", "source_file", "source_line"]).duplicated().any())
    gate("season within snapshot", df["season"].between(config.FIRST_SEASON, config.LAST_COMPLETE_SEASON).all())
    gate("every race_id exists in races", df["race_id"].isin(races["race_id"]).all())
    gate("every circuit_id exists in circuits", df["circuit_id"].isin(circuits["circuit_id"]).all())
    gate("every driver_id exists in drivers", df["driver_id"].isin(drivers["driver_id"]).all())
    gate("every constructor_id exists in constructors", df["constructor_id"].isin(constructors["constructor_id"]).all())
    gate("identifiers are lowercase",
         bool((df["driver_id"] == df["driver_id"].str.lower()).all() and
              (df["constructor_id"] == df["constructor_id"].str.lower()).all()))
    gate("grid_position >= 1 when present", bool((df["grid_position"].dropna() >= 1).all()))
    gate("classified_position missing for every non-classified result",
         bool(df.loc[df["finish_category"] != "Classified", "classified_position"].isna().all()))
    gate("points_normalised within [0, 1]", bool(df["points_normalised"].between(0, 1).all()))
    gate("one winner share of 1.0 per race",
         bool((df[df["points_normalised"] == 1].groupby("race_id").size() >= 1).all()
              and df["race_id"].nunique() == df.loc[df["points_normalised"] == 1, "race_id"].nunique()))
    cls = df.dropna(subset=["classified_position"])
    dup_pos = cls.duplicated(["race_id", "classified_position"], keep=False)
    gate("duplicate classified positions only occur in shared drives",
         bool(cls.loc[dup_pos, "is_shared_drive"].all()), f"{int(dup_pos.sum())} rows share a position")
    gate("race names are not all-lowercase", bool((df["race_name"] != df["race_name"].str.lower()).all()))
    gate("country codes present for every circuit", bool(df["circuit_country_iso3"].notna().all()))
    gate("races table: race_id unique", races["race_id"].is_unique)
    gate("circuits table: circuit_id unique and present", circuits["circuit_id"].notna().all() and circuits["circuit_id"].is_unique)
    gate("drivers table: driver_id unique", drivers["driver_id"].is_unique)
    gate("drivers table: no person under two IDs", not drivers["full_name"].duplicated().any()
         or not drivers[drivers["full_name"].duplicated(keep=False)]["date_of_birth"].duplicated().any())
    gate("reference URLs use https", all(t["wikipedia_url"].dropna().str.startswith("https://").all()
                                         for t in (races, circuits, drivers, constructors)))
    return pd.DataFrame(gates)


# --------------------------------------------------------------------------------------------
# Issue resolution (contract with Component B)
# --------------------------------------------------------------------------------------------
def issue_resolution(raw_issues: pd.DataFrame, df, races, circuits, drivers, constructors, aliases) -> pd.DataFrame:
    lower_name = (df["race_name"] == df["race_name"].str.lower()).sum()
    after = {
        "B01": (int(df["season"].isna().sum()), "Fixed"),
        "B02": (int(df["round"].isna().sum()), "Fixed"),
        "B03": (int(df["car_number"].isna().sum()), "Kept missing (structurally not applicable)"),
        "B04": (int((df["grid_position"] == 0).sum()), "Fixed (sentinel -> missing + flag)"),
        "B05": (None, "Not an error (verified)"),
        "B06": (int(df.drop(columns=["result_id", "source_file", "source_line"]).duplicated().sum()), "Fixed"),
        "B07": (0, "Fixed (keys repaired before de-duplication)"),
        "B08": (int(df["is_shared_drive"].sum()), "Not an error (kept and flagged)"),
        "B09": (int((df["driver_id"] != df["driver_id"].str.lower()).sum()), "Fixed"),
        "B10": (0, "Fixed (schema enforced)"),
        "B11": (int(df.loc[df["finish_category"] != "Classified", "classified_position"].notna().sum()),
                "Fixed (classified_position separated from position_order)"),
        "B12": (int((~df["status_group"].isin(schema.STATUS_GROUPS)).sum()),
                f"Fixed (136 values -> {df['status_group'].nunique()} controlled groups; raw kept)"),
        "B13": (int(df["status_position_conflict"].sum()), "Flagged (kept)"),
        "B14": (int(lower_name), "Fixed"),
        "B15": (None, "Mitigated (points_normalised added)"),
        "B16": (int(df["laps_outlier_iqr"].sum()), "Not an error (kept and flagged)"),
        "B17": (int((~df["race_id"].isin(races["race_id"])).sum()), "Fixed"),
        "B18": (int(races["race_id"].duplicated().sum()), "Fixed"),
        "B19": (int(circuits["circuit_id"].duplicated().sum() + circuits["circuit_id"].isna().sum()), "Fixed"),
        "B20": (int(drivers["full_name"].duplicated().sum()), f"Fixed ({len(aliases)} alias recorded)"),
        "B21": (int(circuits["country_iso3"].isna().sum()), "Fixed (ISO 3166 codes added)"),
        "B22": (int(circuits[["latitude", "longitude"]].isna().any(axis=1).sum()), "Kept missing (documented)"),
        "B23": (int(drivers[["date_of_birth", "nationality", "wikipedia_url"]].isna().any(axis=1).sum()
                    + constructors["wikipedia_url"].isna().sum()), "Kept missing (documented)"),
        "B24": (int((~races["has_results"]).sum()), "Flagged (has_results)"),
        "B25": (int(sum((~t["wikipedia_url"].dropna().str.startswith("https://")).sum()
                        for t in (races, circuits, drivers, constructors))), "Fixed"),
        "B26": (int((drivers["full_name"] == drivers["full_name"].str.lower()).sum()
                    + (circuits["circuit_name"] == circuits["circuit_name"].str.lower()).sum()), "Fixed"),
        "B27": (int(circuits["circuit_name"].str.contains("Losail").sum()), "Kept (documented alias)"),
        "B28": (0, "Handled at extraction (manifest)"),
        "B29": (int(((df["position_text"] == "R") & (df["status_raw"] == "Retired") & (df["season"] >= 2023)).sum()),
                "Kept and documented (cause unknown in source; cause analyses limited to 1950-2022)"),
    }
    rows = []
    for _, issue in raw_issues.iterrows():
        count, status = after[issue["issue_id"]]
        rows.append({"issue_id": issue["issue_id"], "dimension": issue["dimension"], "title": issue["title"],
                     "before": issue["affected_records"], "after": count, "resolution": status,
                     "cleaning_step": issue["cleaning_step"]})
    return pd.DataFrame(rows)


def audit_markdown(audit: pd.DataFrame, gates: pd.DataFrame, resolution: pd.DataFrame, summary: dict) -> str:
    lines = ["# Cleaning audit log", "",
             f"Raw results rows: {summary['raw_rows']} -> clean rows: {summary['clean_rows']} "
             f"({summary['raw_rows'] - summary['clean_rows']} removed); columns: {summary['raw_columns']} -> "
             f"{summary['clean_columns']}.", "", "## Steps", "",
             "| Step | Name | Issues | Table | Rows before | Rows after | Cells changed | Missing before | "
             "Missing after | Columns added |", "|---|---|---|---|---|---|---|---|---|---|"]
    for _, s in audit.iterrows():
        lines.append(f"| {s.step_id} | {s.step_name} | {s.issues_addressed} | {s.table} | {s.rows_before} | "
                     f"{s.rows_after} | {s.cells_changed} | {s.missing_before} | {s.missing_after} | "
                     f"{s.columns_added or '-'} |")
    lines += ["", "### Step details", ""]
    lines += [f"- **{s.step_id} {s.step_name}:** {s.details}" for _, s in audit.iterrows()]
    lines += ["", "## Validation gates", "", "| Gate | Result | Detail |", "|---|---|---|"]
    lines += [f"| {g.gate} | {g.result} | {g.detail} |" for _, g in gates.iterrows()]
    lines += ["", "## Issue resolution (Component B -> C)", "",
              "| Issue | Dimension | Title | Before | After | Resolution |", "|---|---|---|---|---|---|"]
    lines += [f"| {r.issue_id} | {r.dimension} | {r.title} | {r.before} | "
              f"{'-' if pd.isna(r.after) else int(r.after)} | {r.resolution} |" for _, r in resolution.iterrows()]
    return "\n".join(lines) + "\n"


def write_csv(df: pd.DataFrame, path) -> None:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False, lineterminator="\n")


def run() -> dict:
    config.ensure_dirs()
    audit = Audit()
    raw = pd.read_csv(config.RAW_RESULTS_CSV)
    races_raw = pd.read_csv(config.RAW_RACES_CSV)
    circ_raw = pd.read_csv(config.RAW_CIRCUITS_CSV)
    drv_raw = pd.read_csv(config.RAW_DRIVERS_CSV)
    con_raw = pd.read_csv(config.RAW_CONSTRUCTORS_CSV)
    crosswalk = load_crosswalk()
    print("[component C] cleaning pipeline")

    steps = [
        ("C01", "Enforce schema and data types", "B10, B03", c01_enforce_types),
        ("C02", "Repair missing keys by deterministic lookup", "B01, B02, B17", lambda d: c02_repair_keys(d, races_raw)),
        ("C03", "Remove exact duplicates (after key repair)", "B06, B07", c03_remove_duplicates),
        ("C04", "Standardise identifiers", "B09", c04_standardise_ids),
        ("C05", "Replace grid sentinel 0 with missing + flag", "B04", c05_grid_sentinel),
        ("C06", "Separate classification from finishing order", "B11, B13", c06_classification),
        ("C07", "Standardise status into 8 groups", "B12", c07_status),
        ("C08", "Flag statistical outliers (keep valid extremes)", "B16", c08_outliers),
        ("C09", "Normalise points across scoring eras", "B15", c09_points),
    ]
    r = raw
    for step_id, name, issues, fn in steps:
        t0 = time.perf_counter()
        before = r
        r, details = fn(before)
        audit.log(step_id, name, issues, "results", before, r, details, t0)

    t0 = time.perf_counter()
    keys = set(zip(r["season"], r["round"]))
    races, d = c10_races(races_raw, keys)
    audit.log("C10a", "Clean races reference table", "B18, B24, B25", "races", races_raw, races, d, t0,
              rename={"raceName": "race_name", "date": "race_date", "circuitId": "circuit_id", "url": "wikipedia_url"})
    t0 = time.perf_counter()
    circuits, d = c10_circuits(circ_raw, crosswalk)
    audit.log("C10b", "Clean circuits reference table", "B19, B21, B22, B25, B26", "circuits", circ_raw, circuits,
              d, t0, rename={"circuitId": "circuit_id", "circuitName": "circuit_name", "lat": "latitude",
                             "long": "longitude", "url": "wikipedia_url"})
    t0 = time.perf_counter()
    drivers, aliases, d = c10_drivers(drv_raw, crosswalk)
    audit.log("C10c", "Clean drivers reference table", "B09, B20, B21, B23, B25, B26", "drivers", drv_raw, drivers,
              d, t0, rename={"driverId": "driver_id", "name.givenName": "given_name", "name.familyName": "family_name",
                             "dateOfBirth": "date_of_birth", "url": "wikipedia_url"})
    t0 = time.perf_counter()
    constructors, d = c10_constructors(con_raw, crosswalk)
    audit.log("C10d", "Clean constructors reference table", "B21, B23, B25", "constructors", con_raw, constructors,
              d, t0, rename={"constructorId": "constructor_id", "name": "constructor_name", "url": "wikipedia_url"})
    races, circuits, drivers, constructors = (t.reset_index(drop=True) for t in (races, circuits, drivers, constructors))

    t0 = time.perf_counter()
    before = r
    final, d = c11_integrate(r, races, circuits, drivers, constructors)
    audit.log("C11", "Integrate into analysis-ready table", "B08, B14", "results", before, final, d, t0,
              rename={"driverId": "driver_id", "constructorId": "constructor_id", "number": "car_number",
                      "grid": "grid_position", "laps": "laps_completed", "position": "position_order",
                      "positionText": "position_text", "status": "status_raw", "raceName": "race_name",
                      "date": "race_date"})
    final = final.reset_index(drop=True)

    t0 = time.perf_counter()
    gates = c12_validate(final, races, circuits, drivers, constructors)
    failed = gates[gates["result"] != "passed"]
    audit.log("C12", "Validation gates", "all", "results", final, final,
              f"{len(gates) - len(failed)}/{len(gates)} gates passed", t0)

    audit_df = audit.frame()
    audit_df.to_csv(config.CLEANING_DIR / "audit_log.csv", index=False)
    gates.to_csv(config.CLEANING_DIR / "validation_report.csv", index=False)
    if not failed.empty:
        raise RuntimeError(f"validation gates failed - clean files NOT written:\n{failed.to_string()}")

    raw_issues = pd.read_csv(config.QUALITY_DIR / "quality_issues.csv")
    resolution = issue_resolution(raw_issues, final, races, circuits, drivers, constructors, aliases)
    resolution.to_csv(config.CLEANING_DIR / "issue_resolution.csv", index=False)

    write_csv(final, config.CLEAN_RESULTS_CSV)
    write_csv(races, config.CLEAN_RACES_CSV)
    write_csv(circuits, config.CLEAN_CIRCUITS_CSV)
    write_csv(drivers, config.CLEAN_DRIVERS_CSV)
    write_csv(constructors, config.CLEAN_CONSTRUCTORS_CSV)
    aliases.to_csv(config.CLEANING_DIR / "driver_aliases.csv", index=False)

    summary = {"raw_rows": len(raw), "clean_rows": len(final), "raw_columns": len(BUSINESS_COLUMNS),
               "clean_columns": final.shape[1], "gates_passed": int(len(gates)),
               "qid_coverage_drivers": float(drivers["wikidata_qid"].notna().mean())}
    (config.CLEANING_DIR / "audit_log.md").write_text(audit_markdown(audit_df, gates, resolution, summary),
                                                      encoding="utf-8")
    print("[component C] done:", summary)
    return summary


if __name__ == "__main__":
    run()
