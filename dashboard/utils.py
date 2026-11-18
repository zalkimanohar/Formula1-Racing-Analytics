import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(DASHBOARD_DIR, ".."))
BASE = os.path.join(PROJECT_ROOT, "data")


def _to_native_df(df: pd.DataFrame) -> pd.DataFrame:
    """Strips PyArrow/extension dtypes completely so Plotly never falls back to index numbers."""
    if df.empty:
        return df
    out = pd.DataFrame(index=range(len(df)))
    for col in df.columns:
        s = df[col]
        dtype_name = str(s.dtype).lower()
        if any(k in dtype_name for k in ["int", "float", "double", "decimal"]):
            out[col] = pd.to_numeric(s, errors="coerce").to_numpy(dtype="float64")
        elif "bool" in dtype_name:
            out[col] = s.fillna(False).to_numpy(dtype=bool)
        else:
            out[col] = [None if pd.isna(v) else str(v).strip() for v in s.tolist()]
    return out


def load_gold(table: str) -> pd.DataFrame:
    mapping = {
        "drivers": f"{BASE}/gold/dim_drivers/dim_drivers.parquet",
        "constructors": f"{BASE}/gold/dim_constructors/dim_constructors.parquet",
        "races": f"{BASE}/gold/dim_races/dim_races.parquet",
        "results": f"{BASE}/gold/fact_session_results/fact_session_results.parquet",
        "nationality": f"{BASE}/gold/ref_nationality_region/ref_nationality_region.parquet",
    }
    path = mapping.get(table)
    if not path or not os.path.exists(path):
        return pd.DataFrame()

    df = _to_native_df(pd.read_parquet(path))
    rename_map = {
        "year": "season",
        "grid": "grid_position",
        "position": "final_position",
    }
    df = df.rename(columns=rename_map)

    for col in ["season", "round", "grid_position", "final_position", "points", "laps"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype="float64")

    return df


def load_silver(table: str) -> pd.DataFrame:
    mapping = {
        "circuits": f"{BASE}/silver/circuits/circuits.parquet",
        "sprints": f"{BASE}/silver/sprints/sprints.parquet",
    }
    path = mapping.get(table)
    if not path or not os.path.exists(path):
        return pd.DataFrame()

    df = _to_native_df(pd.read_parquet(path))
    rename_map = {
        "grid": "grid_position",
        "position": "final_position",
    }
    df = df.rename(columns=rename_map)

    for col in ["season", "round", "grid_position", "final_position", "points"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype="float64")

    return df


def load_table(table: str) -> pd.DataFrame:
    if table in ["drivers", "constructors", "races", "results", "nationality"]:
        return load_gold(table)
    if table in ["circuits", "sprints"]:
        return load_silver(table)
    return pd.DataFrame()


def f1_fig(title: str = "", height: int = 450) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        height=height,
        template="plotly_dark",
        paper_bgcolor="#0d0d0d",
        plot_bgcolor="#0d0d0d",
        font=dict(color="#e6e6e6", size=13),
        title_font=dict(color="#ff1e00", size=20),
        margin=dict(l=40, r=40, t=70, b=60),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="#333333",
            borderwidth=1
        )
    )
    return fig