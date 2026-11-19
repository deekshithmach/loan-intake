"""Draw each document type to PDF with ReportLab (amounts in cents -> dollars)."""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

W, H = letter


def usd(c: int) -> str:
    return f"{'-' if c < 0 else ''}${abs(c) / 100:,.2f}"


def _rows(c: canvas.Canvas, x: float, y: float, rows: list[tuple[str, str]], gap: int = 16) -> float:
    for k, v in rows:
        c.setFont("Helvetica", 10)
        c.drawString(x, y, k)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 200, y, v)
        y -= gap
    return y


def paystub(f: dict, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, H - 60, f["employer"])
    c.setFont("Helvetica", 11)
    c.drawString(50, H - 78, "EARNINGS STATEMENT")
    y = _rows(c, 50, H - 115, [
        ("Employee", f["employee"]),
        ("Pay Period", f"{f['pay_period_start']} to {f['pay_period_end']}"),
        ("Pay Date", f["pay_date"]),
        ("Gross Pay", usd(f["gross"])),
        ("YTD Gross", usd(f["ytd_gross"]))])
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y - 10, "Deductions")
    y = _rows(c, 50, y - 30, [(k.replace("_", " ").title(), usd(v)) for k, v in f["deductions"].items()])
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y - 14, "NET PAY")
    c.drawString(250, y - 14, usd(f["net"]))
    c.save()


def w2(f: dict, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(50, H - 55, f"Form W-2  Wage and Tax Statement  {f['year']}")
    boxes = [("a Employee SSN", f["ssn"]), ("b Employer ID (EIN)", f["ein"]),
             ("c Employer name", f["employer"]), ("e Employee name", f["employee"]),
             ("1 Wages, tips, other comp.", usd(f["wages_box1"])),
             ("2 Federal income tax withheld", usd(f["federal_tax_box2"])),
             ("3 Social security wages", usd(f["ss_wages_box3"])),
             ("4 Social security tax withheld", usd(f["ss_tax_box4"])),
             ("5 Medicare wages and tips", usd(f["medicare_wages_box5"])),
             ("6 Medicare tax withheld", usd(f["medicare_tax_box6"]))]
    y = H - 90
    for i in range(0, len(boxes), 2):
        for j, (label, val) in enumerate(boxes[i:i + 2]):
            x = 50 + j * 260
            c.rect(x, y - 40, 250, 45)
            c.setFont("Helvetica", 7)
            c.drawString(x + 4, y - 8, label)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(x + 8, y - 30, val)
        y -= 50
    c.setFont("Helvetica", 8)
    c.drawString(50, y - 10, "Copy B - To Be Filed With Employee's Federal Tax Return")
    c.save()


def statement(f: dict, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)

    def header() -> None:
        c.setFont("Helvetica-Bold", 15)
        c.drawString(50, H - 55, f["bank"])
        c.setFont("Helvetica", 10)
        c.drawString(50, H - 72, f"Account holder: {f['account_holder']}   Account: ****{f['account_last4']}")
        c.drawString(50, H - 86, f"Statement period: {f['period_start']} to {f['period_end']}")
        c.drawString(50, H - 100, f"Opening balance: {usd(f['opening_balance'])}")

    header()
    y = H - 130
    c.setFont("Helvetica-Bold", 9)
    for x, t in ((50, "Date"), (120, "Description"), (350, "Amount"), (440, "Balance")):
        c.drawString(x, y, t)
    y -= 14
    c.setFont("Helvetica", 9)
    for t in f["transactions"]:
        if y < 70:
            c.showPage()
            header()
            y = H - 130
            c.setFont("Helvetica", 9)
        c.drawString(50, y, t["date"])
        c.drawString(120, y, t["description"])
        c.drawRightString(410, y, usd(t["amount"]))
        c.drawRightString(500, y, usd(t["balance"]))
        y -= 13
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, max(y - 10, 40), f"Closing balance: {usd(f['closing_balance'])}")
    c.save()


DRAW = {"paystub": paystub, "w2": w2, "statement": statement}
