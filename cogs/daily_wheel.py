"""
The Circle — Daily Wheel Spin Cog
Free daily spin with animated effect. Rewards coins, XP boosts, streak freezes, or jackpot.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, date, timedelta, timezone

import aiosqlite
import discord
from discord.ext import commands

from config import (
    EMBED_COLOR_ACCENT,
    EMBED_COLOR_WARNING,
    ECONOMY_CURRENCY_EMOJI,
    WHEEL_SEGMENTS,
)
from database import DB_PATH, add_coins, award_jackpot, get_jackpot_pot


class DailyWheel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Ensure required tables exist."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS daily_spins (
                    user_id INTEGER PRIMARY KEY,
                    last_spin_date TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS active_boosts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    boost_type TEXT NOT NULL,
                    multiplier REAL NOT NULL DEFAULT 2.0,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS streak_freezes (
                    user_id INTEGER PRIMARY KEY,
                    tokens_held INTEGER NOT NULL DEFAULT 0
                );
            """)
            await db.commit()

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _pick_segment() -> dict:
        """Weighted random selection from wheel segments."""
        population = WHEEL_SEGMENTS
        weights = [s["weight"] for s in population]
        return random.choices(population, weights=weights, k=1)[0]

    @staticmethod
    def _random_label() -> str:
        """Pick a random segment label for the animation tease."""
        return random.choice(WHEEL_SEGMENTS)["label"]

    @staticmethod
    def _spinning_embed(tick: int) -> discord.Embed:
        """Build an animation frame embed."""
        dots = "." * ((tick % 3) + 1)
        arrows = " | ".join(DailyWheel._random_label() for _ in range(3))
        em = discord.Embed(
            description=(
                f"```\n"
                f"  >>> {arrows} <<<\n"
                f"```\n"
                f"**The wheel turns{dots}**"
            ),
            color=EMBED_COLOR_WARNING,
        )
        em.set_author(name="DAILY WHEEL SPIN")
        return em

    @staticmethod
    def _result_embed(
        user: discord.Member, segment: dict, extra: str = ""
    ) -> discord.Embed:
        """Build the final result embed."""
        label = segment["label"]
        stype = segment["type"]

        if stype == "jackpot":
            title = "JACKPOT!!!"
            desc = (
                f"The Circle's vault has shattered open.\n"
                f"{user.mention} claims the **progressive jackpot**!\n\n"
                f"{extra}"
            )
            color = 0xFFD700  # gold
        elif stype == "xp_boost_30":
            title = "XP BOOST ACTIVATED"
            desc = (
                f"{user.mention} pulled **{label}**!\n"
                f"All your XP is doubled for the next 30 minutes. Make it count."
            )
            color = EMBED_COLOR_ACCENT
        elif stype == "streak_freeze":
            title = "STREAK FREEZE TOKEN"
            desc = (
                f"{user.mention} pulled **{label}**!\n"
                f"Your streak is protected for one missed day. The Circle is merciful... this once."
            )
            color = 0x00CED1  # dark turquoise
        else:
            title = "COINS WON"
            coins = segment["coins"]
            desc = (
                f"{user.mention} pulled **{label}**!\n"
                f"**+{coins}** {ECONOMY_CURRENCY_EMOJI} added to your balance."
            )
            color = EMBED_COLOR_ACCENT

        em = discord.Embed(title=f"🎰  {title}", description=desc, color=color)
        em.set_footer(text="The wheel resets at midnight UTC. Spin again tomorrow.")
        return em

    # ── command ──────────────────────────────────────────────────────────

    @commands.command(name="spin", aliases=["wheel"])
    @commands.guild_only()
    async def spin_cmd(self, ctx: commands.Context):
        """Spin the daily wheel for a free reward."""
        user_id = ctx.author.id
        today = datetime.now(timezone.utc).date().isoformat()

        # ── daily limit check ────────────────────────────────────────────
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT last_spin_date FROM daily_spins WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()

        if row and row[0] == today:
            now_utc = datetime.now(timezone.utc)
            tomorrow = datetime.combine(
                now_utc.date() + timedelta(days=1),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            diff = tomorrow - now_utc
            hours, remainder = divmod(int(diff.total_seconds()), 3600)
            minutes = remainder // 60
            em = discord.Embed(
                title="🎰  ALREADY SPUN TODAY",
                description=(
                    f"The wheel only turns once per day, {ctx.author.mention}.\n"
                    f"Come back in **{hours}h {minutes}m**."
                ),
                color=EMBED_COLOR_WARNING,
            )
            await ctx.send(embed=em)
            return

        # ── animation ────────────────────────────────────────────────────
        msg = await ctx.send(embed=self._spinning_embed(0))
        for tick in range(1, 3):
            await asyncio.sleep(0.6)
            await msg.edit(embed=self._spinning_embed(tick))
        await asyncio.sleep(0.6)

        # ── pick result ──────────────────────────────────────────────────
        segment = self._pick_segment()
        stype = segment["type"]
        extra = ""

        # ── apply reward ─────────────────────────────────────────────────
        if stype == "coins":
            await add_coins(user_id, segment["coins"])

        elif stype == "xp_boost_30":
            expires = (
                datetime.now(timezone.utc) + timedelta(minutes=30)
            ).isoformat()
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """INSERT INTO active_boosts (user_id, boost_type, multiplier, expires_at, created_at)
                       VALUES (?, 'xp_2x', 2.0, ?, ?)""",
                    (user_id, expires, datetime.now(timezone.utc).isoformat()),
                )
                await db.commit()

        elif stype == "streak_freeze":
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """INSERT INTO streak_freezes (user_id, tokens_held)
                       VALUES (?, 1)
                       ON CONFLICT(user_id) DO UPDATE SET tokens_held = tokens_held + 1""",
                    (user_id,),
                )
                await db.commit()

        elif stype == "jackpot":
            pot = await award_jackpot(user_id)
            extra = f"**{int(pot)}** {ECONOMY_CURRENCY_EMOJI} deposited."

        # ── record spin ──────────────────────────────────────────────────
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO daily_spins (user_id, last_spin_date)
                   VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET last_spin_date = ?""",
                (user_id, today, today),
            )
            await db.commit()

        # ── show result ──────────────────────────────────────────────────
        result_em = self._result_embed(ctx.author, segment, extra=extra)
        await msg.edit(embed=result_em)


async def setup(bot: commands.Bot):
    await bot.add_cog(DailyWheel(bot))
