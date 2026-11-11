"""Component A - FAIR assessment with the RDA FAIR Data Maturity Model (doi:10.15497/RDA00050).

The 41 indicators and their priorities are read from the official RDA evaluation workbook
(FAIR_evaluation_levels_v0.02.xlsx, Zenodo record 3909563). Each indicator is scored on the RDA
maturity scale (0 not applicable, 1 not considered, 2 under consideration/planned,
3 in implementation, 4 fully implemented) for two states of the dataset:

* as_obtained - racing_f1_data.zip in the public GitHub repository plus the Jolpica (Ergast) API.
                The group later deposited the same archive on Zenodo (DOI 10.5281/zenodo.23416916, byte-identical);
                that deposit is evaluated with F-UJI and cited as the source of the curated package.
* curated     - the package delivered by the group: cleaned CSVs, DataCite/schema.org/Data Package
                metadata, checksums, provenance and identifiers. Anything that only exists once the
                package is deposited in Zenodo (DOI, landing page, indexing) is scored 3, not 4.

Scores are justified with evidence, including F-UJI results (src/run_fuji_assessment.py, metrics v0.8).
"""
from __future__ import annotations

import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src import config  # noqa: E402
from src.schema import RESULTS_COLUMNS  # noqa: E402

N_VARIABLES = len(RESULTS_COLUMNS)

# Reference palette of the dataviz method (light surface); slots validated as a pair.
SURFACE, INK, INK_2, MUTED, GRID, BASELINE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")

FRAMEWORK_DIR = config.FAIR_DIR / "framework_evidence"
RDA_WORKBOOK = FRAMEWORK_DIR / "FAIR_evaluation_levels_v0.02.xlsx"
RDA_INDICATORS_CSV = config.REFERENCE_DIR / "rda_fair_indicators.csv"
RDA_SOURCE = "RDA FAIR Data Maturity Model WG (2020), doi:10.15497/RDA00050, Zenodo record 3909563"

MATURITY_LABELS = {0: "not applicable", 1: "not being considered yet",
                   2: "under consideration or planned", 3: "in implementation", 4: "fully implemented"}

