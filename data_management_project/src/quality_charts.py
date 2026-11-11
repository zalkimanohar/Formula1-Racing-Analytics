"""Figures for Component B (quality findings) and Component C (cleaning outcome).

Each chart makes one point; every value shown is also available in the CSV tables next to it
(table view for accessibility).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config
from src import plot_style as ps

ps.apply()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

SOURCE = "Source: Ergast/Jolpica F1 results 1950-2025 (racing_f1_data.zip); group analysis."
thousands = FuncFormatter(lambda x, _: f"{x:,.0f}")


def fig_b1_hidden_missingness(raw: pd.DataFrame, path) -> pd.DataFrame:
    disguised = {
        "position": int(raw["positionText"].isin(["R", "W", "D"]).sum()),
        "grid": int((raw["grid"] == 0).sum()),
    }
    rows = []
    for col in ["position", "grid", "number", "round", "season", "laps", "points", "status", "driverId", "date"]:
        rows.append({"column": col, "explicit_missing": int(raw[col].isna().sum()),
                     "disguised_missing": disguised.get(col, 0)})
    df = pd.DataFrame(rows)
    df["total"] = df["explicit_missing"] + df["disguised_missing"]
    df = df.sort_values("total")

    fig, ax = plt.subplots(figsize=(7.4, 3.9))
    y = np.arange(len(df))
    ax.barh(y, df["explicit_missing"], height=0.62, color=ps.CATEGORICAL[0], label="Explicit missing (null)")
    ax.barh(y, df["disguised_missing"], left=df["explicit_missing"] + 0, height=0.62, color=ps.CATEGORICAL[1],
            label="Disguised missing (value present but not meaningful)", edgecolor=ps.SURFACE, linewidth=1.5)
    ax.set_yticks(y, df["column"])
    ax.set_xscale("symlog", linthresh=10)
    ax.set_xlim(0, 30000)
    ax.xaxis.set_major_formatter(thousands)
    ax.grid(axis="y", visible=False)
    for yi, (_, r) in zip(y, df.iterrows()):
        if r["total"]:
            ax.text(r["total"] * 1.12 + 0.5, yi, f"{r['total']:,}", va="center", fontsize=8, color=ps.INK_SECONDARY)
    ax.set_xlabel("Affected rows (symmetric log scale)")
    ps.titles(ax, "Only 18 cells are null, but 9,913 values only pretend to be data",
              "Results table, 25,907 rows. 'position' is filled for retirements; 'grid' uses 0 for 'no grid slot'.")
    ax.legend(loc="lower right")
    ps.source_note(fig, SOURCE)
    ps.save(fig, path)
    return df


def fig_b2_duplicates(raw: pd.DataFrame, path) -> pd.DataFrame:
    business = [c for c in raw.columns if c not in ("source_file", "source_line")]
    season = raw["source_file"].str.extract(r"(\d{4})")[0].astype(int)
    exact = raw.duplicated(business, keep="first")
    hidden = (raw["season"].isna() | raw["round"].isna()) & ~exact
    hidden &= raw.assign(season=season).duplicated(
        [c for c in business if c not in ("season", "round")], keep="first")
    dedup = raw[~exact]
    legit = dedup.duplicated(["season", "round", "driverId"], keep=False) & dedup["season"].notna() & dedup["round"].notna()
    df = pd.DataFrame({
        "season": range(1950, 1966),
    })
    df["true_duplicates"] = [int(((season == s) & (exact | hidden)).sum()) for s in df["season"]]
    df["shared_drives"] = [int(((season.loc[dedup.index] == s) & legit).sum()) for s in df["season"]]

    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    x = np.arange(len(df))
    ax.bar(x, df["shared_drives"], width=0.7, color=ps.CATEGORICAL[0], label="Same driver, two cars (valid history)")
    ax.bar(x, df["true_duplicates"], bottom=df["shared_drives"], width=0.7, color=ps.STATUS_CRITICAL,
           label="True duplicate record (error)", edgecolor=ps.SURFACE, linewidth=1.5)
    ax.set_xticks(x, df["season"], rotation=0, fontsize=8)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Rows matching another row on (season, round, driver)")
    i1960 = int(np.where(df["season"] == 1960)[0][0])
    top = df.loc[i1960, "true_duplicates"] + df.loc[i1960, "shared_drives"]
    ax.annotate("1960: 34 copied rows\n(23 exact + 11 with blanked keys)", xy=(i1960 + 0.38, top - 2),
                xytext=(i1960 + 0.9, top - 1), fontsize=8, color=ps.INK, va="top",
                arrowprops=dict(arrowstyle="-", color=ps.INK_MUTED, lw=0.8))
    ax.set_ylim(0, 40)
    ps.titles(ax, "A naive duplicate check would delete 172 valid historic results",
              "Rows sharing season, round and driver: errors (red) vs. legitimate shared drives (blue).")
    ax.legend(loc="upper right", bbox_to_anchor=(1.0, 0.62))
    ps.source_note(fig, SOURCE)
    ps.save(fig, path)
    return df


def fig_b3_points_eras(raw: pd.DataFrame, path) -> pd.DataFrame:
    winners = raw[raw["positionText"] == "1"].copy()
    winners["season_i"] = raw["source_file"].str.extract(r"(\d{4})")[0].astype(int)
    df = winners.groupby("season_i")["points"].agg(typical=lambda s: s.mode().iloc[0], maximum="max").reset_index()
    df = df.rename(columns={"season_i": "season"})

    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    ax.step(df["season"], df["typical"], where="mid", color=ps.CATEGORICAL[0], lw=2)
    peak = df.loc[df["maximum"].idxmax()]
    ax.scatter([peak["season"]], [peak["maximum"]], s=40, color=ps.CATEGORICAL[0], zorder=3,
               edgecolor=ps.SURFACE, linewidth=2)
    ax.annotate(f"{int(peak['season'])} Abu Dhabi: double points ({peak['maximum']:g})",
                xy=(peak["season"], peak["maximum"]), xytext=(1985, 45), fontsize=8,
                arrowprops=dict(arrowstyle="-", color=ps.INK_MUTED, lw=0.8))
    for x, y, text in [(1953, 11.5, "8-9 pts\n(+1 fastest lap)"), (1993, 13.5, "10 pts"), (2011, 28.5, "25 pts")]:
        ax.text(x, y, text, fontsize=8, color=ps.INK_SECONDARY)
    ax.set_xlim(1949, 2026)
    ax.set_ylim(0, 55)
    ax.set_ylabel("Points for winning a race")
    ax.grid(axis="x", visible=False)
    ps.titles(ax, "The same achievement is worth 8 to 50 points depending on the era",
              "Most common points total for a race win, per season; raw points are not comparable over time.")
    ps.source_note(fig, SOURCE)
    ps.save(fig, path)
    return df


def fig_b4_laps_outliers(raw: pd.DataFrame, path) -> pd.DataFrame:
    q1, q3 = raw["laps"].quantile([0.25, 0.75])
    fence = q3 + 1.5 * (q3 - q1)
    indy = raw["raceName"] == "indianapolis 500"
    bins = np.arange(0, 210, 5)
    fig, ax = plt.subplots(figsize=(7.4, 3.5))
    ax.hist(raw.loc[~indy, "laps"], bins=bins, color=ps.CATEGORICAL[0], label="Other Grands Prix",
            edgecolor=ps.SURFACE, linewidth=0.8)
    ax.hist(raw.loc[indy, "laps"], bins=bins, color=ps.CATEGORICAL[1], label="Indianapolis 500 (1950-1960)",
            edgecolor=ps.SURFACE, linewidth=0.8)
    ax.axvline(fence, color=ps.INK_SECONDARY, lw=1)
    ax.text(fence + 2, ax.get_ylim()[1] * 0.85, f"IQR upper fence\n{fence:g} laps", fontsize=8, color=ps.INK_SECONDARY)
    ax.yaxis.set_major_formatter(thousands)
    ax.set_xlabel("Laps completed")
    ax.set_ylabel("Results")
    ax.grid(axis="x", visible=False)
    n_out = int((raw["laps"] > fence).sum())
    ps.titles(ax, f"All {n_out} statistical outliers are valid Indianapolis 500 results",
              "Outlier rule flags them; domain knowledge keeps them (flagged, not deleted).")
    ax.legend(loc="upper left")
    ps.source_note(fig, SOURCE)
    ps.save(fig, path)
    return pd.DataFrame({"iqr_upper_fence": [fence], "outliers": [n_out], "indy500_rows": [int(indy.sum())]})


RESOLUTION_BUCKETS = ["Fixed", "Mitigated or flagged (kept)", "Kept as is (documented)", "Not an error (verified)"]


def bucket(resolution: str) -> str:
    if resolution.startswith("Not an error"):
        return RESOLUTION_BUCKETS[3]
    if resolution.startswith("Kept"):
        return RESOLUTION_BUCKETS[2]
    if resolution.startswith(("Flagged", "Mitigated")):
        return RESOLUTION_BUCKETS[1]
    return RESOLUTION_BUCKETS[0]


def fig_c1_resolution(resolution: pd.DataFrame, path) -> pd.DataFrame:
    res = resolution.copy()
    res["bucket"] = res["resolution"].map(bucket)
    table = res.pivot_table(index="dimension", columns="bucket", values="issue_id", aggfunc="count", fill_value=0)
    table = table.reindex(columns=RESOLUTION_BUCKETS, fill_value=0)
    table = table.loc[table.sum(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    left = np.zeros(len(table))
    y = np.arange(len(table))
    for i, col in enumerate(RESOLUTION_BUCKETS):
        vals = table[col].to_numpy()
        ax.barh(y, vals, left=left, height=0.62, color=ps.CATEGORICAL[i], label=col,
                edgecolor=ps.SURFACE, linewidth=1.5)
        for yi, (l, v) in enumerate(zip(left, vals)):
            if v:
                ax.text(l + v / 2, yi, str(int(v)), ha="center", va="center", fontsize=8,
                        color=ps.INK if ps.CATEGORICAL[i] == "#eda100" else "#ffffff")
        left += vals
    ax.set_yticks(y, table.index)
    ax.set_xlabel("Quality issues")
    ax.grid(axis="y", visible=False)
    ps.titles(ax, f"All {len(res)} issues are closed: {int(table[RESOLUTION_BUCKETS[0]].sum())} fixed, "
                  f"the rest flagged or documented",
              "Resolution of every Component B issue by the Component C pipeline, per quality dimension.")
    ax.legend(loc="lower right", ncol=1)
    ps.source_note(fig, SOURCE)
    ps.save(fig, path)
    return table.reset_index()


def fig_c2_status(clean: pd.DataFrame, path) -> pd.DataFrame:
    s = clean["status_raw"]
    df = (pd.DataFrame({"status": s, "group": clean["status_group"]})
          .groupby("group").agg(rows=("status", "size"), raw_values=("status", "nunique"))
          .sort_values("rows").reset_index())
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    y = np.arange(len(df))
    ax.barh(y, df["rows"], height=0.62, color=ps.CATEGORICAL[0])
    for yi, (_, r) in zip(y, df.iterrows()):
        label = "raw label" if r["raw_values"] == 1 else "raw labels"
        ax.text(r["rows"] + 120, yi, f"{r['rows']:,} rows  ·  {r['raw_values']} {label}", va="center",
                fontsize=8, color=ps.INK_SECONDARY)
    ax.set_yticks(y, df["group"])
    ax.set_xlim(0, df["rows"].max() * 1.45)
    ax.xaxis.set_major_formatter(thousands)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Results")
    ps.titles(ax, f"{s.nunique()} free-text status values reduced to {len(df)} analysable groups",
              "Exhaustive mapping (unmapped values stop the pipeline); the raw status is kept in status_raw.")
    ps.source_note(fig, SOURCE)
    ps.save(fig, path)
    return df


def run() -> None:
    config.ensure_dirs()
    raw = pd.read_csv(config.RAW_RESULTS_CSV)
    out = config.QUALITY_FIG_DIR
    tables = {
        "fig_b1_hidden_missingness": fig_b1_hidden_missingness(raw, out / "fig_b1_hidden_missingness.png"),
        "fig_b2_duplicates": fig_b2_duplicates(raw, out / "fig_b2_duplicates_vs_shared_drives.png"),
        "fig_b3_points_eras": fig_b3_points_eras(raw, out / "fig_b3_points_scale_by_era.png"),
        "fig_b4_laps_outliers": fig_b4_laps_outliers(raw, out / "fig_b4_laps_outliers.png"),
    }
    resolution = pd.read_csv(config.CLEANING_DIR / "issue_resolution.csv")
    tables["fig_c1_resolution"] = fig_c1_resolution(resolution, config.CLEANING_DIR / "fig_c1_issue_resolution.png")
    clean = pd.read_csv(config.CLEAN_RESULTS_CSV)
    tables["fig_c2_status"] = fig_c2_status(clean, config.CLEANING_DIR / "fig_c2_status_standardisation.png")
    for name, df in tables.items():
        target = (config.CLEANING_DIR if name.startswith("fig_c") else out) / f"{name}_data.csv"
        df.to_csv(target, index=False)
    print("[charts] written:", list(tables))


if __name__ == "__main__":
    run()
