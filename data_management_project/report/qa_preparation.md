# Q&A preparation - likely examiner questions and defensible answers

Answers are short on purpose: state the decision, the evidence, the trade-off. All numbers come from the
pipeline outputs (re-check after any re-run).

## Component A - FAIR assessment and metadata

1. **Why two assessment methods?** F-UJI is automated and reproducible but only sees machine-readable signals
   online; the RDA maturity model covers all 41 indicators, including licence and provenance documented for
   humans. Together (F-UJI 4.0.1, metrics v0.8, as on f-uji.net): Jolpica 11.5%, GitHub 42.3%, Kaggle 84.6%
   and the group's Zenodo record of the raw archive 84.6%; 54% -> 93% maturity (RDA).
2. **Why is Findable still level 0 after curation?** F1 (persistent identifier) is an essential indicator. The
   raw archive has a DOI (10.5281/zenodo.23416916, byte-identical to our source, MD5 checked), but the curated
   package does not have its own yet; we cite the raw DOI as IsDerivedFrom instead of borrowing it.
2b. **Why not CC BY 4.0, as on the Zenodo record?** Jolpica's terms license the data CC BY-NC-SA 4.0; share-alike
   forbids a more open licence for derived data. F-UJI gives the Zenodo record full marks for licence because it
   only checks that one is present. The record's licence will be corrected (metadata edit, DOI unchanged).
3. **Why DataCite and not Dublin Core?** DataCite is the schema required to mint a DOI (Zenodo uses it), it is
   richer for datasets (relatedIdentifiers, rights with SPDX, geoLocations). schema.org JSON-LD is added for
   search engines; Dublin Core terms map onto both.
4. **What licence did you choose and why?** CC BY-NC-SA 4.0 for data, because Jolpica licenses the source under it
   and ShareAlike obliges derivatives to keep it; MIT only for code. Our repository's "MIT for everything" and
   Kaggle's CC0 conflict with the source terms.
5. **Which PIDs for the key variables?** Wikidata QIDs for drivers (98.7%), constructors (98.1%) and circuits
   (100%), obtained from the Wikipedia URLs; ISO 3166-1 alpha-3 for countries (ISO 3166-3 for East Germany,
   Rhodesia); ISO 8601 dates; SPDX licence id; ORCID and ROR for people and institution.
6. **How do you know the XML is valid?** It is validated against the official DataCite kernel-4.5 XSD on every
   run; validation once caught an invalid dateType, which was fixed.
7. **What is the single most impactful improvement?** Depositing on Zenodo: it gives a DOI, indexing, a
   landing page, metadata persistence (A2) and versioning at once.

## Component B - data quality and profiling

1. **Which dimensions did you use?** Completeness, uniqueness, validity, consistency, accuracy, timeliness and
   referential integrity: 29 findings, 24 errors, 5 documented non-errors, 6 high severity.
2. **What is "disguised missingness"?** Values that exist but carry no information: position filled for 9,646
   non-classified drivers and grid = 0 for 267 cars. Only 18 cells are actually null.
3. **How did you know the 172 "duplicates" are valid?** All 83 groups differ in car number: in the 1950s a driver
   could take over another car and be classified twice. True duplicates are identical on all 14 fields.
4. **Why are the Indy 500 rows not errors?** They are statistical outliers (laps > 122.5 IQR fence) but valid:
   the Indianapolis 500 counted for the championship 1950-1960 with 200 laps.
5. **What is the downstream impact on AI?** Double-counted wins, biased targets (retirements as "18th"),
   fictitious grid 0, 136 sparse one-hot features, failed joins, train/test leakage through duplicates, and
   non-comparable points across eras.
6. **Root causes?** Export artefacts (duplicated blocks, blanked keys, lowercasing), undocumented source semantics
   (position, grid 0, constructor), and genuine historical change (scoring rules, shared drives).
7. **What did profiling miss?** Two things. The changing meaning of "constructor" before the 1970s (seen in the
   graph analysis), and issue B29: from 2023 the source records retirements only as "Retired", without the cause
   (89% in 2023, 100% in 2024-2025). Every value was present and valid, so no rule fired; the dashboard's
   reliability chart exposed it.

## Component C - cleaning pipeline

1. **Why does the order of steps matter?** 11 duplicates had blanked season/round; they only match their
   originals after key repair. De-duplicating first leaves them in the data (a unit test proves it).
2. **Why no statistical imputation?** Every missing key had a deterministic source (file name, races.csv lookup);
   the other gaps (car number of withdrawn entries, coordinates of a new circuit) are structurally missing, so
   imputing would invent facts.
3. **How do you prove the cleaning is correct?** 55 validation gates (schema, keys, foreign keys, vocabularies,
   ranges); if one fails, no file is written. The issue-resolution table re-measures all 29 issues after cleaning.
