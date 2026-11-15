"""Report exporters: CSV, Excel (openpyxl) and PDF (reportlab). Each returns bytes."""
import csv
import io

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def _safe(v):
    s = "" if v is None else str(v)
    return "'" + s if s.startswith(_DANGEROUS) else s


def to_csv(headers, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow([_safe(c) for c in r])
    return buf.getvalue().encode("utf-8-sig")


def to_xlsx(headers, rows, title="Attendance"):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2B3550")
    for r in rows:
        ws.append([_safe(c) for c in r])
    for i, h in enumerate(headers, start=1):
        width = max([len(str(h))] + [len(str(r[i - 1])) for r in rows] or [10])
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(width + 3, 40)
    ws.freeze_panes = "A2"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def to_pdf(headers, rows, title="Attendance report"):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=24, rightMargin=24,
                            topMargin=24, bottomMargin=24, title=title)
    styles = getSampleStyleSheet()
    data = [headers] + [[_pdf_text(c) for c in r] for r in rows] if rows else [headers]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B3550")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF1F6")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D0DC")),
    ]))
    doc.build([Paragraph(_pdf_text(title), styles["Title"]), Spacer(1, 8), table])
    return out.getvalue()


def _pdf_text(v):
    # Built-in Helvetica cannot draw non-Latin text (e.g. Devanagari); replace instead of crashing.
    s = "" if v is None else str(v)
    return s.encode("latin-1", "replace").decode("latin-1")