# indicator_id: (as_obtained score, evidence, curated score, evidence, related F-UJI metric)
ASSESSMENT: dict[str, tuple[int, str, int, str, str]] = {
    "RDA-F1-01M": (1, "No persistent identifier for any metadata; the only metadata is a project README reached by a GitHub URL. F-UJI FsF-F1-02MD = 0 for GitHub, Jolpica and Kaggle.",
                   3, "DataCite record prepared for a Zenodo deposit; the group's Zenodo deposit of the raw archive (DOI 10.5281/zenodo.23416916, 16 Oct 2026) scores FsF-F1-02MD = 1, but the curated package's own DOI is not minted yet.", "FsF-F1-02MD"),
    "RDA-F1-01D": (1, "As obtained, racing_f1_data.zip (GitHub) and the API responses have no DOI/Handle/ARK. F-UJI FsF-F1-02MD = 0 for GitHub, Jolpica and Kaggle.",
                   3, "The source archive now has a DOI (the group's Zenodo deposit of the raw archive (DOI 10.5281/zenodo.23416916, 16 Oct 2026)), cited as IsDerivedFrom; the curated package's own DOI is planned (placeholder 10.5281/zenodo.TO-BE-MINTED).", "FsF-F1-02MD"),
    "RDA-F1-02M": (3, "README has a unique but non-persistent URL and describes the software project, not the dataset.",
                   3, "Metadata files have unique repository paths; the record identifier will be the DOI once minted.", "FsF-F1-01MD"),
    "RDA-F1-02D": (4, "Unique URLs exist for the archive (GitHub) and every API endpoint. F-UJI FsF-F1-01MD = 1 for all four evaluated locations.",
                   4, "Each distribution is identified by URL and SHA-256 content hash (schema.org sha256, Data Package hash).", "FsF-F1-01MD"),
    "RDA-F2-01M": (2, "No dataset title, creator, keywords or summary; the README documents the pipeline. F-UJI FsF-F2-01M = 0/2 for GitHub, Jolpica and Kaggle.",
                   4, f"DataCite 4.5 mandatory and recommended properties plus schema.org Dataset with {N_VARIABLES} variableMeasured entries.", "FsF-F2-01M"),
    "RDA-F3-01M": (1, "No metadata record contains the identifier of the data. F-UJI FsF-F3-01M = 0 for GitHub and Jolpica.",
                   3, "DataCite identifier and schema.org distribution/contentUrl reference the data; final DOI pending.", "FsF-F3-01M"),
    "RDA-F4-01M": (2, "GitHub exposes generic page metadata only (F-UJI FsF-F4-01M = 2/2, for the repository page, not the dataset); the API exposes none (0/2).",
                   3, "schema.org JSON-LD ready for Google Dataset Search; Zenodo exposes DataCite and OAI-PMH after deposit.", "FsF-F4-01M"),
    "RDA-A1-01M": (1, "No access level or access conditions stated. F-UJI FsF-A1-01M = 0 for GitHub and Jolpica.",
                   4, "Open access stated in DataCite rightsList and schema.org isAccessibleForFree/conditionsOfAccess.", "FsF-A1-01M"),
    "RDA-A1-02M": (4, "README and API JSON can be read in a browser.",
                   4, "Human-readable data dictionary (Markdown) and metadata files shipped with the data.", ""),
    "RDA-A1-02D": (4, "Archive downloadable from GitHub; API answers in the browser.",
                   4, "CSV files open in any spreadsheet tool.", ""),
    "RDA-A1-03M": (3, "The GitHub URL resolves to the README, which is not a dataset metadata record.",
                   3, "DOI will resolve to the Zenodo landing page with the DataCite record; pending deposit.", ""),
    "RDA-A1-03D": (4, "Archive URL and API endpoints resolve (http redirects 301 to https).",
                   3, "Data resolve through repository URLs now; DOI resolution pending deposit.", ""),
    "RDA-A1-04M": (4, "Metadata served over HTTPS. F-UJI FsF-A1.1-01MD = 1/2 for GitHub and Jolpica (2/2 for Kaggle and the Zenodo deposit).",
                   4, "Metadata served over HTTPS (GitHub; Zenodo after deposit).", "FsF-A1.1-01MD"),
    "RDA-A1-04D": (3, "Data downloadable over HTTPS, but no machine-discoverable data link. F-UJI FsF-A1-02MD = 1/2 (GitHub), 0/2 (Jolpica).",
                   4, "schema.org DataDownload entries with HTTPS contentUrl and encodingFormat.", "FsF-A1-02MD"),
    "RDA-A1-05D": (4, "REST API and raw GitHub URLs allow scripted access.",
                   4, "Direct CSV URLs plus a reproducible loader (src/build_raw_dataset.py).", ""),
    "RDA-A1.1-01M": (4, "HTTPS is free, open and universally implemented.", 4, "Same.", ""),
    "RDA-A1.1-01D": (4, "HTTPS is free, open and universally implemented.", 4, "Same.", ""),
    "RDA-A1.2-01D": (4, "HTTPS supports authentication and authorisation (not required: open data).", 4, "Same.", ""),
    "RDA-A2-01M": (1, "No persistence guarantee: the original Ergast API and its terms page are offline (404, Wayback copy only); a GitHub repository can be deleted.",
                   3, "Zenodo keeps metadata (tombstone page) even if files are withdrawn; pending deposit.", ""),
    "RDA-I1-01M": (2, "Only generic GitHub page metadata; no formal representation of the dataset. F-UJI FsF-I1-01M = 2/2 for GitHub (generic repository page), 0/2 (Jolpica).",
                   4, "DataCite XML (validated against the 4.5 XSD) and JSON-LD.", "FsF-I1-01M"),
    "RDA-I1-01D": (3, "Standard formats (CSV, JSON), but mixed in one package: JSON Lines, pretty-printed JSON arrays, CSV and OS files (.DS_Store).",
                   4, "Uniform UTF-8 CSV (RFC 4180) with a Frictionless Table Schema.", ""),
    "RDA-I1-02M": (2, "No machine-understandable description of the dataset itself. F-UJI FsF-I1-01M credits only GitHub's generic page metadata.",
                   4, "schema.org JSON-LD (RDF) with typed properties.", "FsF-I1-01M"),
    "RDA-I1-02D": (1, "Plain JSON/CSV fields with no semantic annotation of columns or values.",
                   3, "Columns described with schema.org PropertyValue and typed in a Table Schema; the data themselves are not RDF.", ""),
    "RDA-I2-01M": (1, "No vocabularies used in metadata. F-UJI FsF-I2-01M = 0 for GitHub and Jolpica.",
                   4, "schema.org, DataCite controlled lists, SPDX licence ids, ISO 8601, ISO 3166, Wikidata.", "FsF-I2-01M"),
    "RDA-I2-01D": (1, "Free-text values: countries 'UK', 'USA', 'UAE', 'Korea'; lowercase nationality demonyms incl. 'east german', 'rhodesian'; 136 free-text status values.",
                   3, "ISO 3166 codes, Wikidata QIDs and an 8-value status vocabulary documented in the data dictionary (not yet published as SKOS).", ""),
    "RDA-I3-01M": (1, "No links to other metadata. F-UJI FsF-I3-01M = 0 for GitHub and Jolpica.",
                   4, "DataCite relatedIdentifiers to the Jolpica API, the archived Ergast terms, the GitHub repository and the Kaggle mirror.", "FsF-I3-01M"),
    "RDA-I3-01D": (3, "Each driver, constructor and circuit links to Wikipedia, but 12 records have no URL, 1 URL is a talk page and 2 pages no longer exist.",
                   4, "Wikidata QIDs for 98.7% of drivers, 98.1% of constructors and 100% of circuits; validated foreign keys.", ""),
    "RDA-I3-02M": (1, "Metadata does not reference the source datasets.",
                   4, "relatedIdentifiers IsDerivedFrom the Jolpica API and Ergast; References the Kaggle mirror.", ""),
    "RDA-I3-02D": (1, "Wikipedia URLs are unqualified (no relation type).",
                   3, "QID columns documented as 'same as' links in the data dictionary; relation types live in metadata, not in the data.", ""),
    "RDA-I3-03M": (1, "No qualified references.",
                   4, "DataCite relationType values (IsDerivedFrom, IsSupplementTo, References, IsDocumentedBy).", ""),
    "RDA-I3-04M": (1, "No qualified references to data.",
                   4, "relatedIdentifier with relationType and resourceTypeGeneral for every source dataset.", ""),
    "RDA-R1-01M": (2, "No variable descriptions, units, coverage or quality notes. F-UJI FsF-R1-01M = 1/2 (GitHub), 0/2 (Jolpica).",
                   4, "Data dictionary for every column (type, unit/format, allowed values, source field), temporal and spatial coverage, quality notes.", "FsF-R1-01M"),
    "RDA-R1.1-01M": (1, "The README declares 'MIT License' for the whole project, which conflicts with the upstream data licence CC BY-NC-SA 4.0; no data licence. F-UJI FsF-R1.1-01M = 0.",
                     4, "CC BY-NC-SA 4.0 declared, consistent with the Jolpica terms (ShareAlike).", "FsF-R1.1-01M"),
    "RDA-R1.1-02M": (2, "MIT is a standard licence, but it applies to software and is not valid for this data.",
                     4, "Standard Creative Commons licence with legal-code URI.", "FsF-R1.1-01M"),
    "RDA-R1.1-03M": (1, "No machine-readable licence (no LICENSE file, no licence metadata).",
                     4, "SPDX identifier CC-BY-NC-SA-4.0 with rightsURI in DataCite, schema.org license and datapackage.json.", "FsF-R1.1-01M"),
    "RDA-R1.2-01M": (2, "The repository does not name Ergast or Jolpica as the source; no checksums or transformation history. F-UJI FsF-R1.2-01M = 1/1 for GitHub (repository dates only), 0/1 (Jolpica).",
                     4, "DataCite IsDerivedFrom, Created/Collected dates, SHA-256 source manifest of all 93 archive members and a step-by-step cleaning audit log.", "FsF-R1.2-01M"),
    "RDA-R1.2-02M": (1, "No provenance in a cross-community language.",
                     4, "W3C PROV-O provenance graph (JSON-LD): source entity, cleaning activities and derived files.", ""),
    "RDA-R1.3-01M": (2, "No community metadata standard for the dataset. F-UJI FsF-R1.3-01M = 1 (GitHub page metadata only), 0 (Jolpica).",
                     4, "DataCite Metadata Schema 4.5 and schema.org Dataset.", "FsF-R1.3-01M"),
    "RDA-R1.3-01D": (2, "Ergast JSON layout is a de facto F1 community format, but the archive mixes layouts. F-UJI FsF-R1.3-02D = 0.",
                     4, "Tidy CSV following Ergast naming plus ISO 8601 dates and ISO 3166 country codes.", "FsF-R1.3-02D"),
    "RDA-R1.3-02M": (1, "No machine-understandable metadata standard used.",
                     4, "DataCite XML validated against the official XSD; schema.org JSON-LD.", ""),
    "RDA-R1.3-02D": (2, "JSON keys follow Ergast conventions, but there is no machine-readable schema.",
                     4, "Frictionless Data Package / Table Schema with types, primary and foreign keys.", ""),
}

