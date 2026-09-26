"""Invoice totals in integer cents."""


def total_cents(unit_price, quantity, discount=0.0):
    # BUG: floating-point rounding drops a cent on .5 boundaries.
    return int(unit_price * quantity * (1 - discount))
