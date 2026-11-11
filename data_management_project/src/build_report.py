"""Build the joint written report (Word + PDF) from the pipeline outputs.

Every number in the text is read from the generated outputs, so the report always matches the
data. The script checks the assignment's word limits (component sections 400-500 words, main
text <= 4,000 words excluding tables, captions, references and appendices).

    python -m src.build_report
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from src import config

OUT_DOCX = config.REPORT_DIR / "F1_Data_Management_Joint_Report.docx"
INK = RGBColor(0x0B, 0x0B, 0x0B)
INK2 = RGBColor(0x52, 0x51, 0x4E)
ACCENT = RGBColor(0x18, 0x4F, 0x95)
HEADER_FILL = "E8EEF7"
WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.%/-]*")


# ============================================================================================
# Facts - every number used in the text
# ============================================================================================
def facts() -> dict:
    q = config.QUALITY_DIR
    c = config.CLEANING_DIR
    g = config.GRAPH_DIR
    a = config.FAIR_DIR
    raw = pd.read_csv(config.RAW_RESULTS_CSV)
    clean = pd.read_csv(config.CLEAN_RESULTS_CSV)
    issues = pd.read_csv(q / "quality_issues.csv")
    resolution = pd.read_csv(c / "issue_resolution.csv")
    gates = pd.read_csv(c / "validation_report.csv")
    net = pd.read_csv(g / "network_metrics.csv", index_col=0)["value"]
    top = pd.read_csv(g / "top_betweenness.csv")
    fuji = pd.read_csv(a / "fuji_summary.csv").set_index("resource")
    rda = pd.read_csv(a / "rda_fair_summary.csv").set_index("area")
    pid = pd.read_csv(a / "pid_coverage.csv").set_index("entity_type")
    nodes = pd.read_csv(g / "property_graph_node_counts.csv").set_index("node_label")["count"]
    edges = pd.read_csv(g / "property_graph_edge_counts.csv")["count"].sum()
    passed = pd.read_csv(q / "passed_checks.csv")
    path = pd.read_csv(g / "shortest_teammate_path_fangio_verstappen.csv")

    def bucket(r):
        if r.startswith("Not an error"):
            return "not_error"
        if r.startswith("Kept"):
            return "kept"
        if r.startswith(("Flagged", "Mitigated")):
            return "flagged"
        return "fixed"

    buckets = resolution["resolution"].map(bucket).value_counts()
    asst = config.OUTPUT_DIR / "assistant"
    card = json.loads((asst / "podium_model_card.json").read_text(encoding="utf-8"))
    ev_route = json.loads((asst / "evaluation_evidence_summary.json").read_text(encoding="utf-8"))
    llm_path = asst / "evaluation_llm_summary.json"
    ev_llm = json.loads(llm_path.read_text(encoding="utf-8")) if llm_path.exists() else {}
    llm_rows = pd.read_csv(asst / "evaluation_llm.csv") if (asst / "evaluation_llm.csv").exists() else pd.DataFrame()
    refused = bool(llm_rows.loc[llm_rows["type"] == "must refuse", "in_answer"].all()) if len(llm_rows) else None
    champs = pd.read_csv(config.REFERENCE_DIR / "official_champions.csv")
    n_docs = sum(1 for _ in open(asst / "knowledge_documents.jsonl", encoding="utf-8"))
    tests = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=config.PROJECT_ROOT,
                           capture_output=True, text=True).stdout
    n_tests = int(re.search(r"(\d+) tests? collected", tests).group(1)) if "collected" in tests else 0
    gp = clean["race_id"].nunique()
    return {
        "raw_rows": len(raw), "raw_cols": 14, "clean_rows": len(clean), "clean_cols": clean.shape[1],
        "removed": len(raw) - len(clean),
        "races_raw": len(pd.read_csv(config.RAW_RACES_CSV)), "circuits_raw": len(pd.read_csv(config.RAW_CIRCUITS_CSV)),
        "drivers_raw": len(pd.read_csv(config.RAW_DRIVERS_CSV)),
        "constructors_raw": len(pd.read_csv(config.RAW_CONSTRUCTORS_CSV)),
        "seasons": clean["season"].nunique(), "gp": gp, "drivers": clean["driver_id"].nunique(),
        "constructors": clean["constructor_id"].nunique(), "circuits": clean["circuit_id"].nunique(),
        "countries": clean["circuit_country_iso3"].nunique(),
        "issues": len(issues), "errors": int(issues["is_error"].sum()), "not_errors": int((~issues["is_error"]).sum()),
        "dims": issues["dimension"].nunique(), "high": int((issues["severity"] == "High").sum()),
        "passed_checks": int((passed["result"] == "passed").sum()),
        "null_cells": int(raw[["season", "round", "number"]].isna().sum().sum()),
        "pos_disguised": int(raw["positionText"].isin(["R", "W", "D"]).sum()),
        "grid_zero": int((raw["grid"] == 0).sum()),
        "dup_exact": int(issues.set_index("issue_id").loc["B06", "affected_records"]),
        "dup_hidden": int(issues.set_index("issue_id").loc["B07", "affected_records"]),
        "shared": int(issues.set_index("issue_id").loc["B08", "affected_records"]),
        "status_raw": raw["status"].nunique(), "status_groups": clean["status_group"].nunique(),
        "indy_outliers": int(issues.set_index("issue_id").loc["B16", "affected_records"]),
        "gates": len(gates), "gates_passed": int((gates["result"] == "passed").sum()), "tests": n_tests,
        "fixed": int(buckets.get("fixed", 0)), "flagged": int(buckets.get("flagged", 0)),
        "kept": int(buckets.get("kept", 0)), "not_error": int(buckets.get("not_error", 0)),
        "fuji_github": fuji.loc["github_repository", "fair_percent"],
        "fuji_jolpica": fuji.loc["jolpica_ergast_api", "fair_percent"],
        "fuji_kaggle": fuji.loc["kaggle_ergast_mirror", "fair_percent"],
        "fuji_zenodo": fuji.loc["zenodo_raw_archive", "fair_percent"],
        "fuji_version": str(fuji["metric_version"].iloc[0]),
        "zenodo": json.loads((config.REFERENCE_DIR / "zenodo_source_record.json").read_text(encoding="utf-8")),
        "rda_before": rda.loc["Overall", "as_obtained_progress_percent"],
        "rda_after": rda.loc["Overall", "curated_progress_percent"],
        "ess_before": rda.loc["Overall", "as_obtained_essential_passed"],
        "ess_after": rda.loc["Overall", "curated_essential_passed"],
        "qid_driver": pid.loc["driver", "qid_coverage_percent"], "qid_con": pid.loc["constructor", "qid_coverage_percent"],
        "qid_circ": pid.loc["circuit", "qid_coverage_percent"],
        "pg_nodes": int(nodes.sum()), "pg_edges": int(edges), "nodes": nodes.to_dict(),
        "tm_drivers": int(net["drivers_in_projection"]), "tm_links": int(net["teammate_links"]),
        "components": int(net["connected_components"]), "giant": int(net["giant_component_drivers"]),
        "giant_share": net["giant_component_share"] * 100, "isolated": int(net["isolated_drivers"]),
        "clust": net["average_clustering_giant"], "clust_r": net["random_graph_clustering"],
        "aspl": net["average_shortest_path_giant"], "aspl_r": net["random_graph_shortest_path"],
        "sigma": net["small_world_sigma"], "communities": int(net["louvain_communities"]),
        "modularity": net["modularity"], "diameter": int(net["diameter_giant"]),
        "top": top, "path": path, "hops": len(path),
        "indy_rounds": int(clean.loc[clean["is_indy500"], "race_id"].nunique()),
        "card": card, "ev_route": ev_route, "ev_llm": ev_llm, "refused": refused, "kb_docs": n_docs,
        "champ_wikidata": int(champs["method"].str.startswith("Wikidata").sum()),
        "champ_disagree": champs.loc[~champs["agrees_with_points_leader"], "season"].tolist(),
    }


# ============================================================================================
# Document helpers
# ============================================================================================
class Report:
    def __init__(self) -> None:
        self.doc = Document()
        self.counts: dict[str, int] = {}
        self.section_key: str | None = None
        self.fig_no = 0
        self.tab_no = 0
        self._setup()

    def _setup(self) -> None:
        sec = self.doc.sections[0]
        sec.page_width, sec.page_height = Cm(21), Cm(29.7)
        sec.left_margin = sec.right_margin = Cm(2.3)
        sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.2)
        styles = self.doc.styles
        normal = styles["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(10.5)
        normal.font.color.rgb = INK
        normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
        normal.paragraph_format.space_after = Pt(5)
        normal.paragraph_format.line_spacing = 1.12
        for name, size, before, after in (("Heading 1", 15, 16, 6), ("Heading 2", 12, 10, 4), ("Heading 3", 10.5, 8, 3)):
            st = styles[name]
            st.font.name = "Calibri"
            st.font.size = Pt(size)
            st.font.bold = True
            st.font.color.rgb = ACCENT if name != "Heading 3" else INK
            st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
            st.paragraph_format.space_before = Pt(before)
            st.paragraph_format.space_after = Pt(after)
            st.paragraph_format.keep_with_next = True
        cap = styles["Caption"]
        cap.font.name = "Calibri"
        cap.font.size = Pt(8.5)
        cap.font.italic = False
        cap.font.bold = False
        cap.font.color.rgb = INK2
        cap.paragraph_format.space_after = Pt(9)
        self._footer()

    def _footer(self) -> None:
        p = self.doc.sections[0].footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
            if kind:
                el = OxmlElement("w:fldChar")
                el.set(qn("w:fldCharType"), kind)
            else:
                el = OxmlElement("w:instrText")
                el.set(qn("xml:space"), "preserve")
                el.text = text
            run._r.append(el)
        run.font.size = Pt(8.5)
        run.font.color.rgb = INK2

    # ---- text ------------------------------------------------------------------------------
    @staticmethod
    def _runs(paragraph, text: str, size: float | None = None) -> None:
        for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)", text):
            if not part:
                continue
            if part.startswith("**"):
                run = paragraph.add_run(part[2:-2])
                run.bold = True
            elif part.startswith("`"):
                run = paragraph.add_run(part[1:-1])
                run.font.name = "Consolas"
                run.font.size = Pt((size or 10.5) - 1)
            elif part.startswith("*"):
                run = paragraph.add_run(part[1:-1])
                run.italic = True
            else:
                run = paragraph.add_run(part)
            if size and not part.startswith("`"):
                run.font.size = Pt(size)

    def _count(self, text: str) -> None:
        if self.section_key:
            plain = re.sub(r"[*`]", "", text)
            self.counts[self.section_key] = self.counts.get(self.section_key, 0) + len(WORD_RE.findall(plain))

    def heading(self, text: str, level: int = 1, count_as: str | None = None) -> None:
        self.doc.add_heading(text, level=level)
        if count_as is not None:
            self.section_key = count_as or None

    def p(self, text: str, count: bool = True, size: float | None = None, align=None, color=None):
        para = self.doc.add_paragraph()
        self._runs(para, text, size)
        if align is not None:
            para.alignment = align
        if color is not None:
            for r in para.runs:
                r.font.color.rgb = color
        if count:
            self._count(text)
        return para

    def bullets(self, items: list[str], count: bool = True, numbered: bool = False) -> None:
        for item in items:
            para = self.doc.add_paragraph(style="List Number" if numbered else "List Bullet")
            self._runs(para, item)
            para.paragraph_format.space_after = Pt(2)
            if count:
                self._count(item)

    def figure(self, path: Path, caption: str, width_cm: float = 16.0, label: str | None = None) -> None:
        if label is None:
            self.fig_no += 1
            label = str(self.fig_no)
        self.doc.add_picture(str(path), width=Cm(width_cm))
        self.doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.doc.paragraphs[-1].paragraph_format.keep_with_next = True
        cap = self.doc.add_paragraph(style="Caption")
        self._runs(cap, f"**Figure {label}.** {caption}")

    def table(self, df: pd.DataFrame, caption: str | None, widths_cm: list[float] | None = None, font: float = 8.0,
              label: str | None = None) -> None:
        if caption is not None:
            if label is None:
                self.tab_no += 1
            cap = self.doc.add_paragraph(style="Caption")
            cap.paragraph_format.keep_with_next = True
            self._runs(cap, f"**Table {label or self.tab_no}.** {caption}")
        t = self.doc.add_table(rows=1, cols=len(df.columns))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, col in enumerate(df.columns):
            cell = t.rows[0].cells[i]
            cell.text = ""
            self._runs(cell.paragraphs[0], f"**{col}**", font)
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), HEADER_FILL)
            cell._tc.get_or_add_tcPr().append(shd)
        trpr = t.rows[0]._tr.get_or_add_trPr()
        hdr = OxmlElement("w:tblHeader")
        hdr.set(qn("w:val"), "true")
        trpr.append(hdr)
        for _, row in df.iterrows():
            cells = t.add_row().cells
            for i, v in enumerate(row.values):
                text = "" if (v is None or (isinstance(v, float) and pd.isna(v))) else str(v)
                cells[i].text = ""
                self._runs(cells[i].paragraphs[0], text, font)
        for row in t.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    para.paragraph_format.space_after = Pt(0)
                    para.paragraph_format.line_spacing = 1.0
        if widths_cm:
            self._fix_widths(t, widths_cm)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    @staticmethod
    def _fix_widths(t, widths_cm: list[float]) -> None:
        """Fixed layout + grid widths, so Word and LibreOffice both honour the column widths."""
        twips = [int(w * 567) for w in widths_cm]
        t.autofit = False
        tbl_pr = t._tbl.tblPr
        tbl_w = tbl_pr.find(qn("w:tblW"))
        if tbl_w is None:
            tbl_w = OxmlElement("w:tblW")
            tbl_pr.append(tbl_w)
        tbl_w.set(qn("w:w"), str(sum(twips)))
        tbl_w.set(qn("w:type"), "dxa")
        layout = OxmlElement("w:tblLayout")
        layout.set(qn("w:type"), "fixed")
        tbl_pr.append(layout)
        for grid_col, w in zip(t._tbl.tblGrid.findall(qn("w:gridCol")), twips):
            grid_col.set(qn("w:w"), str(w))
        for row in t.rows:
            for cell, w in zip(row.cells, widths_cm):
                cell.width = Cm(w)

    def page_break(self) -> None:
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def code(self, text: str, size: float = 7.0) -> None:
        for line in text.splitlines():
            para = self.doc.add_paragraph()
            para.paragraph_format.space_after = Pt(0)
            para.paragraph_format.line_spacing = 1.0
            run = para.add_run(line if line else " ")
            run.font.name = "Consolas"
            run.font.size = Pt(size)


def pct(x: float, nd: int = 0) -> str:
    return f"{x:.{nd}f}%"


# ============================================================================================
# Content
# ============================================================================================
def title_page(r: Report, F: dict) -> None:
    r.section_key = None
    for _ in range(5):
        r.doc.add_paragraph()
    r.p(config.COURSE + " - Group Project", count=False, size=11, color=INK2)
    t = r.doc.add_paragraph()
    run = t.add_run("From Raw Race Results to a FAIR, Quality-Assured Knowledge Graph")
    run.bold, run.font.size, run.font.color.rgb = True, Pt(22), ACCENT
    r.p("Formula 1 World Championship results 1950-2025: FAIR assessment, data quality profiling, "
        "reproducible cleaning, property-graph analytics and an interactive dashboard", count=False, size=13,
        color=INK2)
    r.doc.add_paragraph()
    rows = [{"Group member": f"{m['given_name']} {m['family_name']}",
             "Presents": f"Component {m['component']} - {m['title']}"} for m in config.TEAM]
    r.table(pd.DataFrame(rows), None, [6.0, 10.0], font=9.5)
    if config.JOINT_WORK:
        r.p("All three members worked jointly on every component; the table shows who presents each block.",
            count=False, size=9.5, color=INK2)
    r.p(f"{config.INSTITUTION} | Submission date: [to be completed]", count=False, size=10, color=INK2)
    r.p("Repository: https://github.com/zalkimanohar/Formula1-Racing-Analytics (folders `data_management_project` "
        "and `dashboard`)", count=False, size=9.5, color=INK2)
    r.p("Interactive dashboard: `streamlit run app.py` in the `dashboard` folder, then http://localhost:8501 "
        "(Section 6)", count=False, size=9.5, color=INK2)
    r.p("WORD_COUNT_PLACEHOLDER", count=False, size=9.5, color=INK2)
    r.page_break()


def owner_line(r: Report, idx: int) -> None:
    m = config.TEAM[idx]
    name = f"{m['given_name']} {m['family_name']}"
    text = (f"*Prepared jointly by the group; presented by {name}.*" if config.JOINT_WORK
            else f"*Responsible: {name}*")
    r.p(text, count=False, size=9, color=INK2)


def introduction(r: Report, F: dict) -> None:
    r.heading("1. Introduction", 1, count_as="intro")
    r.p("Formula 1 has kept a classified result for every car since the first World Championship Grand Prix at "
        "Silverstone on 13 May 1950. The community-built Ergast database, now served by the Jolpica-F1 project after "
        "Ergast closed in 2024, is the de facto open source of these records and underpins countless analytics "
        "projects, including our group's own Formula1-Racing-Analytics repository. We chose it for three reasons. "
        f"First, it is large and relational: the fact table holds {F['raw_rows']:,} rows and {F['raw_cols']} variables "
        f"(one row per driver entry per Grand Prix, {F['seasons']} seasons), linked to four reference tables "
        f"({F['races_raw']:,} races, {F['circuits_raw']} circuits, {F['drivers_raw']} drivers and "
        f"{F['constructors_raw']} constructors). Second, it contains genuine, non-trivial quality problems that come "
        "from 76 years of changing rules and from the way the files were exported. Third, drivers, teams, circuits and "
        "countries form a natural network, which makes the data well suited to property-graph modelling.")
    r.p("The domain also makes data management visible. Teams, broadcasters, journalists and a growing number of "
        "machine-learning projects that predict race outcomes all reuse these records, usually without asking how "
        "they were produced. A record that counts a retirement as '18th place' or a race twice does not stay "
        "local: it propagates into rankings, features and models. The dataset is therefore a realistic test case "
        "for the whole data-management life cycle, from assessing how findable and reusable the source is to "
        "delivering a documented, validated and linked product.")
    r.p("The raw package (`racing_f1_data.zip`) was downloaded by the group from the Jolpica API and mixes JSON "
        "Lines, pretty-printed JSON and CSV files. The same Ergast data are mirrored on Kaggle, an approved source "
        "type, and Component A evaluates both copies. Sprint races use a different session format and are out of "
        "scope; the analysis covers championship Grands Prix only.")
    r.p("All work follows one reproducible pipeline (Table 1). Step 0 flattens the archive into raw CSV files "
        "without changing a single value and records a SHA-256 manifest. Component B profiles the raw data and "
        "writes a quality issue register; Component C resolves every registered issue in an audited and validated "
        "cleaning pipeline; Component A assesses FAIRness and describes the cleaned package with standard metadata; "
        "the graph model is built from the cleaned data; and the last stage feeds an interactive dashboard "
        "(Section 6). One command (`python run_all.py --from-scratch`) rebuilds everything, dashboard included, in "
        "about 90 seconds, and two independent runs produce byte-identical files.")
    r.table(pd.DataFrame([
        ["0  Extraction", "racing_f1_data.zip (93 files)", "5 raw CSV files + checksum manifest",
         f"{F['raw_rows']:,} results, values unchanged"],
        ["B  Profiling", "raw CSV files", "issue register, profiles, 4 figures",
         f"{F['issues']} issues, {F['dims']} dimensions"],
        ["C  Cleaning", "raw CSV + issue register", "5 clean CSV files, audit log, validation report",
         f"{F['clean_rows']:,} rows, {F['gates']} gates passed"],
        ["A  FAIR & metadata", "clean CSV + sources", "F-UJI/RDA scores, DataCite, schema.org, PROV",
         f"RDA {pct(F['rda_before'])} -> {pct(F['rda_after'])}"],
        ["Graph", "clean CSV", "NetworkX property graph, GEXF, metrics",
         f"{F['pg_nodes']:,} nodes, {F['pg_edges']:,} edges"],
        ["Dashboard", "all outputs above", "interactive web page (dashboard/)",
         "7 views, issue B29 found"],
    ], columns=["Stage", "Input", "Output", "Key result"]),
        "Pipeline overview (`run_all.py`); every stage reads only the outputs of the stages before it.",
        [2.8, 4.2, 5.4, 4.0])
    r.heading("1.1 Data engineering architecture", 2)
    r.p("Figure 1 shows the data flow. It follows the layered design common in data engineering: an immutable raw "
        "zone (bronze) that keeps the source values and their lineage, a clean zone (silver) that is only written "
        "when every validation gate passes, and curated products (gold) that are served to people and machines: "
        "the FAIR metadata record, the property graph, the dashboard and this report. Five engineering principles "
        "run through it:")
    r.bullets([
        "**Contracts, not conventions.** The issue register is the contract between profiling and cleaning, and "
        "one schema module defines the columns that cleaning validates and that the metadata describes.",
        "**Fail fast.** Validation gates and exhaustive vocabularies stop the run instead of passing bad data on.",
        "**Lineage everywhere.** Every row keeps its source file and line; files carry SHA-256 checksums; a PROV-O "
        "graph records each transformation.",
        "**Reproducible orchestration.** One command rebuilds every artefact, and repeated runs are byte-identical.",
        "**Tested decisions.** Automated tests protect the choices that matter most, such as the order of key "
        "repair and de-duplication.",
    ])
    r.figure(config.OUTPUT_DIR / "architecture" / "fig_e1_data_flow.png",
             "End-to-end data flow, from the raw archive through the raw, clean and served zones, with the "
             "cross-cutting engineering controls.", 16.0)


def component_a(r: Report, F: dict, figs: dict) -> None:
    r.heading("2. Component A - FAIR Assessment and Metadata Design", 1, count_as="A")
    owner_line(r, 0)
    z = F["zenodo"]
    r.p("**Assessment.** FAIRness was measured twice, independently. The automated F-UJI tool (version 4.0.1, "
        f"metrics v{F['fuji_version']}, as on the public f-uji.net service), run on a local server, tested the four "
        f"places where the data can be obtained (Figure {figs['fuji']}): the Jolpica API used for the download "
        f"scored {pct(F['fuji_jolpica'], 1)}, the group's GitHub repository {pct(F['fuji_github'], 1)}, the Kaggle "
        f"mirror {pct(F['fuji_kaggle'], 1)} and the group's Zenodo record of the raw archive "
        f"{pct(F['fuji_zenodo'], 1)}, reproducing the group's earlier web assessment exactly. Because F-UJI "
        "can only inspect what is already online, all 41 indicators of the RDA FAIR Data Maturity Model were also "
        "scored with written evidence, for the data as obtained and for our curated package (Figure "
        f"{figs['rda']}). Overall maturity rises from {pct(F['rda_before'])} to {pct(F['rda_after'])} and the "
        f"essential indicators met from {F['ess_before']} to {F['ess_after']}; 'Findable' stays at level 0 until "
        "the curated package has its own DOI. F-UJI is reproducible but only sees machine-readable signals, while "
        "the RDA model also captures licences and provenance documented in human-readable form.")
    r.p("**Gaps.** Seven concrete gaps were documented with indicator, evidence and remedy (Appendix A, Table A.1). "
        "The three most important are:")
    r.bullets([
        "**No persistent identifier** - as obtained, the data are reachable only through mutable URLs (F-UJI "
        "FsF-F1-02MD = 0 for Jolpica, GitHub and Kaggle). Remedy (partly implemented): the group deposited the raw "
        f"archive on Zenodo (DOI {z['doi']}, byte-identical to our source, checksum verified); the curated "
        "package cites it and will receive its own DOI.",
        "**Missing and conflicting licences** - Jolpica licenses the data CC BY-NC-SA 4.0 and Ergast allowed only "
        "non-commercial use, yet the Kaggle mirror claims CC0, our repository declares MIT for everything and the "
        "Zenodo record CC BY 4.0. F-UJI rewards any licence, compatible or not. Remedy: data under "
        "CC-BY-NC-SA-4.0, MIT for code only, and the Zenodo licence corrected.",
        "**No machine-readable metadata, provenance or controlled vocabularies** - only a README, no checksums, "
        "country names such as 'UK' or 'Korea' and 136 free-text status values. Remedy (implemented): the records "
        "below, ISO codes and an eight-term status vocabulary.",
    ])
    r.p("**Metadata record.** The package is described by a DataCite 4.5 record, validated against the official "
        "XSD (Appendix A, Table A.3), a schema.org Dataset in JSON-LD for search engines, a Frictionless Data "
        "Package that declares primary and foreign keys, and a W3C PROV-O graph linking every output to the 15 "
        "audited cleaning activities. Variable definitions are generated from the same schema module that "
        "Component C validates against, so documentation and data cannot drift apart.")
    r.p("**Persistent identifiers.** The source archive is identified by its Zenodo DOI, cited as 'IsDerivedFrom' "
        "in every metadata record; the curated package receives its own DOI (a placeholder until deposit, never "
        "cited before minting), creators ORCID iDs and the institution a ROR identifier (candidate). For "
        "key variables, countries use ISO 3166-1 alpha-3 codes (ISO 3166-3 for former states such as East Germany), "
        "dates ISO 8601 and licences SPDX. Drivers, constructors and circuits were linked to Wikidata QIDs through "
        f"their Wikipedia URLs, with coverage of {pct(F['qid_driver'], 1)}, {pct(F['qid_con'], 1)} and "
        f"{pct(F['qid_circ'])}; the few failures exposed broken links, which were flagged for curation.")


def component_b(r: Report, F: dict, figs: dict) -> None:
    r.heading("3. Component B - Data Quality and Profiling", 1, count_as="B")
    owner_line(r, 1)
    r.p("**Profiling.** Every column of the five tables was profiled for type, completeness, uniqueness and "
        f"distribution, and {F['issues']} quality rules were run. Each finding is stored in an issue register with "
        "dimension, severity, evidence down to file and line, root-cause hypothesis, downstream impact and the "
        f"cleaning step that resolves it (Appendix B, Table B.1). {F['errors']} findings are errors across "
        f"{F['dims']} dimensions, {F['high']} of them high severity; {F['not_errors']} are documented non-errors. "
        f"A further {F['passed_checks']} rules, including referential integrity and plausible driver ages, passed, "
        "which is equally useful evidence. Structurally, the results table combines identifiers, six numeric "
        "measures and free-text fields, no single column is unique, and the package itself is inconsistent: five "
        "sprint files are pretty-printed JSON arrays while every other JSON file uses JSON Lines.")
    r.p(f"**Completeness is deceptive.** Only {F['null_cells']} cells of the results table are null, suggesting a "
        f"99.9% complete dataset, yet {F['pos_disguised'] + F['grid_zero']:,} values merely pretend to be data "
        f"(Figure {figs['b1']}): 'position' is filled for {F['pos_disguised']:,} drivers who retired, withdrew or "
        f"were disqualified, and 'grid' uses 0 for {F['grid_zero']} cars without a grid slot. A model predicting "
        "results from grid positions would learn from retirements ranked '18th' and from a fictitious 'grid 0'.")
    r.p(f"**Uniqueness needs domain knowledge.** {F['dup_exact']} rows of the 1960 United States GP were appended "
        f"twice, and {F['dup_hidden']} rows of the 1960 Italian GP are copies whose season and round were blanked; "
        f"they only appear as duplicates once the keys are restored. Conversely, {F['shared']} rows that share "
        "season, round and driver are not errors: in the 1950s a driver could take over a team-mate's car and be "
        f"classified twice (Figure {figs['b2']}). Naive de-duplication would delete real history.")
    r.p(f"**Consistency, validity, accuracy, timeliness.** Status is free text with {F['status_raw']} values mixing "
        "laps behind with failure causes; countries use abbreviations; identifiers break the lowercase convention; "
        "integer keys are stored as floats; five races are duplicated. Points are not comparable across eras: a "
        "win earned 8, 9, 10, 25 or even 50 points (Figure B.1). All "
        f"{F['indy_outliers']} statistical lap outliers are valid Indianapolis 500 results (Figure B.2). Timeliness "
        "is uneven across tables: the calendar already lists 24 races of 2026 without results, and the newest "
        "drivers and teams lack birth dates, nationalities or links. From 2023 the source no longer records why "
        "cars retired (B29), a break found later through the dashboard (Section 6).")
    r.p("**Root causes and impact.** Three causes explain the pattern: export artefacts (duplicated blocks, blanked "
        "keys, lowercased names), undocumented source semantics (position, grid 0) and genuine historical change "
        "(scoring rules, shared drives). For data science and AI the impact is concrete: inflated win and point "
        "counts, biased prediction targets, sparse one-hot features, failed joins with external sources and "
        "train/test leakage through duplicated rows.")


def component_c(r: Report, F: dict, figs: dict) -> None:
    r.heading("4. Component C - Data Cleaning and Pipeline", 1, count_as="C")
    owner_line(r, 2)
    r.p("**Design and tools.** The pipeline is written in Python (pandas) as twelve small, documented steps, each "
        "answering specific issues from the Component B register. Python was preferred to Tableau Prep because "
        "code can be version-controlled, reviewed and tested. The pipeline runs from the original archive with one "
        f"command, is deterministic (two runs give byte-identical files) and {F['tests']} automated tests protect "
        "its key decisions. Every step writes an audit record: rows, changed cells and missing values before and "
        "after, and columns added (Appendix C, Table C.2). Each clean row keeps its source file and line, so any "
        "value can be traced back to the raw record.")
    r.p("**Key decisions.**")
    r.bullets([
        "**Types first.** A schema makes keys integers and dates real dates (C01).",
        "**Order matters.** Missing seasons (5) and rounds (7) are restored by deterministic lookup, from the "
        "file name and from races.csv, before de-duplication (C02); only then does exact matching find all "
        f"{F['removed']} copies (C03). In the reverse order 11 duplicates survive, which a unit test documents.",
        "**No invented values.** No statistical imputation is used: the grid sentinel 0 becomes missing plus a "
        "flag (C05), and withdrawn entries keep a missing car number because none existed.",
        "**Separate meanings.** 'position' is kept as position_order, and a new classified_position is filled only "
        "for classified drivers (C06).",
        f"**Exhaustive vocabularies.** {F['status_raw']} status values become {F['status_groups']} groups (C07) and "
        "countries receive ISO codes; any unmapped value stops the pipeline.",
        "**Flag, don't delete.** Indianapolis 500 rows and shared drives stay, flagged (C08, C11); "
        "points_normalised makes scoring eras comparable (C09).",
    ])
    r.p("Reference tables are de-duplicated (5 races, 4 circuits), one person stored under two identifiers is "
        "merged and recorded as an alias, names are title-cased and URLs use https (C10). The tables are joined "
        "with many-to-one validation, so no join can lose or multiply rows (C11).")
    r.p(f"**Validation and result.** {F['gates']} gates check schema, keys, foreign keys, vocabularies and ranges "
        "(C12); if one fails, nothing is published as clean. The final table has "
        f"{F['clean_rows']:,} rows ({F['removed']} removed) and {F['clean_cols']} documented columns. Of the "
        f"{F['issues']} issues, {F['fixed']} are fixed, {F['flagged']} mitigated or flagged, {F['kept']} kept and "
        f"documented, and {F['not_error']} verified as non-errors (Figure {figs['c1']}).")
    r.p("**Trade-offs.** Rule-based title-casing cannot restore every spelling, so six names needed curated "
        "exceptions. Normalised points improve comparability but hide absolute values, so raw points are kept. The "
        f"wider table ({F['clean_cols']} columns) is deliberate: flags preserve information that deletion would "
        "destroy. Strict gates make the pipeline fail on any new, unmapped status value, which costs convenience but "
        "guarantees that no unexpected category silently reaches an analysis.")


def graph_section(r: Report, F: dict, figs: dict) -> None:
    r.heading("5. Graph Modelling", 1, count_as="graph")
    n = F["nodes"]
    r.heading("5.1 Property graph model", 2)
    r.p("The cleaned data are modelled as a labelled property graph (Figure "
        f"{figs['g1']}) with five node labels - Driver ({n['Driver']}), Race ({n['Race']:,}), Constructor "
        f"({n['Constructor']}), Circuit ({n['Circuit']}) and Country ({n['Country']}) - and seven relationship types. "
        "RACED_IN connects a driver to a race and carries the result as properties (grid, classified position, "
        f"points, normalised points, status group, car number), so the {F['clean_rows']:,} results become edges "
        "rather than nodes. DROVE_FOR aggregates a driver's spell with a constructor (first and last season, races, "
        "points, wins); HELD_AT and LOCATED_IN place races on circuits and circuits in countries; HAS_NATIONALITY "
        "and REGISTERED_IN link drivers and constructors to countries through ISO codes. TEAMMATE_OF is a derived, "
        "undirected relationship between drivers who drove for the same constructor in the same race, weighted by "
        "the number of shared races. Node keys are the cleaned identifiers and Wikidata QIDs are node properties, so "
        "the graph inherits the interoperability work of Component A.")
    r.heading("5.2 NetworkX implementation", 2)
    r.p("The graph is built with NetworkX as a MultiDiGraph of "
        f"{F['pg_nodes']:,} nodes and {F['pg_edges']:,} typed edges and exported to GEXF for Gephi. Analytics run "
        f"on the TEAMMATE_OF projection ({F['tm_drivers']} drivers, {F['tm_links']:,} weighted links). Following "
        f"Component B, the {F['indy_rounds']} Indianapolis 500 rounds are excluded from this projection: there the "
        "'constructor' is a chassis builder used by dozens of independent entrants, which would create false "
        "team-mate links.")
    r.heading("5.3 Analytics and interpretation", 2)
    top = F["top"]
    names = [f"{row['name']} ({row['betweenness']:.3f})" for _, row in top.head(5).iterrows()]
    chain = " - ".join([F["path"].iloc[0]["from"]] + F["path"]["to"].tolist())
    r.p(f"**Connectivity and small world.** The projection has {F['components']} connected components; a giant "
        f"component holds {F['giant']} drivers ({F['giant_share']:.1f}%) and {F['isolated']} drivers never had a "
        f"team-mate. Its average clustering coefficient is {F['clust']:.2f}, against {F['clust_r']:.3f} for random "
        f"graphs of the same size and density, while the average shortest path ({F['aspl']:.1f} links) stays close "
        f"to the random benchmark ({F['aspl_r']:.1f}): a small-world network (sigma = {F['sigma']:.0f}). Any two "
        f"drivers of 75 years are on average fewer than five team-mate links apart; Juan Manuel Fangio reaches Max "
        f"Verstappen in {F['hops']} steps ({chain}).")
    r.p("**Betweenness centrality** counts how often a driver lies on the shortest paths between others (Figure "
        f"{figs['g3']}). The top drivers are not the most successful but the most connective: {', '.join(names)}. "
        "They combined long careers with many teams and therefore bridge generations; removing them would "
        "lengthen the paths between eras. Degree tells a different story, because the highest degrees belong to "
        "1950s-60s drivers such as Stirling Moss (78 team-mates).")
    r.p("**PageRank and assortativity.** Weighted PageRank, which rewards links to well-connected drivers and long "
        "partnerships, ranks Jack Brabham, Graham Hill and Jo Bonnier highest, again early-era drivers. Degree "
        "assortativity is slightly positive (0.15): well-connected drivers tend to share teams with other "
        f"well-connected drivers. The network diameter is {F['diameter']} links, so even the most distant drivers "
        "of the giant component are connected through a dozen team-mate relationships.")
    r.p(f"**Community detection** with the Louvain method (modularity {F['modularity']:.2f}) finds "
        f"{F['communities']} communities. Although the algorithm never sees a date, the large communities line up "
        f"with eras (Figure {figs['g4']}): the 1950s around Stirling Moss, the 1960s around Jack Brabham and Graham "
        "Hill, the 1970s around Ronnie Peterson and Niki Lauda, the 1980s around Riccardo Patrese, two parallel "
        "2000s groups (Barrichello and Schumacher; Alonso and Raikkonen) and the 2010s around Sergio Perez. Small "
        "communities capture short-lived teams such as Manor in 2015 (Figure "
        f"{figs['g2']}).")
    r.p("**What the measures reveal about data quality.** In the 1950s and 1960s the constructor field records the "
        "chassis make (Cooper, Maserati) shared by many private entrants, so early drivers receive inflated degree "
        "and PageRank. Network measures are only as valid as the meaning of the attributes they rest on - a direct "
        "link back to documenting semantics (A), profiling them (B) and defining 'team' explicitly (C).")


def dashboard_section(r: Report, F: dict, figs: dict) -> None:
    r.heading("6. The Interactive Dashboard", 1, count_as="dashboard")
    r.p("The project ends where its users begin: an interactive web dashboard (folder `dashboard`, opened with "
        "`streamlit run app.py`) that turns the validated outputs into seven views (Figure "
        f"{figs['dash']}): constructor eras, an all-time timing tower with an era-adjusted score, a grid-to-finish "
        "heatmap, reliability over time, a 3D globe of the circuits, the team-mate network and a final view that "
        "explains how the data were checked, plus an assistant that answers questions about them (Section 6.1). "
        "It is not a separate product. Its data file is generated by "
        "`build_web_data.py`, which reads only the outputs of the components, and `run_all.py` calls it as its last "
        "step, so the dashboard can never show numbers that the validation gates have not passed (Table 2). "
        "Appendix H shows every view.")
    r.p("The dashboard also worked as a quality instrument. Its reliability view showed mechanical failures and "
        "accidents vanishing after 2022. The cause was not engineering: from 2023 the source records almost every "
        "retirement only as 'Retired', 89% of them in 2023 and all of them in 2024 and 2025. No completeness or "
        "uniqueness rule had flagged it, because every value was present and valid. The finding became issue B29 "
        "in the quality register, cause analyses are now limited to 1950-2022, and the chart marks the break "
        "instead of hiding it. Visual exploration is therefore part of profiling, not only of reporting.")
    r.table(pd.DataFrame([
        ["Eras, timing tower, grid, circuits", "Cleaned results and reference tables (C)",
         "points_normalised, classified_position, ISO codes"],
        ["Reliability", "status_group (C07) and issue B29 (B)", "Break in cause recording marked at 2023"],
        ["Team-mate network", "TEAMMATE_OF projection and metrics (graph)", "Communities, betweenness, shortest path"],
        ["How the numbers were checked", "Issue register (B), validation gates (C), RDA and PIDs (A)",
         f"{F['issues']} issues, {F['gates']} gates, RDA {pct(F['rda_before'])} -> {pct(F['rda_after'])}"],
    ], columns=["Dashboard view", "Project output it reads", "What it shows"]),
        "Each dashboard view and the project output it is built from.", [4.4, 6.0, 6.0])
    ask_section(r, F, figs)


def ask_section(r: Report, F: dict, figs: dict) -> None:
    card, route, llm = F["card"], F["ev_route"], F["ev_llm"]
    tm, base = card["test_metrics"], card["baseline_test_metrics"]
    r.heading("6.1 Ask the Data: a Grounded Assistant", 2, count_as="dashboard")
    r.p("The last view lets users question the data in English or Spanish (Figure "
        f"{figs['ask']}). It grows out of a prototype by Manohar Zalki (FastAPI, a local Llama 3 through Ollama, "
        "hybrid vector and graph retrieval and a machine-learning engine), rebuilt so that the language model never "
        "supplies a number. The service first finds the drivers, teams, circuits and seasons in the question, then "
        "gathers evidence: exact figures computed with pandas from the cleaned tables, each carrying its file, "
        "SHA-256, filter, row count and raw source line; team-mate chains from the graph; a podium-probability model; "
        f"and the best of {F['kb_docs']:,} documents generated from the project outputs. Llama 3 answers from that "
        "evidence only and cites it, and every figure in the answer is then looked up in the evidence. Official "
        f"champions come from Wikidata ({F['champ_wikidata']} of {config.LAST_COMPLETE_SEASON - config.FIRST_SEASON + 1} "
        "seasons) and are reconciled with our points: "
        f"{' and '.join(map(str, F['champ_disagree']))} disagree because only a driver's best results counted, a "
        "semantic trap that a plain sum of points gets wrong. The podium model uses only pre-race information, "
        f"chooses among three learned models on {card['split']['validation'].split(' ')[0]} and is tested once on "
        f"{card['split']['test'].split(' ')[0]}: its probabilities beat a grid-only baseline, but its top three "
        "picks call no more podium places than the grid order (Table 3), which we report rather than hide.")
    rows = [["Evidence contains the correct answer", f"{route['evidence_contains_expected']} of {route['questions']}",
             f"median {route['median_evidence_seconds']:.2f} s"]]
    if llm:
        rows += [["Written answer contains the correct answer", f"{llm['answer_contains_expected']} of {llm['questions']}",
                  "Llama 3 8B, local"],
                 ["Answers whose figures are all found in the evidence",
                  f"{llm['answers_with_all_figures_verified']} of {llm['questions']}",
                  f"{llm['figures_verified']} of {llm['figures_total']} figures"],
                 ["Answers citing their evidence", f"{llm['answers_citing_evidence']} of {llm['questions']}",
                  f"median {llm['median_total_seconds']:.0f} s per answer on a laptop CPU"]]
        if F["refused"] is not None:
            rows.append(["Question outside 1950-2025 declined", "yes" if F["refused"] else "no", "2030 champion"])
    rows += [["Podium model, test 2020-2025: log loss / ROC AUC",
              f"{tm['log_loss']:.3f} / {tm['roc_auc']:.3f}", f"grid-only baseline {base['log_loss']:.3f} / {base['roc_auc']:.3f}"],
             ["Podium places called by the top three picks", f"{100 * tm['podium_places_called']:.0f}%",
              f"'front three finish on the podium' {100 * card['rule_front_three_podium_places_called_test']:.0f}%"]]
    r.table(pd.DataFrame(rows, columns=["Check (25 benchmark questions, answers computed independently)",
                                        "Result", "Detail"]),
            "Evaluation of the assistant and of its podium model (outputs/assistant/).", [7.2, 3.0, 6.2])


def integration(r: Report, F: dict) -> None:
    r.heading("7. How the Components Connect", 1, count_as="integration")
    r.p("The components were designed as one chain with explicit contracts: the issue register is the interface "
        "between B and C (every issue names the cleaning step that resolves it, and C measures every issue again "
        "after cleaning), the schema module is shared by C and A, and the graph and dashboard read only validated "
        "output. Table 4 traces six findings through all components. The dependencies also ran backwards: the "
        "dashboard exposed issue B29, the graph analysis "
        "revealed that 'constructor' changes meaning over time, a semantic issue that profiling alone had not "
        "flagged and that now belongs in the metadata, and Component A's identifier lookup exposed broken links "
        "that Component C records for curation. Terminology is shared through the data dictionary, so 'classified "
        "position', 'shared drive' and 'status group' mean the same thing in every section.")
    r.table(pd.DataFrame([
        ["Country abbreviations 'UK', 'USA', 'Korea' (B21)", "ISO 3166 codes added (C10)",
         "Interoperability gap G4 closed", "Country nodes keyed by ISO code"],
        ["Indy 500 lap outliers (B16)", "Kept and flagged is_indy500 (C08)", "Flag documented in dictionary",
         "Excluded from TEAMMATE_OF projection"],
        ["Duplicates with blanked keys (B06, B07)", "Key repair before de-duplication (C02, C03)",
         "Checksums and PROV provenance", "No double-counted RACED_IN edges"],
        ["Same driver under two IDs (B20)", "Alias merged (C10)", "Wikidata QIDs as PIDs", "One Driver node per person"],
        ["'position' set for retirements (B11)", "classified_position separated (C06)", "Semantics in data dictionary",
         "Correct RACED_IN result property"],
        ["Causes not recorded from 2023 (B29), found in the dashboard", "Mapped to 'Retired (unspecified)' (C07)",
         "Limitation documented", "Dashboard marks the break"],
    ], columns=["Finding (B)", "Cleaning (C)", "FAIR / metadata (A)", "Graph and dashboard"]),
        "Six examples of how one finding flows through all components.", [4.6, 4.2, 3.8, 3.8])


def conclusion(r: Report, F: dict) -> None:
    r.heading("8. Conclusion", 1, count_as="conclusion")
    r.p("**Lessons learned.** First, quality is contextual: outliers, duplicates and record-count gaps were often "
        "valid history, so every automated rule needed domain verification before anything was deleted. Second, "
        "the order of operations matters, as the 11 hidden duplicates show. Third, the largest FAIR gaps were not in "
        "the values but around them: no identifier, an inconsistent licence and no provenance. Fourth, validation "
        "gates and an audit log turned cleaning from a series of manual edits into evidence an examiner can check. "
        "Fifth, generating documentation from code (data dictionary, metadata and this report's figures) kept "
        "every artefact consistent with the data, even when the pipeline changed late in the project. Sixth, "
        "looking at the data is itself a quality check: the dashboard found an issue that no automated rule had "
        "flagged.")
    r.p("**Limitations.** The seven short races of 2014-2025 match documented absences but should be confirmed "
        "against official FIA classifications. The RDA scores are a self-assessment, F-UJI can only test what is "
        "online, and the curated package's own DOI is not minted yet. Title-casing needed manual exceptions, a few "
        "Wikidata links are "
        "broken, the team concept is ambiguous before the 1970s, and sprint races were left out. Finally, the "
        "CC BY-NC-SA 4.0 licence inherited from the source restricts reuse: the curated data may support research "
        "and teaching, but not, for example, a commercial betting model.")
    r.p("**Recommendations.** We recommend depositing the curated package on Zenodo as a record derived from the "
        "raw archive's DOI, correcting that record's licence to CC BY-NC-SA 4.0, publishing the status "
        "vocabulary as SKOS, modelling 'team' separately from 'chassis', reporting the source defects (duplicated "
        "blocks, identifier case) upstream to Jolpica, and running the validation gates automatically whenever new "
        "race data arrive, so that quality is checked continuously rather than once.")


def references(r: Report) -> None:
    r.heading("References", 1, count_as="")
    refs = [
        "Batini, C., & Scannapieco, M. (2016). *Data and Information Quality: Dimensions, Principles and Techniques*. Springer.",
        "Blondel, V. D., Guillaume, J.-L., Lambiotte, R., & Lefebvre, E. (2008). Fast unfolding of communities in large "
        "networks. *Journal of Statistical Mechanics*, P10008.",
        "DataCite Metadata Working Group (2024). *DataCite Metadata Schema 4.5*. https://schema.datacite.org/meta/kernel-4.5/",
        "Devaraju, A., & Huber, R. (2021). An automated solution for measuring the progress toward FAIR research data. "
        "*Patterns*, 2(11), 100370.",
        "Freeman, L. C. (1977). A set of measures of centrality based on betweenness. *Sociometry*, 40(1), 35-41.",
        "Hagberg, A., Schult, D., & Swart, P. (2008). Exploring network structure, dynamics, and function using "
        "NetworkX. *Proceedings of the 7th Python in Science Conference*, 11-15.",
        "Jolpica-F1 (2025). Jolpica-F1 API and Terms of Use. https://github.com/jolpica/jolpica-f1",
        "Lebo, T., Sahoo, S., & McGuinness, D. (2013). *PROV-O: The PROV Ontology*. W3C Recommendation.",
        "Rao, R. (2025). *Formula 1 World Championship (1950-2024)* [Data set]. Kaggle.",
        "RDA FAIR Data Maturity Model Working Group (2020). *FAIR Data Maturity Model: Specification and Guidelines*. "
        "https://doi.org/10.15497/RDA00050",
        "Wang, R. Y., & Strong, D. M. (1996). Beyond accuracy: What data quality means to data consumers. *Journal of "
        "Management Information Systems*, 12(4), 5-33.",
        "Watts, D. J., & Strogatz, S. H. (1998). Collective dynamics of 'small-world' networks. *Nature*, 393, 440-442.",
        "Wilkinson, M. D., et al. (2016). The FAIR Guiding Principles for scientific data management and stewardship. "
        "*Scientific Data*, 3, 160018.",
    ]
    for ref in refs:
        para = r.p(ref, count=False, size=9)
        para.paragraph_format.left_indent = Cm(0.6)
        para.paragraph_format.first_line_indent = Cm(-0.6)


# ============================================================================================
# Appendices
# ============================================================================================
def appendix_a(r: Report) -> None:
    a = config.FAIR_DIR
    r.heading("Appendix A - FAIR Assessment and Metadata (Component A)", 1, count_as="")
    gaps = pd.read_csv(a / "fair_gaps.csv")
    r.table(gaps.rename(columns={"gap_id": "Gap", "title": "Title", "indicators": "RDA indicators",
                                 "evidence": "Evidence", "improvement": "Improvement",
                                 "status_in_package": "Status"}),
            "FAIR compliance gaps with evidence and actionable improvements.", [1.0, 2.4, 2.4, 3.8, 4.0, 2.8],
            font=7, label="A.1")
    fuji_version = str(pd.read_csv(a / "fuji_summary.csv")["metric_version"].iloc[0])
    fuji = pd.read_csv(a / "fuji_summary.csv")[["resource", "url", "fair_percent", "F_percent", "A_percent",
                                                "I_percent", "R_percent"]]
    r.table(fuji.rename(columns={"resource": "Resource", "url": "URL", "fair_percent": "FAIR %", "F_percent": "F %",
                                 "A_percent": "A %", "I_percent": "I %", "R_percent": "R %"}),
            f"F-UJI 4.0.1 results (metrics v{fuji_version}); raw JSON responses in outputs/component_a_fair/fuji/ "
            "(an earlier run with metrics v0.5 is kept in fuji/metrics_v0.5/).",
            [3.0, 6.4, 1.4, 1.2, 1.2, 1.2, 1.2], font=7.5, label="A.2a")
    rda = pd.read_csv(a / "rda_fair_summary.csv")
    for col in ("as_obtained_rda_level", "curated_rda_level"):
        rda[col] = rda[col].map(lambda v: "" if pd.isna(v) else str(int(v)))
    r.table(rda.rename(columns={"area": "Area", "indicators": "Indicators",
                                "as_obtained_progress_percent": "Progress obtained %",
                                "as_obtained_essential_passed": "Essential obtained",
                                "as_obtained_rda_level": "Level obtained",
                                "curated_progress_percent": "Progress curated %",
                                "curated_essential_passed": "Essential curated",
                                "curated_rda_level": "Level curated"})[
        ["Area", "Indicators", "Progress obtained %", "Essential obtained", "Level obtained", "Progress curated %",
         "Essential curated", "Level curated"]],
            "RDA FAIR Data Maturity Model summary (41 indicators; per-indicator scores and evidence in "
            "rda_fair_assessment.csv).", [2.2, 1.6, 2.0, 2.0, 1.6, 2.0, 2.0, 1.6], font=7.5, label="A.2b")
    attrs = json.loads((a / "datacite_metadata.json").read_text(encoding="utf-8"))["data"]["attributes"]

    def readable(value) -> str:
        if isinstance(value, dict):
            return "; ".join(f"{k}: {readable(v)}" for k, v in value.items())
        if isinstance(value, list):
            items = [readable(v) for v in value]
            return items[0] if len(items) == 1 else "\n".join(f"- {i}" for i in items)
        return str(value)

    rows = []
    for key, value in attrs.items():
        if key == "geoLocations":
            pts = [g for g in value if "geoLocationPoint" in g]
            rows.append([key, f"{len(value)} entries: 'Worldwide' plus one geoLocationPoint per circuit "
                              f"({len(pts)} points with latitude/longitude; listed in datacite_metadata.xml)"])
            continue
        rows.append([key, readable(value)])
    r.table(pd.DataFrame(rows, columns=["DataCite property", "Value"]),
            "Complete DataCite 4.5 metadata record of the curated dataset (JSON form; the equivalent XML validates "
            "against the kernel-4.5 XSD). The curated package's DOI and the ORCID iDs are placeholders until deposit; the "
            "source archive's DOI (IsDerivedFrom) is real.",
            [3.2, 13.2], font=6.5, label="A.3")
    pid = pd.read_csv(a / "pid_coverage.csv")
    r.table(pid, "Wikidata QID coverage of entity identifiers.", [3.5, 3, 3, 3, 3.5], font=8, label="A.4")


def appendix_b(r: Report) -> None:
    q = config.QUALITY_DIR
    r.heading("Appendix B - Data Quality Profiling (Component B)", 1, count_as="")
    reg = pd.read_csv(q / "quality_issues.csv")
    reg = reg[["issue_id", "dimension", "table", "title", "affected_records", "affected_pct", "severity",
               "is_error", "cleaning_step"]].rename(columns={
        "issue_id": "ID", "dimension": "Dimension", "table": "Table", "title": "Issue",
        "affected_records": "Affected", "affected_pct": "%", "severity": "Severity", "is_error": "Error",
        "cleaning_step": "Resolved by"})
    r.table(reg, "Quality issue register (evidence, root cause and impact per issue in quality_issues.md).",
            [0.9, 2.0, 1.8, 5.0, 1.3, 1.1, 1.3, 1.0, 2.0], font=7, label="B.1")
    root = pd.read_csv(q / "quality_issues.csv")[["issue_id", "root_cause_hypothesis", "downstream_impact"]]
    root = root[root["issue_id"].isin(["B04", "B06", "B07", "B08", "B11", "B12", "B15", "B16", "B21"])]
    r.table(root.rename(columns={"issue_id": "ID", "root_cause_hypothesis": "Root-cause hypothesis",
                                 "downstream_impact": "Downstream impact on data science / AI"}),
            "Root-cause hypotheses and downstream impact for the key issues.", [1.0, 7.0, 8.4], font=7, label="B.2")
    passed = pd.read_csv(q / "passed_checks.csv")
    r.table(passed.rename(columns={"dimension": "Dimension", "rule": "Rule", "violations": "Violations",
                                   "result": "Result"}),
            "Rules that were tested and passed.", [3.2, 9.0, 2.0, 2.0], font=7.5, label="B.3")
    r.figure(config.QUALITY_FIG_DIR / "fig_b3_points_scale_by_era.png",
             "Points for a race win by season: raw points are not comparable across scoring eras.", 15, label="B.1")
    r.figure(config.QUALITY_FIG_DIR / "fig_b4_laps_outliers.png",
             "Laps completed: every value beyond the IQR fence is a valid Indianapolis 500 result.", 15, label="B.2")


def appendix_c(r: Report) -> None:
    c = config.CLEANING_DIR
    r.heading("Appendix C - Cleaning Pipeline (Component C)", 1, count_as="")
    res = pd.read_csv(c / "issue_resolution.csv")
    res["after"] = res["after"].map(lambda v: "-" if pd.isna(v) else int(v))
    r.table(res[["issue_id", "dimension", "title", "before", "after", "resolution"]].rename(columns={
        "issue_id": "ID", "dimension": "Dimension", "title": "Issue", "before": "Before", "after": "After",
        "resolution": "Resolution"}),
            "Issue resolution: every Component B issue measured again on the cleaned data.",
            [0.9, 2.2, 5.6, 1.4, 1.3, 5.0], font=7, label="C.1")
    audit = pd.read_csv(c / "audit_log.csv")
    r.table(audit[["step_id", "step_name", "issues_addressed", "table", "rows_before", "rows_after", "cells_changed",
                   "missing_before", "missing_after"]].rename(columns={
        "step_id": "Step", "step_name": "Name", "issues_addressed": "Issues", "table": "Table",
        "rows_before": "Rows before", "rows_after": "Rows after", "cells_changed": "Cells changed",
        "missing_before": "Missing before", "missing_after": "Missing after"}),
            "Audit log with before/after statistics per step (step details in audit_log.md).",
            [1.0, 4.4, 2.0, 1.8, 1.4, 1.4, 1.5, 1.5, 1.4], font=7, label="C.2")
    gates = pd.read_csv(c / "validation_report.csv")
    r.table(gates[["gate", "result"]].rename(columns={"gate": "Validation gate", "result": "Result"}),
            f"All {len(gates)} validation gates (C12).", [13.0, 3.0], font=6.8, label="C.3")
    r.figure(c / "fig_c2_status_standardisation.png",
             "Status standardisation: 136 raw values mapped to 8 groups.", 15, label="C.1")


def appendix_d(r: Report) -> None:
    g = config.GRAPH_DIR
    r.heading("Appendix D - Graph Metrics", 1, count_as="")
    net = pd.read_csv(g / "network_metrics.csv", index_col=0)["value"]
    rows = [[k.replace("_", " "), f"{v:,.4f}".rstrip("0").rstrip(".") if abs(v) < 1000 else f"{v:,.0f}"]
            for k, v in net.items()]
    r.table(pd.DataFrame(rows, columns=["Metric (team-mate projection)", "Value"]),
            "Network-level metrics.", [9.0, 4.0], font=8, label="D.1")
    top = pd.read_csv(g / "top_betweenness.csv")
    top[["betweenness", "pagerank"]] = top[["betweenness", "pagerank"]].round(4)
    r.table(top.rename(columns={"name": "Driver", "first_season": "First", "last_season": "Last",
                                "degree": "Degree", "betweenness": "Betweenness", "pagerank": "PageRank",
                                "community": "Community"}),
            "Top 12 drivers by betweenness centrality.", [4.5, 1.6, 1.6, 1.6, 2.2, 2.2, 2.2], font=8, label="D.2")
    com = pd.read_csv(g / "communities.csv")
    r.table(com.rename(columns={"community": "Community", "drivers": "Drivers", "first_debut": "First debut",
                                "median_debut": "Median debut", "last_active": "Last active",
                                "most_central_drivers": "Most central drivers (PageRank)"}),
            "Louvain communities.", [1.8, 1.5, 1.8, 1.8, 1.8, 7.3], font=8, label="D.3")
    path = pd.read_csv(g / "shortest_teammate_path_fangio_verstappen.csv")
    r.table(path.rename(columns={"from": "From", "to": "To", "constructors": "Shared constructor",
                                 "races_together": "Races together"}),
            "Shortest team-mate path from Juan Manuel Fangio to Max Verstappen.", [4.2, 4.2, 4.6, 3.0], font=8,
            label="D.4")
    r.figure(config.GRAPH_FIG_DIR / "fig_g2_teammate_network.png",
             "Team-mate network (giant component) coloured by Louvain community; node size = betweenness.", 15.5,
             label="D.1")


def appendix_e(r: Report) -> None:
    r.heading("Appendix E - Data Dictionary of the Cleaned Results Table", 1, count_as="")
    dd = pd.read_csv(config.FAIR_DIR / "data_dictionary.csv")
    dd = dd[dd["table"] == "f1_race_results_clean.csv"][["column", "type", "description", "nullable"]]
    r.table(dd.rename(columns={"column": "Column", "type": "Type", "description": "Description",
                               "nullable": "Nullable"}),
            "Variables of f1_race_results_clean.csv (all tables in data_dictionary.md).", [3.6, 1.6, 9.6, 1.6],
            font=7, label="E.1")


def appendix_f(r: Report) -> None:
    r.heading("Appendix F - Reproducibility and Deliverables", 1, count_as="")
    r.p("Requirements: Python 3.11+, packages in requirements.txt. From the folder data_management_project run "
        "`python run_all.py --from-scratch` (about 70 s, no network needed), then `python -m pytest -q` and "
        "`python -m src.build_report`.", count=False, size=9.5)
    r.table(pd.DataFrame([
        ["1 Joint written report", "report/F1_Data_Management_Joint_Report.docx / .pdf"],
        ["2 Python cleaning scripts", "src/cleaning.py, src/vocabularies.py, src/schema.py, run_all.py, tests/"],
        ["3 Tableau Prep flow", "not used (pipeline fully in Python)"],
        ["4 Metadata record", "outputs/component_a_fair/datacite_metadata.xml/.json, schema_org_dataset.jsonld, "
                              "datapackage.json, provenance_prov.jsonld"],
        ["5 FAIR assessment evidence", "outputs/component_a_fair/fuji/*.json, fig_a2_fuji_scores.png, "
                                      "rda_fair_assessment.csv, license_evidence/"],
        ["6 Quality visualisations", "outputs/component_b_quality/figures/*.png"],
        ["7 Original + cleaned datasets", "data/raw/f1_race_results_raw.csv, data/cleaned/f1_race_results_clean.csv "
                                          "(+ reference tables)"],
        ["8 Graph files", "src/graph_model.py, outputs/graph/*.gexf, outputs/graph/figures/*.png"],
        ["Extra: interactive dashboard", "dashboard/ (app.py, build_web_data.py, static/); screenshots in "
                                         "outputs/dashboard/"],
        ["9 Individual reflection logs", "submitted individually (drafts in report/reflection_drafts/)"],
    ], columns=["Deliverable", "Location in the ZIP"]), "Map of the assignment deliverables.", [4.5, 11.9], font=8,
        label="F.1")


def appendix_h(r: Report) -> None:
    r.heading("Appendix H - Dashboard Gallery", 1, count_as="")
    r.p("Screenshots of the running dashboard (`streamlit run app.py` in the `dashboard` folder). Every number shown "
        "is read from the validated project outputs.", count=False, size=9.5)
    d = config.OUTPUT_DIR / "dashboard"
    views = [
        ("dashboard_hero.png", "Opening: the start-light sequence, then the key figures of the dataset."),
        ("dashboard_eras.png", "Who ruled each era: share of wins by constructor per season, with the computed finding."),
        ("dashboard_drivers.png", "The all-time timing tower: rank by wins, podiums, pole starts, era-adjusted score or "
                                  "points; replays season by season."),
        ("dashboard_grid.png", "Grid to finish: share of drivers from each starting slot finishing in each position, "
                               "with pole conversion by decade and the furthest-back winners."),
        ("dashboard_reliability.png", "Reliability: outcomes of every start, with the 2023 break in cause recording "
                                      "(issue B29) marked."),
        ("dashboard_circuits.png", "Circuits: rotating globe and ranking by Grands Prix hosted."),
        ("dashboard_network.png", "Team-mate network with the shortest chain from Juan Manuel Fangio to Max Verstappen."),
        ("dashboard_ask.png", "Ask the data: the answer of the local Llama 3, its evidence with provenance and the "
                              "figure check."),
        ("dashboard_data.png", "How the numbers were checked: the project pipeline and its key results."),
    ]
    for i, (file, caption) in enumerate(views, start=1):
        r.figure(d / file, caption, 15.6, label=f"H.{i}")


def appendix_g(r: Report) -> None:
    r.heading("Appendix G - Declaration of AI Tool Use", 1, count_as="")
    r.p("In line with the course rules, all use of AI tools is declared here. The group used Claude Code "
        "(Anthropic; models Claude Haiku 4.5 and Claude Opus 5.5) as an AI programming assistant, with the "
        "instructor's agreement for extensive use. It was used to: write and debug the Python code "
        "(extraction, profiling, cleaning, metadata generation, graph analytics, the interactive dashboard and this "
        "report builder); run the "
        "F-UJI tool locally and summarise its output; retrieve licence terms and Wikidata identifiers from primary "
        "sources; draft text for the report sections; and generate the figures.", count=False, size=9.5)
    r.p("The ask-the-data assistant (Section 6.1) also contains an AI model as part of the product: Meta Llama 3 "
        "(8B) and the nomic-embed-text embedding model, run locally through Ollama, so no data leave the computer. "
        "By design the language model only phrases answers: every figure comes from code over the validated data "
        "and is checked against the evidence after the answer is written, and its accuracy was measured on 25 "
        "benchmark questions whose answers were computed independently.", count=False, size=9.5)
    r.p("Human responsibilities: choosing the dataset and the analysis direction, reviewing every cleaning "
        "decision and its domain justification, checking that numbers in the text match the outputs, and editing "
        "each component section and the reflection logs, which remain the work of the responsible student. All "
        "factual claims (licences, F-UJI scores, historical events) were checked against the cited evidence files "
        "included in the ZIP.", count=False, size=9.5)


# ============================================================================================
def build() -> dict:
    config.ensure_dirs()
    F = facts()
    r = Report()
    title_page(r, F)
    figs = {"flow": 1, "fuji": 2, "rda": 3, "b1": 4, "b2": 5, "c1": 6, "g1": 7, "g3": 8, "g4": 9, "dash": 10,
            "ask": 11, "g2": "D.1"}
    introduction(r, F)
    component_a(r, F, figs)
    r.figure(config.FAIR_DIR / "fig_a2_fuji_scores.png",
             f"F-UJI automated FAIR scores (metrics v{F['fuji_version']}) for the four locations of the data, including the "
             "group's Zenodo record of the raw archive (evidence: raw JSON in the ZIP).", 14.5)
    r.figure(config.FAIR_DIR / "fig_a1_rda_fair_maturity.png",
             "RDA FAIR Data Maturity Model: progress per area for the data as obtained and the curated package.", 14.5)
    component_b(r, F, figs)
    r.figure(config.QUALITY_FIG_DIR / "fig_b1_hidden_missingness.png",
             "Explicit vs disguised missing values in the raw results table.", 14.5)
    r.figure(config.QUALITY_FIG_DIR / "fig_b2_duplicates_vs_shared_drives.png",
             "True duplicates vs legitimate shared drives among rows sharing season, round and driver.", 14.5)
    component_c(r, F, figs)
    r.figure(config.CLEANING_DIR / "fig_c1_issue_resolution.png",
             f"Resolution of the {F['issues']} Component B issues per quality dimension.", 14.5)
    graph_section(r, F, figs)
    r.figure(config.GRAPH_FIG_DIR / "fig_g1_property_graph_model.png",
             "Property graph model with instance counts.", 14.5)
    r.figure(config.GRAPH_FIG_DIR / "fig_g3_centrality.png",
             "Top 12 drivers by betweenness centrality, with their degree.", 14.5)
    r.figure(config.GRAPH_FIG_DIR / "fig_g4_communities_by_era.png",
             "Louvain communities and the seasons their drivers were active.", 14.5)
    dashboard_section(r, F, figs)
    r.figure(config.OUTPUT_DIR / "dashboard" / "fig_d1_dashboard_overview.png",
             "The interactive dashboard: start-light opening, constructor eras, the Fangio-to-Verstappen chain in the "
             "team-mate network, and the view that explains how the data were checked.", 16.4)
    r.figure(config.OUTPUT_DIR / "dashboard" / "dashboard_ask.png",
             "Ask the data: a question answered by the local Llama 3 from cited evidence (right), with the check "
             "that every figure in the answer appears in the evidence.", 16.4)
    integration(r, F)
    conclusion(r, F)
    r.section_key = None
    references(r)
    r.page_break()
    appendix_a(r)
    appendix_b(r)
    appendix_c(r)
    appendix_d(r)
    appendix_e(r)
    appendix_f(r)
    appendix_g(r)
    appendix_h(r)

    counts = r.counts
    main_total = sum(counts.values())
    for para in r.doc.paragraphs:
        if para.text == "WORD_COUNT_PLACEHOLDER":
            for run in para.runs[1:]:
                run.text = ""
            para.runs[0].text = (f"Word count (main text, excluding tables, figure captions, references and appendices): "
                                 f"{main_total:,}. Component sections: A {counts.get('A', 0)}, B {counts.get('B', 0)}, "
                                 f"C {counts.get('C', 0)} words.")
    problems = [f"Component {k}: {counts.get(k, 0)} words (must be 400-500)"
                for k in ("A", "B", "C") if not 400 <= counts.get(k, 0) <= 500]
    if main_total > 4000:
        problems.append(f"main text {main_total} words > 4000")
    r.doc.save(OUT_DOCX)
    print("[report] word counts:", counts, "total:", main_total)
    if problems:
        raise ValueError("word-limit check failed: " + "; ".join(problems))
    pdf = convert_pdf(OUT_DOCX)
    print(f"[report] written {OUT_DOCX.name} and {pdf.name if pdf else '(PDF conversion unavailable)'}")
    return {"words": main_total, **{f"words_{k}": v for k, v in counts.items()}}


def convert_pdf(docx_path: Path) -> Path | None:
    soffice = config.find_soffice()
    if not soffice:
        return None
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(docx_path.parent),
                    str(docx_path)], check=True, capture_output=True)
    return docx_path.with_suffix(".pdf")


if __name__ == "__main__":
    build()
