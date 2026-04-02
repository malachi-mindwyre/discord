"""
The Circle — Onboarding v2 Cog
7-day staged onboarding pipeline. Keeper guides new members through quests,
nudges, and milestones via DM — culminating in a public graduation ceremony.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_ACCENT,
    EMBED_COLOR_PRIMARY,
    GUILD_ID,
)
from database import (
    add_coins,
    create_onboarding_state,
    get_daily_points,
    get_onboarding_state,
    get_or_create_user,
    unlock_achievement,
    update_onboarding_stage,
)
from dm_coordinator import can_dm as global_can_dm, record_dm as global_record_dm

logger = logging.getLogger("circle.onboarding_v2")

# ─── Constants ────────────────────────────────────────────────────────────────

ONBOARDING_QUEST_INTRO_POINTS = 50
ONBOARDING_GRADUATION_COINS = 100
ONBOARDING_GRADUATION_BADGE = "survivor_7d"

# DM stage keys — used in the dm_log JSON array to prevent duplicate sends
STAGE_WELCOME = "welcome_5s"
STAGE_NUDGE_5M = "nudge_5m"
STAGE_PROGRESS_1H = "progress_1h"
STAGE_STREAK_ANCHOR_4H = "streak_anchor_4h"
STAGE_CHECKIN_24H = "checkin_24h"
STAGE_MOMENTUM_48H = "momentum_48h"
STAGE_MILESTONE_72H = "milestone_72h"
STAGE_REPORT_CARD_D6 = "report_card_d6"
STAGE_GRADUATION_D7 = "graduation_d7"

# Time thresholds (in seconds) from join time
THRESHOLDS = {
    STAGE_WELCOME:          5,
    # STAGE_NUDGE_5M removed — T+5m "Still quiet?" too aggressive for new users
    STAGE_PROGRESS_1H:      7200,       # 2 hr (was 1hr — gives users more breathing room)
    STAGE_STREAK_ANCHOR_4H: 14400,      # 4 hr
    STAGE_CHECKIN_24H:      86400,      # 24 hr
    STAGE_MOMENTUM_48H:     172800,     # 48 hr
    STAGE_MILESTONE_72H:    259200,     # 72 hr
    STAGE_REPORT_CARD_D6:   518400,     # 6 days
    STAGE_GRADUATION_D7:    604800,     # 7 days
}

# Ordered stage list for progression tracking
STAGE_ORDER = [
    STAGE_WELCOME,
    # STAGE_NUDGE_5M removed — too aggressive
    STAGE_PROGRESS_1H,
    STAGE_STREAK_ANCHOR_4H,
    STAGE_CHECKIN_24H,
    STAGE_MOMENTUM_48H,
    STAGE_MILESTONE_72H,
    STAGE_REPORT_CARD_D6,
    STAGE_GRADUATION_D7,
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_dm_log(raw: str | None) -> list[str]:
    """Safely parse the dm_log JSON column."""
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def _seconds_since(iso_str: str) -> float:
    """Seconds elapsed since an ISO timestamp."""
    try:
        joined = datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return 0.0
    return (datetime.utcnow() - joined).total_seconds()


async def _safe_dm(member: discord.Member, embed: discord.Embed, *, skip_coordinator: bool = False) -> bool:
    """Send a DM embed. Returns True on success, False if DMs are disabled.
    Checks global DM coordinator to prevent cross-cog DM fatigue."""
    if not skip_coordinator:
        if not await global_can_dm(member.id, "onboarding_v2"):
            logger.debug("DM to %s blocked by global coordinator", member.id)
            return False
    try:
        await member.send(embed=embed)
        await global_record_dm(member.id, "onboarding_v2")
        return True
    except (discord.Forbidden, discord.HTTPException) as exc:
        logger.warning("Could not DM %s (%s): %s", member, member.id, exc)
        return False


async def _record_dm(user_id: int, stage_key: str, dm_log: list[str], new_stage: str | None = None):
    """Append stage_key to dm_log and persist. Optionally advance the stage column."""
    dm_log.append(stage_key)
    kwargs: dict = {"dm_log": json.dumps(dm_log)}
    stage = new_stage or "active"
    await update_onboarding_stage(user_id, stage, **kwargs)


def _quest_checklist(state: dict) -> str:
    """Build a quest checklist string from onboarding state flags (4 quests, first auto-done)."""
    intro = "✅" if state.get("intro_posted") else "⬜"
    reply = "✅" if state.get("first_reply_at") else "⬜"
    daily = "✅" if state.get("daily_claimed") else "⬜"
    return (
        f"✅ Join The Circle → **Done!**\n"
        f"{intro} Post an intro in #introductions → **+{ONBOARDING_QUEST_INTRO_POINTS} pts**\n"
        f"{reply} Reply to someone's message → **3x points**\n"
        f"{daily} Claim `!daily` → **+10 Circles**"
    )


def _quests_completed(state: dict) -> int:
    """Count how many of the 4 onboarding quests are complete (joining counts as 1)."""
    count = 1  # Joining itself counts
    if state.get("intro_posted"):
        count += 1
    if state.get("first_reply_at"):
        count += 1
    if state.get("daily_claimed"):
        count += 1
    return count


# ─── Cog ──────────────────────────────────────────────────────────────────────

class OnboardingV2(commands.Cog):
    """7-day staged onboarding pipeline driven by background task + on_member_join."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.onboarding_loop.start()
        logger.info("✓ OnboardingV2 cog loaded — loop started")

    async def cog_unload(self):
        self.onboarding_loop.cancel()

    # ── Utility ───────────────────────────────────────────────────────────────

    def _get_guild(self) -> discord.Guild | None:
        return self.bot.get_guild(GUILD_ID)

    def _find_channel(self, guild: discord.Guild, name: str) -> discord.TextChannel | None:
        return discord.utils.get(guild.text_channels, name=name)

    # ── Event: Member Join ────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        await get_or_create_user(member.id, str(member))
        await create_onboarding_state(member.id)
        logger.info("Onboarding state created for %s (%s)", member, member.id)

        # Send the T+5s welcome DM immediately (don't wait for the loop)
        guild = member.guild
        state = await get_onboarding_state(member.id)
        if state:
            await self._send_welcome(member, guild, state)

    # ── Background Loop ───────────────────────────────────────────────────────

    @tasks.loop(minutes=15)
    async def onboarding_loop(self):
        """Check all onboarding users and send the next DM stage they qualify for."""
        guild = self._get_guild()
        if not guild:
            return

        # Query all non-graduated onboarding users
        import aiosqlite
        from database import DB_PATH

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM onboarding_state WHERE stage != 'graduated'"
            )
            rows = await cursor.fetchall()

        for row in rows:
            state = dict(row)
            user_id = state["user_id"]
            joined_at = state["joined_at"]
            dm_log = _parse_dm_log(state.get("dm_log"))
            elapsed = _seconds_since(joined_at)

            member = guild.get_member(user_id)
            if not member:
                continue

            # Walk through stages in order, send the first one that is due
            for stage_key in STAGE_ORDER:
                if stage_key in dm_log:
                    continue  # Already sent
                if elapsed < THRESHOLDS[stage_key]:
                    break  # Not time yet — no need to check later stages

                # Re-fetch state in case an earlier iteration in this loop updated it
                fresh_state = await get_onboarding_state(user_id)
                if not fresh_state:
                    break
                dm_log = _parse_dm_log(fresh_state.get("dm_log"))
                if stage_key in dm_log:
                    continue

                await self._dispatch_stage(member, guild, fresh_state, stage_key, dm_log)
                break  # One stage per loop iteration per user

    @onboarding_loop.before_loop
    async def before_onboarding_loop(self):
        await self.bot.wait_until_ready()

    # ── Stage Dispatcher ──────────────────────────────────────────────────────

    async def _dispatch_stage(
        self,
        member: discord.Member,
        guild: discord.Guild,
        state: dict,
        stage_key: str,
        dm_log: list[str],
    ):
        """Route to the correct DM builder for a given stage."""
        handler = {
            STAGE_WELCOME:          self._send_welcome,
            STAGE_NUDGE_5M:         self._send_nudge_5m,
            STAGE_PROGRESS_1H:      self._send_progress_1h,
            STAGE_STREAK_ANCHOR_4H: self._send_streak_anchor_4h,
            STAGE_CHECKIN_24H:      self._send_checkin_24h,
            STAGE_MOMENTUM_48H:     self._send_momentum_48h,
            STAGE_MILESTONE_72H:    self._send_milestone_72h,
            STAGE_REPORT_CARD_D6:   self._send_report_card_d6,
            STAGE_GRADUATION_D7:    self._send_graduation_d7,
        }.get(stage_key)

        if handler:
            await handler(member, guild, state)

    # ── DM Builders ───────────────────────────────────────────────────────────

    async def _send_welcome(self, member: discord.Member, guild: discord.Guild, state: dict):
        """T+5s: Welcome DM with 3 starter quests."""
        dm_log = _parse_dm_log(state.get("dm_log"))
        if STAGE_WELCOME in dm_log:
            return

        intro_ch = self._find_channel(guild, "introductions")
        intro_mention = intro_ch.mention if intro_ch else "#introductions"

        embed = discord.Embed(
            title="⚫ THE CIRCLE AWAITS",
            description=(
                f"Welcome, **{member.display_name}**. I am **Keeper**, the guardian of this place.\n\n"
                f"You've entered The Circle. What you do next... determines everything.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 **YOUR FIRST 4 QUESTS**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✅ Join The Circle → **Done!**\n"
                f"⬜ Post an intro in {intro_mention} → **+{ONBOARDING_QUEST_INTRO_POINTS} pts**\n"
                f"⬜ Reply to someone's message → **3x points**\n"
                f"⬜ Type `!daily` in any channel → **+10 Circles** 🪙\n\n"
                f"Complete all 4 and you'll be ahead of **90%** of new members.\n\n"
                f"*The Circle remembers everything. Your journey starts now.*"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="The Circle — 7-Day Onboarding")

        sent = await _safe_dm(member, embed, skip_coordinator=True)
        if sent:
            await _record_dm(member.id, STAGE_WELCOME, dm_log, new_stage="welcomed")
            logger.info("Sent welcome DM to %s (%s)", member, member.id)
        else:
            # Fallback: post condensed welcome in #general if DMs are disabled
            fallback_ch = self._find_channel(guild, "general")
            if fallback_ch:
                fallback_embed = discord.Embed(
                    title=f"⚫ WELCOME, {member.display_name.upper()}",
                    description=(
                        f"{member.mention}, I am **Keeper**. Your journey begins now.\n\n"
                        f"🎯 **Quick Start:** Post an intro in #introductions, "
                        f"reply to someone, and type `!daily`.\n\n"
                        f"*Enable DMs from server members for the full onboarding experience.*"
                    ),
                    color=EMBED_COLOR_PRIMARY,
                )
                try:
                    await fallback_ch.send(embed=fallback_embed, delete_after=300)
                except discord.HTTPException:
                    pass
            await _record_dm(member.id, STAGE_WELCOME, dm_log, new_stage="welcomed")
            logger.info("Sent welcome FALLBACK (DMs disabled) for %s (%s)", member, member.id)

    async def _send_nudge_5m(self, member: discord.Member, guild: discord.Guild, state: dict):
        """T+5min: If no message yet, nudge about First Words badge."""
        dm_log = _parse_dm_log(state.get("dm_log"))
        if STAGE_NUDGE_5M in dm_log:
            return

        # Skip this nudge if the user already sent a message
        if state.get("first_message_at"):
            await _record_dm(member.id, STAGE_NUDGE_5M, dm_log)
            return

        general_ch = self._find_channel(guild, "general")
        general_mention = general_ch.mention if general_ch else "#general"

        embed = discord.Embed(
            title="👀 KEEPER IS WATCHING",
            description=(
                f"Still quiet, **{member.display_name}**? The Circle doesn't reward lurkers.\n\n"
                f"🏅 There's a hidden badge — **First Words** — for members who speak up early.\n\n"
                f"Drop a message in {general_mention}. Even \"hey\" counts.\n\n"
                f"*Silence is comfortable. But The Circle rewards the bold.*"
            ),
            color=EMBED_COLOR_ACCENT,
        )

        sent = await _safe_dm(member, embed)
        if sent:
            await _record_dm(member.id, STAGE_NUDGE_5M, dm_log)
            logger.info("Sent 5m nudge to %s (%s)", member, member.id)

    async def _send_progress_1h(self, member: discord.Member, guild: discord.Guild, state: dict):
        """T+1hr: Quest progress update or social proof."""
        dm_log = _parse_dm_log(state.get("dm_log"))
        if STAGE_PROGRESS_1H in dm_log:
            return

        completed = _quests_completed(state)
        checklist = _quest_checklist(state)

        if completed > 0:
            title = "🔥 YOU'RE MOVING"
            desc = (
                f"**{completed}/4** quests done in your first hour. Not bad, **{member.display_name}**.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 **QUEST TRACKER**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{checklist}\n\n"
                f"*Keep going. The Circle is watching who finishes.*"
            )
        else:
            # Social proof approach
            title = "⚡ DID YOU KNOW?"
            desc = (
                f"Members who complete their 3 starter quests rank up **4x faster** "
                f"in their first week.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 **YOUR QUESTS**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{checklist}\n\n"
                f"*The path is laid out. Walk it.*"
            )

        embed = discord.Embed(title=title, description=desc, color=EMBED_COLOR_PRIMARY)
        sent = await _safe_dm(member, embed)
        if sent:
            await _record_dm(member.id, STAGE_PROGRESS_1H, dm_log)
            logger.info("Sent 1h progress to %s (%s)", member, member.id)

    async def _send_streak_anchor_4h(self, member: discord.Member, guild: discord.Guild, state: dict):
        """T+4hr: Streak anchor — 'come back tomorrow'."""
        dm_log = _parse_dm_log(state.get("dm_log"))
        if STAGE_STREAK_ANCHOR_4H in dm_log:
            return

        embed = discord.Embed(
            title="🔥 STREAK SYSTEM ACTIVATED",
            description=(
                f"**{member.display_name}**, here's something most members miss:\n\n"
                f"Come back **tomorrow** and you start building a **streak**.\n\n"
                f"🔥 3 days → **+10%** point bonus\n"
                f"🔥 7 days → **+25%** point bonus\n"
                f"🔥 14 days → **+50%** point bonus\n"
                f"🔥 30 days → **+100%** point bonus (2x everything)\n\n"
                f"One message per day is all it takes. Miss a day? Streak resets to zero.\n\n"
                f"*The Circle rewards consistency above all else.*"
            ),
            color=EMBED_COLOR_ACCENT,
        )

        sent = await _safe_dm(member, embed)
        if sent:
            await _record_dm(member.id, STAGE_STREAK_ANCHOR_4H, dm_log)
            logger.info("Sent 4h streak anchor to %s (%s)", member, member.id)

    async def _send_checkin_24h(self, member: discord.Member, guild: discord.Guild, state: dict):
        """T+24hr: Personalized check-in with stats."""
        dm_log = _parse_dm_log(state.get("dm_log"))
        if STAGE_CHECKIN_24H in dm_log:
            return

        points = await get_daily_points(member.id)
        completed = _quests_completed(state)
        checklist = _quest_checklist(state)

        if points > 0:
            title = "📊 YOUR FIRST 24 HOURS"
            stats_line = f"⚡ **{points:.0f}** points earned so far"
        else:
            title = "📊 DAY 1 CHECK-IN"
            stats_line = "⚡ **0** points — the scoreboard waits for no one"

        embed = discord.Embed(
            title=title,
            description=(
                f"It's been 24 hours, **{member.display_name}**.\n\n"
                f"{stats_line}\n"
                f"🎯 **{completed}/4** quests complete\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 **QUEST STATUS**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{checklist}\n\n"
                f"💡 **Tip:** Replying to someone's message gives **3x** the points "
                f"of a normal message. Start conversations.\n\n"
                f"*The Circle sees your potential. Prove it right.*"
            ),
            color=EMBED_COLOR_PRIMARY,
        )

        sent = await _safe_dm(member, embed)
        if sent:
            await _record_dm(member.id, STAGE_CHECKIN_24H, dm_log, new_stage="day1")
            logger.info("Sent 24h check-in to %s (%s)", member, member.id)

    async def _send_momentum_48h(self, member: discord.Member, guild: discord.Guild, state: dict):
        """T+48hr: Celebrate momentum or provide a social hook."""
        dm_log = _parse_dm_log(state.get("dm_log"))
        if STAGE_MOMENTUM_48H in dm_log:
            return

        completed = _quests_completed(state)

        if completed >= 2:
            title = "🚀 MOMENTUM"
            desc = (
                f"**{member.display_name}**, you're ahead of most.\n\n"
                f"**{completed}/4** quests done in 48 hours. "
                f"The average new member? They're still figuring out where to type.\n\n"
                f"Keep this up for **5 more days** and you'll earn the "
                f"**🏅 Survivor** badge + **{ONBOARDING_GRADUATION_COINS} Circles** 🪙\n\n"
                f"*The Circle doesn't forget early effort.*"
            )
        else:
            # Social hook — reference active channels
            general_ch = self._find_channel(guild, "general")
            memes_ch = self._find_channel(guild, "memes")
            hook_channel = memes_ch or general_ch
            hook_mention = hook_channel.mention if hook_channel else "#general"

            title = "💬 THE CIRCLE IS TALKING"
            desc = (
                f"Things are happening in {hook_mention} right now, **{member.display_name}**.\n\n"
                f"Jump in. Even one reply gets you **3x points**.\n\n"
                f"Your quests are still waiting:\n\n"
                f"{_quest_checklist(state)}\n\n"
                f"*Empty chairs don't climb ranks.*"
            )

        embed = discord.Embed(title=title, description=desc, color=EMBED_COLOR_ACCENT)
        sent = await _safe_dm(member, embed)
        if sent:
            await _record_dm(member.id, STAGE_MOMENTUM_48H, dm_log, new_stage="day2")
            logger.info("Sent 48h momentum to %s (%s)", member, member.id)

    async def _send_milestone_72h(self, member: discord.Member, guild: discord.Guild, state: dict):
        """T+72hr: 3-day streak milestone tease."""
        dm_log = _parse_dm_log(state.get("dm_log"))
        if STAGE_MILESTONE_72H in dm_log:
            return

        embed = discord.Embed(
            title="🔥 3 DAYS IN THE CIRCLE",
            description=(
                f"**{member.display_name}**, you've survived 3 days. Most don't.\n\n"
                f"If you've been active each day, your streak bonus is now live:\n"
                f"🔥 **+10% bonus** on every single point you earn.\n\n"
                f"**4 more days** until your graduation ceremony.\n\n"
                f"Here's what's at stake on Day 7:\n"
                f"🏅 **Survivor** badge (permanent)\n"
                f"🪙 **{ONBOARDING_GRADUATION_COINS} Circles** bonus\n"
                f"📣 Public shoutout in the server\n\n"
                f"*Three days down. Four to go. Don't stop now.*"
            ),
            color=EMBED_COLOR_PRIMARY,
        )

        sent = await _safe_dm(member, embed)
        if sent:
            await _record_dm(member.id, STAGE_MILESTONE_72H, dm_log, new_stage="day3")
            logger.info("Sent 72h milestone to %s (%s)", member, member.id)

    async def _send_report_card_d6(self, member: discord.Member, guild: discord.Guild, state: dict):
        """Day 6: Week 1 Report Card — everything they'd lose if they quit."""
        dm_log = _parse_dm_log(state.get("dm_log"))
        if STAGE_REPORT_CARD_D6 in dm_log:
            return

        # Fetch cumulative stats
        user = await get_or_create_user(member.id, str(member))
        total_score = user.get("total_score", 0)
        current_rank = user.get("current_rank", 1)
        completed = _quests_completed(state)

        embed = discord.Embed(
            title="📋 WEEK 1 REPORT CARD",
            description=(
                f"**{member.display_name}**, tomorrow is Day 7.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 **HERE'S WHAT YOU'VE BUILT**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚡ Total Score: **{total_score:.0f}** pts\n"
                f"📈 Current Rank: **Tier {current_rank}**\n"
                f"🎯 Quests Done: **{completed}/4**\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎁 **TOMORROW YOU UNLOCK:**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🏅 The **Survivor** badge — permanent\n"
                f"🪙 **{ONBOARDING_GRADUATION_COINS} Circles** added to your wallet\n"
                f"📣 A public graduation moment\n\n"
                f"*One more day. You've earned this.*"
            ),
            color=EMBED_COLOR_ACCENT,
        )

        sent = await _safe_dm(member, embed)
        if sent:
            await _record_dm(member.id, STAGE_REPORT_CARD_D6, dm_log)
            logger.info("Sent Day 6 report card to %s (%s)", member, member.id)

    async def _send_graduation_d7(self, member: discord.Member, guild: discord.Guild, state: dict):
        """Day 7: Public graduation ceremony + badge + coins."""
        dm_log = _parse_dm_log(state.get("dm_log"))
        if STAGE_GRADUATION_D7 in dm_log:
            return

        # Award the badge and coins
        badge_new = await unlock_achievement(member.id, ONBOARDING_GRADUATION_BADGE)
        await add_coins(member.id, ONBOARDING_GRADUATION_COINS)

        # DM the graduate
        dm_embed = discord.Embed(
            title="🏅 YOU SURVIVED THE CIRCLE",
            description=(
                f"**{member.display_name}**, 7 days. You made it.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎁 **REWARDS UNLOCKED**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🏅 **Survivor** badge — permanent\n"
                f"🪙 **{ONBOARDING_GRADUATION_COINS} Circles** added to your wallet\n\n"
                f"You're no longer new here. You're one of us.\n\n"
                f"*The Circle remembers those who stay.*"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        await _safe_dm(member, dm_embed)

        # Public graduation in #rank-ups or #general
        announce_ch = (
            self._find_channel(guild, "rank-ups")
            or self._find_channel(guild, "general")
        )
        if announce_ch:
            pub_embed = discord.Embed(
                title="🏅 GRADUATION CEREMONY",
                description=(
                    f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"{member.mention} has survived **7 days** in The Circle.\n\n"
                    f"They've earned the **🏅 Survivor** badge "
                    f"and **{ONBOARDING_GRADUATION_COINS} Circles** 🪙.\n\n"
                    f"Welcome them properly. They've earned it.\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"*The Circle grows stronger.*"
                ),
                color=EMBED_COLOR_ACCENT,
            )
            try:
                await announce_ch.send(embed=pub_embed)
            except discord.HTTPException as exc:
                logger.warning("Could not post graduation announcement: %s", exc)

        # Mark as graduated
        await _record_dm(member.id, STAGE_GRADUATION_D7, dm_log, new_stage="graduated")
        await update_onboarding_stage(
            member.id,
            "graduated",
            graduation_at=datetime.utcnow().isoformat(),
        )
        logger.info("Graduated %s (%s) — badge=%s, coins=%d", member, member.id, badge_new, ONBOARDING_GRADUATION_COINS)


# ─── Setup ────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(OnboardingV2(bot))