GAPS = [
    {"gap_id": "G1", "title": "No persistent identifier for the data or metadata",
     "indicators": "RDA-F1-01D; RDA-F1-01M; RDA-F3-01M; RDA-A1-03D",
     "evidence": "F-UJI FsF-F1-02MD = 0 for the GitHub archive, the Jolpica API and even the Kaggle mirror; data are only reachable by mutable URLs. The group's Zenodo deposit of the raw archive (DOI 10.5281/zenodo.23416916, 16 Oct 2026) scores 1 and lifts the archive to 84.6% overall (F-UJI v0.8).",
     "improvement": "Use the Zenodo DOI as the identifier of the source archive (cited IsDerivedFrom and in PROV-O), and deposit the curated package as its own Zenodo record to mint a versioned DOI and a concept DOI; cite both in README and CITATION.cff.",
     "status_in_package": "Raw archive: implemented (DOI minted by the group, byte-identical to data/source). Curated package: prepared (DataCite record cites the raw DOI; own DOI placeholder)."},
    {"gap_id": "G2", "title": "Missing and conflicting licence information",
     "indicators": "RDA-R1.1-01M; RDA-R1.1-02M; RDA-R1.1-03M",
     "evidence": "Jolpica TERMS.md (27 Aug 2025): data licensed CC BY-NC-SA 4.0. The group's README declares 'MIT License' for everything; the Kaggle mirror declares CC0 although Ergast allowed non-commercial use only; the group's Zenodo record declares CC BY 4.0, which drops the non-commercial and share-alike conditions. F-UJI FsF-R1.1-01M = 0 for GitHub and Jolpica and 1 for Kaggle and Zenodo, because it checks that a licence is present, not that it is compatible.",
     "improvement": "License the data CC BY-NC-SA 4.0 (ShareAlike obliges it), add LICENSE-DATA with the SPDX id CC-BY-NC-SA-4.0 and the legal-code URI, keep MIT for code only, and attribute Jolpica-F1 and Ergast.",
     "status_in_package": "Implemented in DataCite rightsList, schema.org license and datapackage.json; the Zenodo record's licence must be corrected to CC BY-NC-SA 4.0 (a metadata edit, the DOI does not change)."},
    {"gap_id": "G3", "title": "No machine-readable, standard dataset metadata",
     "indicators": "RDA-F2-01M; RDA-F4-01M; RDA-I1-01M; RDA-R1-01M; RDA-R1.3-01M; RDA-R1.3-02M",
     "evidence": "Only a pipeline README; F-UJI FsF-F2-01M = 0/2 (GitHub, Jolpica); FsF-R1-01M = 1/2 (GitHub) and 0/2 (Jolpica).",
     "improvement": "Ship a DataCite 4.5 record (XML validated against the XSD), schema.org Dataset JSON-LD for search engines and a Frictionless Data Package with a full data dictionary.",
     "status_in_package": "Implemented."},
    {"gap_id": "G4", "title": "Non-standard vocabularies inside the data",
     "indicators": "RDA-I2-01D; RDA-I1-02D",
     "evidence": "Country values 'UK', 'USA', 'UAE', 'Korea'; nationalities as lowercase demonyms including former states ('east german', 'rhodesian'); 136 free-text status values mixing laps-behind with failure causes.",
     "improvement": "Add ISO 3166-1 alpha-3 codes (ISO 3166-3 for former states), Wikidata QIDs, and an 8-category status vocabulary; publish the status vocabulary as SKOS.",
     "status_in_package": "ISO codes, QIDs and status groups implemented; SKOS publication proposed."},
    {"gap_id": "G5", "title": "No provenance or integrity information",
     "indicators": "RDA-R1.2-01M; RDA-R1.2-02M",
     "evidence": "The repository never names Ergast or Jolpica as the source; no checksums; no record of transformations; the original Ergast terms page now returns 404.",
     "improvement": "Record derivation (DataCite IsDerivedFrom), SHA-256 checksums of every source and output file, the cleaning audit log, and a W3C PROV-O graph.",
     "status_in_package": "Implemented."},
    {"gap_id": "G6", "title": "Unqualified and partly broken links to external entities",
     "indicators": "RDA-I3-01D; RDA-I3-02D",
     "evidence": "861 of 864 driver URLs use http; 12 entities have no URL; 1 driver URL is a Wikipedia talk page (monarch); 2 constructor pages no longer exist (Hall, Turner).",
     "improvement": "Normalise to https and add Wikidata QIDs as persistent entity identifiers; flag unresolved links for manual curation.",
     "status_in_package": "Implemented (QID crosswalk in data/reference/)."},
    {"gap_id": "G7", "title": "No guarantee that metadata outlives the data",
     "indicators": "RDA-A2-01M",
     "evidence": "The Ergast API was shut down and is only mirrored by a volunteer project (Jolpica) that 'does not guarantee uptime'; GitHub repositories can be deleted.",
     "improvement": "Deposit in a certified repository (Zenodo/CERN) whose policy keeps metadata and a tombstone page after withdrawal.",
     "status_in_package": "Raw archive deposited in Zenodo by the group (16 Oct 2026); deposit of the curated package proposed."},
]


