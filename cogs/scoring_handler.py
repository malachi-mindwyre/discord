"""
The Circle — Scoring Handler Cog v2
Processes every message through the 6-layer scoring engine.
Gathers rich context: quality signals, social depth, combos, diversity, temporal, meta.
"""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set

import discord
from discord.ext import commands

from config import (
    EXCLUDED_CHANNELS,
    COOLDOWN_SECONDS,
    SPAM_MESSAGE_COUNT,
    SPAM_WINDOW_SECONDS,
    SPAM_PAUSE_SECONDS,
    DUPLICATE_WINDOW_SECONDS,
    EMBED_COLOR_ACCENT,
    COMEBACK_INACTIVE_DAYS,
    KEEPER_RANKUP,
    KEEPER_RANKUP_INLINE,
    KEEPER_COMEBACK,
    COMBO_WINDOW_SECONDS,
    CRITICAL_HIT_CHANCE,
    NEAR_MISS_CHANCE,
    NEAR_MISS_MESSAGES,
    BONUS_DROP_CHANCE,
    BONUS_DROP_MULTIPLIERS,
    SCORE_FIRST_MOVER_WINDOW_SECONDS,
    ECONOMY_COIN_PER_MESSAGE,
    COMEBACK_BONUS_TIERS,
    COMEBACK_GIFT_BASE_COINS,
    COMEBACK_GIFT_PER_DAY,
    COMEBACK_GIFT_MAX_COINS,
    NEAR_MISS_MIN_RANK,
)
from scoring import MessageContext, calculate_score, extract_quality_signals
from ranks import get_rank_for_score, get_next_rank, RANK_BY_TIER, make_progress_bar
from database import (
    get_or_create_user,
    update_user_score,
    get_daily_points,
    add_daily_points,
    log_message,
    log_rank_change,
    increment_invitee_messages,
    get_streak,
    get_messages_today_count,
    get_unique_channels_today,
    get_user_faction,
    get_winning_faction,
    get_prestige_level,
    get_combo_state,
    update_combo_state,
    add_coins,
    get_jackpot_pot,
    get_reply_chain_depth,
    is_first_reply_to_message,
    get_active_boost,
)


class ScoringHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory cooldown/spam tracking
        self._last_message_time: dict[int, float] = {}
        self._recent_messages: dict[int, list[float]] = {}
        self._spam_paused_until: dict[int, float] = {}
        self._last_message_content: dict[int, tuple[str, float]] = {}
        # Bonus drops: user_id -> multiplier (for next message)
        self._pending_bonus_drops: dict[int, float] = {}

    def _check_cooldown(self, user_id: int) -> bool:
        """Returns True if the user is on cooldown (should NOT be scored)."""
        now = time.time()
        last = self._last_message_time.get(user_id, 0)
        if now - last < COOLDOWN_SECONDS:
            return True
        self._last_message_time[user_id] = now
        return False

    def _check_spam(self, user_id: int) -> bool:
        """Returns True if user is spam-paused or just triggered spam detection."""
        now = time.time()
        paused_until = self._spam_paused_until.get(user_id, 0)
        if now < paused_until:
            return True

        timestamps = self._recent_messages.get(user_id, [])
        timestamps.append(now)
        timestamps = [t for t in timestamps if now - t < SPAM_WINDOW_SECONDS]
        self._recent_messages[user_id] = timestamps

        if len(timestamps) >= SPAM_MESSAGE_COUNT:
            self._spam_paused_until[user_id] = now + SPAM_PAUSE_SECONDS
            self._recent_messages[user_id] = []
            return True
        return False

    def _check_duplicate(self, user_id: int, content: str) -> bool:
        """Returns True if this is a duplicate message within the window."""
        now = time.time()
        last = self._last_message_content.get(user_id)
        self._last_message_content[user_id] = (content, now)
        if last and last[0] == content and (now - last[1]) < DUPLICATE_WINDOW_SECONDS:
            return True
        return False

    def _get_comeback_multiplier(self, days_inactive: int) -> float:
        """Get tiered comeback multiplier based on days inactive."""
        if days_inactive < COMEBACK_INACTIVE_DAYS:
            return 1.0
        for max_days, mult in sorted(COMEBACK_BONUS_TIERS.items()):
            if days_inactive <= max_days:
                return mult
        return 2.0  # fallback for very long absence

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots, DMs, excluded channels
        if message.author.bot or not message.guild:
            return
        if message.channel.name in EXCLUDED_CHANNELS:
            return

        user_id = message.author.id
        username = str(message.author)

        # Anti-spam checks
        if self._check_spam(user_id):
            return
        if self._check_cooldown(user_id):
            return
        if self._check_duplicate(user_id, message.content):
            return

        # Get or create user in DB
        user = await get_or_create_user(user_id, username)

        # Check if this is a comeback
        last_active = datetime.fromisoformat(user["last_active"])
        days_inactive = (datetime.utcnow() - last_active).days
        is_comeback = days_inactive >= COMEBACK_INACTIVE_DAYS
        comeback_mult = self._get_comeback_multiplier(days_inactive) if is_comeback else 1.0

        # ── Gather rich context ──────────────────────────────────────

        # Quality signals
        quality = extract_quality_signals(message.content)
        has_media = bool(message.attachments) or bool(message.embeds)
        is_reply = message.reference is not None
        has_mention = bool(message.mentions)

        # Daily context
        daily_points = await get_daily_points(user_id)
        messages_today = await get_messages_today_count(user_id)
        unique_channels = await get_unique_channels_today(user_id)

        # Reply chain depth + first mover
        reply_chain_depth = 0
        is_first_reply = False
        minutes_since_parent = 999.0
        if is_reply and message.reference and message.reference.message_id:
            parent_id = message.reference.message_id
            reply_chain_depth = await get_reply_chain_depth(parent_id, message.channel.id)
            is_first_reply = await is_first_reply_to_message(parent_id)
            try:
                parent_msg = message.reference.cached_message
                if parent_msg is None:
                    parent_msg = await message.channel.fetch_message(parent_id)
                if parent_msg:
                    delta = (message.created_at - parent_msg.created_at).total_seconds()
                    minutes_since_parent = delta / 60.0
            except (discord.NotFound, discord.HTTPException):
                pass

        # Combo system
        combo_state = await get_combo_state(user_id)
        current_combo = 0
        if is_reply or has_mention:
            now_ts = datetime.utcnow()
            if combo_state and combo_state["last_social_at"]:
                last_social = datetime.fromisoformat(combo_state["last_social_at"])
                if (now_ts - last_social).total_seconds() <= COMBO_WINDOW_SECONDS:
                    current_combo = combo_state["combo_count"] + 1
                else:
                    current_combo = 1
            else:
                current_combo = 1
            await update_combo_state(user_id, current_combo, now_ts.isoformat())
        else:
            # Non-social message doesn't break combo, just doesn't increment
            if combo_state:
                current_combo = combo_state["combo_count"]

        # Streak multiplier
        from cogs.streaks import get_streak_multiplier
        streak_data = await get_streak(user_id)
        streak_mult = get_streak_multiplier(streak_data["current_streak"])

        # Faction context
        user_faction = await get_user_faction(user_id)
        winning_faction = await get_winning_faction()
        is_winning_faction = (user_faction == winning_faction) if user_faction and winning_faction else False

        # Prestige level
        prestige_level = await get_prestige_level(user_id)

        # Temporal context
        now_utc = datetime.utcnow()
        current_hour = now_utc.hour
        is_weekend = now_utc.weekday() in (5, 6)

        # ── Build scoring context ────────────────────────────────────

        ctx = MessageContext(
            word_count=quality["word_count"],
            has_media=has_media,
            is_reply=is_reply,
            has_mention=has_mention,
            daily_points_so_far=daily_points,
            message_content=message.content,
            is_comeback=is_comeback,
            unique_word_count=quality["unique_word_count"],
            has_link=quality["has_link"],
            has_punctuation=quality["has_punctuation"],
            contains_question=quality["contains_question"],
            reply_chain_depth=reply_chain_depth,
            is_first_reply=is_first_reply,
            minutes_since_parent=minutes_since_parent,
            messages_today=messages_today,
            unique_channels_today=unique_channels,
            current_combo=current_combo,
            current_streak=streak_data["current_streak"],
            streak_multiplier=streak_mult,
            user_rank_tier=user["current_rank"],
            is_winning_faction=is_winning_faction,
            prestige_level=prestige_level,
            current_hour_utc=current_hour,
            is_weekend=is_weekend,
        )

        # ── Calculate score ──────────────────────────────────────────

        result = calculate_score(ctx)

        if result.points <= 0:
            return

        final_points = result.points

        # ── Apply server-wide 2x XP window (if active) ──────────────

        vr_cog = self.bot.get_cog("VariableRewards")
        if vr_cog and vr_cog.is_double_xp:
            final_points *= 2.0

        # ── Apply personal XP boost (from shop/wheel) ────────────────

        personal_boost = await get_active_boost(user_id)
        if personal_boost and personal_boost > 1.0:
            final_points *= personal_boost

        # ── Apply bonus drop multiplier (if pending) ─────────────────

        bonus_mult = self._pending_bonus_drops.pop(user_id, None)
        if bonus_mult and bonus_mult > 1.0:
            final_points *= bonus_mult
            try:
                await message.channel.send(
                    f"💥 **BONUS DROP** — {message.author.mention} got **{bonus_mult:.0f}x** on that message! "
                    f"({final_points:.0f} pts)",
                    delete_after=15,
                )
            except discord.HTTPException:
                pass

        # ── Critical hit check ───────────────────────────────────────

        is_critical = random.random() < CRITICAL_HIT_CHANCE
        if is_critical:
            final_points *= 2.0
            try:
                await message.channel.send(
                    f"⚡ **CRITICAL HIT** — {message.author.mention} scored **2x** on that message! "
                    f"({final_points:.0f} pts)",
                    delete_after=10,
                )
            except discord.HTTPException:
                pass

        # ── Determine new rank ───────────────────────────────────────

        new_total = user["total_score"] + final_points
        new_rank = get_rank_for_score(new_total)
        old_rank_tier = user["current_rank"]
        ranked_up = new_rank.tier > old_rank_tier

        # ── Update database ──────────────────────────────────────────

        await update_user_score(
            user_id,
            final_points,
            new_rank=new_rank.tier if ranked_up else None,
        )
        await add_daily_points(user_id, final_points)
        await log_message(
            user_id, message.channel.id, quality["word_count"],
            has_media, is_reply, has_mention, final_points,
        )

        # Economy: award coins
        await add_coins(user_id, ECONOMY_COIN_PER_MESSAGE)

        # Delegate to variable rewards (jackpot contribution + mystery drops)
        if vr_cog:
            await vr_cog.on_scored_message(user_id, message.channel)

        # Track invitee messages for invite validation
        await increment_invitee_messages(user_id)

        # ── Handle comeback announcement + gift ──────────────────────

        if is_comeback:
            comeback_gift = min(
                COMEBACK_GIFT_BASE_COINS + (days_inactive * COMEBACK_GIFT_PER_DAY),
                COMEBACK_GIFT_MAX_COINS,
            )
            await add_coins(user_id, comeback_gift)
            try:
                await message.channel.send(
                    f"A familiar presence returns... {message.author.mention}, The Circle remembers you.\n"
                    f"⚡ **{comeback_mult:.0f}x** blessing granted + **{comeback_gift}** 🪙 welcome-back gift."
                )
            except discord.HTTPException:
                pass

        # ── Handle rank-up ───────────────────────────────────────────

        if ranked_up:
            await log_rank_change(user_id, old_rank_tier, new_rank.tier)
            await self._announce_rankup(message, new_rank, new_total)
            await self._update_role(message.guild, message.author, old_rank_tier, new_rank.tier)

        # ── Check achievements ───────────────────────────────────────

        achievements_cog = self.bot.get_cog("AchievementChecker")
        if achievements_cog:
            await achievements_cog.check_achievements(user_id, message.guild, message.channel)

        # ── Season XP (50% of message score) ─────────────────────────

        season_cog = self.bot.get_cog("SeasonPass")
        if season_cog:
            await season_cog.add_season_xp(user_id, max(1, int(final_points * 0.5)))

        # ── Variable reward rolls (post-scoring) ─────────────────────

        # Near-miss (1% chance, Regular+ only)
        if random.random() < NEAR_MISS_CHANCE and user["current_rank"] >= NEAR_MISS_MIN_RANK:
            try:
                jackpot_pot = await get_jackpot_pot()
                msg_text = random.choice(NEAR_MISS_MESSAGES).format(
                    jackpot_amount=int(jackpot_pot)
                )
                await message.channel.send(f"👀 {message.author.mention} {msg_text}", delete_after=10)
            except (discord.HTTPException, KeyError):
                pass

        # Bonus drop for NEXT message (2% chance)
        if random.random() < BONUS_DROP_CHANCE:
            # Pick weighted random multiplier
            total_weight = sum(w for _, w in BONUS_DROP_MULTIPLIERS)
            roll = random.uniform(0, total_weight)
            cumulative = 0
            chosen_mult = 2.0
            for mult, weight in BONUS_DROP_MULTIPLIERS:
                cumulative += weight
                if roll <= cumulative:
                    chosen_mult = mult
                    break
            self._pending_bonus_drops[user_id] = chosen_mult
            try:
                await message.author.send(
                    f"🔮 **Your next message is blessed.** Make it count."
                )
            except discord.HTTPException:
                # DMs disabled, send in channel instead
                try:
                    await message.channel.send(
                        f"🔮 {message.author.mention} Something stirs... your next message carries power.",
                        delete_after=8,
                    )
                except discord.HTTPException:
                    pass

    async def _announce_rankup(self, message: discord.Message, new_rank, new_total: float):
        """Post rank-up announcements in #rank-ups and inline."""
        try:
            await message.channel.send(
                KEEPER_RANKUP_INLINE.format(
                    mention=message.author.mention,
                    rank_name=new_rank.name,
                )
            )
        except discord.HTTPException:
            pass

        rank_ups_channel = discord.utils.get(message.guild.text_channels, name="rank-ups")
        if rank_ups_channel:
            next_rank = get_next_rank(new_rank.tier)
            progress = ""
            if next_rank:
                gap = next_rank.threshold - new_rank.threshold
                done = new_total - new_rank.threshold
                pct = min(done / gap, 1.0) if gap > 0 else 1.0
                progress = f"\n📊 Next: **{next_rank.name}** ({next_rank.threshold:,.0f} pts)\n{make_progress_bar(pct)}"

            embed = discord.Embed(
                title="⚡ RANK UP",
                description=KEEPER_RANKUP.format(
                    mention=message.author.mention,
                    rank_name=new_rank.name,
                    tagline=new_rank.tagline,
                ) + f"\n\n🏆 Score: **{new_total:,.0f}** pts{progress}",
                color=new_rank.color,
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            try:
                await rank_ups_channel.send(embed=embed)
            except discord.HTTPException:
                pass

    async def _update_role(self, guild: discord.Guild, member: discord.Member,
                           old_tier: int, new_tier: int):
        """Remove old rank role and assign new one."""
        old_rank = RANK_BY_TIER.get(old_tier)
        new_rank = RANK_BY_TIER.get(new_tier)

        if old_rank:
            old_role = discord.utils.get(guild.roles, name=old_rank.name)
            if old_role and old_role in member.roles:
                try:
                    await member.remove_roles(old_role, reason="Rank change")
                except discord.HTTPException:
                    pass

        if new_rank:
            new_role = discord.utils.get(guild.roles, name=new_rank.name)
            if new_role:
                try:
                    await member.add_roles(new_role, reason="Rank up")
                except discord.HTTPException:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ScoringHandler(bot))
