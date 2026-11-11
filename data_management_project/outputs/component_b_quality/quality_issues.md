# Data quality issue register

| issue_id | dimension | table | title | affected_records | affected_pct | severity | is_error | cleaning_step |
|---|---|---|---|---|---|---|---|---|
| B01 | Completeness | results | Season missing | 5 | 0.019 | High | True | C02 |
| B02 | Completeness | results | Round missing | 7 | 0.027 | High | True | C02 |
| B03 | Completeness | results | Car number missing | 6 | 0.023 | Low | False | C01 |
| B04 | Completeness | results | Disguised missing value: grid = 0 sentinel | 267 | 1.031 | Medium | True | C05 |
| B05 | Completeness | results | Races with fewer entries than the season norm (2014+): verified, not data loss | 7 | 2.778 | Info | False | None (verified as genuine) |
| B06 | Uniqueness | results | Exact duplicate records | 23 | 0.089 | High | True | C03 |
| B07 | Uniqueness | results | Hidden duplicates masked by missing keys | 11 | 0.042 | High | True | C02 + C03 |
| B08 | Uniqueness | results | Natural-key collisions that are NOT errors (shared drives) | 172 | 0.664 | Info | False | C11 (flag is_shared_drive) |
| B09 | Validity | results | Identifier violates lowercase convention | 2 | 0.008 | Medium | True | C04 |
| B10 | Validity | results | Incorrect storage types (integers stored as floats, dates stored as text) | 25907 | 100.0 | Medium | True | C01 |
| B11 | Validity | results | 'position' is filled for drivers who were not classified | 9646 | 37.233 | High | True | C06 |
| B12 | Consistency | results | Non-standard categorical values: free-text status | 25907 | 100.0 | Medium | True | C07 |
| B13 | Consistency | results | Contradiction: retired ('R') but status says lapped finish | 26 | 0.1 | Low | True | C06 (flag status_position_conflict) |
| B14 | Consistency | results | Inconsistent text formatting (proper names stored in lowercase) | 25907 | 100.0 | Low | True | C10, C11 |
| B15 | Consistency | results | Points not comparable across eras (scoring rules changed) | 8425 | 32.52 | Medium | True | C09 |
| B16 | Accuracy | results | Statistical outliers that are valid (Indianapolis 500) | 270 | 1.042 | Info | False | C08 |
| B17 | Referential integrity | results | Results that cannot be linked to a race | 11 | 0.042 | High | True | C02 |
| B18 | Uniqueness | races | Duplicate race records | 5 | 0.424 | Medium | True | C10 |
| B19 | Uniqueness | circuits | Duplicate circuits (exact copies and copies without ID) | 4 | 4.878 | Medium | True | C10 |
| B20 | Uniqueness | drivers | Same person under two identifiers | 2 | 0.229 | Medium | True | C10 |
| B21 | Validity | circuits | Country names not in a standard vocabulary | 19 | 23.171 | Medium | True | C10 |
| B22 | Completeness | circuits | Missing coordinates | 1 | 1.22 | Low | True | Documented (kept missing) |
| B23 | Completeness | drivers / constructors | Missing attributes for newest entities | 12 | 1.103 | Low | True | Documented (kept missing) |
| B24 | Timeliness | races | Reference calendar ahead of the results snapshot | 24 | 2.037 | Low | False | C10 (flag has_results) |
| B25 | Consistency | drivers / constructors | Mixed URL schemes (http vs https) | 1073 | 45.933 | Low | True | C10 |
| B26 | Consistency | drivers / circuits | Proper names stored in lowercase | 956 | 100.0 | Low | True | C10 |
| B27 | Accuracy | circuits | Name differs from the official spelling | 2 | 2.439 | Low | True | Documented (kept, alias noted) |
| B28 | Consistency | source package | Mixed file formats in one package | 8 | 8.602 | Low | True | Step 0 (format detection in manifest) |
| B29 | Consistency | results | Retirement causes no longer recorded in recent seasons | 129 | 0.498 | Medium | True | C07 (mapped to 'Retired (unspecified)'; cause analyses limited to earlier seasons) |

## Details

### B01 - Season missing
- **Dimension:** Completeness | **Table/columns:** results / season
- **Affected:** 5 of 25907 (0.019%) | **Severity:** High | **Error:** True
- **Evidence:** results_1960.json lines 193, 196-199
- **Root-cause hypothesis:** Field dropped while copying a block of rows (all affected rows belong to one race block).
- **Downstream impact (DS/AI):** Rows cannot be joined to races/circuits and silently vanish from per-season aggregates and model training sets.
- **Resolved by:** C02

