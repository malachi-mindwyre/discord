"""
The Circle — Streaks V2 Cog
Multi-dimensional streak system with 5 streak types, freeze tokens,
grace periods, paired streaks, and division-based leaderboards.
Coexists with the original streaks.py — class named StreaksV2 to avoid conflict.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_ACCENT,
    ECONOMY_CURRENCY_EMOJI,
    EXCLUDED_CHANNELS,
    PAIRED_STREAK_BONUS_PER,
    PAIRED_STREAK_MAX_PAIRS,
    PAIRED_STREAK_MILESTONES,
    STREAK_BONUS_MULTIPLIER_V2,
    STREAK_FREEZE_COST,
    STREAK_FREEZE_MAX_HELD,
    STREAK_GRACE_MIN_LENGTH,
    STREAK_TYPES,
)
from database import add_coins, spend_coins

logger = logging.getLogger("circle.streaks_v2")

DB_PATH = "circle.db"

# ─── Streak Divisions ───────────────────────────────────────────────────────
STREAK_DIVISIONS = {
    "Bronze": (1, 6),
    "Silver": (7, 13),
    "Gold": (14, 29),
    "Platinum": (30, 59),
    "Diamond": (60, 99),
    "Mythic": (100, 179),
    "Eternal": (180, 999_999),
}

DIVISION_EMOJI = {
    "Bronze": "🟤",
    "Silver": "⚪",
    "Gold": "🟡",
    "Platinum": "💠",
    "Diamond": "💎",
    "Mythic": "🔮",
    "Eternal": "👑",
}

STREAK_TYPE_EMOJI = {
    "daily": "📅",
    "weekly": "📆",
    "social": "💬",
    "voice": "🎙️",
    "creative": "🎨",
}


# ─── Module-level multiplier function (importable by scoring_handler) ────────

def get_streak_multiplier(streak_count: int) -> float:
    """Get the bonus multiplier for a given streak length.

    Uses the extended V2 multiplier table:
    3: 1.1, 7: 1.25, 14: 1.5, 30: 2.0, 60: 2.5, 100: 3.0, 180: 3.5, 365: 4.0
    """
    best = 1.0
    for threshold, multiplier in sorted(STREAK_BONUS_MULTIPLIER_V2.items()):
        if streak_count >= threshold:
            best = multiplier
        else:
            break
    return best


def _get_division(streak_count: int) -> str:
    """Return the division name for a given streak count."""
    for name, (low, high) in STREAK_DIVISIONS.items():
        if low <= streak_count <= high:
            return name
    if streak_count <= 0:
        return "None"
    return "Eternal"


# ─── Database Helpers ────────────────────────────────────────────────────────

async def _ensure_tables(db: aiosqlite.Connection):
    """Create tables for the V2 streak system if they don't exist."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS streaks_v2 (
            user_id         INTEGER NOT NULL,
            streak_type     TEXT    NOT NULL,
            current_streak  INTEGER NOT NULL DEFAULT 0,
            longest_streak  INTEGER NOT NULL DEFAULT 0,
            last_activity   TEXT,
            grace_period_used INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, streak_type)
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS streak_freezes (
            user_id      INTEGER PRIMARY KEY,
            tokens_held  INTEGER NOT NULL DEFAULT 0
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS paired_streaks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_a        INTEGER NOT NULL,
            user_b        INTEGER NOT NULL,
            current_streak INTEGER NOT NULL DEFAULT 0,
            longest_streak INTEGER NOT NULL DEFAULT 0,
            last_check    TEXT,
            status        TEXT NOT NULL DEFAULT 'pending',
            created_at    TEXT NOT NULL DEFAULT (date('now'))
        )
    """)
    await db.commit()


async def _get_streak_row(db: aiosqlite.Connection, user_id: int, streak_type: str) -> dict | None:
    """Fetch a single streak row."""
    db.row_factory = aiosqlite.Row
    cursor = await db.execute(
        "SELECT * FROM streaks_v2 WHERE user_id = ? AND streak_type = ?",
        (user_id, streak_type),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def _upsert_streak(
    db: aiosqlite.Connection,
    user_id: int,
    streak_type: str,
    current: int,
    longest: int,
    last_activity: str,
    grace_used: int,
):
    """Insert or update a streak row."""
    await db.execute(
        """INSERT INTO streaks_v2 (user_id, streak_type, current_streak, longest_streak, last_activity, grace_period_used)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(user_id, streak_type)
           DO UPDATE SET current_streak = excluded.current_streak,
                         longest_streak = excluded.longest_streak,
                         last_activity  = excluded.last_activity,
                         grace_period_used = excluded.grace_period_used
        """,
        (user_id, streak_type, current, longest, last_activity, grace_used),
    )


async def _get_freeze_tokens(db: aiosqlite.Connection, user_id: int) -> int:
    cursor = await db.execute(
        "SELECT tokens_held FROM streak_freezes WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    return row[0] if row else 0


async def _set_freeze_tokens(db: aiosqlite.Connection, user_id: int, tokens: int):
    await db.execute(
        """INSERT INTO streak_freezes (user_id, tokens_held)
           VALUES (?, ?)
           ON CONFLICT(user_id) DO UPDATE SET tokens_held = excluded.tokens_held
        """,
        (user_id, tokens),
    )


# ─── The Cog ────────────────────────────────────────────────────────────────

class StreaksV2(commands.Cog):
    """Multi-dimensional streak tracking with freezes, grace periods, and paired streaks."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._tables_ready = False
        # Track which (user, streak_type) combos have been updated today to reduce DB hits
        self._today_updated: set[tuple[int, str]] = set()
        self._today_date: str = date.today().isoformat()

    async def cog_load(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await _ensure_tables(db)
        self._tables_ready = True
        self.daily_paired_check.start()
        logger.info("StreaksV2 cog loaded — tables ensured, paired check started")

    async def cog_unload(self):
        self.daily_paired_check.cancel()

    def _check_day_rollover(self):
        """Reset the in-memory cache if the date has changed."""
        today = date.today().isoformat()
        if today != self._today_date:
            self._today_updated.clear()
            self._today_date = today

    # ─── Core Streak Update ──────────────────────────────────────────────

    async def update_streak_type(self, user_id: int, streak_type: str) -> dict:
        """Update a specific streak type for a user.

        Returns a dict with keys:
            current_streak, longest_streak, changed (bool), milestone_hit (int|None),
            freeze_used (bool), grace_activated (bool)
        """
        self._check_day_rollover()

        if (user_id, streak_type) in self._today_updated:
            return {
                "current_streak": 0,
                "longest_streak": 0,
                "changed": False,
                "milestone_hit": None,
                "freeze_used": False,
                "grace_activated": False,
            }

        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        result = {
            "changed": False,
            "milestone_hit": None,
            "freeze_used": False,
            "grace_activated": False,
        }

        async with aiosqlite.connect(DB_PATH) as db:
            row = await _get_streak_row(db, user_id, streak_type)

            if row is None:
                # First ever activity for this streak type
                await _upsert_streak(db, user_id, streak_type, 1, 1, today, 0)
                await db.commit()
                self._today_updated.add((user_id, streak_type))
                result.update(current_streak=1, longest_streak=1, changed=True)
                # Check day-1 milestone
                milestones = STREAK_TYPES.get(streak_type, {}).get("milestones", [])
                if 1 in milestones:
                    result["milestone_hit"] = 1
                return result

            last_activity = row["last_activity"]
            current = row["current_streak"]
            longest = row["longest_streak"]
            grace_used = row["grace_period_used"]

            if last_activity == today:
                # Already updated today
                self._today_updated.add((user_id, streak_type))
                result.update(current_streak=current, longest_streak=longest)
                return result

            if last_activity == yesterday:
                # Consecutive day — increment
                current += 1
                longest = max(longest, current)
                result["changed"] = True
            else:
                # Streak broken — check freeze / grace
                freeze_tokens = await _get_freeze_tokens(db, user_id)

                if freeze_tokens > 0:
                    # Consume a freeze token — streak preserved but not incremented
                    await _set_freeze_tokens(db, user_id, freeze_tokens - 1)
                    result["freeze_used"] = True
                    # Don't increment, don't break
                elif current >= STREAK_GRACE_MIN_LENGTH and grace_used == 0:
                    # Auto-grace: one free pass per streak
                    grace_used = 1
                    result["grace_activated"] = True
                    # Don't increment, don't break
                else:
                    # Hard reset
                    current = 1
                    grace_used = 0
                    result["changed"] = True

                if not result["freeze_used"] and not result["grace_activated"]:
                    # Was reset to 1
                    pass
                else:
                    # Preserved — still count today's activity
                    current += 1
                    longest = max(longest, current)
                    result["changed"] = True

            await _upsert_streak(db, user_id, streak_type, current, longest, today, grace_used)
            await db.commit()

        self._today_updated.add((user_id, streak_type))
        result.update(current_streak=current, longest_streak=longest)

        # Check milestones
        milestones = STREAK_TYPES.get(streak_type, {}).get("milestones", [])
        if current in milestones and result["changed"]:
            result["milestone_hit"] = current

        return result

    # ─── Milestone Announcement ──────────────────────────────────────────

    async def _announce_milestone(
        self, channel: discord.TextChannel, member: discord.Member,
        streak_type: str, milestone: int,
    ):
        emoji = STREAK_TYPE_EMOJI.get(streak_type, "🔥")
        mult = get_streak_multiplier(milestone)
        bonus_pct = int((mult - 1) * 100)

        embed = discord.Embed(
            title=f"🔥 STREAK MILESTONE — {streak_type.upper()}",
            description=(
                f"{member.mention} just hit a **{milestone}-day {streak_type} streak!** {emoji}\n\n"
                f"Bonus multiplier: **+{bonus_pct}%** on all points 🚀\n"
                f"*The Circle remembers the devoted.*"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    # ─── Event Listeners ─────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Update daily, social, and creative streaks based on messages."""
        if message.author.bot or not message.guild:
            return
        if message.channel.name in EXCLUDED_CHANNELS:
            return

        user_id = message.author.id

        # Daily streak — any activity
        daily_result = await self.update_streak_type(user_id, "daily")
        if daily_result.get("milestone_hit"):
            await self._announce_milestone(
                message.channel, message.author, "daily", daily_result["milestone_hit"]
            )
        if daily_result.get("freeze_used"):
            try:
                await message.channel.send(
                    f"❄️ {message.author.mention} — A streak freeze was consumed to protect your daily streak!",
                    delete_after=15,
                )
            except discord.HTTPException:
                pass
        if daily_result.get("grace_activated"):
            try:
                await message.channel.send(
                    f"🛡️ {message.author.mention} — Grace period activated! Your daily streak lives on. (One-time save)",
                    delete_after=15,
                )
            except discord.HTTPException:
                pass

        # Social streak — reply to 3+ unique users in a day
        if message.reference and message.reference.message_id:
            try:
                ref_msg = message.reference.cached_message
                if ref_msg is None:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                if ref_msg and ref_msg.author.id != user_id and not ref_msg.author.bot:
                    social_result = await self._check_social_streak(user_id, ref_msg.author.id)
                    if social_result and social_result.get("milestone_hit"):
                        await self._announce_milestone(
                            message.channel, message.author, "social", social_result["milestone_hit"]
                        )
            except (discord.NotFound, discord.HTTPException):
                pass

        # Creative streak — post media
        has_media = bool(message.attachments) or bool(message.embeds)
        if has_media:
            creative_result = await self.update_streak_type(user_id, "creative")
            if creative_result.get("milestone_hit"):
                await self._announce_milestone(
                    message.channel, message.author, "creative", creative_result["milestone_hit"]
                )

    async def _check_social_streak(self, user_id: int, replied_to_id: int) -> dict | None:
        """Track unique reply targets per day. Activate social streak when 3+ unique reached."""
        today = date.today().isoformat()
        cache_key = f"social_replies:{user_id}:{today}"

        # Use bot-level cache for today's social reply targets
        if not hasattr(self.bot, "_social_reply_cache"):
            self.bot._social_reply_cache = {}

        targets = self.bot._social_reply_cache.get(cache_key, set())
        targets.add(replied_to_id)
        self.bot._social_reply_cache[cache_key] = targets

        if len(targets) >= 3:
            return await self.update_streak_type(user_id, "social")
        return None

    # ─── Voice Streak (called externally by voice_xp cog) ───────────────

    async def check_voice_streak(self, user_id: int, minutes: float, channel: discord.TextChannel | None = None):
        """Called by voice_xp when a user accumulates voice time.

        If the user has been in voice 15+ minutes today, update voice streak.
        """
        if minutes >= 15:
            result = await self.update_streak_type(user_id, "voice")
            if result.get("milestone_hit") and channel:
                member = channel.guild.get_member(user_id)
                if member:
                    await self._announce_milestone(channel, member, "voice", result["milestone_hit"])

    # ─── Weekly Streak (background check) ────────────────────────────────

    @tasks.loop(time=datetime(2026, 1, 1, 0, 5).time())  # 00:05 UTC daily
    async def daily_paired_check(self):
        """Runs daily: check paired streaks and weekly streaks on Sundays."""
        try:
            today = date.today()

            # Weekly streak check on Monday (checks the previous week)
            if today.weekday() == 0:
                await self._process_weekly_streaks()

            # Paired streak check every day
            await self._process_paired_streaks()

        except Exception as e:
            logger.error(f"Error in daily_paired_check: {e}", exc_info=True)

    @daily_paired_check.before_loop
    async def _before_daily_check(self):
        await self.bot.wait_until_ready()

    async def _process_weekly_streaks(self):
        """Check all users' daily activity over the past 7 days.

        If a user was active 5+ of 7 days, increment their weekly streak.
        """
        today = date.today()
        week_start = (today - timedelta(days=7)).isoformat()

        async with aiosqlite.connect(DB_PATH) as db:
            # Count distinct active days per user in the last 7 days
            cursor = await db.execute(
                """SELECT user_id, COUNT(DISTINCT last_activity) as active_days
                   FROM streaks_v2
                   WHERE streak_type = 'daily' AND last_activity >= ?
                   GROUP BY user_id
                   HAVING active_days >= 5
                """,
                (week_start,),
            )
            # Note: the above query only checks the daily streak row's last_activity,
            # but we need actual daily activity counts. Use daily_scores table instead.
            pass

        # Better approach: use daily_scores table if it exists
        async with aiosqlite.connect(DB_PATH) as db:
            try:
                cursor = await db.execute(
                    """SELECT user_id, COUNT(DISTINCT score_date) as active_days
                       FROM daily_scores
                       WHERE score_date >= ?
                       GROUP BY user_id
                       HAVING active_days >= 5
                    """,
                    (week_start,),
                )
                rows = await cursor.fetchall()
            except aiosqlite.OperationalError:
                # daily_scores table might not exist
                rows = []

            for row in rows:
                user_id = row[0]
                await self._update_weekly_streak_for_user(db, user_id)
            await db.commit()

    async def _update_weekly_streak_for_user(self, db: aiosqlite.Connection, user_id: int):
        """Increment a user's weekly streak."""
        today = date.today().isoformat()
        last_monday = (date.today() - timedelta(days=7)).isoformat()

        row = await _get_streak_row(db, user_id, "weekly")
        if row is None:
            await _upsert_streak(db, user_id, "weekly", 1, 1, today, 0)
            return

        last_activity = row["last_activity"]
        current = row["current_streak"]
        longest = row["longest_streak"]

        # If last weekly update was within the past 14 days, it's consecutive
        if last_activity and last_activity >= last_monday:
            current += 1
        else:
            current = 1

        longest = max(longest, current)
        await _upsert_streak(db, user_id, "weekly", current, longest, today, row["grace_period_used"])

    # ─── Paired Streaks ──────────────────────────────────────────────────

    async def _process_paired_streaks(self):
        """Check all active pairs. If both were active today, increment. Otherwise break."""
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM paired_streaks WHERE status = 'active'"
            )
            pairs = [dict(r) for r in await cursor.fetchall()]

            for pair in pairs:
                user_a = pair["user_a"]
                user_b = pair["user_b"]

                # Check if both users were active yesterday (daily streak updated)
                row_a = await _get_streak_row(db, user_a, "daily")
                row_b = await _get_streak_row(db, user_b, "daily")

                a_active = row_a and row_a["last_activity"] in (today, yesterday)
                b_active = row_b and row_b["last_activity"] in (today, yesterday)

                current = pair["current_streak"]
                longest = pair["longest_streak"]
                last_check = pair["last_check"]

                if last_check == today:
                    continue  # Already processed today

                if a_active and b_active:
                    current += 1
                    longest = max(longest, current)

                    # Check milestones
                    if current in PAIRED_STREAK_MILESTONES:
                        reward = PAIRED_STREAK_MILESTONES[current]
                        await add_coins(user_a, reward)
                        await add_coins(user_b, reward)
                        # Announce milestone
                        await self._announce_paired_milestone(user_a, user_b, current, reward)
                else:
                    current = 0

                await db.execute(
                    """UPDATE paired_streaks
                       SET current_streak = ?, longest_streak = ?, last_check = ?
                       WHERE id = ?
                    """,
                    (current, longest, today, pair["id"]),
                )

            await db.commit()

    async def _announce_paired_milestone(
        self, user_a_id: int, user_b_id: int, days: int, reward: int
    ):
        """Send paired streak milestone to the first available text channel."""
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return

        member_a = guild.get_member(user_a_id)
        member_b = guild.get_member(user_b_id)
        if not member_a or not member_b:
            return

        # Find a general-ish channel
        channel = discord.utils.get(guild.text_channels, name="general")
        if not channel:
            return

        embed = discord.Embed(
            title="🔗 PAIRED STREAK MILESTONE",
            description=(
                f"{member_a.mention} & {member_b.mention} hit a **{days}-day paired streak!**\n\n"
                f"Both earned **{reward}** {ECONOMY_CURRENCY_EMOJI}\n"
                f"*Two flames burn brighter than one.*"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    # ─── Commands ────────────────────────────────────────────────────────

    @commands.command(name="allstreaks")
    async def streak_cmd(self, ctx: commands.Context):
        """Show all your active streaks in a single embed."""
        user_id = ctx.author.id

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM streaks_v2 WHERE user_id = ? ORDER BY streak_type",
                (user_id,),
            )
            rows = [dict(r) for r in await cursor.fetchall()]
            freeze_tokens = await _get_freeze_tokens(db, user_id)

        embed = discord.Embed(
            title=f"🔥 {ctx.author.display_name}'s Streaks",
            color=EMBED_COLOR_ACCENT,
        )

        if not rows:
            embed.description = "No active streaks yet. Start chatting to build your first streak!"
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            await ctx.send(embed=embed)
            return

        for row in rows:
            stype = row["streak_type"]
            current = row["current_streak"]
            longest = row["longest_streak"]
            emoji = STREAK_TYPE_EMOJI.get(stype, "🔥")
            division = _get_division(current)
            div_emoji = DIVISION_EMOJI.get(division, "")

            milestones = STREAK_TYPES.get(stype, {}).get("milestones", [])
            next_ms = None
            for m in sorted(milestones):
                if current < m:
                    next_ms = m
                    break

            value_lines = [
                f"Current: **{current}** days {div_emoji} {division}",
                f"Longest: **{longest}** days",
            ]
            if next_ms:
                value_lines.append(f"Next milestone: **{next_ms}** ({next_ms - current} to go)")

            mult = get_streak_multiplier(current)
            if mult > 1.0:
                bonus_pct = int((mult - 1) * 100)
                value_lines.append(f"Bonus: **+{bonus_pct}%**")

            embed.add_field(
                name=f"{emoji} {stype.capitalize()} Streak",
                value="\n".join(value_lines),
                inline=True,
            )

        # Freeze tokens
        embed.set_footer(text=f"❄️ Freeze tokens: {freeze_tokens}/{STREAK_FREEZE_MAX_HELD}")
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="streakboard")
    async def streaks_leaderboard(self, ctx: commands.Context):
        """Show streak leaderboard grouped by division."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT user_id, streak_type, current_streak, longest_streak
                   FROM streaks_v2
                   WHERE streak_type = 'daily' AND current_streak > 0
                   ORDER BY current_streak DESC
                   LIMIT 25
                """
            )
            rows = [dict(r) for r in await cursor.fetchall()]

        if not rows:
            await ctx.send("⚫ No active streaks yet. Be the first to start one.")
            return

        # Group by division
        divisions: dict[str, list[str]] = {}
        for row in rows:
            user_id = row["user_id"]
            current = row["current_streak"]
            division = _get_division(current)
            member = ctx.guild.get_member(user_id) if ctx.guild else None
            name = member.display_name if member else f"User#{user_id}"
            mult = get_streak_multiplier(current)
            bonus = int((mult - 1) * 100)
            bonus_str = f" (+{bonus}%)" if bonus > 0 else ""

            line = f"**{name}** — {current} days{bonus_str}"
            divisions.setdefault(division, []).append(line)

        embed = discord.Embed(
            title="🔥 STREAK LEADERBOARD",
            color=EMBED_COLOR_ACCENT,
        )

        for div_name in reversed(list(STREAK_DIVISIONS.keys())):
            if div_name in divisions:
                emoji = DIVISION_EMOJI.get(div_name, "")
                low, high = STREAK_DIVISIONS[div_name]
                entries = divisions[div_name][:5]  # Max 5 per division
                embed.add_field(
                    name=f"{emoji} {div_name} ({low}-{high} days)",
                    value="\n".join(entries),
                    inline=False,
                )

        await ctx.send(embed=embed)

    @commands.command(name="pairstreak")
    async def pair_streak_cmd(self, ctx: commands.Context, target: discord.Member):
        """Send a paired streak request to another user."""
        if target.bot or target.id == ctx.author.id:
            await ctx.send("❌ You can't pair with yourself or a bot.")
            return

        async with aiosqlite.connect(DB_PATH) as db:
            # Check max pairs for requester
            cursor = await db.execute(
                """SELECT COUNT(*) FROM paired_streaks
                   WHERE (user_a = ? OR user_b = ?) AND status = 'active'
                """,
                (ctx.author.id, ctx.author.id),
            )
            count = (await cursor.fetchone())[0]
            if count >= PAIRED_STREAK_MAX_PAIRS:
                await ctx.send(f"❌ You already have {PAIRED_STREAK_MAX_PAIRS} active pairs. Max reached.")
                return

            # Check for existing pair or pending request
            cursor = await db.execute(
                """SELECT * FROM paired_streaks
                   WHERE ((user_a = ? AND user_b = ?) OR (user_a = ? AND user_b = ?))
                   AND status IN ('active', 'pending')
                """,
                (ctx.author.id, target.id, target.id, ctx.author.id),
            )
            existing = await cursor.fetchone()
            if existing:
                await ctx.send("❌ You already have a pending or active pair with this user.")
                return

            await db.execute(
                """INSERT INTO paired_streaks (user_a, user_b, status, last_check)
                   VALUES (?, ?, 'pending', ?)
                """,
                (ctx.author.id, target.id, date.today().isoformat()),
            )
            await db.commit()

        await ctx.send(
            f"🔗 {ctx.author.mention} wants to start a **paired streak** with {target.mention}!\n"
            f"Use `!acceptpair @{ctx.author.display_name}` to accept."
        )

    @commands.command(name="acceptpair")
    async def accept_pair_cmd(self, ctx: commands.Context, requester: discord.Member):
        """Accept a paired streak request."""
        async with aiosqlite.connect(DB_PATH) as db:
            # Check max pairs for acceptor
            cursor = await db.execute(
                """SELECT COUNT(*) FROM paired_streaks
                   WHERE (user_a = ? OR user_b = ?) AND status = 'active'
                """,
                (ctx.author.id, ctx.author.id),
            )
            count = (await cursor.fetchone())[0]
            if count >= PAIRED_STREAK_MAX_PAIRS:
                await ctx.send(f"❌ You already have {PAIRED_STREAK_MAX_PAIRS} active pairs. Max reached.")
                return

            cursor = await db.execute(
                """SELECT id FROM paired_streaks
                   WHERE user_a = ? AND user_b = ? AND status = 'pending'
                """,
                (requester.id, ctx.author.id),
            )
            row = await cursor.fetchone()
            if not row:
                await ctx.send("❌ No pending pair request from that user.")
                return

            await db.execute(
                "UPDATE paired_streaks SET status = 'active', last_check = ? WHERE id = ?",
                (date.today().isoformat(), row[0]),
            )
            await db.commit()

        await ctx.send(
            f"🔗 **Paired streak activated!** {requester.mention} & {ctx.author.mention}\n"
            f"Stay active together every day. Milestones at {', '.join(str(m) for m in sorted(PAIRED_STREAK_MILESTONES.keys()))} days!"
        )

    @commands.command(name="buyfreeze")
    async def buy_freeze_cmd(self, ctx: commands.Context):
        """Buy a streak freeze token for Circles."""
        user_id = ctx.author.id

        async with aiosqlite.connect(DB_PATH) as db:
            current_tokens = await _get_freeze_tokens(db, user_id)

        if current_tokens >= STREAK_FREEZE_MAX_HELD:
            await ctx.send(
                f"❌ You already hold **{current_tokens}/{STREAK_FREEZE_MAX_HELD}** freeze tokens. Max reached."
            )
            return

        success = await spend_coins(user_id, STREAK_FREEZE_COST)
        if not success:
            await ctx.send(
                f"❌ Not enough {ECONOMY_CURRENCY_EMOJI}. A freeze token costs **{STREAK_FREEZE_COST}** Circles."
            )
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await _set_freeze_tokens(db, user_id, current_tokens + 1)
            await db.commit()

        await ctx.send(
            f"❄️ **Streak freeze purchased!** You now hold **{current_tokens + 1}/{STREAK_FREEZE_MAX_HELD}** tokens.\n"
            f"If you miss a day, a token will auto-activate to protect your streak."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(StreaksV2(bot))
