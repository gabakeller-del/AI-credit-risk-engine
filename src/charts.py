"""Charts of the Monte Carlo and stress test results. Saves PNG images into docs/figures/,
where the README and report on GitHub can show them.

Run it from the project folder with:
    .venv/bin/python src/charts.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw straight to image files (no pop-up windows)
import matplotlib.pyplot as plt
import numpy as np

from cash_flow import load_assumptions, project_years
from scenarios import compare_scenarios
from simulation import run_simulation

OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "figures"

# Colours: one blue family for the data, grey for text and axes, red ONLY for "default".
BLUE_LIGHT = "#b7d3f6"
BLUE_MID = "#6da7ec"
BLUE_DARK = "#1c5cab"
RED = "#d03b3b"
TEXT = "#0b0b0b"
TEXT_SOFT = "#52514e"
GRID = "#e4e3df"
BACKGROUND = "#fcfcfb"


def style_axes(ax, title, subtitle):
    """Shared look: quiet axes, light grid, title + one-line explanation."""
    ax.set_facecolor(BACKGROUND)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=TEXT_SOFT, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=TEXT, pad=26)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9.5, color=TEXT_SOFT)


def debt_fan_chart(results, labels, path):
    """Chart 1: how CoreWeave's total debt could evolve, across all simulated futures."""
    debt = np.array(results["debt_path"].tolist()) / 1000  # rows = futures, columns = periods; $ billions
    p5, p25, p50, p75, p95 = np.percentile(debt, [5, 25, 50, 75, 95], axis=0)
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(9, 5.2), facecolor=BACKGROUND)
    ax.fill_between(x, p5, p95, color=BLUE_LIGHT, linewidth=0)
    ax.fill_between(x, p25, p75, color=BLUE_MID, linewidth=0)
    ax.plot(x, p50, color=BLUE_DARK, linewidth=2)

    # Direct labels at the right-hand end instead of a legend box.
    last = len(labels) - 1
    ax.annotate("Median future", (last, p50[-1]), xytext=(8, 0), textcoords="offset points",
                va="center", fontsize=9, color=TEXT)
    ax.annotate("Middle 50% of futures", (last, p75[-1]), xytext=(8, 0), textcoords="offset points",
                va="center", fontsize=9, color=TEXT_SOFT)
    ax.annotate("90% of futures", (last, p95[-1]), xytext=(8, 0), textcoords="offset points",
                va="center", fontsize=9, color=TEXT_SOFT)

    # Label the peak of the median path with its value.
    peak = int(np.argmax(p50))
    ax.annotate(f"${p50[peak]:.0f}B", (peak, p50[peak]), xytext=(0, 10), textcoords="offset points",
                ha="center", fontsize=9, color=TEXT)

    ax.set_xticks(x, labels)
    ax.set_xlim(-0.2, last + 1.3)  # room on the right for the labels
    ax.set_ylim(0, p95.max() * 1.15)
    ax.set_ylabel("Total debt at period end ($ billions)", color=TEXT_SOFT, fontsize=9)
    style_axes(ax, "CoreWeave's debt peaks in 2028 in most futures",
               f"Range of total debt across {len(results):,} simulated futures, starting from $35.6B on 30 June 2026")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=BACKGROUND)
    plt.close(fig)


def leverage_histogram(results, limit, path):
    """Chart 2: how close each future came to the lenders' borrowing limit."""
    worst = results["worst_forward_leverage"]
    bins = np.arange(np.floor(worst.min() * 4) / 4, max(worst.max(), limit) + 0.25, 0.1)

    fig, ax = plt.subplots(figsize=(9, 5.2), facecolor=BACKGROUND)
    counts, _, _ = ax.hist(worst, bins=bins, color=BLUE_MID, edgecolor=BACKGROUND, linewidth=1)
    ax.set_ylim(0, counts.max() * 1.18)  # headroom for the labels

    # The lenders' limit: red + a text label, so it never relies on colour alone.
    ax.axvline(limit, color=RED, linewidth=2)
    ax.annotate(f"Lenders' limit: {limit:.1f}x\nabove this, no new loans", (limit, 1), xycoords=("data", "axes fraction"),
                xytext=(-8, -4), textcoords="offset points", ha="right", va="top", fontsize=9, color=TEXT)

    # How many futures got within 1x of the limit.
    near = (worst >= limit - 1).mean()
    median = worst.median()
    ax.axvline(median, color=BLUE_DARK, linewidth=1.5, linestyle="--")
    ax.annotate(f"Median future: {median:.1f}x", (median, 1), xycoords=("data", "axes fraction"),
                xytext=(6, -4), textcoords="offset points", ha="left", va="top", fontsize=9, color=TEXT)

    ax.set_xlabel("Worst forward leverage in the future (debt / next year's EBITDA)", color=TEXT_SOFT, fontsize=9)
    ax.set_ylabel("Number of futures", color=TEXT_SOFT, fontsize=9)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.0fx"))
    style_axes(ax, "Most futures stay well below the lending limit",
               f"{near:.1%} of {len(results):,} futures came within 1x of the {limit:.0f}x limit at their worst point")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=BACKGROUND)
    plt.close(fig)


