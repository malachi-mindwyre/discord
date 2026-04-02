"""
The Circle — Oracle Cog
Evening prediction ritual. Keeper's Oracle speaks once daily at 9 PM UTC
with a cryptic prediction about what tomorrow holds.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, date, timedelta, timezone, time

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import EMBED_COLOR_PRIMARY, EMBED_COLOR_ACCENT, ORACLE_PREDICTIONS, GUILD_ID
from database import DB_PATH

logger = logging.getLogger("circle.oracle")

ORACLE_HOUR_UTC = 21  # 9 PM UTC


# ─── Database Helpers ────────────────────────────────────────────────────────

async def _ensure_table():
    """Create oracle_log table if it doesn't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS oracle_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction TEXT NOT NULL,
                posted_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def _get_recent_predictions(days: int = 7) -> list[str]:
    """Get predictions posted in the last N days to avoid repeats."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT prediction FROM oracle_log WHERE posted_at > ?",
            (cutoff,),
        )
        return [row[0] for row in await cursor.fetchall()]


async def _log_prediction(prediction: str):
    """Log a prediction to the oracle_log table."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO oracle_log (prediction, posted_at) VALUES (?, ?)",
            (prediction, now),
        )
        await db.commit()


async def _get_todays_prediction() -> str | None:
    """Return today's prediction if one was already posted."""
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT prediction FROM oracle_log WHERE date(posted_at) = ? ORDER BY id DESC LIMIT 1",
            (today,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


# ─── The Cog ────────────────────────────────────────────────────────────────

class Oracle(commands.Cog):
    """The Oracle speaks each evening with a cryptic prediction."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await _ensure_table()
        self.oracle_loop.start()
        logger.info("✓ Oracle cog loaded — evening ritual scheduled")

    def cog_unload(self):
        self.oracle_loop.cancel()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_general(self) -> discord.TextChannel | None:
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return None
        return discord.utils.get(guild.text_channels, name="general")

    def _pick_prediction(self, recent: list[str]) -> str:
        """Pick a prediction not used recently."""
        available = [p for p in ORACLE_PREDICTIONS if p not in recent]
        if not available:
            available = list(ORACLE_PREDICTIONS)
        return random.choice(available)

    # ── Background Task ──────────────────────────────────────────────────

    @tasks.loop(hours=1)
    async def oracle_loop(self):
        """Check if it's time for the Oracle to speak."""
        now = datetime.now(timezone.utc)

        # Only fire at the Oracle hour
        if now.hour != ORACLE_HOUR_UTC:
            return

        # Check if already posted today
        today_pred = await _get_todays_prediction()
        if today_pred:
            return

        # Pick and post prediction
        recent = await _get_recent_predictions(days=7)
        prediction = self._pick_prediction(recent)

        channel = self._get_general()
        if not channel:
            logger.warning("Oracle: #general not found")
            return

        embed = discord.Embed(
            title="🔮 THE ORACLE SPEAKS",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"*{prediction}*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"The Oracle has spoken. Interpret as you will.\n"
                f"*Tomorrow will reveal the truth.*"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="The Circle • The Oracle sees what others cannot")

        try:
            await channel.send(embed=embed)
            await _log_prediction(prediction)
            logger.info("Oracle posted: %s", prediction[:50])
        except discord.HTTPException:
            logger.warning("Oracle: failed to post prediction")

    @oracle_loop.before_loop
    async def before_oracle(self):
        await self.bot.wait_until_ready()

    # ── Command ──────────────────────────────────────────────────────────

    @commands.command(name="oracle")
    async def oracle_cmd(self, ctx: commands.Context):
        """View today's Oracle prediction, or wait for dusk."""
        prediction = await _get_todays_prediction()

        if prediction:
            embed = discord.Embed(
                title="🔮 TODAY'S ORACLE",
                description=(
                    f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"*{prediction}*\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=EMBED_COLOR_PRIMARY,
            )
            embed.set_footer(text="The Circle • The Oracle speaks at dusk")
        else:
            embed = discord.Embed(
                title="🔮 THE ORACLE IS SILENT",
                description=(
                    "The Oracle speaks at **dusk** (9 PM UTC).\n\n"
                    "Return then to hear what tomorrow holds.\n\n"
                    "*Patience is its own reward... but not a very good one.*"
                ),
                color=EMBED_COLOR_PRIMARY,
            )
            embed.set_footer(text="The Circle • The Oracle sees what others cannot")

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Oracle(bot))