### B02 - Round missing
- **Dimension:** Completeness | **Table/columns:** results / round
- **Affected:** 7 of 25907 (0.027%) | **Severity:** High | **Error:** True
- **Evidence:** results_1960.json lines 193-195, 200-203
- **Root-cause hypothesis:** Same corrupted block as B01 (1960 Italian GP).
- **Downstream impact (DS/AI):** Race-level features (circuit, date) cannot be attached; orphaned facts in a star schema.
- **Resolved by:** C02

### B03 - Car number missing
- **Dimension:** Completeness | **Table/columns:** results / number
- **Affected:** 6 of 25907 (0.023%) | **Severity:** Low | **Error:** False
- **Evidence:** all 6 rows have positionText 'W' (withdrawn entries): {'W': 6}
- **Root-cause hypothesis:** Structurally missing (not applicable): a withdrawn entry was never assigned a race number.
- **Downstream impact (DS/AI):** None if handled as nullable; imputing a number would invent facts.
- **Resolved by:** C01

### B04 - Disguised missing value: grid = 0 sentinel
- **Dimension:** Completeness | **Table/columns:** results / grid
- **Affected:** 267 of 25907 (1.031%) | **Severity:** Medium | **Error:** True
- **Evidence:** 0 is not a grid slot; status of these rows: {'Withdrew': 164, 'Accident': 19, '+1 Lap': 18, 'Finished': 11}
- **Root-cause hypothesis:** Source encodes 'pit-lane start / no grid slot' as 0 instead of null.
- **Downstream impact (DS/AI):** Grid-vs-result models treat 0 as pole-better-than-pole; mean grid is biased low; correlation with finishing position is distorted.
- **Resolved by:** C05

### B05 - Races with fewer entries than the season norm (2014+): verified, not data loss
- **Dimension:** Completeness | **Table/columns:** results / (record level)
- **Affected:** 7 of 252 (2.778%) | **Severity:** Info | **Error:** False
- **Evidence:** 2014 R16: 21/22 entries, absent vs neighbouring rounds: ['jules_bianchi'] | 2014 R17: 18/22 entries, absent vs neighbouring rounds: ['chilton', 'ericsson', 'kobayashi'] | 2014 R18: 18/22 entries, absent vs neighbouring rounds: ['kobayashi', 'stevens'] | 2014 R19: 20/22 entries, absent vs neighbouring rounds: [] | 2015 R1: 18/20 entries, absent vs neighbouring rounds: ['alonso', 'merhi', 'stevens'] | 2024 R3: 19/20 entries, absent vs neighbouring rounds: ['bearman', 'sargeant'] | 2025 R9: 19/20 entries, absent vs neighbouring rounds: ['stroll']
- **Root-cause hypothesis:** Each gap matches a documented real-world absence (e.g. Marussia/Caterham missing late 2014, Stroll injured for the 2025 Spanish GP), not a lost record. Should still be confirmed against the official FIA classification before publication.
- **Downstream impact (DS/AI):** None if verified; shows why record-count anomaly detection needs domain verification before imputation.
- **Resolved by:** None (verified as genuine)

### B06 - Exact duplicate records
- **Dimension:** Uniqueness | **Table/columns:** results / all
- **Affected:** 23 of 25907 (0.089%) | **Severity:** High | **Error:** True
- **Evidence:** duplicated copies at results_1960.json lines 227-249
- **Root-cause hypothesis:** A block of rows was appended twice (copy/paste or a re-run of an append-only load).
- **Downstream impact (DS/AI):** Double-counts points and wins, inflates sample weight of one race, leaks identical rows across train/test splits.
- **Resolved by:** C03

### B07 - Hidden duplicates masked by missing keys
- **Dimension:** Uniqueness | **Table/columns:** results / all
- **Affected:** 11 of 25907 (0.042%) | **Severity:** High | **Error:** True
- **Evidence:** rows results_1960.json lines 193-203 become exact copies of complete rows once season/round are restored
- **Root-cause hypothesis:** The duplicated block of B06 was additionally damaged (keys blanked), so naive exact-match de-duplication misses it.
- **Downstream impact (DS/AI):** Same as B06; also shows that cleaning order matters (repair keys before de-duplicating).
- **Resolved by:** C02 + C03

