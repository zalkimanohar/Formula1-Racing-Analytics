"""Tests for the ask-the-data assistant (no language model needed).  Run:  python -m pytest -q"""
import pandas as pd
import pytest

from src import config
from src.assistant import podium_model as pm
from src.assistant import reference
from src.assistant.engine import Engine
from src.assistant.facts import Evidence, store


def test_official_champions_reconcile_with_points():
    ch = reference.champions().set_index("season")
    assert list(ch.index) == list(range(config.FIRST_SEASON, config.LAST_COMPLETE_SEASON + 1))
    assert ch.loc[1988, "champion_driver_id"] == "senna" and ch.loc[1964, "champion_driver_id"] == "surtees"
    # dropped-scores seasons are the only disagreements with the points leader, and they are explained
    assert sorted(ch.index[~ch["agrees_with_points_leader"]]) == [1964, 1988]
    assert ch.loc[[1964, 1988], "note"].str.contains("dropped-scores").all()


@pytest.mark.parametrize("question, expected", [
    ("Paddy Driver", [("driver", "driver")]),
    ("may the best driver win", []),                                   # everyday words are not drivers
    ("How did Red Bull do in 2023?", [("team", "red_bull"), ("year", "2023")]),
    ("Tell me about Monaco", [("circuit", "monaco")]),
    ("¿Cuántos podios tiene Fernando Alonso con Ferrari?", [("driver", "alonso"), ("team", "ferrari")]),
    ("Who won the 2008 British Grand Prix?", [("race", "British Grand Prix"), ("year", "2008")]),
])
def test_entity_resolution(question, expected):
    assert [(e.type, e.id) for e in store().resolve(question)] == expected


def test_ambiguous_family_name_keeps_alternatives():
    e = store().resolve("Schumacher")[0]
    assert e.id == "michael_schumacher" and "Ralf Schumacher" in e.alternatives


def test_driver_facts_match_direct_count():
    r = pd.read_csv(config.CLEAN_RESULTS_CSV)
    wins = int(((r["driver_id"] == "hamilton") & (r["classified_position"] == 1)).sum())
    ev = store().driver_career("hamilton")
    assert f"Wins: {wins} " in " ".join(ev.lines)
    assert ev.source["rows"] == int((r["driver_id"] == "hamilton").sum())
    assert all(":" in x for x in ev.source["lineage"])          # raw file:line of first and last row


def test_team_wins_count_shared_cars_once():
    r = store().results
    ferrari = r[r["family"] == "ferrari"]
    assert store()._summary(ferrari, team=True)["wins"] == ferrari.loc[ferrari["win"], "race_id"].nunique()
    assert int(ferrari["win"].sum()) > ferrari.loc[ferrari["win"], "race_id"].nunique()   # a 1950s shared win exists


def test_podium_model_uses_only_pre_race_information():
    leaked = {"points", "points_normalised", "laps_completed", "classified_position", "position_order",
              "finish_category", "status_group", "podium", "classified"}
    assert not leaked & set(pm.FEATURES)
    f = pm.build_features(pd.read_csv(config.CLEAN_RESULTS_CSV))
    first = f.sort_values(["season", "round"]).groupby("driver_id").head(1)
    assert (first["driver_starts_before"] == 0).all() and (first["driver_podium_rate"] == 0).all()


def test_podium_model_card_is_computed_not_set():
    card = pm.podium_model().card
    board = pd.read_csv(pm.LEADERBOARD_CSV)
    chosen = board[(board["model"] == card["selected_model"]) & board["split"].str.startswith("test")].iloc[0]
    assert card["test_metrics"]["log_loss"] == pytest.approx(chosen["log_loss"])
    valid = board[board["split"].str.startswith("validation") & (board["model"] != "grid_baseline")]
    assert valid.sort_values("log_loss").iloc[0]["model"] == card["selected_model"]   # chosen on validation only


def test_figure_check_flags_untraceable_numbers():
    ev = [Evidence("fact", "Career", ["Wins: 105; points: 4955.5"], {}, "S1")]
    c = Engine.check(Engine.__new__(Engine), "He won 105 races [S1] and scored 4,955.5 points, plus 12 poles.", ev, "")
    assert c["numbers"] == 3 and c["verified"] == 2 and c["unverified"] == ["12"] and c["cited"] == ["S1"]


def test_out_of_range_year_is_stated_not_answered():
    eng = Engine.__new__(Engine)
    eng.store = store()
    p = Engine.plan(eng, "Who won the 2030 World Championship?")
    ev = Engine.gather(eng, p)
    assert p.outside == [2030] and len(ev) == 1 and "outside this range" in " ".join(ev[0].lines)
