"""
PDF report generator (ReportLab) - multi-page, automatic.

Sections: title page (with a 3D thumbnail), parameters, R/Y/G rating of key
parameters, 3D polar charts, 2D airfoil polars + Cp distribution, stability
derivatives table, raw data, AI interpretation. Page numbers and a footer.
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                Table, TableStyle, HRFlowable, PageBreak)

from . import charts

_ACCENT = colors.HexColor("#2563eb")
_DARK = colors.HexColor("#111827")
_MUTED = colors.HexColor("#6b7280")
_GREEN = colors.HexColor("#059669")
_YELLOW = colors.HexColor("#d97706")
_RED = colors.HexColor("#dc2626")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("FTitle", parent=ss["Title"], fontSize=26,
                          textColor=_DARK, spaceAfter=2))
    ss.add(ParagraphStyle("FSub", parent=ss["Normal"], fontSize=9,
                          textColor=_MUTED, spaceAfter=10))
    ss.add(ParagraphStyle("FH2", parent=ss["Heading2"], fontSize=12,
                          textColor=_ACCENT, spaceBefore=12, spaceAfter=4))
    ss.add(ParagraphStyle("FBody", parent=ss["Normal"], fontSize=9.5,
                          leading=14, textColor=_DARK))
    ss.add(ParagraphStyle("FBig", parent=ss["Normal"], fontSize=11,
                          textColor=_MUTED))
    return ss


def _img(png: bytes, width=85 * mm):
    bio = io.BytesIO(png)
    img = Image(bio)
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth = width
    img.drawHeight = width * ratio
    return img


def _kv_table(rows, ss):
    data = [[Paragraph(f"<b>{k}</b>", ss["FBody"]), Paragraph(str(v), ss["FBody"])]
            for k, v in rows]
    t = Table(data, colWidths=[62 * mm, 98 * mm])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#eef2f7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _data_table(res, ss):
    header = ["alpha", "CL", "CD", "Cm", "L/D"]
    data = [header]
    for i in range(len(res.alpha_deg)):
        ld = res.CL[i] / res.CD[i] if res.CD[i] > 1e-6 else 0
        data.append([f"{res.alpha_deg[i]:.1f}", f"{res.CL[i]:.3f}",
                     f"{res.CD[i]:.4f}", f"{res.Cm[i]:.3f}", f"{ld:.1f}"])
    t = Table(data, colWidths=[26 * mm] * 5)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _verdict_static_margin(sm):
    if 0.05 <= sm <= 0.20:
        return _GREEN, "OK", "stable (margin in the recommended 5-20% MAC range)"
    if 0.0 <= sm < 0.05:
        return _YELLOW, "CAUTION", "small margin - sensitive to rear loading"
    if sm > 0.20:
        return _YELLOW, "CAUTION", "large margin - very stable but sluggish in control"
    return _RED, "BAD", "unstable - move the CG forward"


def _verdict_clmax(clmax):
    if clmax >= 1.1:
        return _GREEN, "OK", "good maximum lift"
    if clmax >= 0.9:
        return _YELLOW, "CAUTION", "moderate CL_max - higher stall speed"
    return _RED, "BAD", "low CL_max - high minimum speed"


def _verdict_ld(ld):
    if ld >= 15:
        return _GREEN, "OK", "good aerodynamic efficiency"
    if ld >= 9:
        return _YELLOW, "CAUTION", "average efficiency"
    return _RED, "BAD", "low efficiency - high drag"


def _assessment_table(res, ss):
    rows = [("Parameter", "Value", "Rating", "Comment")]
    styles = [("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
              ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("FONTSIZE", (0, 0), (-1, -1), 8.5),
              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
              ("TOPPADDING", (0, 0), (-1, -1), 4),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    items = [
        ("Static margin", f"{res.static_margin*100:.1f}% MAC",
         _verdict_static_margin(res.static_margin)),
        ("CL max", f"{res.CL_max:.2f}", _verdict_clmax(res.CL_max)),
        ("(L/D) max", f"{res.LD_max:.1f}", _verdict_ld(res.LD_max)),
    ]
    for ri, (name, val, (col, tag, comment)) in enumerate(items, start=1):
        rows.append([name, val, tag, comment])
        styles.append(("BACKGROUND", (2, ri), (2, ri), col))
        styles.append(("TEXTCOLOR", (2, ri), (2, ri), colors.white))
        styles.append(("ALIGN", (2, ri), (2, ri), "CENTER"))
    t = Table(rows, colWidths=[40 * mm, 30 * mm, 20 * mm, 70 * mm])
    t.setStyle(TableStyle(styles))
    return t


def _derivatives_table(res, ss):
    ex = res.extras or {}
    rows = [
        ("CL_alpha", f"{res.CL_alpha:.3f} /rad"),
        ("Cm_alpha", f"{res.Cm_alpha:.3f} /rad"),
    ]
    if "CL_q" in ex:
        rows.append(("CL_q", f"{ex['CL_q']:.3f}"))
    if "Cm_q" in ex:
        rows.append(("Cm_q", f"{ex['Cm_q']:.3f}"))
    rows += [
        ("Neutral point x_np", f"{res.neutral_point_x:.4f} m"),
        ("Center of gravity x_cg", f"{res.cg_x:.4f} m"),
        ("Static margin", f"{res.static_margin*100:.1f}% MAC"),
    ]
    return _kv_table(rows, ss)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(_MUTED)
    canvas.drawString(18 * mm, 10 * mm, "Flovis - aerodynamic analysis report")
    canvas.drawRightString(192 * mm, 10 * mm, f"Page {canvas.getPageNumber()}")
    canvas.setStrokeColor(colors.HexColor("#e5e7eb"))
    canvas.line(18 * mm, 13 * mm, 192 * mm, 13 * mm)
    canvas.restoreState()


def build_report(res, output_path: str | Path, model=None,
                 ai_text: str | None = None, airfoil=None,
                 polar2d=None, thumbnail_png: bytes | None = None) -> Path:
    """Build the multi-page PDF report from the analysis results."""
    output_path = Path(output_path)
    ss = _styles()
    doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            title=f"Flovis - {res.model_name}")
    story = []

    # ---------------- title page ----------------
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph("Flovis", ss["FTitle"]))
    story.append(Paragraph("Aerodynamic analysis report", ss["FBig"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=_ACCENT))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>{res.model_name}</b>", ss["FH2"]))
    story.append(Paragraph(f"Method: {res.method} &nbsp;|&nbsp; "
                           f"{datetime.now():%Y-%m-%d %H:%M}", ss["FSub"]))
    if thumbnail_png:
        story.append(Spacer(1, 6))
        story.append(_img(thumbnail_png, width=150 * mm))
    story.append(PageBreak())

    # ---------------- parameters ----------------
    story.append(Paragraph("Analysis parameters", ss["FH2"]))
    rows = [
        ("Method", res.method),
        ("Velocity", f"{res.velocity:.1f} m/s"),
        ("Reference area", f"{res.reference_area:.4f} m2"),
        ("Mean aerodynamic chord (MAC)", f"{res.mac:.4f} m"),
    ]
    if model is not None:
        rows.insert(1, ("Layout", getattr(model.layout, "value", str(model.layout))))
        rows.append(("Mass", f"{model.mass_kg:.2f} kg"))
    story.append(_kv_table(rows, ss))

    # ---------------- R/Y/G rating ----------------
    story.append(Paragraph("Key parameters rating", ss["FH2"]))
    story.append(_assessment_table(res, ss))

    # ---------------- 3D polar charts ----------------
    story.append(Paragraph("Model polars (3D)", ss["FH2"]))
    grid = Table([
        [_img(charts.cl_alpha_png(res)), _img(charts.polar_png(res))],
        [_img(charts.cm_alpha_png(res)), _img(charts.ld_png(res))],
    ], colWidths=[88 * mm, 88 * mm])
    grid.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.append(grid)

    # ---------------- stability / derivatives ----------------
    story.append(PageBreak())
    story.append(Paragraph("Longitudinal stability and derivatives", ss["FH2"]))
    story.append(_derivatives_table(res, ss))

    # ---------------- airfoil + 2D polars ----------------
    if airfoil is not None:
        story.append(Paragraph("Airfoil", ss["FH2"]))
        story.append(_img(charts.airfoil_png(airfoil), width=150 * mm))
    if polar2d is not None:
        story.append(Paragraph("Airfoil polars (2D)", ss["FH2"]))
        g2 = Table([[_img(charts.polar2d_cl_png(polar2d)),
                     _img(charts.polar2d_clcd_png(polar2d))],
                    [_img(charts.cp_png(polar2d)), ""]],
                   colWidths=[88 * mm, 88 * mm])
        g2.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        story.append(g2)
        story.append(Paragraph(
            f"Cl_max = {polar2d.cl_max:.2f} at {polar2d.alpha_stall:.1f} deg; "
            f"(Cl/Cd)_max = {polar2d.ld_max:.0f}; method: {polar2d.method}.",
            ss["FBody"]))

    # ---------------- raw data ----------------
    story.append(PageBreak())
    story.append(Paragraph("Raw data (3D polar)", ss["FH2"]))
    story.append(_data_table(res, ss))

    # ---------------- AI interpretation ----------------
    story.append(Paragraph("Interpretation (AI)", ss["FH2"]))
    if ai_text:
        for para in ai_text.split("\n"):
            if para.strip():
                story.append(Paragraph(para.strip(), ss["FBody"]))
                story.append(Spacer(1, 4))
    else:
        story.append(Paragraph(
            "<i>AI interpretation unavailable (optional section). Run Ollama "
            "with the qwen3:30b-a3b model to add a written description.</i>", ss["FBody"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_path
