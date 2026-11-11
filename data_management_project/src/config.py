"""Central configuration: every path and constant used by the pipeline lives here."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SOURCE_ARCHIVE = PROJECT_ROOT / "data" / "source" / "racing_f1_data.zip"
SOURCE_ARCHIVE_SHA256 = "81b027c4221901d92d30ad7b76eacf22668d299098e5c16dcb391c91fd39c748"
ARCHIVE_PREFIX = "bronze/landing/"

RAW_DIR = PROJECT_ROOT / "data" / "raw"
CLEAN_DIR = PROJECT_ROOT / "data" / "cleaned"
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"

OUTPUT_DIR = PROJECT_ROOT / "outputs"
FAIR_DIR = OUTPUT_DIR / "component_a_fair"
QUALITY_DIR = OUTPUT_DIR / "component_b_quality"
QUALITY_FIG_DIR = QUALITY_DIR / "figures"
CLEANING_DIR = OUTPUT_DIR / "component_c_cleaning"
GRAPH_DIR = OUTPUT_DIR / "graph"
GRAPH_FIG_DIR = GRAPH_DIR / "figures"
REPORT_DIR = PROJECT_ROOT / "report"

RAW_RESULTS_CSV = RAW_DIR / "f1_race_results_raw.csv"
RAW_RACES_CSV = RAW_DIR / "races_raw.csv"
RAW_CIRCUITS_CSV = RAW_DIR / "circuits_raw.csv"
RAW_DRIVERS_CSV = RAW_DIR / "drivers_raw.csv"
RAW_CONSTRUCTORS_CSV = RAW_DIR / "constructors_raw.csv"
SOURCE_MANIFEST_CSV = RAW_DIR / "source_manifest.csv"

CLEAN_RESULTS_CSV = CLEAN_DIR / "f1_race_results_clean.csv"
CLEAN_RACES_CSV = CLEAN_DIR / "races_clean.csv"
CLEAN_CIRCUITS_CSV = CLEAN_DIR / "circuits_clean.csv"
CLEAN_DRIVERS_CSV = CLEAN_DIR / "drivers_clean.csv"
CLEAN_CONSTRUCTORS_CSV = CLEAN_DIR / "constructors_clean.csv"

# Snapshot boundary: the results fact table covers complete seasons 1950-2025.
FIRST_SEASON = 1950
LAST_COMPLETE_SEASON = 2025

RANDOM_SEED = 42

# Group members. All three worked jointly on every component; "component" is the block each member
# presents. Metadata, report and slides read this list - edit here, then re-run run_all.py.
TEAM = [
    {"component": "A", "title": "FAIR assessment and metadata design",
     "given_name": "Chirag", "family_name": "Adhikari", "orcid": "TO-BE-ADDED"},
    {"component": "B", "title": "Data quality and profiling",
     "given_name": "Manohar", "family_name": "Zalki", "orcid": "TO-BE-ADDED"},
    {"component": "C", "title": "Data cleaning and pipeline",
     "given_name": "Nicolas", "family_name": "Bonilla", "orcid": "TO-BE-ADDED"},
]
JOINT_WORK = True
TEAM_NAMES = ", ".join(f"{m['given_name']} {m['family_name']}" for m in TEAM)
# Repository layout: <repo>/data_management_project + <repo>/dashboard.
# Submission ZIP layout: F1_DataManagement_Group/ holds src/ and dashboard/ side by side.
DASHBOARD_DIR = (PROJECT_ROOT / "dashboard" if (PROJECT_ROOT / "dashboard" / "build_web_data.py").exists()
                 else PROJECT_ROOT.parent / "dashboard")
COURSE = "Data Management, Winter 2026/27"
INSTITUTION = "SRH University"


SOFFICE_CANDIDATES = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
)


def find_soffice() -> str | None:
    """LibreOffice binary for the Word/PowerPoint -> PDF conversion, on Windows, macOS or Linux."""
    import shutil
    found = shutil.which("soffice") or shutil.which("libreoffice")
    return found or next((p for p in SOFFICE_CANDIDATES if Path(p).exists()), None)


def ensure_dirs() -> None:
    for d in (RAW_DIR, CLEAN_DIR, REFERENCE_DIR, FAIR_DIR, QUALITY_DIR, QUALITY_FIG_DIR,
              CLEANING_DIR, GRAPH_DIR, GRAPH_FIG_DIR, REPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)
