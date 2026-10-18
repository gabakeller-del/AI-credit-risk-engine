"""One year of CoreWeave's cash flow (Phase 2).

Run it from the project folder with:
    .venv/bin/python src/cash_flow.py

All money is in $ millions, matching data/assumptions.toml.
"""

import tomllib
from pathlib import Path

import pandas as pd

from debt import blended_rate, scheduled_repayment, total_principal

# Where the assumptions file lives, worked out relative to this file so it works from anywhere.
ASSUMPTIONS_FILE = Path(__file__).parent.parent / "data" / "assumptions.toml"


def load_assumptions():
    """Read data/assumptions.toml and return it as a dictionary (a labelled set of values)."""
    with open(ASSUMPTIONS_FILE, "rb") as f:
        return tomllib.load(f)


def annual_interest(loans):
    """Yearly interest bill: each loan's principal x its effective interest rate, added up."""
    total = 0
    for loan in loans:
        total += loan["principal"] * loan["effective_rate"]
    return total


def midpoint(low, high):
    """Halfway between two numbers, e.g. the middle of a guidance range."""
    return (low + high) / 2


def base_case_year(a):
    """Walk from revenue down to free cash flow for one year. `a` is the assumptions dictionary."""
    base = a["base_case"]

    # Top line: what customers pay CoreWeave.
    revenue = midpoint(a["revenue"]["fy2026_guidance_low"], a["revenue"]["fy2026_guidance_high"])

    # EBITDA: cash profit from running the data centers, before interest, tax and new equipment.
    ebitda = revenue * base["ebitda_margin"]

    # Interest: what lenders must be paid this year.
    interest = annual_interest(a["debt_facilities"])

    # Cash from operations (simplified): what's left after paying lenders and the tax authorities.
    taxes = base["cash_taxes"]
    operating_cash_flow = ebitda - interest - taxes

    # Capex: cash spent buying new GPUs and data-center equipment.
    capex = midpoint(a["capex"]["fy2026_capex_guidance_low"], a["capex"]["fy2026_capex_guidance_high"])

    # Free cash flow: the cash the business produces (or burns) after everything above.
    free_cash_flow = operating_cash_flow - capex

    # Liquidity = cash on hand + what can still be borrowed on the credit line, right now.
    liquidity = a["debt_summary"]["cash_2026_06_30"] + a["debt_summary"]["revolver_undrawn_2026_06_30"]

    return {
        "revenue": revenue,
        "ebitda": ebitda,
        "interest": interest,
        "taxes": taxes,
        "operating_cash_flow": operating_cash_flow,
        "capex": capex,
        "free_cash_flow": free_cash_flow,
        "liquidity": liquidity,
    }


def print_waterfall(year, r):
    """Show the results like a column in a spreadsheet. Negative numbers appear in brackets."""

    def money(x):
        return f"({abs(x):>8,.0f})" if x < 0 else f" {x:>8,.0f} "

    print(f"\nCoreWeave base case, {year} ($ millions)")
    print("-" * 44)
    print(f"Revenue                         {money(r['revenue'])}")
    print(f"EBITDA                          {money(r['ebitda'])}")
    print(f"  less: interest                {money(-r['interest'])}")
    print(f"  less: cash taxes              {money(-r['taxes'])}")
    print(f"Cash from operations            {money(r['operating_cash_flow'])}")
    print(f"  less: capex                   {money(-r['capex'])}")
    print("-" * 44)
    print(f"Free cash flow                  {money(r['free_cash_flow'])}")
    print()
    print(f"Interest cover (EBITDA / interest):   {r['ebitda'] / r['interest']:.1f}x")
    print(f"Liquidity (cash + undrawn revolver):  {r['liquidity']:,.0f}")
    if r["free_cash_flow"] < 0:
        gap = -r["free_cash_flow"]
        print(f"Funding gap (cash burned this year):  {gap:,.0f}")
        print(f"Gap covered by liquidity alone?       {'Yes' if r['liquidity'] >= gap else 'No - needs new borrowing'}")


def project_years(a):
    """Phase 3: roll the company forward year by year. Returns a table (one row per year)."""
    p = a["projection"]
    loans = a["debt_facilities"]

    # Opening balances: where CoreWeave stands on 30 June 2026.
    cash = a["debt_summary"]["cash_2026_06_30"]
    existing_debt = total_principal(loans)  # today's 16 loans, repaid on the 10-Q schedule
    new_debt = 0                            # extra borrowing our model adds to fill funding gaps
    existing_rate = blended_rate(loans)

    rows = []
    revenue = None
    for i, year in enumerate(p["years"]):
        # 1. Operations
        if i == 0:
            revenue = midpoint(a["revenue"]["fy2026_guidance_low"], a["revenue"]["fy2026_guidance_high"])
        else:
            revenue = revenue * (1 + p["revenue_growth"][i])
        ebitda = revenue * p["ebitda_margin"][i]
        interest = existing_debt * existing_rate + new_debt * p["new_debt_rate"]
        free_cash_flow = ebitda - interest - p["cash_taxes"][i] - p["capex"][i]

        # 2. Repay the principal due this year (can't repay more than is left).
        repayment = min(scheduled_repayment(a["debt_maturities"], year), existing_debt)
        existing_debt -= repayment

        # 3. If cash would fall below the safety minimum, borrow the difference.
        cash = cash + free_cash_flow - repayment
        new_borrowing = max(0, p["minimum_cash"] - cash)
        cash += new_borrowing
        new_debt += new_borrowing

        # 4. Record the year. Closing balances carry into next year automatically.
        total_debt = existing_debt + new_debt
        rows.append({
            "Year": year,
            "Revenue": revenue,
            "EBITDA": ebitda,
            "Interest": interest,
            "Capex": p["capex"][i],
            "Free cash flow": free_cash_flow,
            "Debt repaid": repayment,
            "New borrowing": new_borrowing,
            "Closing cash": cash,
            "Closing debt": total_debt,
            "Leverage (x)": total_debt / ebitda,
            "Interest cover (x)": ebitda / interest,
        })

    # A pandas table: rows = years. We flip it so years run across like a spreadsheet.
    return pd.DataFrame(rows).set_index("Year").T


def print_projection(table):
    """Print the 5-year table: money rounded to $ millions, ratios (the "(x)" rows) like 2.5x."""
    pretty = table.copy().astype(object)
    for row in table.index:
        if row.endswith("(x)"):
            pretty.loc[row] = [f"{x:.1f}x" for x in table.loc[row]]
        else:
            pretty.loc[row] = [f"{x:,.0f}" for x in table.loc[row]]
    print("\nCoreWeave 5-year projection ($ millions)")
    print(pretty.to_string())


if __name__ == "__main__":
    # This part only runs when you run the file directly (not when another file borrows its functions).
    assumptions = load_assumptions()
    results = base_case_year(assumptions)
    print_waterfall(assumptions["base_case"]["year"], results)
    print_projection(project_years(assumptions))