### B08 - Natural-key collisions that are NOT errors (shared drives)
- **Dimension:** Uniqueness | **Table/columns:** results / season, round, driverId
- **Affected:** 172 of 25907 (0.664%) | **Severity:** Info | **Error:** False
- **Evidence:** 83 driver-race groups; car number differs in 83/83; seasons 1950-1964
- **Root-cause hypothesis:** Historic rule allowed a driver to take over a team-mate's car; each car is a separate classified entry.
- **Downstream impact (DS/AI):** Naive de-duplication on (season, round, driver) would delete real history; the correct key includes the car number.
- **Resolved by:** C11 (flag is_shared_drive)

### B09 - Identifier violates lowercase convention
- **Dimension:** Validity | **Table/columns:** results / driverId
- **Affected:** 2 of 25907 (0.008%) | **Severity:** Medium | **Error:** True
- **Evidence:** values ['Cannoc', 'scott_Brown'] at results_1956.json line 134; results_1971.json line 242
- **Root-cause hypothesis:** Manual edit of identifiers (mixed case) in the source.
- **Downstream impact (DS/AI):** Case-sensitive joins with other F1 sources fail; the same driver can appear as two entities.
- **Resolved by:** C04

### B10 - Incorrect storage types (integers stored as floats, dates stored as text)
- **Dimension:** Validity | **Table/columns:** results / season, round, number, date
- **Affected:** 25907 of 25907 (100.0%) | **Severity:** Medium | **Error:** True
- **Evidence:** season/round/number inferred as float64 because of missing values; date is an untyped string
- **Root-cause hypothesis:** JSON nulls force numeric columns to float when loaded; no schema was enforced at ingestion.
- **Downstream impact (DS/AI):** Keys like 1960.0 break joins and string IDs; dates cannot be used for time-based splits without parsing.
- **Resolved by:** C01

### B11 - 'position' is filled for drivers who were not classified
- **Dimension:** Validity | **Table/columns:** results / position, positionText
- **Affected:** 9646 of 25907 (37.233%) | **Severity:** High | **Error:** True
- **Evidence:** positionText codes R/W/D: {'R': 9129, 'W': 358, 'D': 159} all carry a numeric 'position'
- **Root-cause hypothesis:** Source semantics: 'position' is the order of finishing incl. retirements, not the official result.
- **Downstream impact (DS/AI):** Analyses that treat 'position' as the result (e.g. grid-vs-finish regressions, the project dashboard) count a retirement as e.g. 18th place, biasing targets for prediction models.
- **Resolved by:** C06

### B12 - Non-standard categorical values: free-text status
- **Dimension:** Consistency | **Table/columns:** results / status
- **Affected:** 25907 of 25907 (100.0%) | **Severity:** Medium | **Error:** True
- **Evidence:** 136 distinct values; 122 values each <1% of rows; mixes finishing margin ('+1 Lap' to '+46 Laps', 'Lapped') with causes ('Engine', 'Accident')
- **Root-cause hypothesis:** Status is recorded verbatim from race reports over 75 years without a controlled vocabulary.
- **Downstream impact (DS/AI):** One-hot encoding creates 136 sparse features; reliability analyses (DNF causes) cannot be aggregated.
- **Resolved by:** C07

### B13 - Contradiction: retired ('R') but status says lapped finish
- **Dimension:** Consistency | **Table/columns:** results / positionText, status
- **Affected:** 26 of 25907 (0.1%) | **Severity:** Low | **Error:** True
- **Evidence:** seasons [1956, 1967, 1978, 1979, 1980, 2005, 2006, 2010, 2011, 2012, 2014]
- **Root-cause hypothesis:** Driver was running at the flag but covered <90% distance (not classified); status and code disagree.
- **Downstream impact (DS/AI):** DNF-rate features are inconsistent depending on which field is used.
- **Resolved by:** C06 (flag status_position_conflict)

### B14 - Inconsistent text formatting (proper names stored in lowercase)
- **Dimension:** Consistency | **Table/columns:** results / raceName
- **Affected:** 25907 of 25907 (100.0%) | **Severity:** Low | **Error:** True
- **Evidence:** raceName, circuitName, locality and driver names are lowercase while constructor names keep proper case
- **Root-cause hypothesis:** A normalisation step lowercased some tables during an earlier export.
- **Downstream impact (DS/AI):** Cosmetic for models but reduces readability, breaks exact matching with external sources (e.g. Wikidata labels).
- **Resolved by:** C10, C11

