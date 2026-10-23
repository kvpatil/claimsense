"""Money. Integer cents, start to finish.

Every figure that reaches a claimant is computed here. There is no float in
this module and no model call: a deductible applied by a language model is a
language model deciding what someone is owed, which is exactly the thing the
engagement's architecture forbids.

The order of operations is the part worth being careful about, because it
changes the number:

    1. cap the loss at the coverage limit
    2. subtract the deductible
    3. apply coinsurance
    4. floor at zero

Applying coinsurance before the deductible, or the deductible before the cap,
both produce defensible-looking numbers that are wrong. The order below is the
standard one: the limit bounds the loss, the deductible is the insured's
retention, and coinsurance splits what remains.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Settlement:
    claimed_cents: int
    limit_cents: int
    deductible_cents: int
    coinsurance_pct: int
    capped_cents: int
    after_deductible_cents: int
    payable_cents: int
    limit_applied: bool
    fully_absorbed_by_deductible: bool

    def explain(self) -> str:
        parts = [f"claimed ${self.claimed_cents / 100:,.2f}"]
        if self.limit_applied:
            parts.append(f"capped at the ${self.limit_cents / 100:,.2f} limit")
        parts.append(f"less ${self.deductible_cents / 100:,.2f} deductible")
        if self.coinsurance_pct != 100:
            parts.append(f"at {self.coinsurance_pct}% coinsurance")
        parts.append(f"= ${self.payable_cents / 100:,.2f} payable")
        return ", ".join(parts)


def settle(claimed_cents: int, limit_cents: int, deductible_cents: int,
           coinsurance_pct: int = 100) -> Settlement:
    """What is payable on a covered loss. Pure arithmetic."""
    if claimed_cents < 0 or limit_cents < 0 or deductible_cents < 0:
        raise ValueError("money is non-negative; got "
                         f"claimed={claimed_cents} limit={limit_cents} "
                         f"deductible={deductible_cents}")
    if not 0 <= coinsurance_pct <= 100:
        raise ValueError(f"coinsurance must be 0-100, got {coinsurance_pct}")

    # A claim EQUAL to the limit is payable in full up to that limit — it is not
    # "over". ADV-03 exists to pin this boundary, because `>` and `>=` here are
    # a silent difference of one cent on every capped claim.
    capped = min(claimed_cents, limit_cents)
    limit_applied = claimed_cents > limit_cents

    after_deductible = max(0, capped - deductible_cents)
    # Integer division, floored. Rounding up would pay a cent that was never
    # owed, and on a book of claims that is a real number.
    payable = after_deductible * coinsurance_pct // 100

    return Settlement(
        claimed_cents=claimed_cents, limit_cents=limit_cents,
        deductible_cents=deductible_cents, coinsurance_pct=coinsurance_pct,
        capped_cents=capped, after_deductible_cents=after_deductible,
        payable_cents=payable, limit_applied=limit_applied,
        fully_absorbed_by_deductible=after_deductible == 0,
    )


def usd(cents: int | None) -> str:
    """Cents as a display string. The ONE place cents become a decimal."""
    if cents is None:
        return "—"
    return f"${cents / 100:,.2f}"


# Which coverage pays for which peril. Deterministic: the model is never asked
# which bucket a loss comes out of, because that choice selects the limit and
# the deductible and therefore the number the claimant receives.
_PERIL_COVERAGE = {
    "HO3": {"fire": "DWELL", "water": "DWELL", "wind": "DWELL",
            "earthquake": "DWELL", "vandalism": "DWELL", "theft": "PP",
            "liability": "LIAB"},
    "HO4": {"theft": "PP", "fire": "PP", "water": "PP", "wind": "PP",
            "vandalism": "PP", "liability": "LIAB"},
    "AUTO": {"collision": "COLL", "theft": "COMP", "fire": "COMP",
             "vandalism": "COMP", "wind": "COMP", "water": "COMP",
             "liability": "LIAB"},
}


def governing_coverage(product: str, peril: str, coverages: list[dict]) -> dict | None:
    """The coverage section a loss is settled under, or None if the form has none.

    None is a real answer, not a failure: a renters form has no dwelling
    coverage, so a structural loss on HO4 genuinely has nowhere to be paid from.
    """
    code = _PERIL_COVERAGE.get(product, {}).get(peril)
    if not code:
        return None
    for cov in coverages:
        if cov["coverage_code"] == code:
            return cov
    return None
