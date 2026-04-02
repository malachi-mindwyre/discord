"""
The Circle — Daily Login Rewards Cog
Escalating daily rewards: coins, mystery boxes, badges.
Miss a day = reset.
"""

from __future__ import annotations

from datetime import datetime, date, timedelta

import aiosqlite
import discord
from discord.ext import commands

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    ECONOMY_CURRENCY_EMOJI,
    ECONOMY_CURRENCY_NAME,
    LOGIN_REWARD_SCHEDULE,
)
from database import DB_PATH, unlock_achievement


class DailyRewards(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="daily", aliases=["claim", "login"])
    async def daily_cmd(self, ctx: commands.Context):
        """Claim your daily login reward."""
        user_id = ctx.author.id
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT current_day, last_claim_date FROM login_rewards WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()

            if row:
                current_day, last_claim = row

                if last_claim == today:
                    await ctx.send(f"⚫ You already claimed today's reward! Come back tomorrow.")
                    return

                if last_claim == yesterday:
                    # Continue streak
                    new_day = current_day + 1
                else:
                    # Streak broken — reset
                    new_day = 1

                await db.execute(
                    "UPDATE login_rewards SET current_day = ?, last_claim_date = ? WHERE user_id = ?",
                    (new_day, today, user_id),
                )
            else:
                new_day = 1
                await db.execute(
                    "INSERT INTO login_rewards (user_id, current_day, last_claim_date) VALUES (?, 1, ?)",
                    (user_id, today),
                )

            await db.commit()

        # Find reward for this day
        reward = self._get_reward(new_day)

        # Award coins
        if reward["coins"] > 0:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """INSERT INTO economy (user_id, coins, total_earned)
                       VALUES (?, ?, ?)
                       ON CONFLICT(user_id) DO UPDATE SET
                       coins = coins + ?, total_earned = total_earned + ?""",
                    (user_id, reward["coins"], reward["coins"], reward["coins"], reward["coins"]),
                )
                await db.commit()

        # Special milestones
        extra_text = ""
        if new_day == 30:
            await unlock_achievement(user_id, "login_30")
            extra_text = "\n🏅 **Badge unlocked: Dedicated (30-day login streak)!**"

        # Build response
        embed = discord.Embed(
            title=f"📅 DAILY REWARD — DAY {new_day}",
            description=(
                f"🎁 You earned: **{reward['label']}**\n"
                f"{extra_text}\n"
            ),
            color=EMBED_COLOR_ACCENT,
        )

        # Show upcoming rewards
        upcoming = self._get_upcoming_preview(new_day)
        if upcoming:
            embed.add_field(name="📆 COMING UP", value=upcoming, inline=False)

        embed.set_footer(text="Claim every day to keep your streak! Miss a day = reset to Day 1")
        await ctx.send(embed=embed)

    def _get_reward(self, day: int) -> dict:
        """Get the reward for a specific day."""
        # Check exact day match first
        if day in LOGIN_REWARD_SCHEDULE:
            return LOGIN_REWARD_SCHEDULE[day]

        # For days not in schedule, give a base reward that scales
        base_coins = min(10 + (day * 2), 100)
        return {"coins": base_coins, "label": f"{base_coins} {ECONOMY_CURRENCY_EMOJI}"}

    def _get_upcoming_preview(self, current_day: int) -> str:
        """Show next few reward milestones."""
        lines = []
        for day in sorted(LOGIN_REWARD_SCHEDULE.keys()):
            if day > current_day:
                lines.append(f"Day {day}: {LOGIN_REWARD_SCHEDULE[day]['label']}")
                if len(lines) >= 3:
                    break
        return "\n".join(lines) if lines else ""

    @commands.command(name="loginstreak")
    async def login_streak_cmd(self, ctx: commands.Context):
        """Check your daily login streak."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT current_day, last_claim_date FROM login_rewards WHERE user_id = ?",
                (ctx.author.id,),
            )
            row = await cursor.fetchone()

        if not row:
            await ctx.send(f"⚫ You haven't claimed a daily reward yet. Use `!daily` to start!")
            return

        current_day, last_claim = row
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        if last_claim not in (today, yesterday):
            status = "❌ **Streak broken!** Claim `!daily` to restart at Day 1."
        elif last_claim == today:
            status = "✅ **Claimed today!** Come back tomorrow."
        else:
            status = "⚠️ **Claim today or lose your streak!** Use `!daily`"

        embed = discord.Embed(
            title="📅 LOGIN STREAK",
            description=(
                f"**Day {current_day}** of daily rewards\n\n"
                f"{status}"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(DailyRewards(bot))
