"""
The Circle -- Time Capsules Cog
Send a message to your future self. Sealed for 90 days, then revealed
with a nostalgic flourish. The Circle preserves what was written.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import EMBED_COLOR_PRIMARY, EMBED_COLOR_ACCENT, GUILD_ID
from database import DB_PATH

logger = logging.getLogger("circle.time_capsules")

CAPSULE_DURATION_DAYS = 90
MAX_CAPSULES_PER_USER = 3
MAX_MESSAGE_LENGTH = 500
CHECK_INTERVAL_HOURS = 6


# --- Database Helpers --------------------------------------------------------

async def _ensure_table():
    """Create time_capsules table if it doesn't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS time_capsules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                reveal_at TEXT NOT NULL,
                revealed INTEGER DEFAULT 0
            )
        """)
        await db.commit()


async def _create_capsule(user_id: int, message: str) -> dict:
    """Insert a new time capsule. Returns the capsule row as a dict."""
    now = datetime.now(timezone.utc)
    reveal_at = now + timedelta(days=CAPSULE_DURATION_DAYS)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO time_capsules (user_id, message, submitted_at, reveal_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, message, now.isoformat(), reveal_at.isoformat()),
        )
        await db.commit()
        return {
            "id": cursor.lastrowid,
            "submitted_at": now,
            "reveal_at": reveal_at,
        }


async def _active_capsule_count(user_id: int) -> int:
    """Return how many unrevealed capsules a user has."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM time_capsules WHERE user_id = ? AND revealed = 0",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def _get_active_capsules(user_id: int) -> list[tuple]:
    """Return all unrevealed capsules for a user: (id, submitted_at, reveal_at)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, submitted_at, reveal_at FROM time_capsules "
            "WHERE user_id = ? AND revealed = 0 ORDER BY reveal_at ASC",
            (user_id,),
        )
        return await cursor.fetchall()


async def _get_due_capsules() -> list[tuple]:
    """Return capsules ready to be revealed: (id, user_id, message, submitted_at)."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, message, submitted_at FROM time_capsules "
            "WHERE reveal_at <= ? AND revealed = 0",
            (now,),
        )
        return await cursor.fetchall()


