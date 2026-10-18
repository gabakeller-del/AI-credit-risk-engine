"""CoreWeave's cash flow: one base-case year (Phase 2), five years (Phase 3), default checks (Phase 4).

Run it from the project folder with:
    .venv/bin/python src/cash_flow.py

All money is in $ millions, matching data/assumptions.toml.
"""

import tomllib
from pathlib import Path

import pandas as pd

from debt import blended_rate, scheduled_repayment, total_principal
from default import borrowing_capacity, check_default

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
    """Roll the company forward year by year.

    Returns (table, default_year, default_reason). default_year is None if CoreWeave never defaults.
    """
    p = a["projection"]
    rules = a["default_rules"]
    loans = a["debt_facilities"]
    years = p["years"]

    # Operations first: revenue and EBITDA for every year (they don't depend on the debt),
    # so each year can look ahead to next year's EBITDA for the borrowing limit.
    revenues = []
    for i in range(len(years)):
        if i == 0:
            revenues.append(midpoint(a["revenue"]["fy2026_guidance_low"], a["revenue"]["fy2026_guidance_high"]))
        else:
            revenues.append(revenues[-1] * (1 + p["revenue_growth"][i]))
    ebitdas = [revenues[i] * p["ebitda_margin"][i] for i in range(len(years))]

    # What already happened in January-June 2026 (actuals), to take away from the 2026 full-year
    # figures, because our first period only covers July-December 2026.
    h1_revenue = a["revenue"]["q1_2026_actual"] + a["revenue"]["q2_2026_actual"]
    h1_capex = a["capex"]["cash_capex_q1_2026"] + a["capex"]["cash_capex_q2_2026"]

    # Opening balances: where CoreWeave stands on 30 June 2026.
    cash = a["debt_summary"]["cash_2026_06_30"]
    existing_debt = total_principal(loans)  # today's 16 loans, repaid on the 10-Q schedule
    new_debt = 0                            # extra borrowing our model adds to fill funding gaps
    existing_rate = blended_rate(loans)

    rows = []
    default_year, default_reason = None, None
    for i, year in enumerate(years):
        # 1. Operations. The first period is July-December 2026 = full year minus January-June.
        length = p["period_length"][i]  # 0.5 = half a year
        if i == 0:
            label = f"Jul-Dec {year}"
            revenue = revenues[0] - h1_revenue
            ebitda = revenue * p["ebitda_margin"][0]
            capex = p["capex"][0] - h1_capex
        else:
            label = str(year)
            revenue, ebitda, capex = revenues[i], ebitdas[i], p["capex"][i]
        # Interest is charged only for the length of the period (half a year = half the interest).
        interest = (existing_debt * existing_rate + new_debt * p["new_debt_rate"]) * length
        free_cash_flow = ebitda - interest - p["cash_taxes"][i] - capex

        # 2. Repay the principal due this year (can't repay more than is left).
        repayment = min(scheduled_repayment(a["debt_maturities"], year), existing_debt)
        existing_debt -= repayment

        # 3. If cash would fall below the safety minimum, try to borrow the difference,
        #    but lenders only lend up to max leverage x NEXT year's EBITDA.
        cash = cash + free_cash_flow - repayment
        needed = max(0, p["minimum_cash"] - cash)
        forward_ebitda = ebitdas[i + 1] if i + 1 < len(years) else ebitda
        lendable = borrowing_capacity(existing_debt + new_debt, forward_ebitda, rules["max_forward_leverage"])
        new_borrowing = min(needed, lendable)
        cash += new_borrowing
        new_debt += new_borrowing

        # 4. Default check at year-end. We remember the FIRST year anything goes wrong.
        interest_cover = ebitda / interest
        reason = check_default(cash, interest_cover, rules)
        if reason and default_year is None:
            default_year, default_reason = label, reason

        # 5. Record the year. Closing balances carry into next year automatically.
        total_debt = existing_debt + new_debt
        yearly_ebitda = ebitda / length  # "annualised": a half-year's EBITDA x 2, so leverage compares fairly
        rows.append({
            "Year": label,
            "Revenue": revenue,
            "EBITDA": ebitda,
            "Interest": interest,
            "Capex": capex,
            "Free cash flow": free_cash_flow,
            "Debt repaid": repayment,
            "New borrowing": new_borrowing,
            "Closing cash": cash,
            "Closing debt": total_debt,
            "Leverage (x)": total_debt / yearly_ebitda,
            "Forward leverage (x)": total_debt / forward_ebitda,
            "Interest cover (x)": interest_cover,
        })

    # A pandas table: rows = years. We flip it so years run across like a spreadsheet.
    table = pd.DataFrame(rows).set_index("Year").T
    return table, default_year, default_reason


def print_projection(table):
    """Print the 5-year table: money rounded to $ millions, ratios (the "(x)" rows) like 2.5x."""
    pretty = table.copy().astype(object)
    for row in table.index:
        if row.endswith("(x)"):
            pretty.loc[row] = [f"{x:.1f}x" for x in table.loc[row]]
        else:
            pretty.loc[row] = [f"{x:,.0f}" for x in table.loc[row]]
    print("\nCoreWeave projection from 30 June 2026 ($ millions)")
    print(pretty.to_string())


if __name__ == "__main__":
    # This part only runs when you run the file directly (not when another file borrows its functions).
    assumptions = load_assumptions()
    results = base_case_year(assumptions)
    print_waterfall(assumptions["base_case"]["year"], results)
    table, default_year, default_reason = project_years(assumptions)
    print_projection(table)
    if default_year:
        print(f"\nDEFAULT in {default_year}: {default_reason}")
    else:
        print("\nNo default in any year under these assumptions.")
