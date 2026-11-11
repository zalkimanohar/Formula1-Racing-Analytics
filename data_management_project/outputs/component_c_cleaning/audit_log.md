# Cleaning audit log

Raw results rows: 25907 -> clean rows: 25873 (34 removed); columns: 14 -> 35.

## Steps

| Step | Name | Issues | Table | Rows before | Rows after | Cells changed | Missing before | Missing after | Columns added |
|---|---|---|---|---|---|---|---|---|---|
| C01 | Enforce schema and data types | B10, B03 | results | 25907 | 25907 | 0 | 18 | 18 | - |
| C02 | Repair missing keys by deterministic lookup | B01, B02, B17 | results | 25907 | 25907 | 12 | 18 | 6 | - |
| C03 | Remove exact duplicates (after key repair) | B06, B07 | results | 25907 | 25873 | 0 | 6 | 6 | - |
| C04 | Standardise identifiers | B09 | results | 25873 | 25873 | 2 | 6 | 6 | - |
| C05 | Replace grid sentinel 0 with missing + flag | B04 | results | 25873 | 25873 | 267 | 6 | 273 | grid_position_missing |
| C06 | Separate classification from finishing order | B11, B13 | results | 25873 | 25873 | 0 | 273 | 273 | classified_position, finish_category, status_position_conflict |
| C07 | Standardise status into 8 groups | B12 | results | 25873 | 25873 | 0 | 9911 | 9911 | status_group |
| C08 | Flag statistical outliers (keep valid extremes) | B16 | results | 25873 | 25873 | 0 | 9911 | 9911 | laps_outlier_iqr, is_indy500 |
| C09 | Normalise points across scoring eras | B15 | results | 25873 | 25873 | 0 | 9911 | 9911 | points_normalised |
| C10a | Clean races reference table | B18, B24, B25 | races | 1178 | 1173 | 1173 | 0 | 0 | race_id, has_results |
| C10b | Clean circuits reference table | B19, B21, B22, B25, B26 | circuits | 82 | 78 | 174 | 4 | 2 | country_iso3, wikidata_qid |
| C10c | Clean drivers reference table | B09, B20, B21, B23, B25, B26 | drivers | 874 | 873 | 3475 | 28 | 25 | full_name, nationality_iso3, wikidata_qid |
| C10d | Clean constructors reference table | B21, B23, B25 | constructors | 214 | 214 | 426 | 2 | 2 | nationality_iso3, wikidata_qid |
| C11 | Integrate into analysis-ready table | B08, B14 | results | 25873 | 25873 | 25873 | 9911 | 9911 | result_id, race_id, circuit_id, circuit_name, circuit_locality, circuit_country, circuit_country_iso3, driver_name, driver_nationality_iso3, constructor_name, constructor_nationality_iso3, is_shared_drive |
| C12 | Validation gates | all | results | 25873 | 25873 | 0 | 9911 | 9911 | - |

### Step details

