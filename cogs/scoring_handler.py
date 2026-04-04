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
from discord.ext import commands, tasks

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
    GUILD_ID,
    POST_SCORE_MULT_CAP,
    DAILY_CAP_TIERS,
    DAILY_CAP_DEFAULT,
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
    get_onboarding_state,
    update_onboarding_stage,
)


class ScoringHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory cooldown/spam tracking
        self._last_message_time: dict[int, float] = {}
        self._recent_messages: dict[int, list[float]] = {}
        self._spam_paused_until: dict[int, float] = {}
        self._last_message_content: dict[int, tuple[str, float]] = {}
        # Bonus drops: user_id -> (multiplier, timestamp) for next message
        self._pending_bonus_drops: dict[int, tuple[float, float]] = {}
        # Welcome Wagon: track which new member first-messages have been replied to
        # Maps new_member_user_id -> set of replier_user_ids who got the bonus
        self._welcome_wagon_replies: dict[int, set[int]] = {}
        # Conversation starter: track message_id -> (author_id, reply_count, bonus_awarded)
        self._conversation_starters: dict[int, list] = {}  # msg_id -> [author_id, reply_count, awarded, timestamp]
        # Dedup: prevent scoring the same message twice (Discord can re-deliver events)
        self._scored_message_ids: set[int] = set()
        self._cleanup_bonus_drops.start()

    def cog_unload(self):
        self._cleanup_bonus_drops.cancel()

    @tasks.loop(minutes=30)
    async def _cleanup_bonus_drops(self):
        """Remove bonus drops older than 1 hour (prevents memory leak)."""
        now = time.time()
        stale = [uid for uid, (_, ts) in self._pending_bonus_drops.items() if now - ts > 3600]
        for uid in stale:
            del self._pending_bonus_drops[uid]

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
        return 1.5  # fallback for very long absence

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots, DMs, excluded channels
        if message.author.bot or not message.guild:
            return
        if message.channel.name in EXCLUDED_CHANNELS:
            return

        user_id = message.author.id
        username = str(message.author)

        # Dedup: skip if we already scored this exact message
        if message.id in self._scored_message_ids:
            return
        self._scored_message_ids.add(message.id)
        # Keep set bounded
        if len(self._scored_message_ids) > 500:
            self._scored_message_ids = set(list(self._scored_message_ids)[-250:])

        # Skip messages deleted by moderation (mass mentions, @everyone, etc.)
        mod_cog = self.bot.get_cog("Moderation")
        if mod_cog and message.id in mod_cog.deleted_message_ids:
            return

        # Anti-spam checks
        if self._check_spam(user_id):
            return
        if self._check_cooldown(user_id):
            return
        if self._check_duplicate(user_id, message.content):
            return

        # Get or create user in DB
        user = await get_or_create_user(user_id, username)

        # ── First-message instant feedback ───────────────────────────────
        is_first_ever = user["total_score"] == 0
        if is_first_ever:
            # Check if joined within last 24h
            joined = datetime.fromisoformat(user["joined_at"])
            if (datetime.utcnow() - joined).total_seconds() < 86400:
                try:
                    await message.channel.send(
                        f"⚡ {message.author.mention} just said their first words. The Circle is watching.",
                        delete_after=30,
                    )
                except discord.HTTPException:
                    pass
                # Update onboarding state
                ob_state = await get_onboarding_state(user_id)
                if ob_state and not ob_state.get("first_message_at"):
                    await update_onboarding_stage(
                        user_id, ob_state.get("stage", "active"),
                        first_message_at=datetime.utcnow().isoformat(),
                    )

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
        from cogs.streaks_v2 import get_streak_multiplier
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

        # ── Apply comeback multiplier (3x/5x/3x by tier) ────────────

        if comeback_mult > 1.0:
            final_points *= comeback_mult

        # ── Apply mega event multiplier (if active) ──────────────────

        mega_cog = self.bot.get_cog("MegaEvents")
        if mega_cog:
            event_mult = mega_cog.active_event_multiplier
            if event_mult > 1.0:
                final_points *= event_mult

        # ── Apply server-wide 2x XP window (if active) ──────────────

        vr_cog = self.bot.get_cog("VariableRewards")
        if vr_cog and vr_cog.is_double_xp:
            final_points *= 2.0

        # ── Apply personal XP boost (from shop/wheel) ────────────────

        personal_boost = await get_active_boost(user_id)
        if personal_boost and personal_boost > 1.0:
            final_points *= personal_boost

        # ── Apply bonus drop multiplier (if pending) ─────────────────

        bonus_entry = self._pending_bonus_drops.pop(user_id, None)
        bonus_mult = bonus_entry[0] if bonus_entry else None
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

        # ── Enforce post-score multiplier cap ────────────────────────

        if result.points > 0:
            cumulative_mult = final_points / result.points
            if cumulative_mult > POST_SCORE_MULT_CAP:
                final_points = result.points * POST_SCORE_MULT_CAP

        # ── Re-enforce daily cap after all multipliers ───────────────

        daily_cap = DAILY_CAP_DEFAULT
        for max_tier, tier_cap in DAILY_CAP_TIERS:
            if user["current_rank"] <= max_tier:
                daily_cap = tier_cap
                break
        remaining_cap = max(0.0, daily_cap - daily_points)
        if final_points > remaining_cap:
            final_points = remaining_cap
        if final_points <= 0:
            final_points = 0

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
        parent_msg_id = None
        if is_reply and message.reference and message.reference.message_id:
            parent_msg_id = message.reference.message_id
        await log_message(
            user_id, message.channel.id, quality["word_count"],
            has_media, is_reply, has_mention, final_points,
            parent_message_id=parent_msg_id,
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
            await self._update_role(message.guild, message.author, old_rank_tier, new_rank.tier)
            # Only announce rank-ups at group boundaries (every 10th tier)
            # to prevent spam — sub-rank changes are silent
            old_group = (old_rank_tier - 1) // 10
            new_group = (new_rank.tier - 1) // 10
            if new_group > old_group:
                await self._announce_rankup(message, new_rank, new_total)

        # ── Check achievements ───────────────────────────────────────

        achievements_cog = self.bot.get_cog("AchievementChecker")
        if achievements_cog:
            await achievements_cog.check_achievements(user_id, message.guild, message.channel)

        # ── Season XP (50% of raw score, before diminishing returns) ──

        season_cog = self.bot.get_cog("SeasonPass")
        if season_cog:
            # Use base * social * temporal * meta (skip engagement layer's DR)
            raw_season_base = result.base_score * result.social_mult * result.temporal_mult * result.meta_mult
            await season_cog.add_season_xp(user_id, max(1, int(raw_season_base * 0.5)))

        # ── Welcome Wagon: reward users who reply to new members ─────

        if is_reply and message.reference and message.reference.message_id:
            try:
                parent_msg = message.reference.cached_message
                if parent_msg is None:
                    parent_msg = await message.channel.fetch_message(message.reference.message_id)
                if parent_msg and not parent_msg.author.bot:
                    parent_user = await get_or_create_user(parent_msg.author.id, str(parent_msg.author))
                    # Check if the parent author is a new member (joined < 48h, score < 50)
                    parent_joined = datetime.fromisoformat(parent_user["joined_at"])
                    is_new_member = (
                        (datetime.utcnow() - parent_joined).total_seconds() < 172800
                        and parent_user["total_score"] < 50
                    )
                    if is_new_member:
                        wagon_set = self._welcome_wagon_replies.setdefault(parent_msg.author.id, set())
                        if user_id not in wagon_set and len(wagon_set) < 3:
                            wagon_set.add(user_id)
                            # Award 10 bonus points + 5 Circles to the replier
                            await update_user_score(user_id, 10)
                            await add_coins(user_id, 5)
                            # Award the new member +5 pts for receiving a welcome
                            await update_user_score(parent_msg.author.id, 5)
                            try:
                                await message.add_reaction("👋")
                            except discord.HTTPException:
                                pass
                            # Clean up old entries (keep only last 50 new members)
                            if len(self._welcome_wagon_replies) > 50:
                                oldest_key = next(iter(self._welcome_wagon_replies))
                                del self._welcome_wagon_replies[oldest_key]
            except (discord.NotFound, discord.HTTPException):
                pass

        # ── Conversation Starter: retroactive bonus for popular messages ──

        # Track this message for potential future bonus
        self._conversation_starters[message.id] = [user_id, 0, False, time.time()]
        # Clean old entries (older than 1 hour)
        cutoff_ts = time.time() - 3600
        self._conversation_starters = {
            k: v for k, v in self._conversation_starters.items()
            if v[3] > cutoff_ts
        }
        # Check if this reply triggers a bonus for the parent
        if is_reply and message.reference and message.reference.message_id:
            parent_id = message.reference.message_id
            if parent_id in self._conversation_starters:
                starter = self._conversation_starters[parent_id]
                # Only count replies with 3+ words (prevents "." farming)
                if len(message.content.split()) < 3:
                    pass  # Too short — don't count
                else:
                    starter[1] += 1  # increment reply count
                if starter[1] >= 3 and not starter[2]:
                    # 3+ replies within the hour — award conversation starter bonus
                    starter[2] = True
                    starter_user_id = starter[0]
                    await update_user_score(starter_user_id, 25)
                    await add_coins(starter_user_id, 10)
                    starter_member = message.guild.get_member(starter_user_id)
                    if starter_member:
                        try:
                            await message.channel.send(
                                f"🗣️ **CONVERSATION STARTER** — {starter_member.mention}'s message "
                                f"sparked a discussion! +25 pts +10 🪙",
                                delete_after=15,
                            )
                        except discord.HTTPException:
                            pass

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
            self._pending_bonus_drops[user_id] = (chosen_mult, time.time())
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
        """Post rank-up announcement in #rank-ups only (no inline spam)."""
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
