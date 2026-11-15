"""Exports Excel (openpyxl) et PDF (reportlab)."""
from io import BytesIO
from xml.sax.saxutils import escape

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from database import repository as repo
from config import periode_label
from services.scoring_service import mention, to_percent

TEAL, BLUE, GREEN = colors.HexColor("#0E7C86"), colors.HexColor("#2E86AB"), colors.HexColor("#1B998B")


# ===================== EXCEL =====================
def _style_sheet(ws) -> None:
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0E7C86")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for col in ws.columns:
        width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max(12, width + 2), 60)
    ws.freeze_panes = "A2"


def _to_excel(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
            _style_sheet(writer.sheets[name[:31]])
    return buf.getvalue()


def _score(ev):
    return ev["score_final"] if ev else float("nan")


def excel_individual(bundle: dict) -> bytes:
    auto, mgr, df = bundle["auto"], bundle["manager"], bundle["comparison"]
    sa, sm = _score(auto), _score(mgr)
    synthese = pd.DataFrame([{
        "Collaborateur": bundle["user"]["nom_complet"],
        "Période": periode_label(bundle["periode"], bundle["annee"]),
        "Score auto (/5)": sa, "Score manager (/5)": sm,
        "Score manager (%)": to_percent(sm), "Écart (manager - auto)": sm - sa,
        "Mention": mention(sm)}])
    comments = []
    for row_auto in (auto["scores"] if auto else []):
        comments.append({"Critère": row_auto["nom"], "Type": "Auto", "Commentaire": row_auto["commentaire"]})
    for row_mgr in (mgr["scores"] if mgr else []):
        comments.append({"Critère": row_mgr["nom"], "Type": "Manager", "Commentaire": row_mgr["commentaire"]})
    for ev, label in ((auto, "Auto"), (mgr, "Manager")):
        if ev and ev["commentaires"]:
            comments.append({"Critère": "Commentaire général", "Type": label, "Commentaire": ev["commentaires"]})
    cdf = pd.DataFrame(comments, columns=["Critère", "Type", "Commentaire"])
    sheets = {"Synthèse": synthese, "Détail critères": df}
    if len(bundle["items_comparison"]):
        sheets["Éléments évalués"] = bundle["items_comparison"]
    sheets["Commentaires"] = cdf
    return _to_excel(sheets)


def excel_team(annee: int, periode: str, team: pd.DataFrame, manager_id: int | None = None) -> bytes:
    summary = team.drop(columns=["Statut auto", "Statut manager"]).copy()
    detail = pd.DataFrame(repo.list_scores_year(annee, manager_id, periode)).rename(columns={
        "collaborateur": "Collaborateur", "periode": "Période", "type": "Type", "critere": "Critère",
        "poids": "Poids (%)", "score": "Note", "commentaire": "Commentaire"})
    return _to_excel({"Équipe": summary, "Détail notes": detail})


# ===================== PDF =====================
_styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_styles["Title"], textColor=TEAL, fontSize=20)
H2 = ParagraphStyle("H2", parent=_styles["Heading2"], textColor=colors.HexColor("#0B4F6C"))
BODY = ParagraphStyle("B", parent=_styles["BodyText"], fontSize=9, leading=12)


def _fmt(v, nd=2) -> str:
    return "—" if v is None or v != v else f"{v:.{nd}f}"


def _table(data, col_widths=None) -> Table:
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF4F5")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8D4D8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 1), (-1, -1), "CENTER"),
    ]))
    return t


def _bar_chart(labels, series: list[list], names: list[str], height=190) -> Drawing:
    d = Drawing(480, height)
    ch = VerticalBarChart()
    ch.x, ch.y, ch.width, ch.height = 35, 35, 420, height - 55
    ch.data = [[0 if v is None or v != v else v for v in s] for s in series]
    ch.categoryAxis.categoryNames = [str(l)[:14] for l in labels]
    ch.categoryAxis.labels.fontSize = 7
    ch.valueAxis.valueMin, ch.valueAxis.valueMax, ch.valueAxis.valueStep = 0, 5, 1
    for i, col in enumerate((BLUE, GREEN)[:len(series)]):
        ch.bars[i].fillColor = col
    d.add(ch)
    return d