def load_indicators() -> pd.DataFrame:
    """Official indicator list; extracted from the RDA workbook once and cached as CSV."""
    if RDA_WORKBOOK.exists():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            raw = pd.read_excel(RDA_WORKBOOK, sheet_name="FAIR Indicators_v0.05", dtype=str)
        table = raw[raw["INDICATOR_ID"].fillna("").str.startswith("RDA-")]
        indicators = pd.DataFrame({
            "indicator_id": table["INDICATOR_ID"].str.strip(),
            "principle": table["PRINCIPLE"].str.strip(),
            "area": table["INDICATOR_ID"].str.extract(r"RDA-([FAIR])")[0],
            "indicator": table["INDICATORS"].str.strip(),
            "priority": table["PRIORITY"].str.strip(),
        }).reset_index(drop=True)
        indicators["source"] = RDA_SOURCE
        indicators.to_csv(RDA_INDICATORS_CSV, index=False)
    indicators = pd.read_csv(RDA_INDICATORS_CSV)
    if len(indicators) != 41:
        raise ValueError(f"Expected 41 RDA indicators, found {len(indicators)}")
    return indicators


def rda_level(group: pd.DataFrame, score_col: str) -> int:
    """Official RDA area level (0-5): an indicator passes when fully implemented (4) or not applicable (0)."""
    passed = group[score_col].isin([0, 4])
    share = {p: passed[group["priority"] == p].mean() if (group["priority"] == p).any() else 1.0
             for p in ("Essential", "Important", "Useful")}
    if share["Essential"] < 1:
        return 0
    if share["Important"] < 0.5:
        return 1
    if share["Important"] < 1:
        return 2
    if share["Useful"] < 0.5:
        return 3
    if share["Useful"] < 1:
        return 4
    return 5


