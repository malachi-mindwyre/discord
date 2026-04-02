"""
The Circle — Streaks Cog
Tracks daily streaks. Consecutive days active earn bonus multipliers.
Integrates with scoring handler via bot-level streak data.
"""

from __future__ import annotations

import discord
from discord.ext import commands

from config import STREAK_BONUS_MULTIPLIER, EMBED_COLOR_ACCENT, EXCLUDED_CHANNELS
from database import update_streak, get_streak, get_top_streaks


def get_streak_multiplier(streak_length: int) -> float:
    """Get the bonus multiplier for a given streak length."""
    best = 1.0
    for threshold, multiplier in sorted(STREAK_BONUS_MULTIPLIER.items()):
        if streak_length >= threshold:
            best = multiplier
        else:
            break
    return best


def get_next_streak_milestone(current: int) -> int | None:
    """Get the next streak milestone."""
    for threshold in sorted(STREAK_BONUS_MULTIPLIER.keys()):
        if current < threshold:
            return threshold
    return None


class Streaks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Cache today's streak updates to avoid repeated DB calls
        self._today_updated: set[int] = set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Update streak on first message of the day."""
        if message.author.bot or not message.guild:
            return
        if message.channel.name in EXCLUDED_CHANNELS:
            return

        user_id = message.author.id
        if user_id in self._today_updated:
            return

        streak_info = await update_streak(user_id)
        self._today_updated.add(user_id)

        if not streak_info["streak_changed"]:
            return

        streak = streak_info["current_streak"]

        # Announce streak milestones
        if streak in STREAK_BONUS_MULTIPLIER:
            mult = STREAK_BONUS_MULTIPLIER[streak]
            bonus_pct = int((mult - 1) * 100)

            embed = discord.Embed(
                title="🔥 STREAK MILESTONE",
                description=(
                    f"{message.author.mention} just hit a **{streak}-day streak!**\n\n"
                    f"All points now boosted by **{bonus_pct}%** 🚀\n"
                    f"*Don't break the chain.*"
                ),
                color=EMBED_COLOR_ACCENT,
            )
            try:
                await message.channel.send(embed=embed)
            except discord.HTTPException:
                pass

    @commands.command(name="streak")
    async def streak_cmd(self, ctx: commands.Context):
        """Check your current streak."""
        streak_data = await get_streak(ctx.author.id)
        current = streak_data["current_streak"]
        longest = streak_data["longest_streak"]
        multiplier = get_streak_multiplier(current)
        next_ms = get_next_streak_milestone(current)

        bonus_pct = int((multiplier - 1) * 100)

        embed = discord.Embed(
            title=f"🔥 {ctx.author.display_name}'s Streak",
            color=EMBED_COLOR_ACCENT,
        )
        embed.add_field(name="Current Streak", value=f"**{current} days**", inline=True)
        embed.add_field(name="Longest Streak", value=f"**{longest} days**", inline=True)
        embed.add_field(
            name="Bonus",
            value=f"**+{bonus_pct}%** on all points" if bonus_pct > 0 else "None yet — keep going!",
            inline=True,
        )
        if next_ms:
            days_to_go = next_ms - current
            next_bonus = int((STREAK_BONUS_MULTIPLIER[next_ms] - 1) * 100)
            embed.add_field(
                name="Next Milestone",
                value=f"**{next_ms} days** (+{next_bonus}% bonus) — {days_to_go} days to go",
                inline=False,
            )
        else:
            embed.add_field(name="Status", value="**MAX STREAK BONUS** 💀 You're built different.", inline=False)

        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="streaks")
    async def streaks_leaderboard(self, ctx: commands.Context):
        """Show top streaks."""
        top = await get_top_streaks(10)
        if not top:
            await ctx.send("⚫ No active streaks yet. Be the first.")
            return

        lines = []
        for i, s in enumerate(top):
            mult = get_streak_multiplier(s["current_streak"])
            bonus = int((mult - 1) * 100)
            bonus_str = f" (+{bonus}%)" if bonus > 0 else ""
            lines.append(f"#{i+1} **{s['username']}** — {s['current_streak']} days{bonus_str}")

        embed = discord.Embed(
            title="🔥 STREAK LEADERBOARD",
            description="\n".join(lines),
            color=EMBED_COLOR_ACCENT,
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Streaks(bot))
