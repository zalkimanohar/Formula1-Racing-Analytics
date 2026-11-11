"""Podium-probability model with honest, time-based validation.

Question: before the start, how likely is this driver to finish on the podium?
Only information available before the race is used (grid slot, recent form of driver and team, experience),
all computed from earlier races; nothing from the race itself (points, laps, finishing status) is a feature.

Split by time, never at random: train 1950-2013, choose the model on 2014-2019 (validation), then refit on
1950-2019 and report the untouched 2020-2025 test seasons once. Four candidates are compared with a
grid-only baseline; every score in the model card is computed, none is set by hand.
"""
from __future__ import annotations

import gzip
import json
import pickle
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src import config
from src.assistant.facts import Evidence, family_of

OUT_DIR = config.OUTPUT_DIR / "assistant"
MODEL_PKL = OUT_DIR / "podium_model.pkl.gz"
MODEL_CARD = OUT_DIR / "podium_model_card.json"
LEADERBOARD_CSV = OUT_DIR / "podium_model_leaderboard.csv"
TRAIN_END, VALID_END = 2013, 2019
FORM_WINDOW = 10
FEATURES = ["grid", "grid_rel", "grid_missing", "field_size", "driver_starts_before", "driver_podium_rate",
            "driver_finish_rate", "driver_grid_rel_avg", "team_podiums_per_race", "team_points_share_season",
            "team_points_share_prev_season"]
FEATURE_TEXT = {
    "grid": "starting grid slot (pit-lane starts placed at the back)",
    "grid_rel": "grid slot divided by field size",
    "grid_missing": "pit-lane start or grid not recorded",
    "field_size": "number of cars entered",
    "driver_starts_before": "driver's previous Grand Prix starts",
    "driver_podium_rate": f"driver's podium rate over his previous {FORM_WINDOW} starts",
    "driver_finish_rate": f"driver's classified-finish rate over his previous {FORM_WINDOW} starts",
    "driver_grid_rel_avg": f"driver's average relative grid slot over his previous {FORM_WINDOW} starts",
    "team_podiums_per_race": f"team's podiums per race over its previous {FORM_WINDOW} races",
    "team_points_share_season": "team's share of all points scored so far this season (before this race)",
    "team_points_share_prev_season": "team's share of all points in the previous season",
}


def _rolling_prev(s: pd.Series, keys: pd.Series, window: int = FORM_WINDOW) -> pd.Series:
    """Mean of the previous `window` values within each key (the current row is never included)."""
    return s.groupby(keys).transform(lambda x: x.shift(1).rolling(window, min_periods=1).mean())


def build_features(results: pd.DataFrame) -> pd.DataFrame:
    r = results[~results["is_indy500"] & results["finish_category"].ne("Withdrawn")].copy()
    r["family"] = r["constructor_id"].map(family_of)
    r = r.sort_values(["season", "round", "position_order"]).reset_index(drop=True)
    r["race_seq"] = r.groupby(["season", "round"]).ngroup()
    r["field_size"] = r.groupby("race_id")["driver_id"].transform("size")
    r["grid_missing"] = r["grid_position"].isna().astype(int)
    r["grid"] = r["grid_position"].fillna(r["field_size"]).clip(upper=r["field_size"])
    r["grid_rel"] = r["grid"] / r["field_size"]
    r["podium"] = r["classified_position"].le(3).fillna(False).astype(int)
    r["classified"] = r["classified_position"].notna().astype(int)

    r["driver_starts_before"] = r.groupby("driver_id").cumcount()
    r["driver_podium_rate"] = _rolling_prev(r["podium"], r["driver_id"]).fillna(0.0)
    r["driver_finish_rate"] = _rolling_prev(r["classified"], r["driver_id"]).fillna(0.5)
    r["driver_grid_rel_avg"] = _rolling_prev(r["grid_rel"], r["driver_id"]).fillna(0.75)

    team_race = (r.groupby(["family", "race_seq"]).agg(pod=("podium", "sum"), pts=("points", "sum"),
                                                       season=("season", "first")).reset_index()
                 .sort_values(["family", "race_seq"]))
    team_race["team_podiums_per_race"] = _rolling_prev(team_race["pod"], team_race["family"]).fillna(0.0)
    season_pts = r.groupby(["season", "race_seq"])["points"].sum().rename("all_pts").reset_index()
    season_pts["all_before"] = season_pts.groupby("season")["all_pts"].cumsum() - season_pts["all_pts"]
    team_race["team_before"] = team_race.groupby(["family", "season"])["pts"].cumsum() - team_race["pts"]
    team_race = team_race.merge(season_pts[["race_seq", "all_before"]], on="race_seq")
    team_race["team_points_share_season"] = np.where(team_race["all_before"] > 0,
                                                     team_race["team_before"] / team_race["all_before"], np.nan)
    final = r.groupby(["season", "family"])["points"].sum()
    final = (final / final.groupby(level=0).transform("sum")).rename("team_points_share_prev_season").reset_index()
    final["season"] += 1
    r = r.merge(team_race[["family", "race_seq", "team_podiums_per_race", "team_points_share_season"]],
                on=["family", "race_seq"], how="left")
    r = r.merge(final, on=["season", "family"], how="left")
    r["team_points_share_prev_season"] = r["team_points_share_prev_season"].fillna(0.0)
    r["team_points_share_season"] = r["team_points_share_season"].fillna(r["team_points_share_prev_season"])
    return r


