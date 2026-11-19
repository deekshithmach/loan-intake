"""Build one synthetic applicant: all money in integer cents, consistent across docs."""
import random
from datetime import date, timedelta

from faker import Faker

TAX_YEAR = 2025
PERIODS = 26  # biweekly
LAST_PAY_DATE = date(2025, 12, 26)
STMT_START, STMT_END = date(2025, 10, 1), date(2025, 12, 31)
BANKS = ["First Meridian Bank", "Lakeshore Savings", "Evergreen Credit Union", "Harborview Bank"]
ANOMALY_CODES = ["income_mismatch", "overdrafts", "fake_employer", "altered_totals"]
RATES = {"federal_tax": 0.12, "social_security": 0.062, "medicare": 0.0145, "state_tax": 0.04}
HEALTH_CENTS = 7500
SPEND = [  # (description pool, txns per month, share of monthly net)
    (["WHOLE FOODS", "SAFEWAY", "TRADER JOES", "KROGER"], 5, 0.14),
    (["SHELL OIL", "CHEVRON", "EXXON"], 3, 0.05),
    (["NETFLIX", "SPOTIFY", "AMAZON PRIME"], 2, 0.02),
    (["CHIPOTLE", "STARBUCKS", "DOORDASH", "PANERA"], 6, 0.07),
    (["CITY UTILITIES", "COMCAST", "VERIZON"], 2, 0.07),
]


def _d(d: date) -> str:
    return d.isoformat()


def _running(txns: list[dict], opening: int) -> int:
    bal = opening
    for t in txns:
        bal += t["amount"]
        t["balance"] = bal
    return bal


def _ein(rng: random.Random) -> str:
    return f"{rng.randrange(10, 99)}-{rng.randrange(1_000_000, 9_999_999)}"


def build_applicant(index: int, seed: int) -> dict:
    rng = random.Random(seed * 100_003 + index)
    fk = Faker("en_US")
    fk.seed_instance(seed * 100_003 + index)

    employer = fk.company().upper()
    salary = rng.randrange(38_000, 140_000, 500)
    gross = salary * 100 // PERIODS
    ded = {k: round(gross * r) for k, r in RATES.items()}
    ded["health_insurance"] = HEALTH_CENTS
    net = gross - sum(ded.values())
    ytd = gross * PERIODS  # last pay date of the tax year -> equals W-2 box 1
    name = fk.name().upper()
    ein = _ein(rng)
    ssn = f"9{rng.randrange(10, 99)}-{rng.randrange(10, 99)}-{rng.randrange(1000, 9999)}"  # 9xx never issued
    bank = rng.choice(BANKS)

    pay_dates = [LAST_PAY_DATE - timedelta(days=14 * k) for k in range(PERIODS)][::-1]
    stub = {
        "employer": employer, "employee": name,
        "pay_period_start": _d(LAST_PAY_DATE - timedelta(days=13)),
        "pay_period_end": _d(LAST_PAY_DATE), "pay_date": _d(LAST_PAY_DATE),
        "gross": gross, "net": net, "ytd_gross": ytd, "deductions": dict(ded),
    }
    w2 = {
        "employer": employer, "ein": ein, "employee": name, "ssn": ssn, "year": TAX_YEAR,
        "wages_box1": ytd, "federal_tax_box2": ded["federal_tax"] * PERIODS,
        "ss_wages_box3": ytd, "ss_tax_box4": ded["social_security"] * PERIODS,
        "medicare_wages_box5": ytd, "medicare_tax_box6": ded["medicare"] * PERIODS,
    }

    # bank statement: payroll deposits + spending
    txns = [{"date": _d(p), "description": f"PAYROLL {employer}", "amount": net}
            for p in pay_dates if STMT_START <= p <= STMT_END]
    monthly_net = net * PERIODS // 12
    for m in (10, 11, 12):
        txns.append({"date": _d(date(2025, m, 1)), "description": "RENT PAYMENT",
                     "amount": -round(monthly_net * 0.28)})
        for pool, n, share in SPEND:
            for _ in range(n):
                amt = round(monthly_net * share / n * rng.uniform(0.6, 1.4))
                txns.append({"date": _d(date(2025, m, rng.randint(2, 28))),
                             "description": rng.choice(pool), "amount": -amt})
    txns.sort(key=lambda t: t["date"])
    opening = rng.randrange(2500, 6000, 50) * 100
    statement = {"bank": bank, "account_holder": name, "account_last4": f"{rng.randrange(10000):04d}",
                 "period_start": _d(STMT_START), "period_end": _d(STMT_END),
                 "opening_balance": opening, "transactions": txns}

    # planted anomalies (~40% of applicants)
    anomalies: list[dict] = []
    if rng.random() < 0.4:
        codes = rng.sample(ANOMALY_CODES, 1 if rng.random() < 0.7 else 2)
        for code in codes:
            if code == "income_mismatch":
                w2["wages_box1"] = round(ytd * rng.uniform(1.2, 1.4))
                anomalies.append({"code": code, "doc": "w2", "field": "wages_box1",
                                  "detail": {"paystub_ytd_gross": ytd, "w2_wages": w2["wages_box1"]}})
            elif code == "fake_employer":
                fake = fk.company().upper()
                w2["employer"] = fake
                w2["ein"] = _ein(rng)
                anomalies.append({"code": code, "doc": "w2", "field": "employer",
                                  "detail": {"paystub_employer": employer, "w2_employer": fake}})
            elif code == "altered_totals":
                stub["net"] = net + rng.randrange(300, 900)
                anomalies.append({"code": code, "doc": "paystub", "field": "net",
                                  "detail": {"computed_net": net, "printed_net": stub["net"]}})
            elif code == "overdrafts":
                _running(txns, opening)
                i = rng.randrange(len(txns) // 3, 2 * len(txns) // 3)
                day = txns[i]["date"]
                over = txns[i]["balance"] + rng.randrange(50, 300)
                txns.insert(i + 1, {"date": day, "description": "ONLINE TRANSFER OUT", "amount": -over})
                txns.insert(i + 2, {"date": day, "description": "OVERDRAFT FEE", "amount": -3500})
                anomalies.append({"code": code, "doc": "statement", "field": "transactions",
                                  "detail": {"date": day, "fee_cents": 3500}})
    statement["closing_balance"] = _running(txns, opening)

    return {
        "applicant_id": f"A{index:04d}", "seed": seed,
        "identity": {"name": name, "ssn": ssn, "address": fk.address().replace("\n", ", ")},
        "documents": {
            "paystub": {"file": "paystub.pdf", "scanned": False, "fields": stub},
            "w2": {"file": "w2.pdf", "scanned": False, "fields": w2},
            "statement": {"file": "statement.pdf", "scanned": False, "fields": statement},
        },
        "anomalies": anomalies,
        "expected_flags": sorted({a["code"] for a in anomalies}),
    }
