"""
The Circle — Reaction Scoring Cog
Users earn points when their messages receive reactions.
"""

from __future__ import annotations

import discord
from discord.ext import commands

from config import (
    REACTION_POINTS_PER,
    REACTION_DAILY_CAP,
    REACTION_SELF_EXCLUDED,
    EXCLUDED_CHANNELS,
    EMBED_COLOR_PRIMARY,
)
from database import log_reaction, update_user_score, get_or_create_user


class ReactionScoring(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track daily reaction points per user (resets on restart, daily_scores table handles persistence)
        self._daily_reaction_points: dict[int, float] = {}

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Award points to message author when someone reacts to their message."""
        # Ignore bot reactions
        if payload.member and payload.member.bot:
            return
        if not payload.guild_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = guild.get_channel(payload.channel_id)
        if not channel or channel.name in EXCLUDED_CHANNELS:
            return

        # Fetch the message to get the author
        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.HTTPException):
            return

        # Don't award for bot messages
        if message.author.bot:
            return

        # Self-reactions don't count
        if REACTION_SELF_EXCLUDED and payload.user_id == message.author.id:
            return

        author_id = message.author.id

        # Check daily cap
        current_daily = self._daily_reaction_points.get(author_id, 0.0)
        if current_daily >= REACTION_DAILY_CAP:
            return

        points = min(REACTION_POINTS_PER, REACTION_DAILY_CAP - current_daily)

        # Log and award
        was_new = await log_reaction(
            message_author_id=author_id,
            reactor_id=payload.user_id,
            message_id=payload.message_id,
            channel_id=payload.channel_id,
            points=points,
        )

        if was_new:
            await get_or_create_user(author_id, str(message.author))
            await update_user_score(author_id, points)
            self._daily_reaction_points[author_id] = current_daily + points


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionScoring(bot))
