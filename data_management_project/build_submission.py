"""Package the group submission ZIP (deliverables 1-8 of the assignment).

Reflection logs (deliverable 9) are submitted individually and are therefore NOT included.

    python build_submission.py
"""
from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

from docx import Document
from docx.shared import Pt

from src import config

ROOT = config.PROJECT_ROOT
DIST = ROOT / "dist"
ZIP_PATH = DIST / "F1_DataManagement_Group_Submission.zip"

INCLUDE = [
    "README.md", "requirements.txt", "run_all.py", "build_submission.py",
    "src/*.py", "src/assistant/*.py", "tests/*.py",
    "data/source/*", "data/raw/*", "data/cleaned/*", "data/reference/**/*",
    "outputs/**/*",
    "report/*.docx", "report/*.pdf", "report/presentation/*",
]
EXCLUDE = re.compile(r"(__pycache__|\.pytest_cache|\.pyc$|~\$|api\.log$|\.lo_profile)")
DASHBOARD_INCLUDE = ["app.py", "build_web_data.py", "static/*", "static/vendor/*"]


def reflection_docx() -> None:
    """Word versions of the reflection drafts for each student to personalise (not part of the ZIP)."""
    for md in sorted((config.REPORT_DIR / "reflection_drafts").glob("*.md")):
        doc = Document()
        doc.styles["Normal"].font.name = "Calibri"
        doc.styles["Normal"].font.size = Pt(11)
        for block in md.read_text(encoding="utf-8").split("\n\n"):
            block = block.strip()
            if not block:
                continue
            if block.startswith("# "):
                doc.add_heading(block[2:], level=1)
                continue
            para = doc.add_paragraph()
            text = " ".join(line.lstrip("> ").strip() for line in block.splitlines())
            for part in re.split(r"(\*\*[^*]+\*\*)", text):
                run = para.add_run(part.strip("*") if part.startswith("**") else part)
                run.bold = part.startswith("**")
                run.italic = block.startswith(">")
        doc.save(md.with_suffix(".docx"))


def main() -> None:
    reflection_docx()
    DIST.mkdir(exist_ok=True)
    files = sorted({p for pattern in INCLUDE for p in ROOT.glob(pattern)
                    if p.is_file() and not EXCLUDE.search(p.as_posix())})
    dash_files = sorted({p for pattern in DASHBOARD_INCLUDE for p in config.DASHBOARD_DIR.glob(pattern)
                         if p.is_file() and not EXCLUDE.search(p.as_posix())})
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            zf.write(path, Path("F1_DataManagement_Group") / path.relative_to(ROOT))
        for path in dash_files:
            zf.write(path, Path("F1_DataManagement_Group") / "dashboard" / path.relative_to(config.DASHBOARD_DIR))
    files += dash_files
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    print(f"[submission] {len(files)} files -> {ZIP_PATH.relative_to(ROOT)} "
          f"({ZIP_PATH.stat().st_size / 1e6:.1f} MB, sha256 {digest[:16]}...)")
    publish_documents()


FINAL_DOCS = [
    ("report/F1_Data_Management_Joint_Report.pdf", "Joint report (PDF)"),
    ("report/F1_Data_Management_Joint_Report.docx", "Joint report (Word)"),
    ("report/presentation/F1_Data_Management_Presentation.pdf", "Presentation (PDF)"),
    ("report/presentation/F1_Data_Management_Presentation.pptx", "Presentation (PowerPoint)"),
    ("report/presentation/presenter_script.md", "Presenter script, who says what"),
    ("report/qa_preparation.md", "Q&A preparation"),
    ("report/zenodo_record_corrections.md", "Corrections for the group's Zenodo record (licence, title, creators)"),
    ("dist/F1_DataManagement_Group_Submission.zip", "Submission ZIP for the course portal"),
]


def publish_documents() -> None:
    """Copy the final documents to <repo>/00_FINAL_DOCUMENTS so they are the first thing seen on GitHub."""
    repo = ROOT.parent
    if ROOT.name != "data_management_project" or not (repo / "dashboard").is_dir():
        return  # running from the unzipped submission: nothing to publish
    target = repo / "00_FINAL_DOCUMENTS"
    (target / "reflection_drafts").mkdir(parents=True, exist_ok=True)
    rows = []
    for rel, label in FINAL_DOCS:
        src = ROOT / rel
        (target / src.name).write_bytes(src.read_bytes())
        rows.append(f"| [{src.name}]({src.name}) | {label} |")
    for src in sorted((config.REPORT_DIR / "reflection_drafts").glob("*.docx")):
        (target / "reflection_drafts" / src.name).write_bytes(src.read_bytes())
        rows.append(f"| [reflection_drafts/{src.name}](reflection_drafts/{src.name}) | Reflection draft to personalise |")
    (target / "README.md").write_text(
        "# Final documents - Data Management project (SRH, Winter 2026/27)\n\n"
        f"Group: {config.TEAM_NAMES}.\n\n| File | What it is |\n|---|---|\n" + "\n".join(rows) + "\n\n"
        "Copies of the files generated in `data_management_project/` (refreshed by `python build_submission.py`).\n"
        "To reproduce everything, see the README at the top of the repository.\n", encoding="utf-8")
    print(f"[submission] final documents copied to {target.name}/")


if __name__ == "__main__":
    main()