### B15 - Points not comparable across eras (scoring rules changed)
- **Dimension:** Consistency | **Table/columns:** results / points
- **Affected:** 8425 of 25907 (32.52%) | **Severity:** Medium | **Error:** True
- **Evidence:** points for a win range 4-50; the typical winner score changes in 7 seasons (1950: 9, 1951: 8, 1952: 9, 1953: 8, 1961: 9, 1991: 10, 2010: 25); 10 fractional values (shared drives / shared fastest lap, e.g. 8.14, 1.33)
- **Root-cause hypothesis:** Not a recording error: FIA scoring systems changed (1950, 1960, 1961, 1991, 2003, 2010, 2014 double points, 2019 fastest lap).
- **Downstream impact (DS/AI):** All-time rankings and models using raw points are dominated by the post-2010 era (25 points per win).
- **Resolved by:** C09

### B16 - Statistical outliers that are valid (Indianapolis 500)
- **Dimension:** Accuracy | **Table/columns:** results / laps
- **Affected:** 270 of 25907 (1.042%) | **Severity:** Info | **Error:** False
- **Evidence:** IQR upper fence 122.5 laps; flagged rows by race: {'indianapolis 500': 270}
- **Root-cause hypothesis:** Indy 500 (200 laps, 1950-1960) counted for the championship under different rules.
- **Downstream impact (DS/AI):** Removing them as 'outliers' would delete valid history; keeping them unflagged skews lap-based features.
- **Resolved by:** C08

### B17 - Results that cannot be linked to a race
- **Dimension:** Referential integrity | **Table/columns:** results / season, round
- **Affected:** 11 of 25907 (0.042%) | **Severity:** High | **Error:** True
- **Evidence:** results_1960.json lines 193-203
- **Root-cause hypothesis:** Consequence of B01/B02.
- **Downstream impact (DS/AI):** Inner joins drop these rows silently; left joins create rows without circuit/date.
- **Resolved by:** C02

### B18 - Duplicate race records
- **Dimension:** Uniqueness | **Table/columns:** races / all
- **Affected:** 5 of 1178 (0.424%) | **Severity:** Medium | **Error:** True
- **Evidence:** duplicated (season, round): ['2008-R12', '1950-R4', '1991-R15', '1982-R9', '2025-R12']
- **Root-cause hypothesis:** Rows appended twice at the end of the file (rows 1174-1178).
- **Downstream impact (DS/AI):** Join fan-out: every result of these races is duplicated after a join with races.
- **Resolved by:** C10

### B19 - Duplicate circuits (exact copies and copies without ID)
- **Dimension:** Uniqueness | **Table/columns:** circuits / circuitId, url
- **Affected:** 4 of 82 (4.878%) | **Severity:** Medium | **Error:** True
- **Evidence:** exact copies: ['dijon', 'indianapolis']; ID missing but same url as existing circuit: ['circuit gilles villeneuve', 'losail international circuit']
- **Root-cause hypothesis:** Circuits re-added during a merge without their key.
- **Downstream impact (DS/AI):** Join fan-out on circuitId; a map aggregates the same circuit twice.
- **Resolved by:** C10

### B20 - Same person under two identifiers
- **Dimension:** Uniqueness | **Table/columns:** drivers / driverId
- **Affected:** 2 of 874 (0.229%) | **Severity:** Medium | **Error:** True
- **Evidence:** [{'driverId': 'arvid_lindblad', 'dateOfBirth': nan}, {'driverId': 'lindblad', 'dateOfBirth': '2007-08-08'}]
- **Root-cause hypothesis:** A new driver was added twice by two ingestion runs with different ID conventions.
- **Downstream impact (DS/AI):** Entity resolution error: career statistics split across two nodes in the graph.
- **Resolved by:** C10

### B21 - Country names not in a standard vocabulary
- **Dimension:** Validity | **Table/columns:** circuits / country
- **Affected:** 19 of 82 (23.171%) | **Severity:** Medium | **Error:** True
- **Evidence:** {'USA': 13, 'UK': 4, 'UAE': 1, 'Korea': 1} (ambiguous: 'Korea'); nationalities are free-text demonyms incl. former states ('east german', 'rhodesian')
- **Root-cause hypothesis:** Abbreviations typed by hand; no ISO 3166 codes in the source.
- **Downstream impact (DS/AI):** Geo joins and choropleth maps fail (the dashboard map showed only 1 country); no interoperability.
- **Resolved by:** C10

### B22 - Missing coordinates
- **Dimension:** Completeness | **Table/columns:** circuits / lat, long
- **Affected:** 1 of 82 (1.22%) | **Severity:** Low | **Error:** True
- **Evidence:** ['madring']
- **Root-cause hypothesis:** New 2026 venue added before its coordinates were published.
- **Downstream impact (DS/AI):** Circuit cannot be placed on a map or used in distance features.
- **Resolved by:** Documented (kept missing)

