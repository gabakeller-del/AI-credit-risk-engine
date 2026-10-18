"""Debt helpers (Phase 3): average interest rate and repayment schedule.

Check it with:
    .venv/bin/python src/debt.py
"""

# The names used for each year in the [debt_maturities] section of data/assumptions.toml.
MATURITY_KEYS = {
    2026: "remaining_2026",  # only July-December 2026
    2027: "y2027",
    2028: "y2028",
    2029: "y2029",
    2030: "y2030",
}


def total_principal(loans):
    """Total amount owed across all loans."""
    return sum(loan["principal"] for loan in loans)


def blended_rate(loans):
    """Average interest rate, weighted by loan size (bigger loans count more).

    Same as: total yearly interest / total principal.
    """
    yearly_interest = sum(loan["principal"] * loan["effective_rate"] for loan in loans)
    return yearly_interest / total_principal(loans)


def scheduled_repayment(maturities, year):
    """Principal that must be repaid in `year`, per the 10-Q schedule. Zero for years not listed."""
    key = MATURITY_KEYS.get(year)
    return maturities[key] if key else 0


if __name__ == "__main__":
    from cash_flow import load_assumptions

    a = load_assumptions()
    loans = a["debt_facilities"]
    print(f"Total debt today:        ${total_principal(loans):,.0f} million")
    print(f"Blended interest rate:   {blended_rate(loans):.2%}")
    for year in a["projection"]["years"]:
        print(f"Repayment due in {year}:  ${scheduled_repayment(a['debt_maturities'], year):,.0f} million")
