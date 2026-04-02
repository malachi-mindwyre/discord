"""
The Circle -- Monthly Mega Events Cog
Server-shaking monthly events that warp the rules of The Circle for days at a time.
The Purge, The Circle Games, and Community Build -- each bending reality in its own way.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import MEGA_EVENT_ROTATION, EMBED_COLOR_ACCENT, GUILD_ID

logger = logging.getLogger("circle.mega_events")

DB_PATH = "circle.db"

# ─── Event Theme Descriptions ──────────────────────────────────────────────
EVENT_THEMES: dict[str, dict] = {
    "The Purge": {
        "tagline": "ALL LIMITS REMOVED",
        "description": (
            "For the next **3 days**, diminishing returns are **disabled**. "
            "Every message hits at full force. No caps. No mercy.\n\n"
            "The Circle has unleashed its full power. **1.5x everything.**"
        ),
        "summary_flavor": "The Purge has ended. The dust settles... but the scores remain.",
        "emoji": "\U0001f480",  # skull
        "effect": "All diminishing returns disabled. 1.5x server-wide multiplier.",
    },
    "The Circle Games": {
        "tagline": "ONLY THE SOCIAL SURVIVE",
        "description": (
            "For the next **5 days**, social multipliers are **doubled**. "
            "Quick Fire rounds fire at **3x frequency**.\n\n"
            "Talk to each other or fall behind. The Circle rewards connection."
        ),
        "summary_flavor": "The Games are over. Champions forged in conversation.",
        "emoji": "\u2694\ufe0f",  # crossed swords
        "effect": "Social multipliers doubled. Quick Fire frequency tripled.",
    },
    "Community Build": {
        "tagline": "GROW THE CIRCLE",
        "description": (
            "For the next **7 days**, invite bonuses are **tripled** and "
            "milestone thresholds are **halved**.\n\n"
            "Bring your people. The Circle expands for those who build it."
        ),
        "summary_flavor": "The Build is complete. The Circle grows stronger.",
        "emoji": "\U0001f3d7\ufe0f",  # building construction
        "effect": "Invite bonuses tripled. Milestone thresholds halved.",
    },
}

DEFAULT_MULTIPLIER = 1.5


class MegaEvents(commands.Cog):
    """Monthly mega events that warp server scoring rules for days at a time."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Lifecycle ───────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self._ensure_table()
        if not self.event_loop.is_running():
            self.event_loop.start()
        logger.info("MegaEvents cog ready.")

    def cog_unload(self) -> None:
        self.event_loop.cancel()

    # ── DB Setup ────────────────────────────────────────────────────────────

    async def _ensure_table(self) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mega_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,
                    active INTEGER DEFAULT 1,
                    server_multiplier REAL DEFAULT 1.5
                )
            """)
            await db.commit()

    # ── Public Property (for scoring_handler) ──────────────────────────────

    @property
    def active_event_multiplier(self) -> float:
        """Synchronous check -- returns cached multiplier. Updated by the loop."""
        return getattr(self, "_cached_multiplier", 1.0)

    async def _refresh_cached_multiplier(self) -> None:
        """Pull the current active event multiplier from DB."""
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            row = await db.execute_fetchall(
                "SELECT server_multiplier FROM mega_events WHERE active = 1 AND ends_at > ? LIMIT 1",
                (now,),
            )
        if row:
            self._cached_multiplier = float(row[0]["server_multiplier"])
        else:
            self._cached_multiplier = 1.0

    async def get_active_event(self) -> dict | None:
        """Return the active event row as a dict, or None."""
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(
                "SELECT * FROM mega_events WHERE active = 1 AND ends_at > ? LIMIT 1",
                (now,),
            )
        if rows:
            return dict(rows[0])
        return None

    # ── Background Loop ────────────────────────────────────────────────────

    @tasks.loop(hours=6)
    async def event_loop(self) -> None:
        """Check if we need to start or end a mega event."""
        try:
            await self._check_event_end()
            await self._check_event_start()
            await self._refresh_cached_multiplier()
        except Exception:
            logger.exception("Error in mega event loop")

    @event_loop.before_loop
    async def _before_event_loop(self) -> None:
        await self.bot.wait_until_ready()

    # ── Event Start Logic ──────────────────────────────────────────────────

    async def _check_event_start(self) -> None:
        now = datetime.utcnow()
        day = now.day
        current_week = ((day - 1) // 7) + 1  # 1-indexed: days 1-7 = week 1, etc.
        current_month = now.strftime("%Y-%m")

        # Already have an active event?
        active = await self.get_active_event()
        if active:
            return

        # Already ran an event this month?
        if await self._event_ran_this_month(current_month):
            return

        # Find matching event for this week
        for event_cfg in MEGA_EVENT_ROTATION:
            if event_cfg["week"] == current_week:
                await self._start_event(event_cfg, now)
                return

    async def _event_ran_this_month(self, year_month: str) -> bool:
        """Check if any mega event started this calendar month."""
        async with aiosqlite.connect(DB_PATH) as db:
            rows = await db.execute_fetchall(
                "SELECT id FROM mega_events WHERE started_at LIKE ? LIMIT 1",
                (f"{year_month}%",),
            )
        return len(rows) > 0

    async def _start_event(self, event_cfg: dict, now: datetime) -> None:
        event_name = event_cfg["name"]
        duration = event_cfg["duration_days"]
        ends_at = now + timedelta(days=duration)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO mega_events (event_name, started_at, ends_at, active, server_multiplier)
                   VALUES (?, ?, ?, 1, ?)""",
                (event_name, now.isoformat(), ends_at.isoformat(), DEFAULT_MULTIPLIER),
            )
            await db.commit()

        logger.info("Mega event started: %s (ends %s)", event_name, ends_at.isoformat())
        await self._post_start_announcement(event_name, ends_at)

    # ── Event End Logic ────────────────────────────────────────────────────

    async def _check_event_end(self) -> None:
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            expired = await db.execute_fetchall(
                "SELECT * FROM mega_events WHERE active = 1 AND ends_at <= ?",
                (now,),
            )
            if expired:
                await db.execute(
                    "UPDATE mega_events SET active = 0 WHERE active = 1 AND ends_at <= ?",
                    (now,),
                )
                await db.commit()

        for row in expired:
            logger.info("Mega event ended: %s", row["event_name"])
            await self._post_end_announcement(dict(row))

    # ── Announcements ──────────────────────────────────────────────────────

    def _find_general_channel(self) -> discord.TextChannel | None:
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return None
        for ch in guild.text_channels:
            if ch.name == "general":
                return ch
        return None

    async def _post_start_announcement(self, event_name: str, ends_at: datetime) -> None:
        channel = self._find_general_channel()
        if not channel:
            logger.warning("Could not find #general to announce mega event.")
            return

        theme = EVENT_THEMES.get(event_name, {})
        emoji = theme.get("emoji", "\u26a1")
        tagline = theme.get("tagline", "SOMETHING STIRS")
        description = theme.get("description", "A mega event has begun.")
        effect = theme.get("effect", "Server-wide 1.5x multiplier.")

        embed = discord.Embed(
            title=f"{emoji}  {event_name.upper()}  {emoji}",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"**{tagline}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{description}"
            ),
            color=EMBED_COLOR_ACCENT,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(
            name="\U0001f4a0 Active Effect",
            value=f"```{effect}```",
            inline=False,
        )
        embed.add_field(
            name="\u23f3 Ends",
            value=f"<t:{int(ends_at.timestamp())}:R>",
            inline=True,
        )
        embed.set_footer(text="The Circle pulses with energy. Seize it.")

        try:
            await channel.send("@everyone", embed=embed)
        except discord.Forbidden:
            logger.warning("Missing permissions to announce mega event in #general.")

    async def _award_event_badges(self, event_row: dict) -> int:
        """Award participation badges to users active during the event."""
        badge_map = {
            "The Purge":        "event_purge",
            "The Circle Games": "event_circle_games",
            "Community Build":  "event_community",
        }
        badge_key = badge_map.get(event_row["event_name"])
        if not badge_key:
            return 0

        started_at = event_row["started_at"]
        ends_at = event_row["ends_at"]
        awarded = 0

        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # Find users who sent messages during the event window
                cursor = await db.execute(
                    """SELECT DISTINCT user_id FROM messages
                       WHERE timestamp >= ? AND timestamp <= ?""",
                    (started_at, ends_at),
                )
                participants = [row[0] for row in await cursor.fetchall()]

                for user_id in participants:
                    await db.execute(
                        """INSERT OR IGNORE INTO achievements (user_id, achievement_key, unlocked_at)
                           VALUES (?, ?, ?)""",
                        (user_id, badge_key, datetime.utcnow().isoformat()),
                    )
                await db.commit()
                awarded = len(participants)
        except Exception as e:
            logger.error("Failed to award event badges: %s", e)

        logger.info("Awarded '%s' badge to %d participants", badge_key, awarded)
        return awarded

    async def _post_end_announcement(self, event_row: dict) -> None:
        channel = self._find_general_channel()
        if not channel:
            return

        event_name = event_row["event_name"]
        theme = EVENT_THEMES.get(event_name, {})
        emoji = theme.get("emoji", "\u26a1")
        flavor = theme.get("summary_flavor", "The event has concluded.")

        started = datetime.fromisoformat(event_row["started_at"])
        ended = datetime.fromisoformat(event_row["ends_at"])
        duration_hours = int((ended - started).total_seconds() // 3600)

        # Award participation badges
        badge_count = await self._award_event_badges(event_row)

        embed = discord.Embed(
            title=f"{emoji}  {event_name.upper()} -- CONCLUDED  {emoji}",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"*{flavor}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"The event ran for **{duration_hours}** hours with a "
                f"**{event_row['server_multiplier']}x** server multiplier.\n\n"
                f"🏅 **{badge_count}** participants earned an exclusive event badge.\n\n"
                f"Normal rules have been restored. Until next time."
            ),
            color=EMBED_COLOR_ACCENT,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="The Circle remembers what you did.")

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning("Missing permissions to post mega event summary in #general.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MegaEvents(bot))
