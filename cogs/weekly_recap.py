"""
The Circle — Weekly Recap Cog
Posts a highlights embed every Sunday.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks

from config import (
    WEEKLY_RECAP_DAY,
    WEEKLY_RECAP_HOUR,
    WEEKLY_RECAP_CHANNEL,
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
)
from database import get_weekly_stats, get_top_streaks


class WeeklyRecap(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.post_weekly_recap.start()

    def cog_unload(self):
        self.post_weekly_recap.cancel()

    @tasks.loop(hours=168)  # Weekly
    async def post_weekly_recap(self):
        """Post weekly recap embed."""
        stats = await get_weekly_stats()
        top_streaks = await get_top_streaks(3)

        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name=WEEKLY_RECAP_CHANNEL)
            if not channel:
                continue

            embed = discord.Embed(
                title="📊 WEEKLY RECAP — THE CIRCLE",
                description="The Circle never sleeps. Here's what happened this week.\n\n━━━━━━━━━━━━━━━━━━━━━",
                color=EMBED_COLOR_ACCENT,
            )

            # Overall stats
            embed.add_field(
                name="📈 THIS WEEK",
                value=(
                    f"💬 **{stats['total_messages']:,}** messages sent\n"
                    f"👥 **{stats['active_users']}** active members\n"
                    f"❤️ **{stats['total_reactions']:,}** reactions given"
                ),
                inline=False,
            )

            # Top poster
            if stats["top_poster"]:
                tp = stats["top_poster"]
                embed.add_field(
                    name="👑 TOP POSTER",
                    value=f"**{tp['username']}** — {tp['week_points']:,.0f} pts ({tp['msg_count']} msgs)",
                    inline=True,
                )

            # Most social
            if stats["most_social"]:
                ms = stats["most_social"]
                embed.add_field(
                    name="🗣️ MOST SOCIAL",
                    value=f"**{ms['username']}** — {ms['reply_count']} replies",
                    inline=True,
                )

            # Biggest climber
            if stats["biggest_climber"]:
                bc = stats["biggest_climber"]
                embed.add_field(
                    name="🚀 BIGGEST CLIMBER",
                    value=f"**{bc['username']}** — gained {bc['tiers_gained']} rank(s)",
                    inline=True,
                )

            # Top streaks
            if top_streaks:
                streak_lines = []
                for i, s in enumerate(top_streaks):
                    streak_lines.append(f"{'🥇🥈🥉'[i] if i < 3 else '#'+str(i+1)} **{s['username']}** — {s['current_streak']} days")
                embed.add_field(
                    name="🔥 HOTTEST STREAKS",
                    value="\n".join(streak_lines),
                    inline=False,
                )

            # Fun stat
            if stats["top_poster"] and stats["total_messages"] > 0:
                msgs_per_person = stats["total_messages"] / max(stats["active_users"], 1)
                embed.add_field(
                    name="📱 FUN STAT",
                    value=f"Average member sent **{msgs_per_person:.0f}** messages this week.",
                    inline=False,
                )

            embed.set_footer(text="See you next Sunday. Keep climbing. 🏔️")

            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

    @post_weekly_recap.before_loop
    async def before_recap(self):
        """Wait until the target day and hour."""
        await self.bot.wait_until_ready()
        now = datetime.utcnow()
        # Find next target day
        days_ahead = WEEKLY_RECAP_DAY - now.weekday()
        if days_ahead < 0 or (days_ahead == 0 and now.hour >= WEEKLY_RECAP_HOUR):
            days_ahead += 7
        target = (now + timedelta(days=days_ahead)).replace(
            hour=WEEKLY_RECAP_HOUR, minute=0, second=0, microsecond=0
        )
        wait_seconds = (target - now).total_seconds()
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

    @commands.command(name="recap")
    @commands.has_permissions(administrator=True)
    async def force_recap(self, ctx: commands.Context):
        """Force post a weekly recap now. Admin only."""
        stats = await get_weekly_stats()
        if stats["total_messages"] == 0:
            await ctx.send("⚫ No data to recap yet. The Circle needs more activity.")
            return
        # Trigger the recap manually
        await self.post_weekly_recap()
        await ctx.send("⚫ Weekly recap posted.")


async def setup(bot: commands.Bot):
    await bot.add_cog(WeeklyRecap(bot))
