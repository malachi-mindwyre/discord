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
    GIVE_MIN,
    GIVE_MAX_DAILY,
    GIVE_TAX_RATE,
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


    @commands.command(name="give", aliases=["transfer", "send"])
    async def give_cmd(self, ctx: commands.Context, target: discord.Member = None, amount: int = 0):
        """Give coins to another member. 10% tax applies."""
        if not target or target.bot or target.id == ctx.author.id:
            await ctx.send(f"⚫ Usage: `!give @user <amount>` (min {GIVE_MIN}, max {GIVE_MAX_DAILY}/day, 10% tax)")
            return

        if amount < GIVE_MIN:
            await ctx.send(f"⚫ Minimum transfer is **{GIVE_MIN}** {ECONOMY_CURRENCY_EMOJI}.")
            return

        # Check daily limit
        today = datetime.utcnow().strftime("%Y-%m-%d")
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM coin_transfers WHERE sender_id = ? AND transferred_at LIKE ?",
                (ctx.author.id, f"{today}%"),
            )
            row = await cursor.fetchone()
            today_total = row[0] if row else 0

        if today_total + amount > GIVE_MAX_DAILY:
            remaining = GIVE_MAX_DAILY - today_total
            await ctx.send(
                f"⚫ Daily transfer limit is **{GIVE_MAX_DAILY}** {ECONOMY_CURRENCY_EMOJI}. "
                f"You can still give **{max(0, remaining)}** today."
            )
            return

        # Calculate tax
        tax = max(1, int(amount * GIVE_TAX_RATE))
        net = amount - tax

        # Deduct from sender
        success = await self._spend_coins(ctx.author.id, amount)
        if not success:
            balance = await self.get_balance(ctx.author.id)
            await ctx.send(
                f"⚫ Not enough coins. You have **{balance:,}** {ECONOMY_CURRENCY_EMOJI}, "
                f"need **{amount:,}**."
            )
            return

        # Credit to receiver
        await self._add_coins(target.id, net)

        # Log transfer
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO coin_transfers (sender_id, receiver_id, amount, tax, transferred_at) VALUES (?, ?, ?, ?, ?)",
                (ctx.author.id, target.id, amount, tax, datetime.utcnow().isoformat()),
            )
            await db.commit()

        embed = discord.Embed(
            title=f"{ECONOMY_CURRENCY_EMOJI} TRANSFER COMPLETE",
            description=(
                f"{ctx.author.mention} → {target.mention}\n\n"
                f"💰 Sent: **{amount:,}** {ECONOMY_CURRENCY_EMOJI}\n"
                f"📉 Tax (10%): **{tax:,}** {ECONOMY_CURRENCY_EMOJI}\n"
                f"✅ Received: **{net:,}** {ECONOMY_CURRENCY_EMOJI}"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
