"""Default rules (Phase 4): how much lenders will lend, and when CoreWeave counts as defaulted.

Check it with:
    .venv/bin/python src/default.py
"""


def borrowing_capacity(current_debt, forward_ebitda, max_forward_leverage):
    """How much MORE lenders will lend: the debt ceiling (max leverage x next year's EBITDA)
    minus what's already owed. Never below zero."""
    debt_ceiling = max_forward_leverage * forward_ebitda
    return max(0, debt_ceiling - current_debt)


def check_default(cash, interest_cover, rules):
    """Return the reason CoreWeave is in default this year, or None if it isn't."""
    # Liquidity default: even after borrowing all it can, cash is below zero = bills go unpaid.
    if cash < 0:
        return "Liquidity default (ran out of cash)"
    # Covenant default: cash profit doesn't cover interest by the required margin.
    if interest_cover < rules["min_interest_cover"]:
        return "Covenant default (interest cover too low)"
    return None


if __name__ == "__main__":
    # Quick checks with made-up numbers, so you can see each rule work.
    rules = {"max_forward_leverage": 6.0, "min_interest_cover": 1.5}

    print("Borrowing capacity examples ($ millions):")
    print("  Debt 50,000, next-year EBITDA 10,000 ->", borrowing_capacity(50_000, 10_000, 6.0), "(ceiling 60,000)")
    print("  Debt 70,000, next-year EBITDA 10,000 ->", borrowing_capacity(70_000, 10_000, 6.0), "(already over the ceiling)")

    print("\nDefault check examples:")
    print("  Cash  2,000, cover 2.5x ->", check_default(2_000, 2.5, rules))
    print("  Cash -1,000, cover 2.5x ->", check_default(-1_000, 2.5, rules))
    print("  Cash  2,000, cover 1.2x ->", check_default(2_000, 1.2, rules))
