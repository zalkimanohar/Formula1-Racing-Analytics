# Corrections for the Zenodo record 10.5281/zenodo.23416916

For Manohar (record owner). The record is valuable: it is byte-identical to our source archive
(`data/source/racing_f1_data.zip`, size 520,240 bytes, MD5 `b56e823340c6b99f2494def16261b349`, checked against the
Zenodo API) and gives the raw data a DOI. F-UJI 4.0.1 (metrics v0.8) scores it 84.6%, the same 22/26 points as
the web assessment of 17 Oct 2026 (see `outputs/component_a_fair/fuji/fuji_zenodo_raw_archive.json`).

All changes below are metadata edits: open the record on zenodo.org, click **Edit**, change the fields and
**Publish**. The DOI does not change (only new files would require a new version).

| # | Field | Now | Change to | Why |
|---|---|---|---|---|
| 1 | Licence | CC BY 4.0 | **CC BY-NC-SA 4.0** | Jolpica-F1 licenses the data CC BY-NC-SA 4.0 (`outputs/component_a_fair/license_evidence/jolpica_TERMS.md`); share-alike forbids a more open licence for the same data. F-UJI rewards any licence, so the score hides this conflict. |
| 2 | Title | Study of ML models for Racing LLM Appliances | **Formula 1 World Championship results 1950-2025: raw archive (Ergast / Jolpica-F1 export)** | The title should describe the content; the record holds raw results, not a study. |
| 3 | Creators | Zalki, Manohar | **Zalki, Manohar; Adhikari, Chirag; Bonilla, Nicolas** (ORCID iDs when available), affiliation SRH University | Group project; matches `src/config.py` and the DataCite record of the curated package. |
| 4 | Keywords | none registered | Formula 1; motorsport; sports statistics; Ergast; Jolpica-F1; data quality; FAIR data | F-UJI FsF-F2-01M gives 1/2 because the registered record has no keywords. |
| 5 | Description | short | What the zip contains (circuits.csv, races.csv, drivers.json, constructors.json, results per season 1950-2025, sprint files 2021-2025, batch flags; 93 members), the source (Ergast data served by the Jolpica-F1 API, downloaded by the group), the licence and the SHA-256 `81b027c4221901d92d30ad7b76eacf22668d299098e5c16dcb391c91fd39c748` | Reuse needs provenance and integrity information. |
| 6 | Related works | none | **Is derived from** `https://api.jolpi.ca/ergast/f1/` (URL); **Is supplement to** `https://github.com/zalkimanohar/Formula1-Racing-Analytics` (URL); later **Is source of** the DOI of the curated package | Qualified links to the source and to the code (FAIR I3, R1.2). |

After the edit, re-run the assessment with `python -m src.run_fuji_assessment` (local F-UJI server, see the
README) to store the new evidence.

The hand-written files in `MetaData-FAIR/` (DataCite kernel 4.4, Dublin Core, schema.org) describe the Zenodo
record with the old title and licence. The validated, generated records of the curated package are in
`data_management_project/outputs/component_a_fair/` (DataCite 4.5 XML validated against the official XSD,
schema.org JSON-LD, Data Package, PROV-O); they already cite this DOI as `IsDerivedFrom`.
