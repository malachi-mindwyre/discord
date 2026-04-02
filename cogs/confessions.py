"""
The Circle — Confessions Cog
Anonymous confession posting via DM (!confess) or slash command.
Content filtering + report system for safety.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

import aiosqlite
import discord
from discord.ext import commands

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    EMBED_COLOR_ERROR,
    CONFESSION_COOLDOWN_HOURS,
    CONFESSION_CHANNEL,
    CONFESSION_DISCUSSION_CHANNEL,
    CONFESSION_AUTO_REACTIONS,
    CONFESSION_MAX_LENGTH,
    CONFESSION_BLOCKED_PATTERNS,
    CONFESSION_REPORT_THRESHOLD,
    GUILD_ID,
)
from database import DB_PATH

logger = logging.getLogger("circle.confessions")

# Pre-compile blocked patterns for performance
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in CONFESSION_BLOCKED_PATTERNS]


def _check_content_filter(content: str) -> bool:
    """Returns True if the content is blocked by the filter."""
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(content):
            return True
    return False


async def _ensure_report_table():
    """Create confession_reports table if it doesn't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS confession_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                confession_number INTEGER NOT NULL,
                reporter_id INTEGER NOT NULL,
                reported_at TEXT NOT NULL,
                UNIQUE(confession_number, reporter_id)
            )
        """)
        await db.commit()


class Confessions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        await _ensure_report_table()

    async def _get_next_confession_number(self) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT MAX(number) FROM confessions")
            row = await cursor.fetchone()
            return (row[0] or 0) + 1

    async def _check_cooldown(self, user_id: int) -> bool:
        """Returns True if user is on cooldown."""
        cutoff = (datetime.utcnow() - timedelta(hours=CONFESSION_COOLDOWN_HOURS)).isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id FROM confessions WHERE user_id = ? AND timestamp > ?",
                (user_id, cutoff),
            )
            return await cursor.fetchone() is not None

    async def _post_confession(self, user_id: int, content: str) -> tuple[bool, str]:
        """Post a confession. Returns (success, message)."""
        # Length check
        if len(content) > CONFESSION_MAX_LENGTH:
            return False, f"Confession too long. Maximum {CONFESSION_MAX_LENGTH} characters."

        # Content filter
        if _check_content_filter(content):
            logger.warning("Confession blocked by content filter: user=%s", user_id)
            return False, "Your confession was flagged by our safety filter. Please revise and try again."

        # Check cooldown
        if await self._check_cooldown(user_id):
            return False, f"You can only confess once every {CONFESSION_COOLDOWN_HOURS} hours. Be patient."

        # Get confession number
        number = await self._get_next_confession_number()

        # Store in DB
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO confessions (user_id, content, number, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, content, number, now),
            )
            await db.commit()

        # Find the confessions channel
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return False, "Could not find The Circle."

        channel = discord.utils.get(guild.text_channels, name=CONFESSION_CHANNEL)
        if not channel:
            return False, f"#{CONFESSION_CHANNEL} channel not found."

        # Post the confession
        embed = discord.Embed(
            title=f"🔮 CONFESSION #{number}",
            description=content,
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="Anonymous • The Circle keeps your secrets • !report to flag")
        embed.timestamp = datetime.utcnow()

        try:
            msg = await channel.send(embed=embed)
            # Store the message_id for potential deletion via reports
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE confessions SET message_id = ? WHERE number = ?",
                    (msg.id, number),
                )
                await db.commit()

            # Add auto-reactions
            for emoji in CONFESSION_AUTO_REACTIONS:
                try:
                    await msg.add_reaction(emoji)
                except discord.HTTPException:
                    pass

            # Post discussion prompt
            discuss_ch = discord.utils.get(guild.text_channels, name=CONFESSION_DISCUSSION_CHANNEL)
            if discuss_ch:
                try:
                    await discuss_ch.send(
                        f"💭 **Confession #{number}** just dropped in {channel.mention}. Thoughts?"
                    )
                except discord.HTTPException:
                    pass

        except discord.HTTPException:
            return False, "Failed to post confession."

        return True, f"Your confession has been posted as **#{number}**. The Circle keeps your secret. 🔮"

    @commands.command(name="confess")
    async def confess_cmd(self, ctx: commands.Context, *, content: str = None):
        """Submit an anonymous confession. Use in DMs or any channel."""
        if not content:
            await ctx.send("⚫ Usage: `!confess <your confession>`\nDM Keeper for full anonymity.")
            return

        # If used in a guild channel, delete the original message for privacy
        if ctx.guild:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass

        success, response = await self._post_confession(ctx.author.id, content)

        # Always respond in DM for privacy
        try:
            await ctx.author.send(f"⚫ {response}")
        except (discord.HTTPException, discord.Forbidden):
            if ctx.guild:
                # Can't DM, so whisper in channel (ephemeral-like)
                try:
                    await ctx.send(f"⚫ {response}", delete_after=10)
                except discord.HTTPException:
                    pass

    @commands.command(name="report")
    async def report_cmd(self, ctx: commands.Context, confession_number: int = None):
        """Report a confession for inappropriate content."""
        if confession_number is None:
            await ctx.send("⚫ Usage: `!report <confession_number>` — Flag a confession for review.")
            return

        user_id = ctx.author.id

        async with aiosqlite.connect(DB_PATH) as db:
            # Check confession exists
            cursor = await db.execute(
                "SELECT id, number FROM confessions WHERE number = ?",
                (confession_number,),
            )
            confession = await cursor.fetchone()
            if not confession:
                await ctx.send(f"❌ Confession #{confession_number} not found.")
                return

            # Check if already reported by this user
            cursor = await db.execute(
                "SELECT id FROM confession_reports WHERE confession_number = ? AND reporter_id = ?",
                (confession_number, user_id),
            )
            if await cursor.fetchone():
                await ctx.send("⚫ You've already reported this confession.")
                return

            # Log the report
            now = datetime.utcnow().isoformat()
            await db.execute(
                "INSERT INTO confession_reports (confession_number, reporter_id, reported_at) VALUES (?, ?, ?)",
                (confession_number, user_id, now),
            )
            await db.commit()

            # Count total reports for this confession
            cursor = await db.execute(
                "SELECT COUNT(*) FROM confession_reports WHERE confession_number = ?",
                (confession_number,),
            )
            report_count = (await cursor.fetchone())[0]

        await ctx.send(f"⚫ Confession #{confession_number} reported. Thank you for keeping The Circle safe.", delete_after=10)
        logger.info("Confession #%d reported by %s (total reports: %d)", confession_number, user_id, report_count)

        # Auto-delete if threshold reached
        if report_count >= CONFESSION_REPORT_THRESHOLD:
            await self._auto_delete_confession(confession_number)

    async def _auto_delete_confession(self, confession_number: int):
        """Delete a confession from #confessions after enough reports."""
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return

        channel = discord.utils.get(guild.text_channels, name=CONFESSION_CHANNEL)
        if not channel:
            return

        # Try to find and delete the message
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT message_id FROM confessions WHERE number = ?",
                (confession_number,),
            )
            row = await cursor.fetchone()
            message_id = row[0] if row else None

        if message_id:
            try:
                msg = await channel.fetch_message(message_id)
                await msg.delete()
                logger.info("Confession #%d auto-deleted after %d reports", confession_number, CONFESSION_REPORT_THRESHOLD)
            except (discord.NotFound, discord.HTTPException):
                pass

        # Post removal notice
        try:
            embed = discord.Embed(
                title="🚫 CONFESSION REMOVED",
                description=f"Confession **#{confession_number}** was removed after community reports.",
                color=EMBED_COLOR_ERROR,
            )
            embed.set_footer(text="The Circle • Community safety comes first")
            await channel.send(embed=embed, delete_after=3600)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle DM confessions (messages starting with !confess in DMs)."""
        if message.guild or message.author.bot:
            return


async def setup(bot: commands.Bot):
    await bot.add_cog(Confessions(bot))
