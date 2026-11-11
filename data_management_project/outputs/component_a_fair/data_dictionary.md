# Data dictionary

Generated from the delivered files on 2026-11-11.

## f1_race_results_clean.csv

| Column | Type | Description | Unit / format | Allowed values | Non-null | Distinct |
|---|---|---|---|---|---|---|
| `result_id` | string | Deterministic surrogate key: season_round_driverId_carNumber. | YYYY_RR_<driver_id>_<car_number|NA> |  | 25873 | 25873 |
| `race_id` | string | Identifier of the Grand Prix: season and round. | YYYY_RR |  | 25873 | 1149 |
| `season` | Int64 | Championship season (year). | year |  | 25873 | 76 |
| `round` | Int64 | Round number of the race within the season. |  |  | 25873 | 24 |
| `race_name` | string | Official Grand Prix name in title case. |  |  | 25873 | 54 |
| `race_date` | date | Race day. | ISO 8601 (YYYY-MM-DD) |  | 25873 | 1149 |
| `circuit_id` | string | Circuit identifier (Ergast convention). |  |  | 25873 | 77 |
| `circuit_name` | string | Circuit name in title case. |  |  | 25873 | 77 |
| `circuit_locality` | string | City or locality of the circuit. |  |  | 25873 | 74 |
| `circuit_country` | string | Country of the circuit; abbreviations expanded (UK, USA, UAE, Korea), other names kept as in source. |  |  | 25873 | 34 |
| `circuit_country_iso3` | string | Country of the circuit. | ISO 3166-1 alpha-3 |  | 25873 | 34 |
| `driver_id` | string | Driver identifier, lowercase snake case. |  |  | 25873 | 817 |
| `driver_name` | string | Driver full name in title case. |  |  | 25873 | 817 |
| `driver_nationality_iso3` | string | Driver nationality as a country code (ISO 3166-3 code for former states). | ISO 3166-1 alpha-3 / ISO 3166-3 |  | 25873 | 40 |
| `constructor_id` | string | Constructor (team) identifier. |  |  | 25873 | 203 |
| `constructor_name` | string | Constructor name. |  |  | 25873 | 203 |
| `constructor_nationality_iso3` | string | Constructor nationality as a country code. | ISO 3166-1 alpha-3 / ISO 3166-3 |  | 25873 | 23 |
| `car_number` | Int64 | Race number of the car. Missing for some withdrawn entries. |  |  | 25867 | 128 |
| `grid_position` | Int64 | Starting grid slot. Missing when the source used the sentinel 0 (pit-lane start or no grid slot). |  |  | 25606 | 34 |
| `grid_position_missing` | boolean | True when the source grid value was the sentinel 0. |  |  | 25873 | 2 |
| `laps_completed` | Int64 | Laps completed in the race. | laps |  | 25873 | 172 |
| `points` | float | Championship points awarded, as published for that season's rules. | points |  | 25873 | 40 |
| `points_normalised` | float | Points divided by the highest points total awarded in the same race (0-1), comparable across scoring eras. | ratio 0-1 |  | 25873 | 60 |
| `position_order` | Int64 | Finishing order including retirements (source field 'position'). Not a classification. |  |  | 25873 | 39 |
| `classified_position` | Int64 | Official classified finishing position. Missing when the driver was not classified. |  |  | 16235 | 33 |
| `position_text` | string | Source classification code: a number, R, W or D. |  |  | 25873 | 36 |
| `finish_category` | string | Classification outcome derived from position_text. |  | Classified; Retired; Withdrawn; Disqualified | 25873 | 4 |
| `status_raw` | string | Original free-text status (136 values). |  |  | 25873 | 136 |
| `status_group` | string | Standardised status category. |  | Finished; Finished (lapped); Accident or collision; Mechanical or technical failure; Driver health or safety; Did not start or withdrew; Disqualified or excluded; Retired (unspecified) or not classified | 25873 | 8 |
| `is_shared_drive` | boolean | True when the car or the driver appears more than once in the same race (historic shared drives). |  |  | 25873 | 2 |
| `is_indy500` | boolean | True for Indianapolis 500 rounds (1950-1960), which counted for the title but used different rules. |  |  | 25873 | 2 |
| `laps_outlier_iqr` | boolean | True when laps_completed lies outside the 1.5 x IQR fences. |  |  | 25873 | 2 |
| `status_position_conflict` | boolean | True when position_text says retired (R) but the status describes a lapped finish. |  |  | 25873 | 2 |
| `source_file` | string | Lineage: source file inside racing_f1_data.zip. |  |  | 25873 | 76 |
| `source_line` | Int64 | Lineage: line number inside the source file. |  |  | 25873 | 479 |