- **C01 Enforce schema and data types:** source_file: str->string; source_line: int64->Int64; date: str->datetime64[us]; raceName: str->string; round: float64->Int64; season: float64->Int64; url: str->string; constructorId: str->string; driverId: str->string; grid: int64->Int64; laps: int64->Int64; number: float64->Int64; position: int64->Int64; positionText: str->string; status: str->string
- **C02 Repair missing keys by deterministic lookup:** season restored for 5 rows from source file name (cross-checked with race date); round restored for 7 rows by exact lookup in races.csv on (season, date, raceName). Deterministic lookup, no statistical imputation.
- **C03 Remove exact duplicates (after key repair):** removed 34 exact duplicates on all 14 business columns (keep first occurrence) [results_1960.json: 34 rows]; natural key (season, round, driverId, number) verified unique. Shared drives (same driver, different car) are intentionally kept.
- **C04 Standardise identifiers:** trimmed and lower-cased identifiers; changed values: {'driverId': ['Cannoc', 'scott_Brown'], 'constructorId': []}
- **C05 Replace grid sentinel 0 with missing + flag:** grid value 0 (pit-lane start / no grid slot) replaced by missing for 267 rows; boolean flag grid_position_missing keeps the information
- **C06 Separate classification from finishing order:** classified_position kept only where positionText is numeric (16235 rows), set missing for 9638 non-classified rows; finish_category {'Classified': 16235, 'Retired': 9121, 'Withdrawn': 358, 'Disqualified': 159}; 26 R-vs-lapped conflicts flagged (positionText trusted)
- **C07 Standardise status into 8 groups:** 136 free-text values mapped to 8 groups (exhaustive mapping, raw value kept): {'Finished': 8004, 'Finished (lapped)': 7576, 'Mechanical or technical failure': 6662, 'Accident or collision': 2725, 'Retired (unspecified) or not classified': 421, 'Did not start or withdrew': 255, 'Disqualified or excluded': 162, 'Driver health or safety': 68}
- **C08 Flag statistical outliers (keep valid extremes):** IQR fences [-25.5, 122.5] laps; 270 rows flagged, 270 of them are Indianapolis 500 entries; 405 Indy 500 rows flagged in total. Rows are KEPT: the values are valid domain extremes, not errors.
- **C09 Normalise points across scoring eras:** points_normalised = points / highest points awarded in the same race; raw points kept. Winner share = 1.0 in every race; mean share 0.1437
- **C10a Clean races reference table:** removed 5 exact duplicate races; title-cased names; https URLs; has_results=False for 24 races (future 2026 calendar)
- **C10b Clean circuits reference table:** removed 2 exact duplicates and 2 ID-less copies of known circuits; 18 country abbreviations expanded; ISO 3166-1 alpha-3 codes added for all 78 circuits; title-cased names; coordinates of 1 circuit(s) left missing (no source)
- **C10c Clean drivers reference table:** lower-cased 3 IDs ('Cannoc', 'scott_Brown', 'Changy'); merged 1 duplicate person ([{'alias_driver_id': 'arvid_lindblad', 'canonical_driver_id': 'lindblad', 'reason': 'same full name; alias record has no birth date or nationality'}]); nationality mapped to ISO codes (ISO 3166-3 for East Germany and Rhodesia); title-cased names; https URLs
- **C10d Clean constructors reference table:** nationality mapped to ISO codes; https URLs; names already in proper case (kept)
- **C11 Integrate into analysis-ready table:** joined races, circuits, drivers and constructors (many-to-one, validated; 25873 rows in = 25873 rows out); is_shared_drive flags 337 rows; result_id built from race_id + driver_id + car_number
- **C12 Validation gates:** 55/55 gates passed

## Validation gates

| Gate | Result | Detail |
|---|---|---|
| columns match schema (names and order) | passed |  |
| no missing values in required column result_id | passed | 0 missing |
| no missing values in required column race_id | passed | 0 missing |
| no missing values in required column season | passed | 0 missing |
| no missing values in required column round | passed | 0 missing |
| no missing values in required column race_name | passed | 0 missing |
| no missing values in required column race_date | passed | 0 missing |
| no missing values in required column circuit_id | passed | 0 missing |
| no missing values in required column circuit_name | passed | 0 missing |
| no missing values in required column circuit_locality | passed | 0 missing |
| no missing values in required column circuit_country | passed | 0 missing |
| no missing values in required column circuit_country_iso3 | passed | 0 missing |
| no missing values in required column driver_id | passed | 0 missing |
| no missing values in required column driver_name | passed | 0 missing |
| no missing values in required column constructor_id | passed | 0 missing |
| no missing values in required column constructor_name | passed | 0 missing |
| no missing values in required column constructor_nationality_iso3 | passed | 0 missing |
| no missing values in required column grid_position_missing | passed | 0 missing |
| no missing values in required column laps_completed | passed | 0 missing |
| no missing values in required column points | passed | 0 missing |
| no missing values in required column points_normalised | passed | 0 missing |
| no missing values in required column position_order | passed | 0 missing |
| no missing values in required column position_text | passed | 0 missing |
| no missing values in required column finish_category | passed | 0 missing |
| finish_category uses controlled vocabulary | passed | [] |
| no missing values in required column status_raw | passed | 0 missing |
| no missing values in required column status_group | passed | 0 missing |
| status_group uses controlled vocabulary | passed | [] |
| no missing values in required column is_shared_drive | passed | 0 missing |
| no missing values in required column is_indy500 | passed | 0 missing |
| no missing values in required column laps_outlier_iqr | passed | 0 missing |
| no missing values in required column status_position_conflict | passed | 0 missing |
| no missing values in required column source_file | passed | 0 missing |
| no missing values in required column source_line | passed | 0 missing |
| result_id unique | passed |  |
| natural key (season, round, driver_id, car_number) unique | passed |  |
| no exact duplicate records | passed |  |
| season within snapshot | passed |  |
| every race_id exists in races | passed |  |
| every circuit_id exists in circuits | passed |  |
| every driver_id exists in drivers | passed |  |
| every constructor_id exists in constructors | passed |  |
| identifiers are lowercase | passed |  |
| grid_position >= 1 when present | passed |  |
| classified_position missing for every non-classified result | passed |  |
| points_normalised within [0, 1] | passed |  |
| one winner share of 1.0 per race | passed |  |
| duplicate classified positions only occur in shared drives | passed | 152 rows share a position |
| race names are not all-lowercase | passed |  |
| country codes present for every circuit | passed |  |
| races table: race_id unique | passed |  |
| circuits table: circuit_id unique and present | passed |  |
| drivers table: driver_id unique | passed |  |
| drivers table: no person under two IDs | passed |  |
| reference URLs use https | passed |  |