def _build(story) -> bytes:
    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                      topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                      title="Évaluation annuelle").build(story)
    return buf.getvalue()


def pdf_individual(bundle: dict) -> bytes:
    auto, mgr, df = bundle["auto"], bundle["manager"], bundle["comparison"]
    sa, sm = _score(auto), _score(mgr)
    story = [Paragraph("Évaluation annuelle", H1),
             Paragraph(f"<b>{escape(bundle['user']['nom_complet'])}</b> — "
                       f"{periode_label(bundle['periode'], bundle['annee'])}", BODY),
             Spacer(1, 10), Paragraph("Synthèse", H2),
             _table([["Score auto", "Score manager", "Écart", "Mention"],
                     [_fmt(sa) + " / 5", _fmt(sm) + " / 5", _fmt(sm - sa), mention(sm)]])]
    story += [Spacer(1, 12), Paragraph("Détail par critère", H2)]
    rows = [["Critère", "Poids %", "Auto", "Manager", "Écart"]]
    for _, r in df.iterrows():
        rows.append([Paragraph(escape(str(r["Critère"])), BODY), f"{r['Poids (%)']:g}",
                     _fmt(r["Auto"], 1), _fmt(r["Manager"], 1), _fmt(r["Écart"], 1)])
    story.append(_table(rows, [7 * cm, 2 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm]))
    if len(df):
        story += [Spacer(1, 10),
                  _bar_chart(df["Critère"], [list(df["Auto"]), list(df["Manager"])], ["Auto", "Manager"]),
                  Paragraph('<font color="#2E86AB">■ Auto</font> &nbsp; <font color="#1B998B">■ Manager</font>', BODY)]
    items = bundle["items_comparison"]
    if len(items):
        story += [Spacer(1, 12), Paragraph("Éléments évalués", H2)]
        rows = [["Élément", "Auto", "Manager", "Écart"]]
        for _, r in items.iterrows():
            rows.append([Paragraph(escape(str(r["Élément"])), BODY), _fmt(r["Auto"], 0),
                         _fmt(r["Manager"], 0), _fmt(r["Écart"], 0)])
        story.append(_table(rows, [9 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm]))
    story += [Spacer(1, 10), Paragraph("Commentaires", H2)]
    any_comment = False
    for ev, label in ((auto, "Auto-évaluation"), (mgr, "Évaluation manager")):
        if not ev:
            continue
        if ev["commentaires"]:
            any_comment = True
            story.append(Paragraph(f"<b>{label} — général :</b> {escape(ev['commentaires'])}", BODY))
        for s in ev["scores"]:
            if s["commentaire"]:
                any_comment = True
                story.append(Paragraph(f"<b>{label} — {escape(s['nom'])} :</b> {escape(s['commentaire'])}", BODY))
    if not any_comment:
        story.append(Paragraph("Aucun commentaire.", BODY))
    return _build(story)


def pdf_team(annee: int, periode: str, team: pd.DataFrame) -> bytes:
    story = [Paragraph(f"Rapport d'équipe — {periode_label(periode, annee)}", H1), Spacer(1, 8)]
    rows = [["Collaborateur", "Auto", "Manager", "Écart", "Mention"]]
    for _, r in team.iterrows():
        rows.append([Paragraph(escape(r["Collaborateur"]), BODY), _fmt(r["Auto"]), _fmt(r["Manager"]),
                     _fmt(r["Écart"]), r["Mention"]])
    story.append(_table(rows, [6 * cm, 2.3 * cm, 2.3 * cm, 2.3 * cm, 3 * cm]))
    avg = team["Manager"].mean()
    story += [Spacer(1, 8), Paragraph(f"<b>Moyenne manager de l'équipe :</b> {_fmt(avg)} / 5", BODY)]
    if len(team):
        story += [Spacer(1, 10),
                  _bar_chart(team["Collaborateur"], [list(team["Auto"]), list(team["Manager"])], ["Auto", "Manager"]),
                  Paragraph('<font color="#2E86AB">■ Auto</font> &nbsp; <font color="#1B998B">■ Manager</font>', BODY)]
    return _build(story)


def excel_logs(df: pd.DataFrame) -> bytes:
    return _to_excel({"Journal": df.drop(columns=["code"], errors="ignore")})
