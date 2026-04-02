"""
The Circle — Rank System
100 tiers across 10 groups with exponential score thresholds, gradient colors, and taglines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from config import RANK_GROUPS, ROMAN_NUMERALS


@dataclass
class Rank:
    tier: int               # 1-100
    name: str               # e.g. "Veteran III"
    group_name: str         # e.g. "Veteran"
    sub_rank: int           # 1-10 within group
    color: int              # Discord color int
    threshold: int          # Score needed to reach this rank
    tagline: str            # Group tagline


def _interpolate_color(start_hex: int, end_hex: int, step: int, total: int) -> int:
    """Interpolate between two RGB colors. step is 0-indexed, total is count."""
    if total <= 1:
        return start_hex
    sr = (start_hex >> 16) & 0xFF
    sg = (start_hex >> 8) & 0xFF
    sb = start_hex & 0xFF
    er = (end_hex >> 16) & 0xFF
    eg = (end_hex >> 8) & 0xFF
    eb = end_hex & 0xFF
    t = step / (total - 1)
    r = int(sr + (er - sr) * t)
    g = int(sg + (eg - sg) * t)
    b = int(sb + (eb - sb) * t)
    return (r << 16) | (g << 8) | b


def _generate_thresholds() -> list[int]:
    """
    Generate 100 RuneScape-style exponentially increasing score thresholds.
    Rookie I = 0, Immortal X ≈ 2,000,000.

    Uses an adapted RuneScape XP formula where each rank requires exponentially
    more points than the last. The gap between tier groups grows by ~2.7x each time.
    The halfway point (50% of total XP) is around Rank 94 (Immortal IV) — just like
    RuneScape where level 92 is the halfway point to 99.

    At max daily grind (~3000 pts/day with streak): Immortal X takes ~1.8 years.
    At casual play (~1000 pts/day): Immortal X takes ~5.4 years.
    """
    thresholds = [0]  # Rank 1 (Rookie I) starts at 0
    total = 0
    for level in range(2, 101):
        # RS-style: each rank's point requirement grows exponentially
        # The 2^(level/7) term drives the exponential acceleration
        # Base floor of 50 per rank ensures early ranks aren't trivial
        diff = max(50, int((level + 300 * (2 ** (level / 7.0))) / 32))
        total += diff
        thresholds.append(total)
    return thresholds


def build_ranks() -> list[Rank]:
    """Build all 100 rank definitions."""
    thresholds = _generate_thresholds()
    ranks = []

    for group_idx, (group_name, start_color, end_color, tagline) in enumerate(RANK_GROUPS):
        for sub_idx in range(10):
            tier = group_idx * 10 + sub_idx + 1  # 1-100
            color = _interpolate_color(start_color, end_color, sub_idx, 10)
            name = f"{group_name} {ROMAN_NUMERALS[sub_idx]}"
            ranks.append(Rank(
                tier=tier,
                name=name,
                group_name=group_name,
                sub_rank=sub_idx + 1,
                color=color,
                threshold=thresholds[tier - 1],
                tagline=tagline,
            ))

    return ranks


# Pre-built rank list — import this
ALL_RANKS = build_ranks()

# Quick lookup by tier number (1-indexed)
RANK_BY_TIER = {r.tier: r for r in ALL_RANKS}


def get_rank_for_score(score: float) -> Rank:
    """Return the highest rank achieved for a given score."""
    result = ALL_RANKS[0]
    for rank in ALL_RANKS:
        if score >= rank.threshold:
            result = rank
        else:
            break
    return result


def get_next_rank(current_tier: int) -> Optional[Rank]:
    """Return the next rank, or None if at max."""
    if current_tier >= 100:
        return None
    return RANK_BY_TIER.get(current_tier + 1)


def get_progress_to_next(score: float, current_tier: int) -> float:
    """Return 0.0-1.0 progress toward the next rank. 1.0 if maxed."""
    next_rank = get_next_rank(current_tier)
    if next_rank is None:
        return 1.0
    current_threshold = RANK_BY_TIER[current_tier].threshold
    next_threshold = next_rank.threshold
    gap = next_threshold - current_threshold
    if gap <= 0:
        return 1.0
    progress = (score - current_threshold) / gap
    return min(max(progress, 0.0), 1.0)


def make_progress_bar(progress: float, length: int = 12) -> str:
    """Create a visual progress bar like ████████░░░░ 67%"""
    filled = int(progress * length)
    empty = length - filled
    bar = "█" * filled + "░" * empty
    return f"{bar} {int(progress * 100)}%"