### B23 - Missing attributes for newest entities
- **Dimension:** Completeness | **Table/columns:** drivers / constructors / dateOfBirth, nationality, url
- **Affected:** 12 of 1088 (1.103%) | **Severity:** Low | **Error:** True
- **Evidence:** drivers: ['paul_aron', 'luke_browning', 'jak_crawford', 'ryo_hirakawa', 'ayumu_iwasa', 'arthur_leclerc', 'arvid_lindblad', 'lindblad', 'patricio_o_ward', 'cian_shields']; constructors: ['audi', 'cadillac']
- **Root-cause hypothesis:** Timeliness: 2026 entrants/reserves were added before their profiles existed upstream.
- **Downstream impact (DS/AI):** Age and nationality features are missing for recent drivers (none of them has a race result yet).
- **Resolved by:** Documented (kept missing)

### B24 - Reference calendar ahead of the results snapshot
- **Dimension:** Timeliness | **Table/columns:** races / season
- **Affected:** 24 of 1178 (2.037%) | **Severity:** Low | **Error:** False
- **Evidence:** 24 races of season 2026 without results; latest date 2026-12-06
- **Root-cause hypothesis:** Calendar for the upcoming season is published before results exist; tables were exported at different times.
- **Downstream impact (DS/AI):** Counting races per season or per circuit over-states 2026; an inner join hides the mismatch.
- **Resolved by:** C10 (flag has_results)

### B25 - Mixed URL schemes (http vs https)
- **Dimension:** Consistency | **Table/columns:** drivers / constructors / url
- **Affected:** 1073 of 2336 (45.933%) | **Severity:** Low | **Error:** True
- **Evidence:** {'https': 1263, 'http': 1073} across all reference tables
- **Root-cause hypothesis:** Links copied from different Wikipedia snapshots.
- **Downstream impact (DS/AI):** Exact-match linking (e.g. to Wikidata) misses entities; mixed-content warnings in web apps.
- **Resolved by:** C10

### B26 - Proper names stored in lowercase
- **Dimension:** Consistency | **Table/columns:** drivers / circuits / name, circuitName, locality
- **Affected:** 956 of 956 (100.0%) | **Severity:** Low | **Error:** True
- **Evidence:** e.g. 'carlo abate', 'circuit gilles villeneuve', 'montreal'; constructors use proper case ('McLaren')
- **Root-cause hypothesis:** Same lowercasing step as B14.
- **Downstream impact (DS/AI):** Readability and matching with external authority files.
- **Resolved by:** C10

### B27 - Name differs from the official spelling
- **Dimension:** Accuracy | **Table/columns:** circuits / circuitName
- **Affected:** 2 of 82 (2.439%) | **Severity:** Low | **Error:** True
- **Evidence:** 'losail international circuit' while the Wikipedia/official name is 'Lusail International Circuit'
- **Root-cause hypothesis:** Legacy transliteration kept from an older source.
- **Downstream impact (DS/AI):** Text matching against official sources fails.
- **Resolved by:** Documented (kept, alias noted)

### B28 - Mixed file formats in one package
- **Dimension:** Consistency | **Table/columns:** source package / file format
- **Affected:** 8 of 93 (8.602%) | **Severity:** Low | **Error:** True
- **Evidence:** 5 sprint files are pretty-printed JSON arrays while all other JSON files are JSON Lines; 3 non-data files (.DS_Store, empty .flag markers)
- **Root-cause hypothesis:** Files produced by different scripts; macOS metadata zipped by accident.
- **Downstream impact (DS/AI):** Generic loaders fail on part of the package; reproducibility depends on undocumented conventions.
- **Resolved by:** Step 0 (format detection in manifest)

### B29 - Retirement causes no longer recorded in recent seasons
- **Dimension:** Consistency | **Table/columns:** results / status
- **Affected:** 129 of 25907 (0.498%) | **Severity:** Medium | **Error:** True
- **Evidence:** share of retirements stored only as 'Retired': 2019: 2%, 2020: 2%, 2021: 2%, 2022: 0%, 2023: 89%, 2024: 100%, 2025: 100% (found when the reliability trend was visualised in the project dashboard)
- **Root-cause hypothesis:** Recording practice changed in the source from 2023: retirements are entered with the generic status 'Retired' instead of the cause (engine, accident, ...).
- **Downstream impact (DS/AI):** Reliability trends and failure-cause models see a false collapse of mechanical failures and accidents after 2022; models trained across this boundary learn a spurious time effect.
- **Resolved by:** C07 (mapped to 'Retired (unspecified)'; cause analyses limited to earlier seasons)
