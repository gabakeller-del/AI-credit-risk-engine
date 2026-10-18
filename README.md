# AI Infrastructure Credit Risk Engine

A Monte Carlo credit model of **CoreWeave**, the AI cloud provider. It projects cash flows and debt from
the company's SEC filings, stress-tests them under three scenarios (major customer loss, faster GPU
depreciation, refinancing rate spike), and estimates the **probability of default (PD)** from July 2026
to December 2030.

**[Read the full report →](docs/report.md)**

![Probability of default by scenario](docs/figures/4_scenarios.png)

## Key findings

| Scenario | Probability of default |
|---|---|
| Base case | 0.1% |
| GPU depreciation (4-year life, not 6) | 4.2% |
| Refinancing rate spike (+5 pts on new debt) | 4.5% |
| **Largest customer leaves (30% of revenue)** | **52.1%** |
| All three together | 97.9% |

- **Ordinary uncertainty rarely breaks CoreWeave.** Its contracted revenue grows fast enough to carry
  a debt load that peaks around $70B in 2028.
- **Customer concentration is the dominant risk.** Lenders size loans on next year's EBITDA, so losing
  the largest customer cuts borrowing capacity *immediately*, while ~$23B of already-ordered GPUs
  still need paying for.
- **The market is more worried than the base case.** Bond yields of ~9.5-9.75% imply a rough 30-35%
  default probability over the period, between the base case and the severe scenarios.

## How it works

```
data/assumptions.toml    Every input, with its source (10-K, 10-Q, press releases)
        |
src/cash_flow.py         Revenue -> EBITDA -> interest -> capex -> free cash flow, Jul 2026-2030
src/debt.py              16 loans, blended rate, contractual repayment schedule
src/default.py           Default rules: lenders cap debt at 6x next year's EBITDA (liquidity
        |                default if cash runs out); interest cover below 1.5x (covenant default)
        |
src/simulation.py        10,000 random futures (revenue growth, margin, new-debt rate) -> PD
src/scenarios.py         Stress scenarios applied on top of the Monte Carlo
src/charts.py            Charts in docs/figures/
```

## Run it

Requires Python 3.11+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python src/cash_flow.py    # base case: 2026 waterfall + projection to 2030
.venv/bin/python src/simulation.py   # Monte Carlo probability of default (~3 seconds)
.venv/bin/python src/scenarios.py    # stress test comparison (~15 seconds)
.venv/bin/python src/charts.py       # redraw all charts
```

To try your own assumptions, edit [`data/assumptions.toml`](data/assumptions.toml) and rerun.

## Data sources

All company figures come from CoreWeave's public filings: the FY2025 10-K, the Q2 2026 10-Q, and the
Q4 2025, Q1 2026 and Q2 2026 results press releases. Each number in `assumptions.toml` is tagged with
its source. Forecast assumptions (growth, margins, shock sizes) are labelled **OUR ASSUMPTION** with
the reasoning beside them.

## Limitations

This is a learning project, not a professional credit rating. Main simplifications:
CoreWeave can't cut capex or issue shares in a crisis; random surprises are independent of each other;
covenant levels are estimated (the real ones aren't public); and the market-implied PD is a rough rule
of thumb. See the [report](docs/report.md#8-limitations) for details.

*Not investment advice.*