async def _mark_revealed(capsule_id: int):
    """Mark a capsule as revealed."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE time_capsules SET revealed = 1 WHERE id = ?",
            (capsule_id,),
        )
        await db.commit()


# --- Helpers -----------------------------------------------------------------

def _days_ago_text(submitted_at_iso: str) -> str:
    """Return a human-readable string for how long ago the capsule was created."""
    created = datetime.fromisoformat(submitted_at_iso)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - created
    days = delta.days
    if days < 1:
        return "earlier today"
    if days == 1:
        return "1 day ago"
    if days < 30:
        return f"{days} days ago"
    months = days // 30
    remaining = days % 30
    if months == 1 and remaining == 0:
        return "1 month ago"
    if remaining == 0:
        return f"{months} months ago"
    return f"{months} month{'s' if months != 1 else ''}, {remaining} day{'s' if remaining != 1 else ''} ago"


def _days_until_text(reveal_at_iso: str) -> str:
    """Return a human-readable string for how long until reveal."""
    reveal = datetime.fromisoformat(reveal_at_iso)
    if reveal.tzinfo is None:
        reveal = reveal.replace(tzinfo=timezone.utc)
    delta = reveal - datetime.now(timezone.utc)
    days = max(delta.days, 0)
    if days == 0:
        return "any moment now"
    if days == 1:
        return "1 day"
    if days < 30:
        return f"{days} days"
    months = days // 30
    remaining = days % 30
    if remaining == 0:
        return f"{months} month{'s' if months != 1 else ''}"
    return f"{months} month{'s' if months != 1 else ''}, {remaining} day{'s' if remaining != 1 else ''}"


# --- The Cog -----------------------------------------------------------------

class TimeCapsules(commands.Cog):
    """Seal a message to your future self. The Circle preserves what was written."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._task_started = False

    async def cog_load(self):
        await _ensure_table()
        if not self._task_started:
            self._task_started = True
            self.reveal_loop.start()

    async def cog_unload(self):
        if self.reveal_loop.is_running():
            self.reveal_loop.cancel()
        self._task_started = False

    # --- Background Task -----------------------------------------------------

    @tasks.loop(hours=CHECK_INTERVAL_HOURS)
    async def reveal_loop(self):
        """Check for capsules due to be revealed."""
        try:
            due = await _get_due_capsules()
            if not due:
                return

            guild = self.bot.get_guild(GUILD_ID)
            if not guild:
                logger.warning("TimeCapsules: guild %s not found", GUILD_ID)
                return

            # Find #general for announcements
            general_channel = discord.utils.get(guild.text_channels, name="general")

            for capsule_id, user_id, message, submitted_at in due:
                member = guild.get_member(user_id)
                if not member:
                    # User left the server -- still mark revealed
                    await _mark_revealed(capsule_id)
                    logger.info("Capsule %d: user %d no longer in server, marked revealed", capsule_id, user_id)
                    continue

                ago_text = _days_ago_text(submitted_at)

                # DM the user
                dm_embed = discord.Embed(
                    title="\U0001f4dc TIME CAPSULE OPENED",
                    description=(
                        "A message from your past self awaits...\n"
                        f"Written **{ago_text}**, sealed by The Circle.\n\n"
                        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                        f"\u201c{message}\u201d\n"
                        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
                        "*The Circle preserves what was written. Do these words still hold true?*"
                    ),
                    color=EMBED_COLOR_ACCENT,
                )
                dm_embed.set_footer(text="The Circle remembers.")

                try:
                    await member.send(embed=dm_embed)
                except discord.Forbidden:
                    logger.info("Capsule %d: cannot DM user %d (DMs disabled)", capsule_id, user_id)

                # Announce in #general
                if general_channel:
                    announce_embed = discord.Embed(
                        description=(
                            f"\U0001f4dc A time capsule has been opened... "
                            f"**{member.display_name}** receives a message from {ago_text}. "
                            f"The Circle reveals what was sealed."
                        ),
                        color=EMBED_COLOR_PRIMARY,
                    )
                    try:
                        await general_channel.send(embed=announce_embed)
                    except discord.Forbidden:
                        logger.warning("TimeCapsules: cannot send to #general")

                await _mark_revealed(capsule_id)
                logger.info("Capsule %d revealed for user %d", capsule_id, user_id)

                # Small delay between reveals to avoid rate limits
                await asyncio.sleep(2)

        except Exception:
            logger.exception("TimeCapsules: error in reveal_loop")

    @reveal_loop.before_loop
    async def before_reveal_loop(self):
        await self.bot.wait_until_ready()

    # --- Commands ------------------------------------------------------------

    @commands.command(name="timecapsule", aliases=["tc"])
    async def timecapsule(self, ctx: commands.Context, *, message: str):
        """Seal a message to your future self. Revealed in 90 days.

        Usage: !timecapsule <message>
        """
        if len(message) > MAX_MESSAGE_LENGTH:
            embed = discord.Embed(
                description=(
                    f"\u274c Your message is too long ({len(message)} chars). "
                    f"Max **{MAX_MESSAGE_LENGTH}** characters. "
                    "Distill your thoughts, traveler."
                ),
                color=EMBED_COLOR_ACCENT,
            )
            await ctx.send(embed=embed)
            return

        count = await _active_capsule_count(ctx.author.id)
        if count >= MAX_CAPSULES_PER_USER:
            embed = discord.Embed(
                description=(
                    f"\u274c You already have **{count}** sealed capsules. "
                    f"The Circle allows a maximum of **{MAX_CAPSULES_PER_USER}** at a time. "
                    "Patience... one will open soon."
                ),
                color=EMBED_COLOR_ACCENT,
            )
            await ctx.send(embed=embed)
            return

        capsule = await _create_capsule(ctx.author.id, message)
        reveal_date = capsule["reveal_at"].strftime("%B %d, %Y")

        embed = discord.Embed(
            title="\U0001f512 TIME CAPSULE SEALED",
            description=(
                "The Circle has accepted your message and sealed it in time.\n\n"
                f"\U0001f5d3\ufe0f **Reveals on:** {reveal_date}\n"
                f"\U0001f4e6 **Active capsules:** {count + 1}/{MAX_CAPSULES_PER_USER}\n\n"
                "*Your words are now beyond your reach. "
                "In 90 days, they will find you again.*"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="The Circle preserves what was written.")
        await ctx.send(embed=embed)

        # Delete the original command message so the capsule contents stay secret
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        logger.info(
            "User %s (%d) sealed time capsule #%d, reveals %s",
            ctx.author, ctx.author.id, capsule["id"], reveal_date,
        )

    @commands.command(name="capsules")
    async def capsules(self, ctx: commands.Context):
        """View your active (unrevealed) time capsules.

        Usage: !capsules
        """
        rows = await _get_active_capsules(ctx.author.id)

        if not rows:
            embed = discord.Embed(
                description=(
                    "You have no sealed time capsules.\n"
                    "Use `!timecapsule <message>` to send a message to your future self."
                ),
                color=EMBED_COLOR_PRIMARY,
            )
            await ctx.send(embed=embed)
            return

        lines: list[str] = []
        for i, (capsule_id, submitted_at, reveal_at) in enumerate(rows, 1):
            until = _days_until_text(reveal_at)
            created_date = datetime.fromisoformat(submitted_at).strftime("%b %d, %Y")
            lines.append(f"**#{i}** \u2014 Sealed {created_date} \u2022 Opens in **{until}**")

        embed = discord.Embed(
            title=f"\U0001f4e6 YOUR TIME CAPSULES ({len(rows)}/{MAX_CAPSULES_PER_USER})",
            description="\n".join(lines) + (
                "\n\n*The Circle holds your words safe. When the time comes, they will return.*"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="The Circle preserves what was written.")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(TimeCapsules(bot))