4. **How is it reproducible?** One command from the original archive; deterministic; two runs from scratch give
   byte-identical SHA-256 hashes; 14 tests; every clean row keeps source_file and source_line.
5. **Why keep 35 columns?** Flags (is_indy500, is_shared_drive, grid_position_missing, status_position_conflict)
   preserve information that deleting rows would destroy; analysts can filter instead.
6. **Main trade-offs?** Strict gates fail on new status values (safety over convenience); normalised points
   improve comparability but hide absolute values (raw kept); six names needed manual casing exceptions.
7. **Why Python and not Tableau Prep?** Version control, code review, automated tests and determinism.

## Graph modelling (whole group)

1. **Why a property graph?** Results are relationships between drivers and races with attributes; edges with
   properties (RACED_IN) model them naturally, and team-mate relations are a projection.
2. **Why exclude the Indy 500 from the team-mate projection?** There the constructor is a chassis builder used by
   dozens of independent entrants, which would create false team-mate links (a Component B finding).
3. **Interpret betweenness.** Drivers on many shortest paths between others: Jo Bonnier, Jack Brabham, Andrea de
   Cesaris - long careers with many teams that bridge generations.
4. **Is it a small world?** Yes: clustering 0.41 vs 0.014 random, average path 4.8 vs 3.2 random, sigma about 19.
5. **What do the communities mean?** Louvain (modularity 0.70) finds 11 communities that align with eras although
   the algorithm sees no dates.
6. **Limitation?** Early-era "constructor" = chassis make inflates degree and PageRank of 1950s-60s drivers.

## Data engineering and the dashboard (whole group)

1. **Describe your architecture.** Layered zones: an immutable raw zone (bronze) with lineage columns and
   checksums, a clean zone (silver) written only when all 55 gates pass, and served products (gold): FAIR record,
   property graph, dashboard, report. Every arrow is code orchestrated by run_all.py.
2. **What makes it reproducible?** One command from the pinned source archive (SHA-256), no network needed,
   deterministic outputs (identical hashes on re-runs), 28 automated tests, configuration and vocabularies as code.
3. **What is a data contract here?** The issue register (B to C: every issue names its fix and is re-measured) and
   the schema module (C validates against it, A documents from it).
4. **How is the dashboard connected to the project?** build_web_data.py reads only validated outputs (clean
   tables, graph metrics, issue register, FAIR scores); run_all.py calls it as its last step. The dashboard can
   never show a number that failed validation.
5. **What did the dashboard add to data management?** A feedback loop: visual exploration found issue B29, which
   went back into the quality register and is now documented and marked in the chart.
6. **Why the era-adjusted score?** Points systems changed (8 to 50 points for a win); dividing by the race
   winner's points makes a win worth exactly 1 in any era (issue B15, step C09).

## The ask-the-data assistant (whole group; idea and prototype by Manohar)

1. **Why put a language model in a data-management project?** To show the served zone answering questions,
   and to show how to do it safely: the model only phrases answers. Every number comes from pandas code over the
   validated tables, carries its file, SHA-256, filter, row count and raw `source_file:source_line`, and every
   figure in the answer is checked against that evidence afterwards (untraceable figures are flagged).
2. **How do you stop it from hallucinating?** Three layers: the prompt allows only the evidence and asks for
   citations; questions outside the data get an explicit coverage block (it declined "2030 champion"); and the
   figure check. Without Ollama the assistant still returns the evidence, never an unchecked answer.
3. **How good is it?** 25 benchmark questions with answers computed independently from the CSV (evaluate.py):
   the evidence contained the answer in all 25; see outputs/assistant/evaluation_llm_summary.json for the written
   answers, the figure check and the timing (laptop CPU, no GPU).
4. **Why is 1988 Senna and not Prost, if Prost scored more points?** Until 1990 only a driver's best results
   counted. The results table has points per race, not standings, so champions come from Wikidata and are
   reconciled with our points: 1964 and 1988 are the only disagreements, and both are explained.
5. **What changed from the original prototype?** The prototype's model scores were fixed numbers in the code,
   three of its six models were never trained, the vector store was empty and the graph lookup searched the whole
   question as a driver name. The rebuilt version computes every score, uses the cleaned data, and keeps the
   prototype's `/chat` interface so its RQ6 page still works.
6. **Is the podium model useful?** Its probabilities are better than the grid alone (lower log loss and Brier,
   higher ROC AUC on 2020-2025, chosen on 2014-2019 only), but its top three picks find no more podium finishers
   than the grid order. We report that instead of claiming accuracy it does not have.
7. **Is it leaking the answer?** No: every form feature is computed from earlier races (shifted rolling windows),
   and points, laps or finishing status of the race itself are never inputs; a test checks this.