def candidates() -> dict:
    return {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0)),
        "random_forest": RandomForestClassifier(n_estimators=400, min_samples_leaf=25, n_jobs=-1,
                                                random_state=config.RANDOM_SEED),
        "gradient_boosting": HistGradientBoostingClassifier(learning_rate=0.1, max_iter=150, max_leaf_nodes=15,
                                                            min_samples_leaf=50, l2_regularization=1.0,
                                                            random_state=config.RANDOM_SEED),
    }


class GridBaseline:
    """P(podium) = podium rate of each grid slot in the training seasons (what a fan would guess)."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "GridBaseline":
        slot = X["grid"].clip(upper=26).astype(int)
        self.rate = y.groupby(slot).mean()
        self.default = float(y.mean())
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p = X["grid"].clip(upper=26).astype(int).map(self.rate).fillna(self.default).to_numpy()
        return np.column_stack([1 - p, p])


def evaluate(p: np.ndarray, frame: pd.DataFrame) -> dict:
    y = frame["podium"].to_numpy()
    eps = np.clip(p, 1e-6, 1 - 1e-6)
    hit = (frame.assign(p=p).sort_values(["race_id", "p"], ascending=[True, False])
           .groupby("race_id").head(3).groupby("race_id")["podium"].sum() / 3)
    return {"log_loss": round(float(log_loss(y, eps)), 4), "brier": round(float(brier_score_loss(y, p)), 4),
            "roc_auc": round(float(roc_auc_score(y, p)), 4), "podium_places_called": round(float(hit.mean()), 4),
            "rows": int(len(frame)), "races": int(frame["race_id"].nunique())}


def train() -> dict:
    results = pd.read_csv(config.CLEAN_RESULTS_CSV)
    data = build_features(results)
    train_f = data[data["season"] <= TRAIN_END]
    valid_f = data[(data["season"] > TRAIN_END) & (data["season"] <= VALID_END)]
    test_f = data[data["season"] > VALID_END]
    rows = []
    fitted = {}
    models = {"grid_baseline": GridBaseline(), **candidates()}
    for name, model in models.items():
        model.fit(train_f[FEATURES], train_f["podium"])
        rows.append({"model": name, "split": "validation 2014-2019",
                     **evaluate(model.predict_proba(valid_f[FEATURES])[:, 1], valid_f)})
        fitted[name] = model
    board = pd.DataFrame(rows)
    learned = board[board["model"] != "grid_baseline"]
    winner = learned.sort_values("log_loss").iloc[0]["model"]

    trainval = data[data["season"] <= VALID_END]
    test_rows = []
    final_models = {}
    for name in models:
        model = GridBaseline() if name == "grid_baseline" else candidates()[name]
        model.fit(trainval[FEATURES], trainval["podium"])
        final_models[name] = model
        test_rows.append({"model": name, "split": "test 2020-2025",
                          **evaluate(model.predict_proba(test_f[FEATURES])[:, 1], test_f)})
    board = pd.concat([board, pd.DataFrame(test_rows)], ignore_index=True)
    board["selected"] = board["model"] == winner

    grid_rule = (test_f["grid"] <= 3).astype(int)
    grid_rule_hit = float((test_f.assign(g=grid_rule)[lambda d: d["g"] == 1].groupby("race_id")["podium"].sum() / 3)
                          .mean())
    final = final_models[winner]
    importance = _importance(final, test_f)
    card = {
        "task": "Probability that a driver finishes on the podium, estimated before the start",
        "unit": "one row per driver per Grand Prix start (Indy 500 and non-starters excluded)",
        "features": {f: FEATURE_TEXT[f] for f in FEATURES},
        "leakage_guard": "every form feature uses earlier races only (shifted rolling windows); "
                         "points, laps and finishing status of the race itself are never inputs",
        "split": {"train": f"1950-{TRAIN_END}", "validation": f"{TRAIN_END + 1}-{VALID_END} (model choice)",
                  "test": f"{VALID_END + 1}-{config.LAST_COMPLETE_SEASON} (reported once, refit on 1950-{VALID_END})"},
        "selection_rule": "lowest validation log loss among the learned models",
        "selected_model": winner,
        "test_metrics": board[(board["model"] == winner) & (board["split"].str.startswith("test"))]
        .drop(columns=["model", "split", "selected"]).iloc[0].to_dict(),
        "baseline_test_metrics": board[(board["model"] == "grid_baseline") & (board["split"].str.startswith("test"))]
        .drop(columns=["model", "split", "selected"]).iloc[0].to_dict(),
        "rule_front_three_podium_places_called_test": round(grid_rule_hit, 4),
        "feature_importance_test": importance,
        "metrics_explained": {
            "log_loss": "penalty for confident wrong probabilities (lower is better)",
            "brier": "mean squared error of the probabilities (lower is better)",
            "roc_auc": "chance a random podium finisher gets a higher probability than a random non-podium one",
            "podium_places_called": "share of the three podium places taken by the model's top three picks per race"},
        "trained_rows": int(len(trainval)), "test_rows": int(len(test_f)),
        "random_seed": config.RANDOM_SEED,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    board.to_csv(LEADERBOARD_CSV, index=False)
    MODEL_CARD.write_text(json.dumps(card, indent=2), encoding="utf-8")
    with gzip.open(MODEL_PKL, "wb", compresslevel=6) as fh:
        pickle.dump({"model": final, "name": winner, "features": FEATURES}, fh)
    return card


def _importance(model, frame: pd.DataFrame, repeats: int = 3) -> dict:
    """Permutation importance on the test seasons: rise in log loss when one feature is shuffled."""
    rng = np.random.default_rng(config.RANDOM_SEED)
    base = log_loss(frame["podium"], np.clip(model.predict_proba(frame[FEATURES])[:, 1], 1e-6, 1 - 1e-6))
    out = {}
    for f in FEATURES:
        losses = []
        for _ in range(repeats):
            shuffled = frame[FEATURES].copy()
            shuffled[f] = rng.permutation(shuffled[f].to_numpy())
            losses.append(log_loss(frame["podium"], np.clip(model.predict_proba(shuffled)[:, 1], 1e-6, 1 - 1e-6)))
        out[f] = round(float(np.mean(losses) - base), 4)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


@dataclass
class PodiumModel:
    model: object
    name: str
    card: dict
    latest: pd.DataFrame       # one row per driver: form features after the last race in the data

    def probability(self, driver_id: str, grid: int, field_size: int = 20) -> float:
        row = self.latest.loc[driver_id, FEATURES].copy()
        row["grid"], row["field_size"], row["grid_missing"] = grid, field_size, 0
        row["grid_rel"] = grid / field_size
        return float(self.model.predict_proba(pd.DataFrame([row])[FEATURES])[0, 1])

    def explain(self, driver_id: str, name: str, grid: int | None, team: str) -> Evidence:
        last = self.latest.loc[driver_id]
        lines = []
        grids = [grid] if grid else [1, 3, 5, 10]
        for g in grids:
            lines.append(f"Estimated podium probability for {name} ({team}) starting P{g}: "
                         f"{100 * self.probability(driver_id, g):.0f}%")
        lines += [f"Form used (after the last race in the data, {last['last_race']}): podium rate "
                  f"{100 * last['driver_podium_rate']:.0f}% and classified finishes {100 * last['driver_finish_rate']:.0f}% "
                  f"in the previous {FORM_WINDOW} starts; team podiums per race {last['team_podiums_per_race']:.2f}; "
                  f"{int(last['driver_starts_before'])} previous starts",
                  f"Model: {self.name.replace('_', ' ')}, chosen on 2014-2019 by log loss; tested once on 2020-2025: "
                  f"ROC AUC {self.card['test_metrics']['roc_auc']:.3f}, log loss {self.card['test_metrics']['log_loss']:.3f} "
                  f"(grid-only baseline {self.card['baseline_test_metrics']['log_loss']:.3f}); its top three picks took "
                  f"{100 * self.card['test_metrics']['podium_places_called']:.0f}% of podium places vs "
                  f"{100 * self.card['rule_front_three_podium_places_called_test']:.0f}% for 'the front three finish on the podium'",
                  "This is a statistical estimate from past races, not a forecast of a specific future event"]
        return Evidence("model", f"Podium model: {name}", lines,
                        {"dataset": "outputs/assistant/podium_model_card.json", "sha256": "",
                         "filter": f"driver_id == '{driver_id}'", "rows": self.card["trained_rows"],
                         "lineage": [f"features from data/cleaned/f1_race_results_clean.csv up to {last['last_race']}"]})


@lru_cache(maxsize=1)
def podium_model() -> PodiumModel:
    if not MODEL_PKL.exists():
        train()
    with gzip.open(MODEL_PKL, "rb") as fh:
        saved = pickle.load(fh)
    card = json.loads(MODEL_CARD.read_text(encoding="utf-8"))
    data = build_features(pd.read_csv(config.CLEAN_RESULTS_CSV))
    # form after the last race: recompute the rolling windows including that race
    data = data.sort_values(["season", "round"])
    latest = data.groupby("driver_id").tail(FORM_WINDOW)
    agg = latest.groupby("driver_id").agg(driver_podium_rate=("podium", "mean"), driver_finish_rate=("classified", "mean"),
                                          driver_grid_rel_avg=("grid_rel", "mean"),
                                          driver_starts_before=("driver_id", "size"))
    agg["driver_starts_before"] = data.groupby("driver_id").size()
    last_row = data.groupby("driver_id").tail(1).set_index("driver_id")
    agg["family"] = last_row["family"]
    agg["last_race"] = last_row["race_name"] + " " + last_row["season"].astype(str)
    team_last = data[data["season"] == data["season"].max()]
    share = team_last.groupby("family")["points"].sum()
    share = share / share.sum()
    races = data.groupby(["family", "race_seq"])["podium"].sum().groupby(level=0).apply(lambda s: s.tail(FORM_WINDOW).mean())
    agg["team_podiums_per_race"] = agg["family"].map(races).fillna(0.0)
    agg["team_points_share_season"] = agg["family"].map(share).fillna(0.0)
    agg["team_points_share_prev_season"] = agg["team_points_share_season"]
    for f in ("grid", "grid_rel", "grid_missing", "field_size"):
        agg[f] = 0
    return PodiumModel(saved["model"], saved["name"], card, agg)


if __name__ == "__main__":
    c = train()
    print(json.dumps({k: c[k] for k in ("selected_model", "test_metrics", "baseline_test_metrics",
                                        "rule_front_three_podium_places_called_test", "feature_importance_test")},
                     indent=2))
    print(pd.read_csv(LEADERBOARD_CSV).to_string(index=False))
