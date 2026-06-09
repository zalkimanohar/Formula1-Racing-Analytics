# dashboard/utils.py

import pandas as pd
import os

DATA_ROOT = "/Users/manoharazalki/F1-Analytics/data/gold"


def _load(table: str) -> pd.DataFrame:
    path = os.path.join(DATA_ROOT, table, f"{table}.parquet")
    return pd.read_parquet(path)


def load_f1_gold() -> pd.DataFrame:
    fact = _load("fact_session_results")
    races = _load("dim_races")
    drivers = _load("dim_drivers")
    constructors = _load("dim_constructors")

    # Merge
    df = (
        fact
        .merge(races, on=["season", "round"], suffixes=("_fact", "_race"))
        .merge(drivers, on="driver_id")
        .merge(constructors, on="constructor_id")
    )

    # Remove duplicate race columns
    df = df.drop(columns=[c for c in ["race_date_fact", "race_name_fact"] if c in df.columns], errors="ignore")

    # Rename race columns
    df = df.rename(columns={
        "race_date_race": "race_date",
        "race_name_race": "race_name"
    })

    # Convert datetime columns
    df["race_date"] = pd.to_datetime(df["race_date"], errors="coerce")
    df["date_of_birth"] = pd.to_datetime(df["date_of_birth"], errors="coerce")

    # ---------------------------------------------------------
    # FIX nationality_region (unify x/y columns)
    # ---------------------------------------------------------
    if "nationality_region_x" in df.columns:
        df["nationality_region"] = df["nationality_region_x"]
    elif "nationality_region_y" in df.columns:
        df["nationality_region"] = df["nationality_region_y"]
    else:
        df["nationality_region"] = "Other"

    # Derived metrics
    df["age_at_race"] = (df["race_date"] - df["date_of_birth"]).dt.days / 365.25
    df["positions_gained"] = df["grid_position"] - df["final_position"]

    return df