def build_assessment() -> pd.DataFrame:
    indicators = load_indicators()
    missing = set(indicators["indicator_id"]) ^ set(ASSESSMENT)
    if missing:
        raise ValueError(f"Assessment and official indicator list differ: {sorted(missing)}")
    rows = []
    for _, ind in indicators.iterrows():
        s_a, ev_a, s_c, ev_c, fuji = ASSESSMENT[ind["indicator_id"]]
        rows.append({**ind.to_dict(), "score_as_obtained": s_a, "maturity_as_obtained": MATURITY_LABELS[s_a],
                     "evidence_as_obtained": ev_a, "score_curated": s_c,
                     "maturity_curated": MATURITY_LABELS[s_c], "evidence_curated": ev_c,
                     "related_fuji_metric": fuji})
    return pd.DataFrame(rows)


def summarise(assessment: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for area, group in assessment.groupby("area", sort=False):
        row = {"area": {"F": "Findable", "A": "Accessible", "I": "Interoperable", "R": "Reusable"}[area],
               "indicators": len(group)}
        for state in ("as_obtained", "curated"):
            col = f"score_{state}"
            applicable = group[group[col] > 0]
            row[f"{state}_progress_percent"] = round(100 * applicable[col].sum() / (4 * len(applicable)), 1)
            row[f"{state}_fully_implemented"] = int((group[col] == 4).sum())
            row[f"{state}_essential_passed"] = (
                f"{int(((group['priority'] == 'Essential') & group[col].isin([0, 4])).sum())}"
                f"/{int((group['priority'] == 'Essential').sum())}")
            row[f"{state}_rda_level"] = rda_level(group, col)
        rows.append(row)
    summary = pd.DataFrame(rows)
    total = {"area": "Overall", "indicators": len(assessment)}
    for state in ("as_obtained", "curated"):
        col = f"score_{state}"
        total[f"{state}_progress_percent"] = round(100 * assessment[col].sum() / (4 * len(assessment)), 1)
        total[f"{state}_fully_implemented"] = int((assessment[col] == 4).sum())
        total[f"{state}_essential_passed"] = (
            f"{int(((assessment['priority'] == 'Essential') & assessment[col].isin([0, 4])).sum())}"
            f"/{int((assessment['priority'] == 'Essential').sum())}")
        total[f"{state}_rda_level"] = None
    return pd.concat([summary, pd.DataFrame([total])], ignore_index=True)


def _style_axes(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=MUTED, length=0, labelsize=9)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_rda_summary(summary: pd.DataFrame, path) -> None:
    """Grouped horizontal bars: maturity progress per FAIR area, as obtained vs curated."""
    areas = summary[summary["area"] != "Overall"].reset_index(drop=True)
    states = (("as_obtained", "As obtained (GitHub archive + Jolpica API)"),
              ("curated", "Curated package (this project)"))
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    fig, ax = plt.subplots(figsize=(8.6, 4.4), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    _style_axes(ax)
    bar_h, gap = 0.34, 0.04
    y_centers = list(range(len(areas)))[::-1]
    for i, (state, label) in enumerate(states):
        offsets = [y + (bar_h + gap) / 2 * (1 if i == 0 else -1) for y in y_centers]
        values = areas[f"{state}_progress_percent"]
        ax.barh(offsets, values, height=bar_h, color=SERIES[i], edgecolor=SURFACE, linewidth=2, label=label)
        for y, v, lvl in zip(offsets, values, areas[f"{state}_rda_level"]):
            ax.text(v + 1.2, y, f"{v:.0f}%  ·  RDA level {lvl}", va="center", ha="left", fontsize=8.5, color=INK_2)
    ax.set_yticks(y_centers, [f"{a}  ({n} indicators)" for a, n in zip(areas["area"], areas["indicators"])],
                  color=INK, fontsize=9.5)
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("Maturity progress (sum of indicator scores / maximum, RDA 0-4 scale)", color=INK_2, fontsize=9)
    overall = summary[summary["area"] == "Overall"].iloc[0]
    fig.suptitle("FAIR maturity of the F1 results dataset before and after curation", x=0.02, ha="left",
                 fontsize=12.5, color=INK, fontweight="bold", y=0.98)
    fig.text(0.02, 0.905, f"RDA FAIR Data Maturity Model, 41 indicators. Overall progress "
             f"{overall['as_obtained_progress_percent']:.0f}% -> {overall['curated_progress_percent']:.0f}%; "
             "items that need the Zenodo DOI are scored 'in implementation'.",
             fontsize=8.5, color=INK_2, ha="left")
    ax.legend(loc="lower center", bbox_to_anchor=(0.45, -0.36), ncol=2, frameon=False, fontsize=8.5,
              labelcolor=INK_2, handlelength=1.2)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)


def plot_fuji_summary(path) -> None:
    """Grouped bars: F-UJI score per FAIR principle for each evaluated resource."""
    fuji = pd.read_csv(config.FAIR_DIR / "fuji_summary.csv")
    labels = {"github_repository": "Group GitHub repository (raw zip)",
              "jolpica_ergast_api": "Jolpica Ergast API (download source)",
              "kaggle_ergast_mirror": "Kaggle Ergast mirror",
              "zenodo_raw_archive": "Group Zenodo record of the raw zip (DOI)"}
    principles = (("F_percent", "Findable"), ("A_percent", "Accessible"), ("I_percent", "Interoperable"),
                  ("R_percent", "Reusable"), ("fair_percent", "Overall FAIR"))
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    fig, ax = plt.subplots(figsize=(8.6, 5.0), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    _style_axes(ax)
    ax.xaxis.grid(False)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    width = 0.8 / len(fuji)
    for i, (_, row) in enumerate(fuji.iterrows()):
        xs = [p + (i - (len(fuji) - 1) / 2) * width for p in range(len(principles))]
        vals = [row[c] for c, _ in principles]
        ax.bar(xs, vals, width=width, color=SERIES[i], edgecolor=SURFACE, linewidth=2,
               label=f"{labels.get(row['resource'], row['resource'])}: {row['fair_percent']:.1f}% overall")
        ax.text(xs[-1], vals[-1] + 2, f"{vals[-1]:.1f}%", ha="center", fontsize=7.5, color=INK_2)
    ax.set_xticks(range(len(principles)), [n for _, n in principles], color=INK, fontsize=9.5)
    ax.set_ylim(0, 106)
    ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_ylabel("F-UJI score (% of points earned)", color=INK_2, fontsize=9)
    when = pd.to_datetime(fuji["evaluated_at_utc"]).max().strftime("%d %b %Y").lstrip("0")
    fig.suptitle(f"Automated FAIR assessment with F-UJI (metrics v{fuji['metric_version'].iloc[0]})", x=0.02,
                 ha="left", fontsize=12.5, color=INK, fontweight="bold", y=0.98)
    fig.text(0.02, 0.915, f"Evaluated on {when} with a local F-UJI {fuji['software_version'].iloc[0]} server "
             "(same metric version as f-uji.net); raw JSON in outputs/component_a_fair/fuji/.",
             fontsize=8.5, color=INK_2, ha="left")
    handles, legend_labels = ax.get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="upper left", bbox_to_anchor=(0.02, 0.89), ncol=1, frameon=False,
               fontsize=8.5, labelcolor=INK_2, handlelength=1.2)
    fig.tight_layout(rect=(0, 0, 1, 0.80))
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)


