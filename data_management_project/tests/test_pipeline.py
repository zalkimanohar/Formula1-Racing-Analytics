"""Tests for the decisions the cleaning pipeline depends on.  Run:  python -m pytest -q"""
import pandas as pd
import pytest

from src import cleaning, config, schema
from src import vocabularies as voc


@pytest.mark.parametrize("raw, expected", [
    ("circuit of the americas", "Circuit of the Americas"),
    ("70th anniversary grand prix", "70th Anniversary Grand Prix"),
    ("patricio o'ward", "Patricio O'Ward"),
    ("bruce mclaren", "Bruce McLaren"),
    ("pedro de la rosa", "Pedro de la Rosa"),
    ("jean-pierre beltoise", "Jean-Pierre Beltoise"),
    ("são paulo grand prix", "São Paulo Grand Prix"),
    ("avus", "AVUS"),
])
def test_smart_title(raw, expected):
    assert voc.smart_title(raw) == expected


def test_every_raw_status_is_mapped():
    raw = pd.read_csv(config.RAW_RESULTS_CSV)
    unmapped = {s for s in raw["status"].unique() if voc.status_group(s) is None}
    assert not unmapped
    assert set(map(voc.status_group, raw["status"].unique())) <= set(schema.STATUS_GROUPS)


def _frame(rows):
    cols = ["source_file", "source_line"] + cleaning.BUSINESS_COLUMNS
    return pd.DataFrame(rows, columns=cols)


def test_key_repair_must_precede_deduplication():
    """A copy whose keys were blanked is only recognised as a duplicate after key repair."""
    base = ["1960-09-04", "italian grand prix", 9, 1960, "u", "ferrari", "phil_hill", 1, 50, 20, 8.0, 1, "1", "Finished"]
    damaged = base.copy()
    damaged[2], damaged[3] = None, None
    df = _frame([["results_1960.json", 1, *base], ["results_1960.json", 2, *damaged]])
    races = pd.DataFrame({"season": [1960], "round": [9], "url": ["u"], "raceName": ["italian grand prix"],
                          "date": ["1960-09-04"], "circuitId": ["monza"]})
    typed, _ = cleaning.c01_enforce_types(df)
    wrong_order, _ = cleaning.c03_remove_duplicates(typed)
    assert len(wrong_order) == 2
    repaired, _ = cleaning.c02_repair_keys(typed, races)
    right_order, _ = cleaning.c03_remove_duplicates(repaired)
    assert len(right_order) == 1


def test_shared_drives_are_not_removed():
    a = ["1953-05-30", "indianapolis 500", 2, 1953, "u", "kurtis_kraft", "linden", 10, 177, 92, 0.0, 16, "16", "Axle"]
    b = ["1953-05-30", "indianapolis 500", 2, 1953, "u", "stevens", "linden", 5, 3, 32, 0.0, 33, "R", "Accident"]
    typed, _ = cleaning.c01_enforce_types(_frame([["results_1953.json", 1, *a], ["results_1953.json", 2, *b]]))
    out, _ = cleaning.c03_remove_duplicates(typed)
    assert len(out) == 2


def test_grid_sentinel_becomes_missing_with_flag():
    row = ["2024-03-02", "bahrain grand prix", 1, 2024, "u", "haas", "x", 0, 57, 20, 0.0, 15, "15", "Finished"]
    typed, _ = cleaning.c01_enforce_types(_frame([["results_2024.json", 1, *row]]))
    out, _ = cleaning.c05_grid_sentinel(typed)
    assert out["grid"].isna().all() and out["grid_position_missing"].all()


def test_clean_output_matches_schema_and_keys():
    df = pd.read_csv(config.CLEAN_RESULTS_CSV)
    assert list(df.columns) == schema.column_names()
    assert df["result_id"].is_unique
    assert not df.duplicated(list(schema.RESULTS_NATURAL_KEY)).any()
    assert df["classified_position"].isna().equals(df["finish_category"] != "Classified")


def test_validation_report_all_passed():
    report = pd.read_csv(config.CLEANING_DIR / "validation_report.csv")
    assert (report["result"] == "passed").all()