## Issue resolution (Component B -> C)

| Issue | Dimension | Title | Before | After | Resolution |
|---|---|---|---|---|---|
| B01 | Completeness | Season missing | 5 | 0 | Fixed |
| B02 | Completeness | Round missing | 7 | 0 | Fixed |
| B03 | Completeness | Car number missing | 6 | 6 | Kept missing (structurally not applicable) |
| B04 | Completeness | Disguised missing value: grid = 0 sentinel | 267 | 0 | Fixed (sentinel -> missing + flag) |
| B05 | Completeness | Races with fewer entries than the season norm (2014+): verified, not data loss | 7 | - | Not an error (verified) |
| B06 | Uniqueness | Exact duplicate records | 23 | 0 | Fixed |
| B07 | Uniqueness | Hidden duplicates masked by missing keys | 11 | 0 | Fixed (keys repaired before de-duplication) |
| B08 | Uniqueness | Natural-key collisions that are NOT errors (shared drives) | 172 | 337 | Not an error (kept and flagged) |
| B09 | Validity | Identifier violates lowercase convention | 2 | 0 | Fixed |
| B10 | Validity | Incorrect storage types (integers stored as floats, dates stored as text) | 25907 | 0 | Fixed (schema enforced) |
| B11 | Validity | 'position' is filled for drivers who were not classified | 9646 | 0 | Fixed (classified_position separated from position_order) |
| B12 | Consistency | Non-standard categorical values: free-text status | 25907 | 0 | Fixed (136 values -> 8 controlled groups; raw kept) |
| B13 | Consistency | Contradiction: retired ('R') but status says lapped finish | 26 | 26 | Flagged (kept) |
| B14 | Consistency | Inconsistent text formatting (proper names stored in lowercase) | 25907 | 0 | Fixed |
| B15 | Consistency | Points not comparable across eras (scoring rules changed) | 8425 | - | Mitigated (points_normalised added) |
| B16 | Accuracy | Statistical outliers that are valid (Indianapolis 500) | 270 | 270 | Not an error (kept and flagged) |
| B17 | Referential integrity | Results that cannot be linked to a race | 11 | 0 | Fixed |
| B18 | Uniqueness | Duplicate race records | 5 | 0 | Fixed |
| B19 | Uniqueness | Duplicate circuits (exact copies and copies without ID) | 4 | 0 | Fixed |
| B20 | Uniqueness | Same person under two identifiers | 2 | 0 | Fixed (1 alias recorded) |
| B21 | Validity | Country names not in a standard vocabulary | 19 | 0 | Fixed (ISO 3166 codes added) |
| B22 | Completeness | Missing coordinates | 1 | 1 | Kept missing (documented) |
| B23 | Completeness | Missing attributes for newest entities | 12 | 11 | Kept missing (documented) |
| B24 | Timeliness | Reference calendar ahead of the results snapshot | 24 | 24 | Flagged (has_results) |
| B25 | Consistency | Mixed URL schemes (http vs https) | 1073 | 0 | Fixed |
| B26 | Consistency | Proper names stored in lowercase | 956 | 0 | Fixed |
| B27 | Accuracy | Name differs from the official spelling | 2 | 1 | Kept (documented alias) |
| B28 | Consistency | Mixed file formats in one package | 8 | 0 | Handled at extraction (manifest) |
| B29 | Consistency | Retirement causes no longer recorded in recent seasons | 129 | 129 | Kept and documented (cause unknown in source; cause analyses limited to 1950-2022) |
