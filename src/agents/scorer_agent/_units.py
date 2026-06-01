# agents/scorer_agent/_units.py
"""
Unit normalization helpers for the scorer agent.

Margins and FCF margin are stored as fractions by the data normalizer
(e.g. yfinance `profitMargins` = 0.25), but the scoring thresholds are
expressed as percentages (e.g. "net_margin >= 25"). This helper bridges the
two so the scorers work whether they receive a fraction (0.25) or an already
percentage-scaled value (25).
"""

from typing import Optional


def to_percent(value: Optional[float]) -> Optional[float]:
    """
    Normalize a margin/ratio to a percentage.

    Values with |v| <= 1.5 are treated as fractions and scaled by 100
    (0.25 -> 25); larger values are assumed to already be percentages and
    are returned unchanged. 1.5 is a safe cutoff — real margins never reach
    150%, so anything above it is already in percentage form.
    """
    if value is None:
        return None
    return value * 100 if abs(value) <= 1.5 else value