def default_drivers_chart(results, base, path):
    """Chart 3: which random inputs lead to default? One dot per future."""
    survived = results[~results["defaulted"]]
    defaulted = results[results["defaulted"]]

    fig, ax = plt.subplots(figsize=(9, 5.6), facecolor=BACKGROUND)
    ax.scatter(survived["growth_2027"] * 100, survived["ebitda_margin"] * 100,
               s=6, color=BLUE_MID, alpha=0.35, linewidths=0, label=f"Survived ({len(survived):,})")
    # Defaults on top: bigger, red, with a white ring so they stand out from the cloud.
    ax.scatter(defaulted["growth_2027"] * 100, defaulted["ebitda_margin"] * 100,
               s=60, color=RED, edgecolors=BACKGROUND, linewidths=1.5, label=f"Defaulted ({len(defaulted):,})", zorder=3)

    # Mark the base case as a reference point.
    bx, by = base["revenue_growth"][1] * 100, base["ebitda_margin"][0] * 100
    ax.scatter([bx], [by], s=70, marker="+", color=TEXT, linewidths=1.5, zorder=4)
    ax.annotate("Base case", (bx, by), xytext=(8, 6), textcoords="offset points", fontsize=9, color=TEXT)

    ax.set_xlabel("2027 revenue growth (%)", color=TEXT_SOFT, fontsize=9)
    ax.set_ylabel("EBITDA margin (%)", color=TEXT_SOFT, fontsize=9)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    legend = ax.legend(loc="upper right", frameon=False, fontsize=9, markerscale=1.5)
    for text in legend.get_texts():
        text.set_color(TEXT)
    style_axes(ax, "Defaults cluster where weak growth meets thin margins",
               "Each dot is one simulated future, placed by two of its random inputs")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=BACKGROUND)
    plt.close(fig)


def scenario_chart(rows, path):
    """Chart 4: probability of default under each stress scenario (one bar each)."""
    names = [r["Scenario"] for r in rows][::-1]  # reversed so the base case sits at the top
    pds = [r["Probability of default"] * 100 for r in rows][::-1]
    y = np.arange(len(names))

    fig, ax = plt.subplots(figsize=(9, 4.6), facecolor=BACKGROUND)
    # Rough market-implied range, as a reference band (see report for how it's estimated).
    ax.axvspan(30, 35, color=GRID, zorder=0)
    ax.annotate("← grey band: rough range implied\n    by CoreWeave's bond prices (30-35%)", (36, len(names) - 1),
                ha="left", va="center", fontsize=8.5, color=TEXT_SOFT)

    ax.barh(y, pds, height=0.55, color=BLUE_MID, zorder=2)
    for yi, value in zip(y, pds):
        ax.annotate(f"{value:.1f}%", (value, yi), xytext=(5, 0), textcoords="offset points",
                    va="center", fontsize=9.5, color=TEXT, fontweight="bold")

    ax.set_yticks(y, names)
    ax.tick_params(axis="y", length=0, labelsize=10, labelcolor=TEXT)
    ax.set_xlim(0, 108)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.0f%%"))
    ax.set_xlabel("Probability of default, July 2026 to December 2030", color=TEXT_SOFT, fontsize=9)
    style_axes(ax, "Losing the largest customer is the dominant credit risk",
               "Share of 10,000 simulated futures that default, under each stress scenario")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=BACKGROUND)
    plt.close(fig)


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    a = load_assumptions()
    labels = list(project_years(a)[0].columns)  # period names, e.g. "Jul-Dec 2026", "2027", ...
    results = run_simulation(a)

    debt_fan_chart(results, labels, OUTPUT_DIR / "1_debt_fan.png")
    leverage_histogram(results, a["default_rules"]["max_forward_leverage"], OUTPUT_DIR / "2_leverage_histogram.png")
    default_drivers_chart(results, a["projection"], OUTPUT_DIR / "3_default_drivers.png")
    scenario_chart(compare_scenarios(a), OUTPUT_DIR / "4_scenarios.png")
    print(f"Saved charts to {OUTPUT_DIR}")
