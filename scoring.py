"""
The Circle — Scoring Engine v2
6-layer scoring formula: BASE * QUALITY * SOCIAL * TEMPORAL * ENGAGEMENT * META
No Discord dependency — pure scoring logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from config import (
    SCORE_BASE_MESSAGE,
    SCORE_PER_WORD,
    SCORE_MEDIA_POST,
    SCORE_LINK_BONUS,
    SCORE_REPLY_MULTIPLIER,
    SCORE_MENTION_MULTIPLIER,
    SCORE_REPLY_MENTION_SYNERGY,
    SCORE_CHAIN_DEPTH_BONUS,
    SCORE_CHAIN_DEPTH_MAX,
    SCORE_FIRST_MOVER_BONUS,
    SCORE_QUALITY_PUNCTUATION,
    SCORE_QUALITY_QUESTION,
    SCORE_QUALITY_VOCAB_WEIGHT,
    SCORE_SOCIAL_MULT_CAP,
    TIME_MULTIPLIERS,
    WEEKEND_BONUS_MULT,
    DIMINISHING_RETURNS_TIERS,
    DIMINISHING_RETURNS_FLOOR,
    CHANNEL_DIVERSITY_BONUS_PER,
    CHANNEL_DIVERSITY_MAX_CHANNELS,
    COMBO_BONUS_PER_STACK,
    COMBO_MAX_STACKS,
    CATCHUP_TIERS,
    CATCHUP_DEFAULT,
    META_MULT_CAP,
    DAILY_CAP_TIERS,
    DAILY_CAP_DEFAULT,
    FACTION_WIN_BONUS,
)


@dataclass
class MessageContext:
    """All the info needed to score a message."""
    # Basic message info
    word_count: int
    has_media: bool
    is_reply: bool
    has_mention: bool
    daily_points_so_far: float
    message_content: str = ""

    # Comeback
    is_comeback: bool = False

    # Quality signals (new)
    unique_word_count: int = 0
    has_link: bool = False
    has_punctuation: bool = False
    contains_question: bool = False

    # Social depth (new)
    reply_chain_depth: int = 0
    is_first_reply: bool = False
    minutes_since_parent: float = 999.0

    # Engagement context (new)
    messages_today: int = 0
    unique_channels_today: int = 1
    current_combo: int = 0

    # Meta context (new)
    current_streak: int = 0
    streak_multiplier: float = 1.0
    user_rank_tier: int = 1
    is_winning_faction: bool = False
    prestige_level: int = 0

    # Temporal (new)
    current_hour_utc: int = 12
    is_weekend: bool = False


@dataclass
class ScoreResult:
    """Result of scoring a message."""
    points: float
    base_score: float
    quality_mult: float
    social_mult: float
    temporal_mult: float
    engagement_mult: float
    meta_mult: float
    raw_score: float
    capped: bool
    breakdown: str


def _compute_base(ctx: MessageContext) -> float:
    """Layer 1: Quality-aware base score."""
    base = SCORE_BASE_MESSAGE
    word_score = min(ctx.word_count, 200) * SCORE_PER_WORD
    media_score = SCORE_MEDIA_POST if ctx.has_media else 0.0
    link_score = SCORE_LINK_BONUS if ctx.has_link else 0.0

    # Quality factor
    quality = 1.0

    # Vocabulary richness
    if ctx.word_count >= 5 and ctx.unique_word_count > 0:
        unique_ratio = ctx.unique_word_count / ctx.word_count
        quality += max(0.0, (unique_ratio - 0.5)) * SCORE_QUALITY_VOCAB_WEIGHT

    # Punctuation bonus
    if ctx.has_punctuation:
        quality += SCORE_QUALITY_PUNCTUATION

    # Question bonus (drives replies)
    if ctx.contains_question:
        quality += SCORE_QUALITY_QUESTION

    return (base + word_score + media_score + link_score) * quality


def _compute_social(ctx: MessageContext) -> float:
    """Layer 2: Social interaction multiplier."""
    # Reply + Mention synergy
    if ctx.is_reply and ctx.has_mention:
        social = SCORE_REPLY_MENTION_SYNERGY
    elif ctx.is_reply:
        social = SCORE_REPLY_MULTIPLIER
    elif ctx.has_mention:
        social = SCORE_MENTION_MULTIPLIER
    else:
        social = 1.0

    # Thread depth bonus
    depth_bonus = 1.0 + min(ctx.reply_chain_depth, SCORE_CHAIN_DEPTH_MAX) * SCORE_CHAIN_DEPTH_BONUS

    # First-mover bonus
    first_mover = SCORE_FIRST_MOVER_BONUS if (ctx.is_first_reply and ctx.minutes_since_parent <= 5.0) else 1.0

    result = social * depth_bonus * first_mover
    return min(result, SCORE_SOCIAL_MULT_CAP)


def _compute_temporal(ctx: MessageContext) -> float:
    """Layer 3: Time-of-day and weekend multiplier."""
    hour_mult = TIME_MULTIPLIERS.get(ctx.current_hour_utc, 1.0)
    weekend_mult = WEEKEND_BONUS_MULT if ctx.is_weekend else 1.0
    return hour_mult * weekend_mult


def _compute_engagement(ctx: MessageContext) -> float:
    """Layer 4: Diminishing returns + channel diversity + combo."""
    # Diminishing returns
    dim_factor = DIMINISHING_RETURNS_FLOOR
    for threshold, factor in DIMINISHING_RETURNS_TIERS:
        if ctx.messages_today <= threshold:
            dim_factor = factor
            break

    # Channel diversity bonus
    extra_channels = min(ctx.unique_channels_today - 1, CHANNEL_DIVERSITY_MAX_CHANNELS - 1)
    diversity_bonus = 1.0 + max(0, extra_channels) * CHANNEL_DIVERSITY_BONUS_PER

    # Combo system
    combo_bonus = 1.0 + min(ctx.current_combo, COMBO_MAX_STACKS) * COMBO_BONUS_PER_STACK

    return dim_factor * diversity_bonus * combo_bonus


def _compute_meta(ctx: MessageContext) -> float:
    """Layer 5: Comeback + Streak + Catch-up + Faction + Prestige."""
    # Comeback
    comeback = 5.0 if ctx.is_comeback else 1.0

    # Streak (passed in pre-computed)
    streak = ctx.streak_multiplier

    # Catch-up mechanic
    catchup = CATCHUP_DEFAULT
    for max_tier, bonus in CATCHUP_TIERS:
        if ctx.user_rank_tier <= max_tier:
            catchup = bonus
            break

    # Faction winner bonus
    faction = FACTION_WIN_BONUS if ctx.is_winning_faction else 1.0

    # Prestige permanent bonus (+5% per level, max 25%)
    prestige = 1.0 + (min(ctx.prestige_level, 5) * 0.05)

    result = comeback * streak * catchup * faction * prestige
    return min(result, META_MULT_CAP)


def _get_daily_cap(rank_tier: int) -> float:
    """Layer 6: Dynamic daily cap based on rank."""
    cap = DAILY_CAP_DEFAULT
    for max_tier, tier_cap in DAILY_CAP_TIERS:
        if rank_tier <= max_tier:
            cap = tier_cap
            break
    return cap


def calculate_score(ctx: MessageContext) -> ScoreResult:
    """
    Calculate the score for a message using the 6-layer formula.

    final_score = BASE * SOCIAL * TEMPORAL * ENGAGEMENT * META
    Then capped by dynamic daily limit.
    """
    base_score = _compute_base(ctx)
    social_mult = _compute_social(ctx)
    temporal_mult = _compute_temporal(ctx)
    engagement_mult = _compute_engagement(ctx)
    meta_mult = _compute_meta(ctx)

    raw_score = base_score * social_mult * temporal_mult * engagement_mult * meta_mult

    # Apply dynamic daily cap
    daily_cap = _get_daily_cap(ctx.user_rank_tier)
    remaining = max(0.0, daily_cap - ctx.daily_points_so_far)
    capped = raw_score > remaining
    final_score = min(raw_score, remaining)

    # Build breakdown string
    parts = [f"base:{base_score:.1f}"]
    if social_mult > 1.0:
        parts.append(f"×social:{social_mult:.1f}x")
    if temporal_mult != 1.0:
        parts.append(f"×time:{temporal_mult:.2f}x")
    if engagement_mult != 1.0:
        parts.append(f"×eng:{engagement_mult:.2f}x")
    if meta_mult > 1.0:
        parts.append(f"×meta:{meta_mult:.2f}x")
    if capped:
        parts.append(f"[CAPPED {final_score:.1f}/{raw_score:.1f}]")
    breakdown = " ".join(parts) + f" = {final_score:.1f} pts"

    return ScoreResult(
        points=final_score,
        base_score=base_score,
        quality_mult=1.0,  # folded into base
        social_mult=social_mult,
        temporal_mult=temporal_mult,
        engagement_mult=engagement_mult,
        meta_mult=meta_mult,
        raw_score=raw_score,
        capped=capped,
        breakdown=breakdown,
    )


def extract_quality_signals(content: str) -> dict:
    """Extract quality signals from message content. Helper for scoring_handler."""
    words = content.split() if content else []
    unique_words = set(w.lower() for w in words)

    # Check for links
    has_link = bool(re.search(r'https?://\S+', content)) if content else False

    # Check for punctuation (., !, ?)
    has_punctuation = bool(re.search(r'[.!?]', content)) if content else False

    # Check for questions
    contains_question = '?' in content if content else False

    return {
        "word_count": len(words),
        "unique_word_count": len(unique_words),
        "has_link": has_link,
        "has_punctuation": has_punctuation,
        "contains_question": contains_question,
    }
