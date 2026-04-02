"""
The Circle — Economy Cog
Virtual currency "Circles" (🪙) tracking, earning, and spending.
"""

from __future__ import annotations

from datetime import datetime

import aiosqlite
import discord
from discord.ext import commands

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    ECONOMY_COIN_PER_MESSAGE,
    ECONOMY_CURRENCY_NAME,
    ECONOMY_CURRENCY_EMOJI,
    EXCLUDED_CHANNELS,
)
from database import DB_PATH


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Award coins for scored messages (runs alongside scoring handler)."""
        if message.author.bot or not message.guild:
            return
        if message.channel.name in EXCLUDED_CHANNELS:
            return
        # Don't award for command messages
        if message.content.startswith("!"):
            return

        await self._add_coins(message.author.id, ECONOMY_COIN_PER_MESSAGE)

    @staticmethod
    async def _add_coins(user_id: int, amount: int):
        """Add coins to a user's economy balance."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO economy (user_id, coins, total_earned)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                   coins = coins + ?, total_earned = total_earned + ?""",
                (user_id, amount, amount, amount, amount),
            )
            await db.commit()

    @staticmethod
    async def _spend_coins(user_id: int, amount: int) -> bool:
        """Spend coins. Returns True if successful, False if insufficient."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT coins FROM economy WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            if not row or row[0] < amount:
                return False

            await db.execute(
                "UPDATE economy SET coins = coins - ?, total_spent = total_spent + ? WHERE user_id = ?",
                (amount, amount, user_id),
            )
            await db.commit()
            return True

    @staticmethod
    async def get_balance(user_id: int) -> int:
        """Get a user's coin balance."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT coins FROM economy WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    @commands.command(name="balance", aliases=["bal", "coins"])
    async def balance_cmd(self, ctx: commands.Context):
        """Check your coin balance."""
        balance = await self.get_balance(ctx.author.id)
        embed = discord.Embed(
            title=f"{ECONOMY_CURRENCY_EMOJI} YOUR BALANCE",
            description=f"**{balance:,}** {ECONOMY_CURRENCY_NAME}",
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="Use !shop to see what you can buy")
        await ctx.send(embed=embed)

    @commands.command(name="richest")
    async def richest_cmd(self, ctx: commands.Context):
        """Show the richest members."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT e.user_id, e.coins, u.username FROM economy e
                   JOIN users u ON u.user_id = e.user_id
                   ORDER BY e.coins DESC LIMIT 10"""
            )
            rows = await cursor.fetchall()

        if not rows:
            await ctx.send(f"⚫ No one has earned any {ECONOMY_CURRENCY_NAME} yet.")
            return

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, row in enumerate(rows):
            prefix = medals[i] if i < 3 else f"#{i+1}"
            lines.append(f"{prefix} **{row['username']}** — {row['coins']:,} {ECONOMY_CURRENCY_EMOJI}")

        embed = discord.Embed(
            title=f"{ECONOMY_CURRENCY_EMOJI} RICHEST IN THE CIRCLE",
            description="\n".join(lines),
            color=EMBED_COLOR_ACCENT,
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
