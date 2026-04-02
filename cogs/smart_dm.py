"""
The Circle — Smart Re-engagement DMs Cog
Personalized DMs referencing user's top channels and friends.
Max 1 per week. Tiered by days inactive.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    SMART_DM_MAX_PER_WEEK,
    SMART_DM_TIERS,
)
from database import DB_PATH, get_inactive_users
from ranks import RANK_BY_TIER, get_rank_for_score


class SmartDM(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dm_check.start()

    def cog_unload(self):
        self.dm_check.cancel()

    @tasks.loop(hours=12)
    async def dm_check(self):
        """Check for inactive users and send personalized DMs."""
        now = datetime.utcnow()

        # Process each tier from longest inactive to shortest
        for days_threshold in sorted(SMART_DM_TIERS.keys(), reverse=True):
            inactive_users = await get_inactive_users(days_threshold)

            for user_data in inactive_users:
                user_id = user_data["user_id"]

                # Check if we already sent a DM recently
                week_ago = (now - timedelta(days=7)).isoformat()
                async with aiosqlite.connect(DB_PATH) as db:
                    cursor = await db.execute(
                        "SELECT id FROM smart_dm_log WHERE user_id = ? AND sent_at > ?",
                        (user_id, week_ago),
                    )
                    if await cursor.fetchone():
                        continue  # Already DM'd this week

                # Find the member in a guild
                member = None
                guild = None
                for g in self.bot.guilds:
                    m = g.get_member(user_id)
                    if m:
                        member = m
                        guild = g
                        break

                if not member:
                    continue

                # Build personalized message
                template = SMART_DM_TIERS[days_threshold]
                message_text = await self._personalize_message(template, user_data, user_id)

                # Build embed
                embed = discord.Embed(
                    title="⚫ THE CIRCLE REMEMBERS",
                    description=message_text,
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

                try:
                    await member.send(embed=embed)

                    # Log the DM
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute(
                            "INSERT INTO smart_dm_log (user_id, dm_type, sent_at) VALUES (?, ?, ?)",
                            (user_id, f"inactive_{days_threshold}d", now.isoformat()),
                        )
                        await db.commit()
                except (discord.HTTPException, discord.Forbidden):
                    pass  # DMs disabled

    async def _personalize_message(self, template: str, user_data: dict, user_id: int) -> str:
        """Fill in template placeholders with user-specific data."""
        # Get user's top channel
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT c.channel_id, COUNT(*) as cnt FROM messages c
                   WHERE c.user_id = ? GROUP BY c.channel_id ORDER BY cnt DESC LIMIT 1""",
                (user_id,),
            )
            top_ch = await cursor.fetchone()

        top_channel = "general"  # fallback
        if top_ch:
            for guild in self.bot.guilds:
                ch = guild.get_channel(top_ch[0])
                if ch:
                    top_channel = ch.name
                    break

        # Get streak
        from database import get_streak
        streak_data = await get_streak(user_id)

        # Get rank info
        rank = RANK_BY_TIER.get(user_data["current_rank"])
        rank_name = rank.name if rank else "Unknown"

        # Calculate what rank they might have decayed to
        old_rank = rank_name
        new_rank = rank_name  # In practice, decay may have changed this

        return template.format(
            streak=streak_data["current_streak"],
            top_channel=top_channel,
            old_rank=old_rank,
            new_rank=new_rank,
            rank=rank_name,
        )

    @dm_check.before_loop
    async def before_dm_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(SmartDM(bot))
