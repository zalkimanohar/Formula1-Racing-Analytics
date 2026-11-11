"""Build the group presentation (16:9 PowerPoint + PDF + presenter script) from the pipeline outputs.

Visual language: the dashboard's pit wall - asphalt background, start lights, timing-screen numbers,
purple for "the best", Titillium Web and Source Serif 4 (fonts in report/assets/fonts, OFL licence).
Charts are native PowerPoint charts drawn from the project's CSV outputs, so every number on the
slides and in the speaker notes matches the data and the report.

    python -m src.build_slides
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_MARKER_STYLE, XL_TICK_MARK
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

from src import config
from src.build_report import facts

OUT_DIR = config.REPORT_DIR / "presentation"
OUT_PPTX = OUT_DIR / "F1_Data_Management_Presentation.pptx"
OUT_SCRIPT = OUT_DIR / "presenter_script.md"
ASSETS = config.REPORT_DIR / "assets"
DASH = config.OUTPUT_DIR / "dashboard"

SLIDE_W, SLIDE_H = 13.333, 7.5
M = 0.62                     # side margin
TOTAL = 19

# pit-wall palette (same tokens as dashboard/static/styles.css)
ASPHALT, RAISED, DEEP, LINE = "16181C", "1C1F24", "111316", "2A2E36"
INK, INK2, INK3 = "ECEBE6", "B4B7BF", "7D828D"
PURPLE, PURPLE_DEEP, GREEN, AMBER, LAMP, RED = "B26BFF", "2A2140", "3AD17A", "FFCC33", "FF2B2B", "E5484D"
BLUE, ORANGE, TEAL = "3D93D6", "EB6834", "1BAF7A"
BRONZE, SILVER, GOLD = "C07A46", "AEB4BC", "D9B44A"

UI, UI_SEMI, UI_BLACK = "Titillium Web", "Titillium Web SemiBold", "Titillium Web Black"
SERIF, MONO = "Source Serif 4", "Consolas"
SPEAKING_WPM = 130


def rgb(hex_: str) -> RGBColor:
    return RGBColor.from_string(hex_)


def _alpha(fill_parent, pct: int) -> None:
    """Add transparency to the solid fill of a shape (pct = opacity in percent)."""
    clr = fill_parent.find(qn("a:solidFill")).find(qn("a:srgbClr"))
    a = OxmlElement("a:alpha")
    a.set("val", str(pct * 1000))
    clr.append(a)


# ============================================================================================
# Drawing helpers
# ============================================================================================
class Deck:
    def __init__(self) -> None:
        self.prs = Presentation()
        self.prs.slide_width = Inches(SLIDE_W)
        self.prs.slide_height = Inches(SLIDE_H)
        self.script: list[dict] = []

    # ---------------------------------------------------------------- frame
    def slide(self, chapter: str, glow: bool = True):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = rgb(ASPHALT)
        if glow:
            g = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(8.2), Inches(-3.2), Inches(8.5), Inches(6.2))
            g.fill.solid()
            g.fill.fore_color.rgb = rgb(PURPLE)
            _alpha(g.fill._xPr, 9)
            g.line.fill.background()
            eff = OxmlElement("a:effectLst")
            soft = OxmlElement("a:softEdge")
            soft.set("rad", str(int(Inches(1.6))))
            eff.append(soft)
            g._element.spPr.append(eff)
            g.name = "glow"
        idx = len(self.prs.slides)
        self._brand(s, chapter, idx)
        return s

    def _brand(self, s, chapter: str, idx: int) -> None:
        x, y, c = M, 0.3, 0.11
        for i in range(2):
            for j in range(2):
                sq = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x + i * c), Inches(y + j * c), Inches(c), Inches(c))
                sq.fill.solid()
                sq.fill.fore_color.rgb = rgb(INK if (i + j) % 2 == 0 else ASPHALT)
                sq.line.color.rgb = rgb(INK)
                sq.line.width = Pt(0.5)
        self.text(s, x + 0.34, y - 0.07, 2.2, 0.32, "F1 in numbers", size=12, font=UI_SEMI, color=INK)
        self.text(s, x + 1.95, y - 0.07, 6.5, 0.32, chapter, size=12, color=INK3)
        self.text(s, SLIDE_W - M - 1.6, y - 0.07, 1.6, 0.32, f"{idx:02d} / {TOTAL}", size=12, color=INK3,
                  align=PP_ALIGN.RIGHT, font=UI_SEMI)

    def footer(self, s, presenter: str | None) -> None:
        idx = self.prs.slides.index(s) + 1
        if presenter:
            self.text(s, M, 6.98, 6.0, 0.3, [[("Presenting  ", {"color": INK3}), (presenter, {"font": UI_SEMI})]],
                      size=11, color=INK2)
        self.text(s, SLIDE_W - M - 5.2, 6.98, 5.2, 0.3, "Data Management, Winter 2026/27, SRH University", size=11,
                  color=INK3, align=PP_ALIGN.RIGHT)
        track = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(SLIDE_H - 0.07), Inches(SLIDE_W), Inches(0.07))
        track.fill.solid()
        track.fill.fore_color.rgb = rgb(RAISED)
        track.line.fill.background()
        done = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(SLIDE_H - 0.07), Inches(SLIDE_W * idx / TOTAL),
                                  Inches(0.07))
        done.fill.solid()
        done.fill.fore_color.rgb = rgb(PURPLE)
        done.line.fill.background()
        done.name = "lap_progress"

    def title(self, s, text: str, lede: str | None = None, size: int | None = None, width: float = 12.1) -> float:
        if size is None:   # keep every title on one line
            n = len(text)
            size = 34 if n <= 46 else 31 if n <= 52 else 28 if n <= 58 else 26
        self.text(s, M, 0.72, width, 1.0, text, size=size, font=UI, bold=True, color=INK, name="title",
                  line_spacing=0.92)
        if lede:
            self.text(s, M, 1.55, width, 0.6, lede, size=15.5, font=SERIF, color=INK2, name="lede")
            return 2.25
        return 1.75

    # ---------------------------------------------------------------- primitives
    @staticmethod
    def text(s, x, y, w, h, content, size=16, bold=False, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
             font=UI, name=None, spacing_after=0, line_spacing=1.0, italic=False):
        """content: str, or list of paragraphs; a paragraph is a str or a list of (text, overrides) runs."""
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        if name:
            tb.name = name
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = anchor
        paras = content if isinstance(content, list) else [content]
        for i, para in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.space_after = Pt(spacing_after)
            p.line_spacing = line_spacing
            runs = para if isinstance(para, list) else [(para, {})]
            for txt, o in runs:
                r = p.add_run()
                r.text = txt
                r.font.name = o.get("font", font)
                r.font.size = Pt(o.get("size", size))
                r.font.bold = o.get("bold", bold)
                r.font.italic = o.get("italic", italic)
                r.font.color.rgb = rgb(o.get("color", color))
        return tb

    @staticmethod
    def box(s, x, y, w, h, fill=RAISED, line=LINE, radius=0.07, name=None, line_w=0.75, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
        shp = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
        if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
            shp.adjustments[0] = radius
        if fill:
            shp.fill.solid()
            shp.fill.fore_color.rgb = rgb(fill)
        else:
            shp.fill.background()
        if line:
            shp.line.color.rgb = rgb(line)
            shp.line.width = Pt(line_w)
        else:
            shp.line.fill.background()
        shp.shadow.inherit = False
        if name:
            shp.name = name
        return shp

    def panel(self, s, x, y, w, h, accent: str | None = None, fill=RAISED, name=None):
        p = self.box(s, x, y, w, h, fill=fill, name=name)
        if accent:
            self.box(s, x + 0.12, y, w - 0.24, 0.06, fill=accent, line=None, radius=0.5)
        return p

    def pill(self, s, x, y, text, fill, color=DEEP, size=10.5, w=None, h=0.3):
        w = w or (0.34 + 0.075 * len(text))
        p = self.box(s, x, y, w, h, fill=fill, line=None, radius=0.5)
        tf = p.text_frame
        tf.margin_left = tf.margin_right = Inches(0.08)
        tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        para = tf.paragraphs[0]
        para.alignment = PP_ALIGN.CENTER
        r = para.add_run()
        r.text = text
        r.font.name, r.font.size, r.font.bold = UI, Pt(size), True
        r.font.color.rgb = rgb(color)
        return p

    def stat(self, s, x, y, w, number, label, size=44, color=INK, label_size=13, label_h=0.55, font=UI):
        num_h = size / 72 * 1.12
        self.text(s, x, y, w, num_h, number, size=size, bold=True, color=color, font=font)
        self.text(s, x, y + num_h, w, label_h, label, size=label_size, color=INK2)
        return y + num_h + label_h

    @staticmethod
    def arrow(s, x1, y1, x2, y2, color=INK3, width=1.5):
        c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
        c.line.color.rgb = rgb(color)
        c.line.width = Pt(width)
        tail = OxmlElement("a:tailEnd")
        tail.set("type", "triangle")
        tail.set("w", "med")
        tail.set("len", "med")
        c.line._get_or_add_ln().append(tail)
        return c

    def picture(self, s, path: Path, x, y, w, h, alt: str, name=None, frame=LINE, light=False,
                crop=(0.0, 0.0, 0.0, 0.0)):
        """Fit an image in the box (optionally cropped: left, top, right, bottom fractions); returns its geometry."""
        iw, ih = Image.open(path).size
        cl, ct, cr, cb = crop
        iw, ih = iw * (1 - cl - cr), ih * (1 - ct - cb)
        scale = min(w / iw, h / ih)
        pw, ph = iw * scale, ih * scale
        px, py = x + (w - pw) / 2, y + (h - ph) / 2
        if light:   # light-background figures sit on a paper card
            self.box(s, px - 0.12, py - 0.12, pw + 0.24, ph + 0.24, fill="F7F7F4", line=None, radius=0.04)
        pic = s.shapes.add_picture(str(path), Inches(px), Inches(py), Inches(pw), Inches(ph))
        pic.crop_left, pic.crop_top, pic.crop_right, pic.crop_bottom = cl, ct, cr, cb
        try:
            pic.auto_shape_type = MSO_SHAPE.ROUNDED_RECTANGLE
            geom = pic._element.spPr.find(qn("a:prstGeom"))
            av = geom.find(qn("a:avLst"))
            if av is None:
                av = OxmlElement("a:avLst")
                geom.append(av)
            gd = OxmlElement("a:gd")
            gd.set("name", "adj")
            gd.set("fmla", "val 3000")
            av.append(gd)
        except (AttributeError, ValueError):
            pass
        if frame and not light:
            pic.line.color.rgb = rgb(frame)
            pic.line.width = Pt(0.75)
        pic._element.nvPicPr.cNvPr.set("descr", alt)
        if name:
            pic.name = name
        self.last_geom = (px, py, pw, ph)
        return pic

    def lamps(self, s, x, y, on: bool) -> None:
        """The five start-light pods of the dashboard hero."""
        pw, ph, gap = 0.62, 1.06, 0.17
        rail = self.box(s, x - 0.1, y - 0.1, 5 * pw + 4 * gap + 0.2, ph + 0.2, fill="0E0F12", line="23262C", radius=0.12)
        rail.name = "gantry"
        for i in range(5):
            px = x + i * (pw + gap)
            self.box(s, px, y, pw, ph, fill="0A0B0D", line="2B2E35", radius=0.16)
            for j in range(2):
                cy = y + 0.12 + j * 0.45
                lamp = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(px + 0.12), Inches(cy), Inches(0.38), Inches(0.38))
                lamp.fill.solid()
                lamp.fill.fore_color.rgb = rgb(LAMP if on else "3A1416")
                lamp.line.color.rgb = rgb("5A1518" if on else "24262B")
                lamp.line.width = Pt(0.75)
                if on:
                    eff = OxmlElement("a:effectLst")
                    glow = OxmlElement("a:glow")
                    glow.set("rad", str(int(Inches(0.12))))
                    clr = OxmlElement("a:srgbClr")
                    clr.set("val", LAMP)
                    a = OxmlElement("a:alpha")
                    a.set("val", "55000")
                    clr.append(a)
                    glow.append(clr)
                    eff.append(glow)
                    lamp._element.spPr.append(eff)

    def notes(self, s, text: str, title: str, presenter: str, seconds: int) -> None:
        s.notes_slide.notes_text_frame.text = text
        self.script.append({"title": title, "presenter": presenter, "seconds": seconds, "notes": text})

    # ---------------------------------------------------------------- native charts
    def chart(self, s, kind, data, x, y, w, h, legend=True, value_fmt=None, vmin=None, vmax=None, major=None,
              font_size=11, gap=60, overlap=None, labels=False):
        gf = s.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), data)
        ch = gf.chart
        ch.font.name, ch.font.size = UI, Pt(font_size)
        ch.font.color.rgb = rgb(INK2)
        ch.has_legend = legend
        if legend:
            ch.legend.position = XL_LEGEND_POSITION.TOP
            ch.legend.include_in_layout = False
            ch.legend.font.size = Pt(font_size)
            ch.legend.font.color.rgb = rgb(INK2)
        ca, va = ch.category_axis, ch.value_axis
        ca.format.line.color.rgb = rgb(LINE)
        ca.major_tick_mark = XL_TICK_MARK.NONE
        ca.tick_labels.font.color.rgb = rgb(INK2)
        ca.tick_labels.font.size = Pt(font_size)
        va.has_major_gridlines = True
        va.major_gridlines.format.line.color.rgb = rgb(LINE)
        va.major_gridlines.format.line.width = Pt(0.6)
        va.format.line.fill.background()
        va.major_tick_mark = XL_TICK_MARK.NONE
        va.tick_labels.font.color.rgb = rgb(INK3)
        va.tick_labels.font.size = Pt(font_size - 1)
        if value_fmt:
            va.tick_labels.number_format = value_fmt
            va.tick_labels.number_format_is_linked = False
        if vmin is not None:
            va.minimum_scale = vmin
        if vmax is not None:
            va.maximum_scale = vmax
        if major is not None:
            va.major_unit = major
        if kind not in (XL_CHART_TYPE.XY_SCATTER_LINES_NO_MARKERS,):
            plot = ch.plots[0]
            plot.gap_width = gap
            if overlap is not None:
                plot.overlap = overlap
            if labels:
                plot.has_data_labels = True
                dl = plot.data_labels
                dl.number_format = "0;;;"
                dl.number_format_is_linked = False
                dl.font.size = Pt(font_size - 1)
                dl.font.bold = True
                dl.font.color.rgb = rgb(DEEP)
        self._transparent(ch)
        return ch

    @staticmethod
    def _transparent(ch) -> None:
        def nofill(parent, anchor_tag=None):
            sp = parent.find(qn("c:spPr"))
            if sp is None:
                sp = OxmlElement("c:spPr")
                anchor = parent.find(qn(anchor_tag)) if anchor_tag else None
                if anchor is not None:
                    anchor.addnext(sp)
                else:
                    ext = parent.find(qn("c:extLst"))
                    ext.addprevious(sp) if ext is not None else parent.append(sp)
            for child in list(sp):
                sp.remove(child)
            sp.append(OxmlElement("a:noFill"))
            ln = OxmlElement("a:ln")
            ln.append(OxmlElement("a:noFill"))
            sp.append(ln)
        cs = ch._chartSpace
        nofill(cs, "c:chart")
        nofill(cs.find(qn("c:chart")).find(qn("c:plotArea")))

    @staticmethod
    def color_series(ch, colors: list[str | None]) -> None:
        for series, col in zip(ch.plots[0].series, colors):
            if col is None:
                series.format.fill.background()
            else:
                series.format.fill.solid()
                series.format.fill.fore_color.rgb = rgb(col)
            series.format.line.fill.background()


# ============================================================================================
# Facts used by the deck
# ============================================================================================
def presenter(component: str) -> tuple[str, str]:
    """(display name, script name) for a component letter."""
    m = next(t for t in config.TEAM if t["component"] == component)
    name = f"{m['given_name']} {m['family_name']}".strip()
    return name, f"Student {component}"


def extra_facts() -> dict:
    issues = pd.read_csv(config.QUALITY_DIR / "quality_issues.csv").set_index("issue_id")
    gaps = pd.read_csv(config.FAIR_DIR / "fair_gaps.csv")
    rda = pd.read_csv(config.FAIR_DIR / "rda_fair_summary.csv").set_index("area")
    eras = pd.read_csv(config.QUALITY_FIG_DIR / "fig_b3_points_eras_data.csv")
    com = pd.read_csv(config.GRAPH_DIR / "communities.csv")
    return {
        "season_missing": int(issues.loc["B01", "affected_records"]),
        "round_missing": int(issues.loc["B02", "affected_records"]),
        "gaps": len(gaps),
        "rda_indicators": int(rda.loc["Overall", "indicators"]),
        "win_min": int(eras["typical"].min()), "win_max": int(eras["maximum"].max()),
        "win_values": sorted({int(v) for v in eras["typical"]}),
        "years": config.LAST_COMPLETE_SEASON - config.FIRST_SEASON,
        "era_names": com[com["drivers"] >= 10].sort_values("median_debut")["most_central_drivers"]
        .str.split("; ").str[0].tolist(),
        "big_communities": int((com["drivers"] >= 10).sum()),
    }


def surname(full: str) -> str:
    parts = full.split()
    particles = {"de", "da", "di", "van", "von", "la", "le", "del"}
    out = [parts[-1]]
    i = len(parts) - 2
    while i >= 1 and parts[i].lower() in particles:
        out.insert(0, parts[i])
        i -= 1
    return " ".join(out)


# ============================================================================================
# Slides
# ============================================================================================
def build() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    F = facts()
    X = extra_facts()
    d = Deck()
    name = {c: presenter(c)[0] for c in "ABC"}
    A, B, C = name["A"], name["B"], name["C"]
    fuji = pd.read_csv(config.FAIR_DIR / "fuji_summary.csv").set_index("resource")
    llm = F["ev_llm"] or {}
    card = F["card"]

    # 1 ---------------------------------------------------------------------------------- title
    s = d.slide("Group project", glow=True)
    d.lamps(s, 4.55, 0.95, on=True)
    d.text(s, M, 2.55, 12.1, 1.0, "From raw race results", size=54, font=UI_BLACK, color=INK, name="title")
    d.text(s, M, 3.42, 12.1, 0.8, "to a FAIR, quality-assured knowledge graph", size=34, bold=True, color=INK2)
    d.text(s, M, 4.32, 12.1, 0.5, f"Formula 1 World Championship results, {config.FIRST_SEASON}\u2013"
                                  f"{config.LAST_COMPLETE_SEASON}. Data Management, Winter 2026/27.",
           size=17, font=SERIF, color=INK2)
    for i, m in enumerate(config.TEAM):
        x = M + i * 4.08
        d.panel(s, x, 5.15, 3.86, 1.45, accent=PURPLE, name=f"team_{m['component']}")
        d.text(s, x + 0.25, 5.38, 3.4, 1.2, [
            [(f"{m['given_name']} {m['family_name']}", {"font": UI, "bold": True, "size": 18, "color": INK})],
            [(f"Student {m['component']}: {m['title']}", {"size": 12.5, "color": INK2})]], spacing_after=3)
    d.footer(s, None)
    d.notes(s, f"Good morning, we are {A}, {B} and {C}. We take {X['years']} years of Formula 1 results from raw "
               "files to a FAIR, quality-assured dataset, a knowledge graph, a dashboard and an assistant that "
               "answers questions with evidence. Lights out.", "Title", "All (opened by Student A)", 20)

    # 2 ---------------------------------------------------------------------------------- dataset
    s = d.slide("The dataset")
    y0 = d.title(s, f"{F['seasons']} seasons of F1 results with real quality issues",
                 "Every World Championship Grand Prix from Silverstone 1950 to Abu Dhabi 2025, from the Ergast "
                 "database as served by the Jolpica-F1 API.")
    kpis = [(f"{F['raw_rows']:,}", "race results, one row per car per race"),
            (f"{F['gp']:,}", "championship Grands Prix"),
            (f"{F['drivers']}", f"drivers and {F['constructors']} constructor entries"),
            (f"{F['circuits']}", f"circuits in {F['countries']} countries")]
    kw = (SLIDE_W - 2 * M) / 4
    d.box(s, M, y0 + 0.15, SLIDE_W - 2 * M, 0.01, fill=LINE, line=None, shape=MSO_SHAPE.RECTANGLE)
    for i, (num, lab) in enumerate(kpis):
        x = M + i * kw
        if i:
            d.box(s, x, y0 + 0.15, 0.01, 1.75, fill=LINE, line=None, shape=MSO_SHAPE.RECTANGLE)
        d.stat(s, x + (0.25 if i else 0), y0 + 0.4, kw - 0.4, num, lab, size=48, label_size=13)
    d.box(s, M, y0 + 1.9, SLIDE_W - 2 * M, 0.01, fill=LINE, line=None, shape=MSO_SHAPE.RECTANGLE)
    why = [("Relational", "One fact table and four reference tables: joins and keys matter."),
           ("Real defects", f"{F['seasons']} seasons of rule changes and file exports, not planted errors."),
           ("A natural network", "Drivers, teams, circuits and countries connect into a graph.")]
    for i, (h, b) in enumerate(why):
        x = M + i * 4.08
        d.panel(s, x, y0 + 2.25, 3.86, 1.55, accent=BLUE)
        d.text(s, x + 0.25, y0 + 2.48, 3.4, 1.25, [[(h, {"bold": True, "size": 17, "color": INK})],
                                                    [(b, {"size": 13.5, "color": INK2, "font": SERIF})]],
               spacing_after=5)
    d.text(s, M, 6.55, 12, 0.3, "The curated package covers Grands Prix; sprint races are out of its scope.",
           size=11.5, color=INK3)
    d.footer(s, A)
    d.notes(s, f"Our dataset is the Ergast Formula 1 database, which the group downloaded from its successor, the "
               f"Jolpica API. The core table has {F['raw_rows']:,} race results: one row for every car in every "
               f"championship Grand Prix since 1950, {F['gp']:,} races in total. We chose it because it is "
               "relational, so keys and joins matter; its quality problems are real, coming from decades of rule "
               "changes and file exports; and drivers, teams and circuits form a natural network.",
            "Dataset and motivation", "Student A", 40)

    # 3 ---------------------------------------------------------------------------------- CRISP-DM + medallion
    s = d.slide("Method")
    y0 = d.title(s, "CRISP-DM + Medallion architecture & automated execution",
                 "Three zones that only read the zone before them, and every CRISP-DM phase backed by evidence.")
    zones = [(BRONZE, "Bronze", "Raw zone", f"{F['raw_rows']:,}", "rows extracted, values unchanged, lineage to "
                                                                    "file and line"),
             (SILVER, "Silver", "Clean zone", f"{F['gates_passed']}/{F['gates']}",
              f"validation gates before {F['clean_rows']:,} clean rows are written"),
             (GOLD, "Gold", "Served zone", f"{F['pg_edges']:,}", "graph edges, plus the FAIR record, the dashboard "
                                                                 "and the assistant")]
    zw = 3.75
    for i, (col, medal, zone, num, sub) in enumerate(zones):
        x = M + i * (zw + 0.42)
        d.panel(s, x, y0 + 0.05, zw, 2.0, accent=col)
        d.text(s, x + 0.25, y0 + 0.28, zw - 0.5, 0.4, [[(medal, {"bold": True, "color": col}),
                                                         (f"  {zone}", {"color": INK2})]], size=15)
        d.text(s, x + 0.25, y0 + 0.7, zw - 0.5, 0.7, num, size=34, bold=True, color=INK)
        d.text(s, x + 0.25, y0 + 1.32, zw - 0.5, 0.65, sub, size=12.5, color=INK2)
        if i < 2:
            d.arrow(s, x + zw + 0.05, y0 + 1.05, x + zw + 0.37, y0 + 1.05, color=INK3)
    phases = [("Business understanding", "research questions, FAIR goals"),
              ("Data understanding", f"profiling: {F['issues']} issues with file and line"),
              ("Data preparation", f"{F['gates']} gates, an audit record per step"),
              ("Modelling", "property graph, podium-probability model"),
              ("Evaluation", f"{F['tests']} tests" + (f", assistant {llm['answer_contains_expected']}/"
                                                      f"{llm['questions']} benchmark" if llm else "")),
              ("Deployment", "dashboard and grounded assistant")]
    pw = (SLIDE_W - 2 * M - 5 * 0.12) / 6
    for i, (h, b) in enumerate(phases):
        x = M + i * (pw + 0.12)
        d.box(s, x, y0 + 2.35, pw, 1.45, fill=DEEP, line=LINE)
        d.text(s, x + 0.15, y0 + 2.48, pw - 0.3, 1.25, [[(f"{i + 1}", {"bold": True, "color": PURPLE, "size": 16})],
                                                         [(h, {"bold": True, "size": 12.5, "color": INK})],
                                                         [(b, {"size": 11, "color": INK2})]], spacing_after=2)
    d.box(s, M, 6.15, 6.2, 0.55, fill=DEEP, line=PURPLE, radius=0.5)
    d.text(s, M + 0.3, 6.25, 5.8, 0.4, "python run_all.py --from-scratch", size=15, font=MONO, color=INK,
           anchor=MSO_ANCHOR.MIDDLE)
    d.text(s, M + 6.45, 6.27, 6.0, 0.4, f"byte-identical reruns, {F['tests']} automated tests, no network needed",
           size=13, color=INK2)
    d.footer(s, C)
    d.notes(s, "We followed CRISP-DM inside a medallion layout. Bronze keeps the raw archive exactly as received, "
               "with lineage to the file and line. Silver is only written when every validation gate passes. Gold "
               "holds what people use: the FAIR record, the graph, the dashboard and the assistant. Each CRISP-DM "
               "phase has its own evidence, from the issue register to the tests and the assistant benchmark, and "
               "one command rebuilds everything with byte-identical results.", "CRISP-DM and medallion",
            "Student C", 40)

    # 4 ---------------------------------------------------------------------------------- architecture (native)
    s = d.slide("Data engineering")
    y0 = d.title(s, "Data engineering: zones, contracts and controls",
                 "The issue register is the contract between profiling and cleaning; the schema module is the "
                 "contract between cleaning and metadata.")
    cols = [(M, "Source", INK3), (M + 2.5, "Raw zone", BRONZE), (M + 5.0, "Quality", ORANGE),
            (M + 7.5, "Clean zone", SILVER), (M + 10.0, "Served zone", GOLD)]
    bw = 2.1
    for x, label, col in cols:
        d.text(s, x, y0 + 0.02, bw, 0.3, label, size=13, bold=True, color=col)
    def node(x, y, h, t, b, col, emph=False):  # noqa: E306
        d.box(s, x, y, bw, h, fill=PURPLE_DEEP if emph else RAISED, line=PURPLE if emph else LINE)
        d.box(s, x + 0.1, y, bw - 0.2, 0.05, fill=col, line=None, radius=0.5)
        d.text(s, x + 0.15, y + 0.13, bw - 0.3, h - 0.2, [[(t, {"bold": True, "size": 13, "color": INK})],
                                                          [(b, {"size": 10.5, "color": INK2})]], spacing_after=2)
    yA, yB, h1 = y0 + 0.45, y0 + 1.55, 0.95
    node(M, yA, h1, "Ergast / Jolpica", "public F1 API\nCC BY-NC-SA 4.0", INK3)
    node(M, yB, h1, "racing_f1_data.zip", "DOI 10.5281/zenodo.23416916\nSHA-256 pinned", INK3)
    node(M + 2.5, yA, h1, "Step 0: extract", "format detection,\nfile + line lineage", BRONZE)
    node(M + 2.5, yB, h1, "data/raw", "5 CSV tables,\nvalues unchanged", BRONZE)
    node(M + 5.0, yA, h1, "Profiling", f"{F['issues']} issues,\n{F['dims']} dimensions", ORANGE)
    node(M + 5.0, yB, h1, "Issue register", "contract B to C:\nevidence + fix step", ORANGE)
    node(M + 7.5, yA, h1, "Cleaning", "12 audited steps", SILVER)
    node(M + 7.5, yB, h1, "Validation gates", f"{F['gates']} checks, fail-fast", SILVER)
    node(M + 7.5, yB + 1.1, h1, "data/cleaned", f"{F['clean_rows']:,} x {F['clean_cols']}\n+ 4 reference tables",
         SILVER)
    served = [("FAIR record", "DataCite 4.5, PROV-O"), ("Property graph", f"{F['pg_edges']:,} edges"),
              ("Dashboard + assistant", "7 views + Ask"), ("Report and slides", "generated from outputs")]
    for i, (t, b) in enumerate(served):
        node(M + 10.0, yA + i * 0.8, 0.7, t, b, GOLD, emph=(i == 2))
    for x in (M, M + 2.5, M + 5.0, M + 7.5):
        d.arrow(s, x + bw / 2, yA + h1, x + bw / 2, yB)
    d.arrow(s, M + 7.5 + bw / 2, yB + h1, M + 7.5 + bw / 2, yB + 1.1)
    for x in (M, M + 2.5, M + 5.0):
        d.arrow(s, x + bw, yB + h1 / 2, x + 2.5, yA + h1 / 2)
    for i in range(4):
        d.arrow(s, M + 7.5 + bw, yB + 1.1 + h1 / 2, M + 10.0, yA + i * 0.8 + 0.35)
    d.text(s, M + 5.0, yB + 1.15, 2.3, 0.75, "Feedback loop: issue B29 came back from the dashboard", size=11,
           color=PURPLE, font=SERIF, italic=True)
    ctrl = [("Schema as code", "one contract for C and A"), ("Orchestration", "run_all.py, byte-identical reruns"),
            ("Automated tests", f"{F['tests']} tests on key decisions"), ("Lineage", "file + line, checksums, PROV-O")]
    d.box(s, M, 6.0, SLIDE_W - 2 * M, 0.78, fill=DEEP, line=LINE)
    for i, (t, b) in enumerate(ctrl):
        d.text(s, M + 0.25 + i * 3.02, 6.1, 2.9, 0.62, [[(t, {"bold": True, "size": 12.5, "color": INK})],
                                                         [(b, {"size": 11, "color": INK2})]], spacing_after=1)
    d.footer(s, C)
    d.notes(s, "Here is the architecture behind it. Data move through zones: an immutable raw zone that keeps the "
               "source values and their lineage, a clean zone that is only written when every validation gate "
               "passes, and served products. Two contracts hold it together: the issue register between profiling "
               "and cleaning, and one schema module shared by cleaning and metadata. Underneath are four controls: "
               "the schema as code, one orchestrated command, automated tests, and lineage down to the source line.",
            "Data engineering architecture", "Student C", 40)

    # 5 ---------------------------------------------------------------------------------- Spark medallion
    s = d.slide("Data engineering")
    y0 = d.title(s, "The Spark medallion pipeline and its gold star schema",
                 "The incremental batch pipeline in PySpark notebooks: ingest each landing file to bronze, conform it "
                 "in silver, model it as a star schema in gold.")
    d.picture(s, ASSETS / "spark_medallion_pipeline.png", M + 0.1, y0 + 0.2, 4.2, 3.7,
              "Flowchart of the Spark pipeline: ingest, transform and build steps per entity.", light=True)
    d.picture(s, ASSETS / "gold_star_schema.png", M + 4.9, y0 + 0.2, 7.1, 3.7,
              "Gold star schema: fact_session_results with dim_races, dim_constructors and dim_drivers.", light=True)
    d.text(s, M, 6.42, 12.1, 0.5, [[("Gold also holds sprint sessions (session_type) and feeds the classic "
                                     "dashboard (RQ1-RQ6) and the ML prototype; ", {"color": INK2}),
                                    ("the curated FAIR package covers Grands Prix only.", {"color": INK})]],
           size=13)
    d.footer(s, A)
    d.notes(s, "Next to the curated pipeline, the repository also contains the Spark implementation of the medallion "
               "idea. Every landing file is ingested into bronze, transformed in silver and modelled in gold as a "
               "star schema: one fact table of session results with race, constructor and driver dimensions. It runs "
               "in incremental batches and feeds the classic dashboard and the machine-learning prototype. Note that "
               "gold also holds sprint sessions, while the curated FAIR package covers Grands Prix only.",
            "Spark medallion and star schema", "Student A", 35)

    # 6 ---------------------------------------------------------------------------------- A: F-UJI
    s = d.slide("Sector 1: FAIR")
    y0 = d.title(s, f"Same archive, two homes: {F['fuji_github']:.1f}% on GitHub, {F['fuji_zenodo']:.1f}% "
                    "on Zenodo",
                 f"F-UJI 4.0.1 with metrics v{F['fuji_version']} (as on f-uji.net) on the four locations of the "
                 "data; the Zenodo record has a DOI.")
    order = [("zenodo_raw_archive", "Group Zenodo record", "DOI, published 16 Oct 2026", PURPLE),
             ("kaggle_ergast_mirror", "Kaggle mirror", "public copy of Ergast", TEAL),
             ("github_repository", "Group GitHub repository", "raw zip, no identifier", BLUE),
             ("jolpica_ergast_api", "Jolpica API", "where the data was downloaded", ORANGE)]
    tx, tw = M, 7.7
    for i, (key, label, role, col) in enumerate(order):
        r = fuji.loc[key]
        y = y0 + 0.2 + i * 0.92
        d.box(s, tx, y, tw, 0.82, fill=RAISED if i else PURPLE_DEEP, line=PURPLE if i == 0 else LINE)
        d.box(s, tx, y + 0.12, 0.06, 0.62, fill=col, line=None, radius=0.5)
        d.text(s, tx + 0.25, y + 0.1, 3.3, 0.7, [[(label, {"bold": True, "size": 14.5, "color": INK})],
                                                  [(role, {"size": 11, "color": INK3})]])
        bar_x, bar_w = tx + 3.55, 2.2
        d.box(s, bar_x, y + 0.36, bar_w, 0.14, fill=DEEP, line=None, radius=0.5)
        d.box(s, bar_x, y + 0.36, max(0.05, bar_w * r["fair_percent"] / 100), 0.14, fill=col, line=None, radius=0.5)
        d.text(s, bar_x + bar_w + 0.12, y + 0.18, 1.0, 0.5, f"{r['fair_percent']:.1f}%", size=19, bold=True,
               color=PURPLE if i == 0 else INK)
        d.text(s, tx + tw - 0.12 - 4.4, y + 0.57, 4.4, 0.25,
               "   ".join(f"{k} {r[c]:.0f}" for k, c in (("F", "F_percent"), ("A", "A_percent"),
                                                    ("I", "I_percent"), ("R", "R_percent"))), size=10,
               color=INK3, align=PP_ALIGN.RIGHT)
    rx = M + 8.15
    d.panel(s, rx, y0 + 0.2, SLIDE_W - M - rx, 3.6, accent=PURPLE)
    yy = d.stat(s, rx + 0.3, y0 + 0.42, 4.0, f"{F['rda_before']:.0f}% \u2192 {F['rda_after']:.0f}%",
                f"RDA maturity over {X['rda_indicators']} indicators: as obtained \u2192 our package", size=36,
                label_h=0.6)
    yy = d.stat(s, rx + 0.3, yy + 0.15, 4.0, f"{F['ess_before']} \u2192 {F['ess_after']}",
                "essential indicators met", size=36, label_h=0.35)
    d.text(s, rx + 0.3, yy + 0.2, 3.8, 0.9, "Findable stays at RDA level 0 until the curated package has its own DOI; "
                                           "the raw archive already has one.", size=12, font=SERIF, color=INK2)
    d.text(s, M, 6.45, 12, 0.4, "F-UJI checks machine-readable signals only: it scores a licence as present, not as "
                                "compatible. The RDA model also weighs licences and provenance.", size=12,
           color=INK3)
    d.footer(s, A)
    d.notes(s, "We measured FAIRness twice. First automatically with F-UJI, using the same metric version as the "
               f"public service, on four locations of the data. The Jolpica API scores {F['fuji_jolpica']:.1f} "
               f"percent and our GitHub repository {F['fuji_github']:.1f}. The same zip on Zenodo, deposited by our "
               f"group with a DOI, scores {F['fuji_zenodo']:.1f} percent, the same total as the Kaggle mirror but "
               "far more findable. Because F-UJI only sees what is online, we also scored all "
               f"{X['rda_indicators']} RDA indicators with written evidence: our package lifts maturity from "
               f"{F['rda_before']:.0f} to {F['rda_after']:.0f} percent.", "FAIR assessment", "Student A", 45)

    # 7 ---------------------------------------------------------------------------------- A: licences and PIDs
    s = d.slide("Sector 1: FAIR")
    y0 = d.title(s, "Eliminating licensing ambiguity and metadata gaps",
                 "Five places publish the same results under four different terms. The data must stay "
                 "CC BY-NC-SA 4.0.")
    rows = [("Ergast (original source)", "non-commercial use only", "Origin", INK3),
            ("Jolpica-F1 (our download)", "CC BY-NC-SA 4.0", "Binding", GREEN),
            ("Kaggle mirror", "claims CC0, public domain", "Conflict", RED),
            ("Group GitHub repository", "MIT licence for everything", "Conflict", RED),
            ("Group Zenodo record", "CC BY 4.0", "Correct it", AMBER)]
    for i, (who, what, verdict, col) in enumerate(rows):
        y = y0 + 0.05 + i * 0.66
        d.box(s, M, y, 7.3, 0.56, fill=RAISED, line=LINE)
        d.text(s, M + 0.2, y + 0.13, 3.0, 0.35, who, size=13.5, bold=True, color=INK)
        d.text(s, M + 3.25, y + 0.14, 2.75, 0.35, what, size=12.5, color=INK2)
        d.pill(s, M + 7.3 - 0.2 - 1.15, y + 0.13, verdict, col, w=1.15)
    d.box(s, M, y0 + 3.45, 7.3, 0.95, fill=DEEP, line=GREEN)
    d.text(s, M + 0.22, y0 + 3.55, 6.9, 0.8, [
        [("Resolution  ", {"bold": True, "color": GREEN}), ("data CC BY-NC-SA 4.0 with attribution; code MIT", {})],
        [("Zenodo licence to be corrected to CC BY-NC-SA 4.0: a metadata edit, the DOI does not change",
          {"color": INK2, "size": 12})]], size=13.5, color=INK, spacing_after=3)
    rx = M + 7.7
    z = F["zenodo"]
    d.panel(s, rx, y0 + 0.05, SLIDE_W - M - rx, 4.35, accent=PURPLE)
    d.text(s, rx + 0.28, y0 + 0.28, 4.3, 0.35, "Persistent identifiers", size=15, bold=True, color=INK)
    d.text(s, rx + 0.28, y0 + 0.72, 4.4, 0.4, z["doi"], size=17, font=MONO, color=PURPLE)
    d.text(s, rx + 0.28, y0 + 1.1, 4.3, 0.55, "DOI of the raw archive, byte-identical to our source (MD5 checked), "
                                              "cited as IsDerivedFrom", size=11.5, color=INK2)
    pid_rows = [(f"{F['qid_driver']:.1f}%", f"drivers linked to Wikidata (constructors {F['qid_con']:.1f}%, "
                                            f"circuits {F['qid_circ']:.0f}%)"),
                ("4.5", "DataCite record validated against the official XSD"),
                ("Next", "own DOI for the curated package, ORCID iDs, ROR")]
    for i, (n, t) in enumerate(pid_rows):
        y = y0 + 1.85 + i * 0.8
        d.text(s, rx + 0.28, y, 1.35, 0.55, n, size=24, bold=True, color=INK)
        d.text(s, rx + 1.68, y + 0.06, 3.0, 0.65, t, size=11.5, color=INK2)
    d.footer(s, A)
    d.notes(s, "Licences were the biggest gap. Ergast allowed only non-commercial use and Jolpica, where we "
               "downloaded the data, licenses it CC BY-NC-SA 4.0. Yet the Kaggle mirror claims public domain, our "
               "own repository says MIT for everything, and our Zenodo record says CC BY 4.0. Share-alike means "
               "the data must stay CC BY-NC-SA, so that is what our package declares, with MIT for code only, and "
               "the Zenodo licence will be corrected without changing the DOI. On identifiers: the raw archive "
               f"has a DOI, {F['qid_driver']:.1f} percent of drivers are linked to Wikidata, and the DataCite record "
               "validates against the official schema.", "Licences and identifiers", "Student A", 45)

    # 8 ---------------------------------------------------------------------------------- B: disguised nulls
    s = d.slide("Sector 2: Quality")
    disguised = F["pos_disguised"] + F["grid_zero"]
    y0 = d.title(s, "Uncovering disguised nulls behind surface completeness",
                 "The results table looks 99.9% complete. It is not: most of its gaps wear the costume of data.")
    full = SLIDE_W - 2 * M - 2.4
    for i, (lab, val, col) in enumerate([("Explicit nulls", F["null_cells"], INK3),
                                         ("Disguised missing values", disguised, AMBER)]):
        y = y0 + 0.25 + i * 1.25
        d.text(s, M, y, 4.5, 0.35, lab, size=15, bold=True, color=INK)
        d.box(s, M, y + 0.45, full, 0.32, fill=RAISED, line=None, radius=0.5)
        d.box(s, M, y + 0.45, max(0.05, full * val / disguised), 0.32, fill=col, line=None, radius=0.5)
        d.text(s, M + full + 0.25, y + 0.28, 2.1, 0.7, f"{val:,}", size=40, bold=True,
               color=AMBER if i else INK)
    parts = [(f"{F['pos_disguised']:,}", "'positions' that are really retirements, withdrawals or disqualifications"),
             (f"{F['grid_zero']}", "cars on a fictitious 'grid slot 0'"),
             ("18th", "is how a model would read a car that retired")]
    for i, (n, t) in enumerate(parts):
        x = M + i * 4.08
        d.panel(s, x, y0 + 2.85, 3.86, 1.5, accent=AMBER if i < 2 else RED)
        d.text(s, x + 0.25, y0 + 3.05, 3.4, 1.2, [[(n, {"bold": True, "size": 30, "color": INK})],
                                                   [(t, {"size": 12.5, "color": INK2})]], spacing_after=2)
    d.footer(s, B)
    d.notes(s, f"I profiled every column of all five tables and ran {F['issues']} quality rules. The first lesson: "
               f"completeness is deceptive. Only {F['null_cells']} cells are empty, so the table looks almost "
               f"perfect. But {disguised:,} values only pretend to be data: the position column is filled for "
               f"{F['pos_disguised']:,} drivers who did not finish, and {F['grid_zero']} cars start from a grid slot "
               "zero that does not exist. A model would learn that a retirement is eighteenth.",
            "Disguised nulls", "Student B", 40)

    # 9 ---------------------------------------------------------------------------------- B: duplicates
    s = d.slide("Sector 2: Quality")
    y0 = d.title(s, "A naive duplicate check deletes real history",
                 "Rows sharing season, round and driver: true duplicates in red, legitimate shared drives in blue.")
    dup = pd.read_csv(config.QUALITY_FIG_DIR / "fig_b2_duplicates_data.csv")
    cd = CategoryChartData()
    cd.categories = [str(v) for v in dup["season"]]
    cd.add_series("Same driver, two cars (valid history)", [int(v) for v in dup["shared_drives"]])
    cd.add_series("True duplicate record (error)", [int(v) for v in dup["true_duplicates"]])
    ch = d.chart(s, XL_CHART_TYPE.COLUMN_STACKED, cd, M - 0.1, y0 + 0.05, 8.1, 4.25, gap=45, overlap=100)
    d.color_series(ch, [BLUE, RED])
    rx = M + 8.35
    yy = d.stat(s, rx, y0 + 0.15, 4.0, f"{F['dup_exact'] + F['dup_hidden']}", "true duplicates, all from 1960",
                size=40, color=RED, label_h=0.4)
    yy = d.stat(s, rx, yy + 0.15, 4.0, f"{F['dup_hidden']}", "of them hidden behind blanked keys", size=40,
                label_h=0.4)
    yy = d.stat(s, rx, yy + 0.15, 4.0, f"{F['shared']}", "valid rows: one driver, two cars in one race", size=40,
                color=BLUE, label_h=0.4)
    d.text(s, rx, yy + 0.2, 4.0, 0.7, [[("Correct key  ", {"bold": True, "color": INK}),
                                        ("season, round, driver and car number", {"color": INK2})]], size=13)
    d.footer(s, B)
    d.notes(s, f"Uniqueness needs domain knowledge. {F['dup_exact']} rows of the 1960 United States Grand Prix were "
               f"appended twice, and {F['dup_hidden']} rows of the 1960 Italian Grand Prix are copies whose season "
               "and round were blanked. The red bar is the real problem. The blue bars are not: "
               f"{F['shared']} rows share season, round and driver because in the 1950s a driver could take over a "
               "team-mate's car and be classified twice. The correct key includes the car number.",
            "Duplicates vs shared drives", "Student B", 40)

    # 10 --------------------------------------------------------------------------------- B: valid history
    s = d.slide("Sector 2: Quality")
    y0 = d.title(s, "Valid history can look like bad data",
                 "Points for winning a race, season by season: the same achievement, a different currency in "
                 "every era.")
    eras = pd.read_csv(config.QUALITY_FIG_DIR / "fig_b3_points_eras_data.csv")
    xy = XyChartData()
    s1 = xy.add_series("Points for a win (most common)")
    for yr, v in zip(eras["season"], eras["typical"]):
        s1.add_data_point(int(yr), float(v))
    s2 = xy.add_series("Highest award that season")
    for yr, v in zip(eras["season"], eras["maximum"]):
        s2.add_data_point(int(yr), float(v))
    ch = d.chart(s, XL_CHART_TYPE.XY_SCATTER_LINES_NO_MARKERS, xy, M - 0.1, y0 + 0.05, 8.0, 3.2, vmin=0, vmax=55,
                 major=10)
    ca = ch.category_axis
    ca.minimum_scale, ca.maximum_scale, ca.major_unit = 1950, 2025, 10
    ca.tick_labels.number_format, ca.tick_labels.number_format_is_linked = "0", False
    ca.has_major_gridlines = False
    for series, col, wdt in zip(ch.plots[0].series, [PURPLE, INK3], [2.75, 1.0]):
        series.format.line.color.rgb = rgb(col)
        series.format.line.width = Pt(wdt)
        series.smooth = False
        series.marker.style = XL_MARKER_STYLE.NONE
    d.text(s, M + 5.2, y0 + 0.55, 2.7, 0.5, "2014 Abu Dhabi: double points, 50", size=11, color=INK3, font=SERIF,
           italic=True)
    rx = M + 8.35
    yy = d.stat(s, rx, y0 + 0.15, 4.0, f"{X['win_min']}\u2013{X['win_max']}", "points for the same race win",
                size=40, color=PURPLE, label_h=0.4)
    d.stat(s, rx, yy + 0.2, 4.0, f"{F['indy_outliers']}", "lap 'outliers', all valid Indianapolis 500 results: "
                                                          "flag them, never delete", size=40, label_h=0.7)
    impacts = [("Inflated win counts", "from duplicated rows"), ("Biased targets", "a retirement read as 18th"),
               ("Era bias", "raw points favour recent decades")]
    for i, (h, b) in enumerate(impacts):
        x = M + i * 4.08
        d.box(s, x, 5.98, 3.86, 0.75, fill=DEEP, line=LINE)
        d.text(s, x + 0.22, 6.08, 3.5, 0.6, [[(h, {"bold": True, "size": 13.5, "color": INK})],
                                            [(b, {"size": 11.5, "color": INK2})]])
    d.text(s, M, 5.62, 6, 0.3, "Impact on data science and AI", size=12.5, bold=True, color=INK3)
    d.footer(s, B)
    d.notes(s, "Some issues are not errors at all, but they still break analyses. A race win was worth "
               f"{', '.join(map(str, X['win_values']))} or even {X['win_max']} points depending on the era, so raw "
               f"points are not comparable over time. All {F['indy_outliers']} statistical outliers in laps are "
               "valid Indianapolis 500 results, so we flag them instead of deleting them. For data science the "
               "impact is concrete: inflated win counts, biased prediction targets and era bias in all-time "
               "rankings.", "Eras, outliers and impact", "Student B", 40)

    # 11 --------------------------------------------------------------------------------- C: order matters
    s = d.slide("Sector 3: Cleaning")
    y0 = d.title(s, "Order matters: repair keys, then de-duplicate",
                 "The same two steps in the opposite order leave a third of the duplicates in the data.")
    col_w = (SLIDE_W - 2 * M - 0.35) / 2
    for i, (accent, head, steps, num, lab, numcol) in enumerate([
        (RED, "Naive order", ["1  Remove exact duplicates", "2  Repair missing keys"], f"{F['dup_hidden']}",
         "duplicates survive, hidden by the blanked keys", RED),
        (GREEN, "Our order: steps C02 \u2192 C03",
         [f"1  Restore season ({X['season_missing']}) and round ({X['round_missing']}) by exact lookup",
          "2  Remove exact duplicates"], f"{F['dup_exact'] + F['dup_hidden']}",
         "duplicates removed, none left; a unit test locks it in", GREEN)]):
        x = M + i * (col_w + 0.35)
        d.panel(s, x, y0 + 0.05, col_w, 3.3, accent=accent)
        d.text(s, x + 0.3, y0 + 0.3, col_w - 0.6, 0.4, head, size=18, bold=True, color=INK)
        d.text(s, x + 0.3, y0 + 0.82, col_w - 0.6, 0.9, steps, size=14, color=INK2, spacing_after=4)
        d.text(s, x + 0.3, y0 + 1.75, 2.0, 1.1, num, size=60, font=UI_BLACK, color=numcol)
        d.text(s, x + 2.05, y0 + 2.1, col_w - 2.4, 0.8, lab, size=13.5, color=INK2)
    d.text(s, M, y0 + 3.6, 6, 0.4, "No invented values", size=16, bold=True, color=INK)
    d.text(s, M, y0 + 4.0, 12, 0.7, [f"Grid 0 becomes missing plus a flag ({F['grid_zero']} rows); no statistical "
                                     "imputation anywhere.",
                                     "Keys come only from deterministic lookups: the file name and races.csv."],
           size=13.5, color=INK2, font=SERIF, spacing_after=3)
    d.footer(s, C)
    d.notes(s, "The most important design decision was the order of operations. If you remove duplicates first and "
               f"repair keys afterwards, {F['dup_hidden']} duplicates survive, because their season and round were "
               "blanked. So step C02 restores the season from the file name and the round by an exact lookup in "
               f"the races table, and only then does step C03 remove all {F['dup_exact'] + F['dup_hidden']} copies. "
               "A unit test documents both orders, and no value is ever invented.", "Order of operations",
            "Student C", 40)

    # 12 --------------------------------------------------------------------------------- C: every issue closed
    s = d.slide("Sector 3: Cleaning")
    y0 = d.title(s, "Every issue closed, every output validated",
                 f"How the {F['issues']} quality issues were resolved, per dimension. Flag, don't delete.")
    res = pd.read_csv(config.CLEANING_DIR / "fig_c1_resolution_data.csv").iloc[::-1]
    cd = CategoryChartData()
    cd.categories = list(res["dimension"])
    cols_res = [c for c in res.columns if c != "dimension"]
    for c in cols_res:
        cd.add_series(c, [int(v) for v in res[c]])
    ch = d.chart(s, XL_CHART_TYPE.BAR_STACKED, cd, M - 0.1, y0 + 0.0, 8.0, 4.35, gap=45, overlap=100, labels=True,
                 major=2)
    d.color_series(ch, [GREEN, AMBER, INK3, BLUE])
    rx = M + 8.35
    yy = d.stat(s, rx, y0 + 0.15, 4.0, f"{F['gates_passed']}/{F['gates']}", "validation gates passed; one failure "
                                                                            "blocks publishing", size=40,
                color=PURPLE, label_h=0.6)
    yy = d.stat(s, rx, yy + 0.15, 4.0, f"{F['fixed']} of {F['issues']}", "issues fixed; the rest flagged, kept or "
                                                                         "verified", size=40, label_h=0.6)
    d.stat(s, rx, yy + 0.15, 4.0, f"{F['clean_rows']:,}", f"clean rows, {F['clean_cols']} documented columns",
           size=40, label_h=0.4)
    d.footer(s, C)
    d.notes(s, f"Every one of the {F['issues']} issues is now closed: {F['fixed']} are fixed, {F['flagged']} are "
               f"mitigated or flagged, {F['kept']} are kept and documented, and {F['not_error']} were verified as "
               "non-errors. Our rule is flag, don't delete: Indianapolis 500 rows and shared drives stay, with "
               f"flags. Status went from {F['status_raw']} free-text values to {F['status_groups']} groups, and "
               f"{F['gates']} validation gates must all pass before anything is published as clean.",
            "Validation and resolution", "Student C", 40)

    # 13 --------------------------------------------------------------------------------- graph: small world
    s = d.slide("The graph")
    y0 = d.title(s, f"{X['years']} years of F1 form a small world",
                 f"A NetworkX property graph of {F['pg_nodes']:,} nodes and {F['pg_edges']:,} typed edges; drivers "
                 "linked when they shared a team in a Grand Prix.")
    d.picture(s, DASH / "dashboard_network.png", M + 4.45, y0 + 0.05, 7.65, 4.35,
              "The team-mate network in the dashboard, with the Fangio to Verstappen chain highlighted.",
              crop=(0.0, 0.065, 0.0, 0.0))
    yy = d.stat(s, M, y0 + 0.1, 4.1, f"{F['clust']:.2f}", f"clustering, against {F['clust_r']:.3f} in a random "
                                                         "graph", size=40, color=PURPLE, label_h=0.4)
    yy = d.stat(s, M, yy + 0.1, 4.1, f"{F['aspl']:.1f}", "team-mate links between two drivers on average", size=40,
                label_h=0.4)
    chain = [F["path"].iloc[0]["from"]] + F["path"]["to"].tolist()
    d.text(s, M, yy + 0.18, 4.1, 0.35, f"Fangio to Verstappen in {F['hops']} steps", size=14, bold=True, color=INK)
    d.text(s, M, yy + 0.55, 4.1, 1.2, "  \u2192  ".join(surname(n) for n in chain), size=12.5, color=INK2,
           font=SERIF, line_spacing=1.15)
    d.footer(s, B)
    d.notes(s, "We modelled the cleaned data as a property graph: drivers, races, constructors, circuits and "
               "countries, with results on the edges and a derived team-mate relationship. Indianapolis 500 rounds "
               "are excluded from the team-mate projection, a direct consequence of the quality analysis. The result "
               f"is a small world: clustering is {F['clust']:.2f} against {F['clust_r']:.3f} for a random graph, yet "
               f"two drivers are on average only {F['aspl']:.1f} links apart. Fangio reaches Verstappen in "
               f"{F['hops']} steps.", "Property graph and small world", "Student B", 40)

    # 14 --------------------------------------------------------------------------------- graph: communities
    s = d.slide("The graph")
    y0 = d.title(s, "Communities rediscover the eras by themselves",
                 "Louvain communities of the team-mate network: the algorithm never sees a date, yet each community "
                 "is an era.")
    com = pd.read_csv(config.GRAPH_DIR / "communities.csv")
    com = com[com["drivers"] >= 10].sort_values("median_debut", ascending=False)
    cd = CategoryChartData()
    cd.categories = [f"{r.most_central_drivers.split('; ')[0]} ({r.drivers})" for r in com.itertuples()]
    cd.add_series("offset", [int(v) for v in com["first_debut"]])
    cd.add_series("Seasons active (first debut to last season)", [int(b - a) for a, b in
                                                                   zip(com["first_debut"], com["last_active"])])
    ch = d.chart(s, XL_CHART_TYPE.BAR_STACKED, cd, M - 0.1, y0 + 0.0, 8.0, 4.4, legend=False, vmin=1950, vmax=2030,
                 major=10, gap=55, overlap=100)
    ch.value_axis.tick_labels.number_format, ch.value_axis.tick_labels.number_format_is_linked = "0", False
    d.color_series(ch, [None, PURPLE])
    rx = M + 8.35
    top = F["top"]
    yy = d.stat(s, rx, y0 + 0.15, 4.0, f"{F['communities']}", f"Louvain communities, modularity "
                                                             f"{F['modularity']:.2f}", size=40, label_h=0.4)
    yy = d.stat(s, rx, yy + 0.15, 4.0, f"{top['betweenness'].iloc[0]:.2f}",
                "highest betweenness; bridges between eras: " + ", ".join(top["name"].head(3).map(surname)),
                size=40, color=PURPLE, label_h=0.65)
    d.panel(s, rx, yy + 0.2, 4.1, 1.35, accent=AMBER)
    d.text(s, rx + 0.25, yy + 0.38, 3.65, 1.1, [[("Caveat", {"bold": True, "size": 13.5, "color": INK})],
                                                 [("Before the 1970s 'constructor' was the chassis make shared by "
                                                   "private entrants, which inflates early degrees.",
                                                   {"size": 11.5, "color": INK2})]], spacing_after=2)
    d.footer(s, A)
    d.notes(s, f"Louvain community detection finds {F['communities']} communities with a modularity of "
               f"{F['modularity']:.2f}. The algorithm never sees a date, yet the large communities line up with eras, "
               f"from the fifties around {X['era_names'][0]} to the present grid around {X['era_names'][-1]}. "
               f"Betweenness highlights bridges between eras such as {top['name'].iloc[0]}. One caveat links back to "
               "data quality: before the seventies the constructor field records the chassis make shared by "
               "private entrants, so early drivers look more connected than they were.", "Communities by era",
            "Student A", 35)

    # 15 --------------------------------------------------------------------------------- dashboard
    s = d.slide("Served zone")
    y0 = d.title(s, "The project, live: our interactive dashboard",
                 "Seven views and an assistant, built only from validated outputs and rebuilt by run_all.py.")
    d.picture(s, DASH / "dashboard_hero.png", M, y0 + 0.05, 8.0, 4.4, "The dashboard opening: start lights and "
              "the key figures of the dataset.")
    rx = M + 8.35
    feats = [("Validated data only", "build_web_data.py reads the clean tables, graph metrics, issue register and "
                                     "FAIR scores"),
             ("A quality instrument", "its reliability view revealed issue B29: retirement causes not recorded "
                                      "from 2023")]
    yy = y0 + 0.1
    for h, b in feats:
        d.text(s, rx, yy, 4.1, 1.1, [[(h, {"bold": True, "size": 14.5, "color": INK})],
                                     [(b, {"size": 12, "color": INK2})]], spacing_after=2)
        yy += 1.15
    d.box(s, rx, yy + 0.1, 4.1, 1.45, fill=PURPLE_DEEP, line=PURPLE)
    d.text(s, rx + 0.25, yy + 0.25, 3.7, 1.2, [[("Live demo", {"bold": True, "size": 15, "color": INK})],
                                               [("streamlit run app.py", {"font": MONO, "size": 14, "color": INK})],
                                               [("then localhost:8501", {"size": 12, "color": INK2})]],
           spacing_after=3)
    d.footer(s, C)
    d.notes(s, "Everything we showed ends here, in an interactive dashboard that opens with one command. It reads "
               "only validated outputs, and run_all rebuilds it as its last step. It also paid back: the reliability "
               "view showed mechanical failures vanishing after 2022, which turned out to be the source no longer "
               "recording why cars retired. That became issue B29. If time allows, we open it live.",
            "Interactive dashboard", "Student C", 30)

    # 16 --------------------------------------------------------------------------------- dashboard gallery
    s = d.slide("Served zone")
    d.title(s, "Inside the dashboard: every chart reads validated data")
    gallery = [("dashboard_drivers.png", "Timing tower: wins, podiums, era-adjusted score"),
               ("dashboard_grid.png", "Grid to finish, pole conversion, furthest-back wins"),
               ("dashboard_reliability.png", "Reliability, with the 2023 break (B29) marked"),
               ("dashboard_circuits.png", f"{F['circuits']} circuits on a rotating globe")]
    gw, gh = 5.85, 2.22
    for i, (file, cap) in enumerate(gallery):
        x = M + (i % 2) * (gw + 0.4)
        y = 1.5 + (i // 2) * (gh + 0.52)
        d.picture(s, DASH / file, x, y, gw, gh, cap, name=f"gallery_{i}", crop=(0.0, 0.065, 0.0, 0.0))
        px, py, pw, ph = d.last_geom
        d.text(s, px, py + ph + 0.07, pw, 0.3, cap, size=12, color=INK2)
    d.footer(s, B)
    d.notes(s, "Four more views. The timing tower ranks drivers by wins or by our era-adjusted score. The grid view "
               "shows where cars finish from each starting slot, using classified positions only, which is exactly "
               "the fix for issue B11. The reliability view marks the 2023 break that became issue B29, and the "
               "globe places all seventy-seven circuits.", "Dashboard gallery", "Student B", 25)

    # 17 --------------------------------------------------------------------------------- ask the data
    s = d.slide("Served zone")
    y0 = d.title(s, "Ask the data: an LLM that cannot invent numbers",
                 "A local Llama 3 phrases the answer; the figures come from code over the validated data and are "
                 "checked afterwards.")
    d.picture(s, DASH / "dashboard_ask.png", M, y0 + 0.0, 7.75, 3.3, "The Ask section: a question answered by the "
              "local Llama 3 with a cited evidence block and the figure check.")
    steps = [("Understand", "names, seasons, intent"), ("Evidence", "pandas, graph, model, documents"),
             ("Write", "Llama 3, cites [S1]"), ("Check", "every figure traced")]
    sw = 7.75 / 4
    for i, (h, b) in enumerate(steps):
        x = M + i * sw
        shp = d.box(s, x, y0 + 3.45, sw - 0.06, 0.85, fill=RAISED if i < 3 else PURPLE_DEEP,
                    line=LINE if i < 3 else PURPLE, shape=MSO_SHAPE.PENTAGON if i < 3 else MSO_SHAPE.ROUNDED_RECTANGLE)
        shp.name = f"ask_step_{i}"
        d.text(s, x + 0.2, y0 + 3.53, sw - 0.5, 0.75, [[(h, {"bold": True, "size": 13.5, "color": INK})],
                                                     [(b, {"size": 10.5, "color": INK2})]], spacing_after=1)
    rx = M + 8.15
    if llm:
        yy = d.stat(s, rx, y0 + 0.05, 4.2, f"{llm['answer_contains_expected']}/{llm['questions']}",
                    "benchmark answers correct, written by the model", size=40, color=PURPLE, label_h=0.4)
        yy = d.stat(s, rx, yy + 0.1, 4.2, f"{llm['figures_verified']}/{llm['figures_total']}",
                    "figures in the answers traced to the evidence", size=40, label_h=0.4)
        yy = d.stat(s, rx, yy + 0.1, 4.2, f"{llm['median_total_seconds']:.0f} s",
                    "median per answer on a laptop CPU, no GPU", size=40, label_h=0.4)
    else:
        yy = y0
    d.text(s, rx, yy + 0.15, 4.2, 1.0, [[("Podium model, tested on 2020-2025  ", {"bold": True, "color": INK})],
                                        [(f"log loss {card['test_metrics']['log_loss']:.3f} vs "
                                          f"{card['baseline_test_metrics']['log_loss']:.3f} for the grid alone, but no "
                                          "better podium picks: we say so", {"color": INK2})]], size=11.5,
           spacing_after=2)
    d.text(s, rx, 6.62, 4.3, 0.3, "Idea and prototype: Manohar Zalki (Graphic-LlmRag)", size=10.5, color=INK3)
    d.footer(s, B)
    d.notes(s, "The last view lets anyone question the data, in English or Spanish. It grows out of the LLM and RAG "
               "prototype from our group, rebuilt so that the language model never supplies a number. The question "
               "is parsed, the evidence is computed with pandas from the cleaned tables, with the file and raw line "
               "of every figure, plus the team-mate graph and a podium model. Llama 3 runs locally and only phrases "
               "that evidence, and every figure is checked afterwards. On "
               f"{llm.get('questions', 25)} benchmark questions with independently computed answers, "
               f"{llm.get('answer_contains_expected', 0)} were right, and it declined the question about 2030.",
            "Ask the data", "Student B", 40)

    # 18 --------------------------------------------------------------------------------- lessons
    s = d.slide("Finish")
    d.title(s, "What we learned")
    lessons = [("Quality is contextual", "Outliers, duplicates and short grids were often valid history."),
               ("Order of operations matters", f"{F['dup_hidden']} duplicates hid behind blanked keys."),
               ("FAIR gaps sit around the values", "Identifiers, licences and provenance, not the numbers."),
               ("Automate the evidence", f"Audit log, {F['gates']} gates, {F['tests']} tests, metadata from code.")]
    lw, lh = (SLIDE_W - 2 * M - 0.3) / 2, 1.55
    for i, (h, b) in enumerate(lessons):
        x = M + (i % 2) * (lw + 0.3)
        y = 1.65 + (i // 2) * (lh + 0.25)
        d.panel(s, x, y, lw, lh, accent=PURPLE)
        d.text(s, x + 0.3, y + 0.28, 0.8, 1.0, f"{i + 1}", size=40, font=UI_BLACK, color=PURPLE)
        d.text(s, x + 1.1, y + 0.33, lw - 1.4, 1.1, [[(h, {"bold": True, "size": 19, "color": INK})],
                                                     [(b, {"size": 13.5, "color": INK2, "font": SERIF})]],
               spacing_after=4)
    d.box(s, M, 5.35, SLIDE_W - 2 * M, 1.2, fill=PURPLE_DEEP, line=PURPLE)
    d.text(s, M + 0.3, 5.55, 0.8, 0.9, "5", size=40, font=UI_BLACK, color=PURPLE)
    d.text(s, M + 1.1, 5.6, 11.0, 0.9, [[("A language model needs a data layer", {"bold": True, "size": 19,
                                                                                "color": INK})],
                                        [("Code computes every figure; the model only phrases it, and a check "
                                          "follows.", {"size": 13.5, "color": INK2, "font": SERIF})]],
           spacing_after=4)
    d.footer(s, C)
    d.notes(s, "Five lessons. Quality is contextual: outliers, duplicates and short grids were often valid history. "
               f"The order of operations matters, as the {F['dup_hidden']} hidden duplicates show. The largest FAIR "
               "gaps sit around the values: identifiers, licences and provenance. Automating the evidence turns "
               "cleaning into something an examiner can verify. And a language model needs a data layer: code "
               "computes, the model only phrases. Next steps are a DOI for the curated package and reporting the "
               "source defects upstream.", "Conclusion", "Student C", 25)

    # 19 --------------------------------------------------------------------------------- questions
    s = d.slide("Finish")
    d.lamps(s, 4.55, 0.95, on=False)
    d.text(s, M, 2.45, 12.1, 1.4, "Questions?", size=72, font=UI_BLACK, color=INK, name="title")
    d.text(s, M, 3.85, 12.1, 0.45, "Lights out. Code, data, metadata, report and dashboard:", size=17, font=SERIF,
           color=INK2)
    d.text(s, M, 4.32, 12.1, 0.45, "github.com/zalkimanohar/Formula1-Racing-Analytics", size=17, font=MONO,
           color=INK)
    for i, m in enumerate(config.TEAM):
        d.pill(s, M + i * 3.55, 5.15, f"{m['given_name']} {m['family_name']}", RAISED, color=INK, size=12.5, w=3.3,
               h=0.42)
    stripe_w = 0.42
    for i in range(int(SLIDE_W / stripe_w) + 2):
        st = s.shapes.add_shape(MSO_SHAPE.PARALLELOGRAM, Inches(i * stripe_w - 0.2), Inches(6.38),
                                Inches(stripe_w + 0.08), Inches(0.24))
        st.fill.solid()
        st.fill.fore_color.rgb = rgb("D7262E" if i % 2 == 0 else "F2F0EA")
        st.line.fill.background()
    d.footer(s, None)
    d.notes(s, "Thank you. We are happy to take your questions; each of us will answer on our own component.",
            "Questions", "All", 5)

    assert len(d.prs.slides) == TOTAL, f"deck has {len(d.prs.slides)} slides, TOTAL says {TOTAL}"
    d.prs.save(OUT_PPTX)
    write_script(d.script)
    print(f"[slides] {len(d.prs.slides)} slides -> {OUT_PPTX.name}")
    return OUT_PPTX


def write_script(script: list[dict]) -> None:
    budget = sum(i["seconds"] for i in script)
    names = {f"Student {m['component']}": f"{m['given_name']} {m['family_name']}" for m in config.TEAM}
    for item in script:
        item["seconds"] = round(item["seconds"] * 600 / budget)
        item["presenter"] = names.get(item["presenter"], item["presenter"])
        for key, full in names.items():
            item["presenter"] = item["presenter"].replace(key, full)
    script[-1]["seconds"] += 600 - sum(i["seconds"] for i in script)
    lines = ["# Presenter script - group presentation (10 minutes + 5 minutes Q&A)", "",
             f"Speaking pace assumed: {SPEAKING_WPM} words per minute. Time budget per slide below; rehearse "
             "once with a timer. Present from the PDF, or install the fonts in report/assets/fonts before opening "
             "the PowerPoint.", "", "| # | Slide | Presenter | Budget | Words | Est. at pace |",
             "|---|---|---|---|---|---|"]
    per_presenter: dict[str, int] = {}
    for i, item in enumerate(script, start=1):
        words = len(item["notes"].split())
        est = round(words / SPEAKING_WPM * 60)
        lines.append(f"| {i} | {item['title']} | {item['presenter']} | {item['seconds']} s | {words} | {est} s |")
        key = item["presenter"].split(" (")[0]
        per_presenter[key] = per_presenter.get(key, 0) + item["seconds"]
    total = sum(i["seconds"] for i in script)
    lines += ["", f"**Total budget:** {total // 60} min {total % 60:02d} s.", "",
              "| Presenter | Time budget |", "|---|---|"]
    lines += [f"| {k} | {v // 60} min {v % 60:02d} s |" for k, v in per_presenter.items()]
    lines += ["", "## Script per slide", ""]
    for i, item in enumerate(script, start=1):
        lines += [f"### Slide {i} - {item['title']} ({item['presenter']}, {item['seconds']} s)", "", item["notes"], ""]
    lines += ["## Hand-over cues", ""]
    for i in range(1, len(script)):
        prev, nxt = script[i - 1]["presenter"], script[i]["presenter"]
        if prev != nxt and "All" not in (prev, nxt):
            lines.append(f"- Slide {i} -> {i + 1}: {prev} hands over to {nxt} for '{script[i]['title']}'.")
    lines.append("")
    OUT_SCRIPT.write_text("\n".join(lines), encoding="utf-8")


def convert_pdf(pptx: Path) -> Path | None:
    soffice = config.find_soffice()
    if not soffice:
        return None
    profile = (config.REPORT_DIR / "presentation" / ".lo_profile").resolve().as_uri()
    subprocess.run([soffice, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf",
                    "--outdir", str(pptx.parent), str(pptx)], check=True, capture_output=True)
    shutil.rmtree(config.REPORT_DIR / "presentation" / ".lo_profile", ignore_errors=True)
    return pptx.with_suffix(".pdf")


def run() -> None:
    pptx = build()
    pdf = convert_pdf(pptx)
    print(f"[slides] PDF: {pdf.name if pdf else 'LibreOffice not found'}")


if __name__ == "__main__":
    run()
