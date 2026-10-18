"""One year of CoreWeave's cash flow (Phase 2).

Run it from the project folder with:
    .venv/bin/python src/cash_flow.py

All money is in $ millions, matching data/assumptions.toml.
"""

import tomllib
from pathlib import Path

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


if __name__ == "__main__":
    # This part only runs when you run the file directly (not when another file borrows its functions).
    assumptions = load_assumptions()
    results = base_case_year(assumptions)
    print_waterfall(assumptions["base_case"]["year"], results)