## races_clean.csv

| Column | Type | Description | Unit / format | Allowed values | Non-null | Distinct |
|---|---|---|---|---|---|---|
| `race_id` | string | Grand Prix identifier: season and two-digit round (YYYY_RR). |  |  | 1173 | 1173 |
| `season` | integer | Championship season (year). |  |  | 1173 | 77 |
| `round` | integer | Round number within the season. |  |  | 1173 | 24 |
| `race_name` | string | Grand Prix name in title case. |  |  | 1173 | 55 |
| `race_date` | date | Race day (ISO 8601). |  |  | 1173 | 1173 |
| `circuit_id` | string | Circuit identifier (Ergast convention). |  |  | 1173 | 78 |
| `wikipedia_url` | string | English Wikipedia page (https). |  |  | 1173 | 1173 |
| `has_results` | boolean | True when the results table contains this race. |  |  | 1173 | 2 |

## circuits_clean.csv

| Column | Type | Description | Unit / format | Allowed values | Non-null | Distinct |
|---|---|---|---|---|---|---|
| `circuit_id` | string | Circuit identifier (Ergast convention). |  |  | 78 | 78 |
| `circuit_name` | string | Circuit name in title case. |  |  | 78 | 78 |
| `locality` | string | City or locality. |  |  | 78 | 74 |
| `country` | string | Country name (abbreviations expanded). |  |  | 78 | 34 |
| `country_iso3` | string | ISO 3166-1 alpha-3 country code. |  |  | 78 | 34 |
| `latitude` | number | WGS84 latitude (decimal degrees). |  |  | 77 | 77 |
| `longitude` | number | WGS84 longitude (decimal degrees). |  |  | 77 | 77 |
| `wikipedia_url` | string | English Wikipedia page (https). |  |  | 78 | 78 |
| `wikidata_qid` | string | Wikidata item identifier (persistent identifier of the entity). |  |  | 78 | 78 |

## drivers_clean.csv

| Column | Type | Description | Unit / format | Allowed values | Non-null | Distinct |
|---|---|---|---|---|---|---|
| `driver_id` | string | Driver identifier, lowercase snake case. |  |  | 873 | 873 |
| `given_name` | string | Given name in title case. |  |  | 873 | 488 |
| `family_name` | string | Family name in title case. |  |  | 873 | 812 |
| `full_name` | string | Given and family name. |  |  | 873 | 873 |
| `date_of_birth` | date | Date of birth (ISO 8601). |  |  | 865 | 847 |
| `nationality` | string | Nationality (demonym, title case). |  |  | 865 | 40 |
| `nationality_iso3` | string | Nationality as ISO 3166-1 alpha-3 (ISO 3166-3 for former states). |  |  | 865 | 40 |
| `wikipedia_url` | string | English Wikipedia page (https). |  |  | 864 | 864 |
| `wikidata_qid` | string | Wikidata item identifier (persistent identifier of the entity). |  |  | 863 | 863 |

## constructors_clean.csv

| Column | Type | Description | Unit / format | Allowed values | Non-null | Distinct |
|---|---|---|---|---|---|---|
| `constructor_id` | string | Constructor identifier (Ergast convention). |  |  | 214 | 214 |
| `constructor_name` | string | Constructor name. |  |  | 214 | 214 |
| `nationality` | string | Nationality (demonym, title case). |  |  | 214 | 24 |
| `nationality_iso3` | string | Nationality as ISO 3166-1 alpha-3 (ISO 3166-3 for former states). |  |  | 214 | 24 |
| `wikipedia_url` | string | English Wikipedia page (https). |  |  | 212 | 175 |
| `wikidata_qid` | string | Wikidata item identifier (persistent identifier of the entity). |  |  | 210 | 170 |
