"""
The Circle — Comeback System Cog
Handles inactive user DMs, score decay, and comeback detection.
"""

import discord
from discord.ext import commands, tasks

from config import (
    COMEBACK_DM_DAYS,
    COMEBACK_DECAY_DAYS,
    COMEBACK_DECAY_RATE,
    EMBED_COLOR_PRIMARY,
    KEEPER_COMEBACK_DM,
)
from database import get_inactive_users, apply_score_decay
from ranks import get_rank_for_score, RANK_BY_TIER


class Comeback(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track who we've already DM'd to avoid repeat messages
        self._dm_sent: set[int] = set()
        self.inactive_check.start()

    def cog_unload(self):
        self.inactive_check.cancel()

    @tasks.loop(hours=24)
    async def inactive_check(self):
        """Daily check for inactive users — DM nudges and score decay."""

        # ─── 14-day DM nudge ──────────────────────────────────────────
        dm_users = await get_inactive_users(COMEBACK_DM_DAYS)
        for user_data in dm_users:
            user_id = user_data["user_id"]
            if user_id in self._dm_sent:
                continue

            for guild in self.bot.guilds:
                member = guild.get_member(user_id)
                if member:
                    try:
                        embed = discord.Embed(
                            title="⚫ THE CIRCLE REMEMBERS",
                            description=KEEPER_COMEBACK_DM.format(username=member.display_name),
                            color=EMBED_COLOR_PRIMARY,
                        )
                        rank = RANK_BY_TIER.get(user_data["current_rank"])
                        if rank:
                            embed.add_field(
                                name="Your Rank",
                                value=f"**{rank.name}** — {user_data['total_score']:,.0f} pts",
                                inline=False,
                            )
                        embed.set_footer(text="The Circle • Return and reclaim your place")
                        await member.send(embed=embed)
                        self._dm_sent.add(user_id)
                    except (discord.HTTPException, discord.Forbidden):
                        pass
                    break

        # ─── 30-day score decay ────────────────────────────────────────
        decay_users = await get_inactive_users(COMEBACK_DECAY_DAYS)
        for user_data in decay_users:
            user_id = user_data["user_id"]
            if user_data["total_score"] > 0:
                await apply_score_decay(user_id, COMEBACK_DECAY_RATE)

    @inactive_check.before_loop
    async def before_inactive_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Comeback(bot))
