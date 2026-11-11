"""Single source of truth for the cleaned dataset's schema (data dictionary).

Component C validates its output against these definitions and Component A builds the
metadata record (schema.org variableMeasured, data dictionary appendix) from them, so the
documented schema and the delivered file cannot drift apart.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str
    description: str
    source: str
    nullable: bool = False
    unit_or_format: str = ""
    allowed_values: tuple[str, ...] = field(default_factory=tuple)


STATUS_GROUPS = (
    "Finished",
    "Finished (lapped)",
    "Accident or collision",
    "Mechanical or technical failure",
    "Driver health or safety",
    "Did not start or withdrew",
    "Disqualified or excluded",
    "Retired (unspecified) or not classified",
)

FINISH_CATEGORIES = ("Classified", "Retired", "Withdrawn", "Disqualified")

RESULTS_COLUMNS: tuple[Column, ...] = (
    Column("result_id", "string", "Deterministic surrogate key: season_round_driverId_carNumber.",
           "derived", unit_or_format="YYYY_RR_<driver_id>_<car_number|NA>"),
    Column("race_id", "string", "Identifier of the Grand Prix: season and round.", "derived",
           unit_or_format="YYYY_RR"),
    Column("season", "Int64", "Championship season (year).", "season", unit_or_format="year"),
    Column("round", "Int64", "Round number of the race within the season.", "round"),
    Column("race_name", "string", "Official Grand Prix name in title case.", "raceName"),
    Column("race_date", "date", "Race day.", "date", unit_or_format="ISO 8601 (YYYY-MM-DD)"),
    Column("circuit_id", "string", "Circuit identifier (Ergast convention).", "races.circuitId"),
    Column("circuit_name", "string", "Circuit name in title case.", "circuits.circuitName"),
    Column("circuit_locality", "string", "City or locality of the circuit.", "circuits.locality"),
    Column("circuit_country", "string",
           "Country of the circuit; abbreviations expanded (UK, USA, UAE, Korea), other names kept as in source.",
           "circuits.country"),
    Column("circuit_country_iso3", "string", "Country of the circuit.", "circuits.country",
           unit_or_format="ISO 3166-1 alpha-3"),
    Column("driver_id", "string", "Driver identifier, lowercase snake case.", "driverId"),
    Column("driver_name", "string", "Driver full name in title case.", "drivers.name"),
    Column("driver_nationality_iso3", "string",
           "Driver nationality as a country code (ISO 3166-3 code for former states).",
           "drivers.nationality", nullable=True, unit_or_format="ISO 3166-1 alpha-3 / ISO 3166-3"),
    Column("constructor_id", "string", "Constructor (team) identifier.", "constructorId"),
    Column("constructor_name", "string", "Constructor name.", "constructors.name"),
    Column("constructor_nationality_iso3", "string", "Constructor nationality as a country code.",
           "constructors.nationality", unit_or_format="ISO 3166-1 alpha-3 / ISO 3166-3"),
    Column("car_number", "Int64", "Race number of the car. Missing for some withdrawn entries.",
           "number", nullable=True),
    Column("grid_position", "Int64",
           "Starting grid slot. Missing when the source used the sentinel 0 (pit-lane start or no grid slot).",
           "grid", nullable=True),
    Column("grid_position_missing", "boolean", "True when the source grid value was the sentinel 0.",
           "derived from grid"),
    Column("laps_completed", "Int64", "Laps completed in the race.", "laps", unit_or_format="laps"),
    Column("points", "float", "Championship points awarded, as published for that season's rules.",
           "points", unit_or_format="points"),
    Column("points_normalised", "float",
           "Points divided by the highest points total awarded in the same race (0-1), comparable across scoring eras.",
           "derived from points", unit_or_format="ratio 0-1"),
    Column("position_order", "Int64",
           "Finishing order including retirements (source field 'position'). Not a classification.",
           "position"),
    Column("classified_position", "Int64",
           "Official classified finishing position. Missing when the driver was not classified.",
           "positionText", nullable=True),
    Column("position_text", "string", "Source classification code: a number, R, W or D.", "positionText"),
    Column("finish_category", "string", "Classification outcome derived from position_text.",
           "derived from positionText", allowed_values=FINISH_CATEGORIES),
    Column("status_raw", "string", "Original free-text status (136 values).", "status"),
    Column("status_group", "string", "Standardised status category.", "derived from status",
           allowed_values=STATUS_GROUPS),
    Column("is_shared_drive", "boolean",
           "True when the car or the driver appears more than once in the same race (historic shared drives).",
           "derived"),
    Column("is_indy500", "boolean",
           "True for Indianapolis 500 rounds (1950-1960), which counted for the title but used different rules.",
           "derived from raceName"),
    Column("laps_outlier_iqr", "boolean", "True when laps_completed lies outside the 1.5 x IQR fences.",
           "derived from laps"),
    Column("status_position_conflict", "boolean",
           "True when position_text says retired (R) but the status describes a lapped finish.", "derived"),
    Column("source_file", "string", "Lineage: source file inside racing_f1_data.zip.", "extraction"),
    Column("source_line", "Int64", "Lineage: line number inside the source file.", "extraction"),
)

RESULTS_PRIMARY_KEY = ("result_id",)
RESULTS_NATURAL_KEY = ("season", "round", "driver_id", "car_number")


def column_names(columns: tuple[Column, ...] = RESULTS_COLUMNS) -> list[str]:
    return [c.name for c in columns]
