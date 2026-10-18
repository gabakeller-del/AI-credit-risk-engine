"""Stress scenarios (Phase 7): change the base assumptions, then rerun the Monte Carlo.

Run it from the project folder with:
    .venv/bin/python src/scenarios.py
"""

import copy

from cash_flow import load_assumptions, project_years
from simulation import run_simulation


def apply_customer_loss(a):
    """From the start year, the largest customer's revenue disappears; most of its EBITDA goes too."""
    s = a["scenarios"]["customer_loss"]
    stressed = copy.deepcopy(a)
    p = stressed["projection"]
    lost = s["lost_revenue_share"]
    first = p["years"].index(s["start_year"])  # position of 2027 in the list of years

    # Revenue: the start year's growth shrinks, so revenue is 30% lower from then on.
    # Later years keep growing at their normal rate, but from the lower level.
    p["revenue_growth"][first] = (1 + p["revenue_growth"][first]) * (1 - lost) - 1

    # Margin: we lose 80 cents of EBITDA per lost dollar, but only 70% of revenue remains.
    # New margin = (old EBITDA - lost EBITDA) / remaining revenue.
    for i in range(first, len(p["years"])):
        m = p["ebitda_margin"][i]
        p["ebitda_margin"][i] = (m - s["ebitda_lost_per_dollar"] * lost) / (1 - lost)
    return stressed


def extra_replacement_capex(s, years):
    """Extra capex per year when GPUs wear out after 4 years instead of 6.

    Each batch bought in year Y is replaced in Y + useful life. The base case already pays for
    replacements at 6 years, so we add the 4-year replacements and take away the 6-year ones.
    """
    extra = []
    for year in years:
        due_short_life = sum(cost for bought, cost in s["gpu_purchases"].items()
                             if int(bought) + s["useful_life_years"] == year)
        due_base_life = sum(cost for bought, cost in s["gpu_purchases"].items()
                            if int(bought) + s["base_useful_life_years"] == year)
        extra.append((due_short_life - due_base_life) * s["replacement_cost_share"])
    return extra


def apply_gpu_depreciation(a):
    """GPUs wear out faster: replace them sooner (more capex) and lenders lend less against them."""
    s = a["scenarios"]["gpu_depreciation"]
    stressed = copy.deepcopy(a)
    p = stressed["projection"]
    extra = extra_replacement_capex(s, p["years"])
    p["capex"] = [base + more for base, more in zip(p["capex"], extra)]
    stressed["default_rules"]["max_forward_leverage"] = s["max_forward_leverage"]
    return stressed


def apply_rate_spike(a):
    """Credit markets tighten: new debt costs more, floating-rate loans reprice, lenders lend less."""
    s = a["scenarios"]["rate_spike"]
    stressed = copy.deepcopy(a)
    stressed["projection"]["new_debt_rate"] += s["new_debt_rate_increase"]
    # Only the floating part of each loan reprices (floating_share 1 = fully floating, 0 = fixed).
    for loan in stressed["debt_facilities"]:
        loan["effective_rate"] += s["floating_rate_increase"] * loan["floating_share"]
    stressed["default_rules"]["max_forward_leverage"] = s["max_forward_leverage"]
    return stressed


def apply_all_three(a):
    """The "perfect storm": all three shocks at once. The strictest lending limit wins."""
    stressed = apply_rate_spike(apply_gpu_depreciation(apply_customer_loss(a)))
    s = a["scenarios"]
    stressed["default_rules"]["max_forward_leverage"] = min(
        s["gpu_depreciation"]["max_forward_leverage"], s["rate_spike"]["max_forward_leverage"])
    return stressed


SCENARIOS = {
    "Base case": lambda a: a,
    "Customer loss": apply_customer_loss,
    "GPU depreciation": apply_gpu_depreciation,
    "Rate spike": apply_rate_spike,
    "All three together": apply_all_three,
}


def compare_scenarios(a):
    """Run the Monte Carlo for every scenario. Returns one summary row per scenario."""
    rows = []
    for name, apply in SCENARIOS.items():
        stressed = apply(a)
        _, default_year, _ = project_years(stressed)  # the single most-likely path
        results = run_simulation(stressed)
        defaults = results[results["defaulted"]]
        rows.append({
            "Scenario": name,
            "Probability of default": results["defaulted"].mean(),
            "Most-likely path": f"Default {default_year}" if default_year else "Survives",
            "Median worst fwd leverage": results["worst_forward_leverage"].median(),
            "Most common default year": defaults["default_year"].mode()[0] if len(defaults) else "-",
        })
    return rows


if __name__ == "__main__":
    a = load_assumptions()
    print(f"\nStress test: {a['monte_carlo']['n_simulations']:,} random futures per scenario\n")
    print(f"{'Scenario':<22}{'PD':>8}   {'Most-likely path':<22}{'Median worst':>14}   {'Most common':<14}")
    print(f"{'':<22}{'':>8}   {'':<22}{'fwd leverage':>14}   {'default year':<14}")
    print("-" * 86)
    for r in compare_scenarios(a):
        print(f"{r['Scenario']:<22}{r['Probability of default']:>8.1%}   {r['Most-likely path']:<22}"
              f"{r['Median worst fwd leverage']:>13.1f}x   {r['Most common default year']:<14}")
