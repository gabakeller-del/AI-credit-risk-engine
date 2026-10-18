"""Monte Carlo simulation (Phase 5): run the projection thousands of times with random surprises.

Run it from the project folder with:
    .venv/bin/python src/simulation.py
"""

import copy
import time

import numpy as np
import pandas as pd

from cash_flow import load_assumptions, project_years


def draw_scenario(a, rng):
    """Make one random future: a COPY of the assumptions with surprises applied.

    `rng` is the random number generator. The original assumptions are never changed.
    """
    mc = a["monte_carlo"]
    scenario = copy.deepcopy(a)
    p = scenario["projection"]

    # Revenue growth: each year gets its own surprise (rng.normal = a random draw from a bell curve).
    for i, stdev in enumerate(mc["revenue_growth_stdev"]):
        surprise = rng.normal(0, stdev)
        p["revenue_growth"][i] = max(mc["min_revenue_growth"], p["revenue_growth"][i] + surprise)

    # EBITDA margin: one surprise for the whole future, applied to every year.
    margin_surprise = rng.normal(0, mc["ebitda_margin_stdev"])
    p["ebitda_margin"] = [m + margin_surprise for m in p["ebitda_margin"]]

    # Interest rate on new debt: one surprise for the whole future.
    rate_surprise = rng.normal(0, mc["new_debt_rate_stdev"])
    p["new_debt_rate"] = max(mc["min_new_debt_rate"], p["new_debt_rate"] + rate_surprise)

    return scenario


def run_simulation(a, n_simulations=None, seed=None):
    """Run many random futures. Returns a table with one row per future."""
    mc = a["monte_carlo"]
    n_simulations = n_simulations or mc["n_simulations"]
    rng = np.random.default_rng(mc["seed"] if seed is None else seed)

    results = []
    for _ in range(n_simulations):
        scenario = draw_scenario(a, rng)
        table, default_year, default_reason = project_years(scenario)
        p = scenario["projection"]
        results.append({
            "defaulted": default_year is not None,
            "default_year": default_year,
            "default_reason": default_reason,
            # Keep the random inputs and a couple of outcomes, so we can see WHY futures default.
            "growth_2027": p["revenue_growth"][1],
            "ebitda_margin": p["ebitda_margin"][0],
            "new_debt_rate": p["new_debt_rate"],
            "peak_debt": table.loc["Closing debt"].max(),
            "worst_forward_leverage": table.loc["Forward leverage (x)"].max(),
            "worst_interest_cover": table.loc["Interest cover (x)"].min(),
        })
    return pd.DataFrame(results)


def print_summary(results):
    """Probability of default, plus when and why the defaults happened."""
    n = len(results)
    defaults = results[results["defaulted"]]
    pd_estimate = len(defaults) / n

    print(f"\nMonte Carlo: {n:,} random futures")
    print("-" * 50)
    print(f"Futures that defaulted:  {len(defaults):,}")
    print(f"PROBABILITY OF DEFAULT:  {pd_estimate:.1%}  (over Jul 2026 - Dec 2030)")

    if len(defaults) > 0:
        print("\nWhen did they default?")
        counts = defaults["default_year"].value_counts()
        # Sort periods by their year number so "Jul-Dec 2026" comes before "2027".
        for year in sorted(counts.index, key=lambda label: label[-4:]):
            print(f"  {year:<14}{counts[year]:>6,} futures  ({counts[year] / n:.2%} of all)")
        print("\nWhy did they default?")
        for reason, count in defaults["default_reason"].value_counts().items():
            print(f"  {reason:<44}{count / len(defaults):>6.0%} of defaults")

        print("\nTypical random inputs: defaulted futures vs survivors (median)")
        survivors = results[~results["defaulted"]]
        for col, fmt in [("growth_2027", "{:.0%}"), ("ebitda_margin", "{:.1%}"), ("new_debt_rate", "{:.2%}")]:
            print(f"  {col:<16} defaulted {fmt.format(defaults[col].median()):>7}   survived {fmt.format(survivors[col].median()):>7}")


if __name__ == "__main__":
    a = load_assumptions()
    start = time.time()
    results = run_simulation(a)
    print_summary(results)
    print(f"\n(took {time.time() - start:.0f} seconds)")
