# Component A - FAIR assessment and metadata design: key findings

## Automated assessment (F-UJI 4.0.1, metrics v0.8)

| Resource | FAIR | F | A | I | R |
|---|---|---|---|---|---|
| github_repository (https://github.com/zalkimanohar/Formula1-Racing-Analytics) | 42.3% | 42.9% | 42.9% | 33.3% | 50.0% |
| jolpica_ergast_api (http://api.jolpi.ca/ergast/f1/) | 11.5% | 14.3% | 28.6% | 0.0% | 0.0% |
| kaggle_ergast_mirror (https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020) | 84.6% | 57.1% | 100.0% | 100.0% | 83.3% |
| zenodo_raw_archive (https://doi.org/10.5281/zenodo.23416916) | 84.6% | 85.7% | 85.7% | 66.7% | 100.0% |

## RDA FAIR Data Maturity Model (41 indicators, 0-4 maturity scale)

| Area | Progress as obtained | RDA level | Progress curated | RDA level | Essential passed (obtained -> curated) |
|---|---|---|---|---|---|
| Findable | 50.0% | 0 | 82.1% | 0 | 1/7 -> 2/7 |
| Accessible | 83.3% | 0 | 93.8% | 0 | 5/8 -> 5/8 |
| Interoperable | 37.5% | 1 | 93.8% | 2 | 0/0 -> 0/0 |
| Reusable | 40.0% | 0 | 100.0% | 5 | 0/5 -> 5/5 |
| Overall | 53.7% | - | 93.3% | - | 6/20 -> 12/20 |

## Gaps and improvements

- **G1 No persistent identifier for the data or metadata** (RDA-F1-01D; RDA-F1-01M; RDA-F3-01M; RDA-A1-03D): F-UJI FsF-F1-02MD = 0 for the GitHub archive, the Jolpica API and even the Kaggle mirror; data are only reachable by mutable URLs. The group's Zenodo deposit of the raw archive (DOI 10.5281/zenodo.23416916, 16 Oct 2026) scores 1 and lifts the archive to 84.6% overall (F-UJI v0.8). -> Use the Zenodo DOI as the identifier of the source archive (cited IsDerivedFrom and in PROV-O), and deposit the curated package as its own Zenodo record to mint a versioned DOI and a concept DOI; cite both in README and CITATION.cff. *Status: Raw archive: implemented (DOI minted by the group, byte-identical to data/source). Curated package: prepared (DataCite record cites the raw DOI; own DOI placeholder).*
- **G2 Missing and conflicting licence information** (RDA-R1.1-01M; RDA-R1.1-02M; RDA-R1.1-03M): Jolpica TERMS.md (27 Aug 2025): data licensed CC BY-NC-SA 4.0. The group's README declares 'MIT License' for everything; the Kaggle mirror declares CC0 although Ergast allowed non-commercial use only; the group's Zenodo record declares CC BY 4.0, which drops the non-commercial and share-alike conditions. F-UJI FsF-R1.1-01M = 0 for GitHub and Jolpica and 1 for Kaggle and Zenodo, because it checks that a licence is present, not that it is compatible. -> License the data CC BY-NC-SA 4.0 (ShareAlike obliges it), add LICENSE-DATA with the SPDX id CC-BY-NC-SA-4.0 and the legal-code URI, keep MIT for code only, and attribute Jolpica-F1 and Ergast. *Status: Implemented in DataCite rightsList, schema.org license and datapackage.json; the Zenodo record's licence must be corrected to CC BY-NC-SA 4.0 (a metadata edit, the DOI does not change).*
- **G3 No machine-readable, standard dataset metadata** (RDA-F2-01M; RDA-F4-01M; RDA-I1-01M; RDA-R1-01M; RDA-R1.3-01M; RDA-R1.3-02M): Only a pipeline README; F-UJI FsF-F2-01M = 0/2 (GitHub, Jolpica); FsF-R1-01M = 1/2 (GitHub) and 0/2 (Jolpica). -> Ship a DataCite 4.5 record (XML validated against the XSD), schema.org Dataset JSON-LD for search engines and a Frictionless Data Package with a full data dictionary. *Status: Implemented.*
- **G4 Non-standard vocabularies inside the data** (RDA-I2-01D; RDA-I1-02D): Country values 'UK', 'USA', 'UAE', 'Korea'; nationalities as lowercase demonyms including former states ('east german', 'rhodesian'); 136 free-text status values mixing laps-behind with failure causes. -> Add ISO 3166-1 alpha-3 codes (ISO 3166-3 for former states), Wikidata QIDs, and an 8-category status vocabulary; publish the status vocabulary as SKOS. *Status: ISO codes, QIDs and status groups implemented; SKOS publication proposed.*
- **G5 No provenance or integrity information** (RDA-R1.2-01M; RDA-R1.2-02M): The repository never names Ergast or Jolpica as the source; no checksums; no record of transformations; the original Ergast terms page now returns 404. -> Record derivation (DataCite IsDerivedFrom), SHA-256 checksums of every source and output file, the cleaning audit log, and a W3C PROV-O graph. *Status: Implemented.*
- **G6 Unqualified and partly broken links to external entities** (RDA-I3-01D; RDA-I3-02D): 861 of 864 driver URLs use http; 12 entities have no URL; 1 driver URL is a Wikipedia talk page (monarch); 2 constructor pages no longer exist (Hall, Turner). -> Normalise to https and add Wikidata QIDs as persistent entity identifiers; flag unresolved links for manual curation. *Status: Implemented (QID crosswalk in data/reference/).*
- **G7 No guarantee that metadata outlives the data** (RDA-A2-01M): The Ergast API was shut down and is only mirrored by a volunteer project (Jolpica) that 'does not guarantee uptime'; GitHub repositories can be deleted. -> Deposit in a certified repository (Zenodo/CERN) whose policy keeps metadata and a tombstone page after withdrawal. *Status: Raw archive deposited in Zenodo by the group (16 Oct 2026); deposit of the curated package proposed.*

## Persistent identifiers

- Raw archive: DOI 10.5281/zenodo.23416916 (Zenodo, published 16 Oct 2026 by Manohar Zalki); byte-identical to data/source/racing_f1_data.zip (size and MD5 checked, data/reference/zenodo_source_record.json).
- Curated package: own DOI still to be minted (placeholder `10.5281/zenodo.TO-BE-MINTED`, never cite before minting); its metadata already cites the raw archive's DOI (IsDerivedFrom, PROV-O).
- Creators: ORCID iDs to be added by each student.
- Institution: ROR to be confirmed; best candidate https://ror.org/00g07sz63 (SRH University of Applied Sciences Heidelberg) (see data/reference/ror_candidates.csv).
- Countries: ISO 3166-1 alpha-3 (ISO 3166-3 for former states); dates: ISO 8601; licence: SPDX.
- Entities: Wikidata QIDs from Wikipedia URLs (data/reference/wikidata_crosswalk.csv):
  - circuit: 82/82 (100.0%)
  - constructor: 210/214 (98.1%)
  - driver: 863/874 (98.7%)

## Licence findings

- Jolpica-F1 Terms of Use (TERMS.md, updated 27 Aug 2025, https://github.com/jolpica/jolpica-f1/blob/main/TERMS.md): data licensed CC BY-NC-SA 4.0, non-commercial use; the code repository itself is Apache-2.0.
- Ergast Developer API terms (Wayback snapshot 18 May 2024 of https://ergast.com/mrd/terms/, live page now 404): "You may use this API for personal, non-commercial applications and services including educational and research purposes"; attribution appreciated, not required.
- Kaggle mirror (rohanrao/formula-1-world-championship-1950-2020, version 24, updated 29 Jan 2025): declared "CC0: Public Domain", although compiled from Ergast, whose terms were non-commercial - a licence inconsistency.
- Group repository README: "MIT License" for the whole project, no data licence - conflicts with CC BY-NC-SA 4.0.
- Zenodo record of the raw archive (10.5281/zenodo.23416916): declares CC BY 4.0, which drops the non-commercial and share-alike conditions of the source - to be corrected to CC BY-NC-SA 4.0 (a metadata edit; the DOI does not change). F-UJI scores the licence as present, not as compliant.
- Decision: curated data released under CC-BY-NC-SA-4.0 (ShareAlike obligation); MIT kept for code only.

## Metadata record

- DataCite 4.5 XML: valid (valid against DataCite kernel-4.5 XSD).
- Files: datacite_metadata.xml, datacite_metadata.json, schema_org_dataset.jsonld, datapackage.json, provenance_prov.jsonld, data_dictionary.csv/.md, LICENSE-DATA.md.
- Coverage: 1950-05-13 to 2025-12-07, 25,873 rows in the results table; raw files collected 2026-10-15.
