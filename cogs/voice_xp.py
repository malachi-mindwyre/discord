"""
The Circle — Voice XP Cog
Tracks time spent in voice channels and awards points.
Also tracks voice co-presence for the social graph.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from config import (
    VOICE_POINTS_PER_MINUTE,
    VOICE_AFK_CHANNEL_EXCLUDED,
    EMBED_COLOR_PRIMARY,
)
from database import (
    start_voice_session,
    end_voice_session,
    get_or_create_user,
    update_user_score,
    get_user_voice_minutes,
    update_voice_co_presence,
)

logger = logging.getLogger("circle.voice_xp")


class VoiceXP(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track active voice sessions in memory
        self._active_sessions: set[int] = set()

    async def _end_session_and_track(self, member: discord.Member, voice_channel: discord.VoiceChannel | None):
        """End a voice session, award points, and update social graph co-presence."""
        points = await end_voice_session(member.id, VOICE_POINTS_PER_MINUTE)
        if points and points > 0:
            await update_user_score(member.id, points)

            # Track voice co-presence with everyone still in the channel
            if voice_channel:
                session_minutes = points / VOICE_POINTS_PER_MINUTE if VOICE_POINTS_PER_MINUTE > 0 else 0
                for other in voice_channel.members:
                    if other.bot or other.id == member.id:
                        continue
                    try:
                        await update_voice_co_presence(member.id, other.id, session_minutes)
                    except Exception:
                        logger.debug("Failed to update voice co-presence for %s <-> %s", member.id, other.id)

            # Notify streaks_v2 about voice activity
            streaks_cog = self.bot.get_cog("StreaksV2")
            if streaks_cog:
                session_minutes = points / VOICE_POINTS_PER_MINUTE if VOICE_POINTS_PER_MINUTE > 0 else 0
                await streaks_cog.check_voice_streak(member.id, session_minutes)

        self._active_sessions.discard(member.id)
        return points

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Track voice channel join/leave for XP."""
        if member.bot:
            return

        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            # Skip AFK channel
            if VOICE_AFK_CHANNEL_EXCLUDED and after.channel == member.guild.afk_channel:
                return
            await get_or_create_user(member.id, str(member))
            await start_voice_session(member.id, after.channel.id)
            self._active_sessions.add(member.id)

        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            if member.id in self._active_sessions:
                await self._end_session_and_track(member, before.channel)

        # User switched channels
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            # End old session
            if member.id in self._active_sessions:
                await self._end_session_and_track(member, before.channel)

            # Start new session (skip AFK)
            if VOICE_AFK_CHANNEL_EXCLUDED and after.channel == member.guild.afk_channel:
                self._active_sessions.discard(member.id)
            else:
                await start_voice_session(member.id, after.channel.id)
                self._active_sessions.add(member.id)

    @commands.command(name="voicetime")
    async def voice_time_cmd(self, ctx: commands.Context, member: discord.Member = None):
        """Check voice time stats."""
        target = member or ctx.author
        total_minutes = await get_user_voice_minutes(target.id)
        hours = total_minutes / 60

        embed = discord.Embed(
            title=f"🎤 {target.display_name}'s Voice Time",
            color=EMBED_COLOR_PRIMARY,
        )
        embed.add_field(name="Total Time", value=f"**{hours:.1f} hours** ({total_minutes:.0f} min)", inline=True)
        embed.add_field(
            name="Points Earned",
            value=f"**{total_minutes * VOICE_POINTS_PER_MINUTE:.0f} pts**",
            inline=True,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceXP(bot))
