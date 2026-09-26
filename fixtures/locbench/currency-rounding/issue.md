total_cents produces off-by-one-cent amounts because of binary floating point
rounding. The invoice totals must round half-up consistently.