def write_gaps() -> pd.DataFrame:
    gaps = pd.DataFrame(GAPS)
    gaps.to_csv(config.FAIR_DIR / "fair_gaps.csv", index=False)
    lines = ["# FAIR compliance gaps and improvement proposals", ""]
    for g in GAPS:
        lines += [f"## {g['gap_id']} - {g['title']}", "",
                  f"- **RDA indicators:** {g['indicators']}",
                  f"- **Evidence:** {g['evidence']}",
                  f"- **Improvement:** {g['improvement']}",
                  f"- **Status in delivered package:** {g['status_in_package']}", ""]
    (config.FAIR_DIR / "fair_gaps.md").write_text("\n".join(lines), encoding="utf-8")
    return gaps


def run() -> pd.DataFrame:
    config.ensure_dirs()
    assessment = build_assessment()
    assessment.to_csv(config.FAIR_DIR / "rda_fair_assessment.csv", index=False)
    summary = summarise(assessment)
    summary.to_csv(config.FAIR_DIR / "rda_fair_summary.csv", index=False)
    write_gaps()
    plot_rda_summary(summary, config.FAIR_DIR / "fig_a1_rda_fair_maturity.png")
    if (config.FAIR_DIR / "fuji_summary.csv").exists():
        plot_fuji_summary(config.FAIR_DIR / "fig_a2_fuji_scores.png")
    print(summary.to_string(index=False))
    return summary


if __name__ == "__main__":
    run()
