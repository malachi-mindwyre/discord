"""
The Circle — Voice XP Cog
Tracks time spent in voice channels and awards points.
Also tracks voice co-presence for the social graph.
Includes AFK detection: requires 2+ non-bot users, penalizes mute+deaf.
"""

from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands

from config import (
    VOICE_POINTS_PER_MINUTE,
    VOICE_AFK_CHANNEL_EXCLUDED,
    VOICE_MIN_PARTICIPANTS,
    VOICE_AFK_PENALTY_MULT,
    VOICE_AFK_DETECTION_MINUTES,
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
        # Track when users entered mute+deaf state: user_id -> timestamp
        self._mute_deaf_since: dict[int, float] = {}

    def _count_non_bot_members(self, channel: discord.VoiceChannel) -> int:
        """Count non-bot members in a voice channel."""
        return sum(1 for m in channel.members if not m.bot)

    def _is_mute_deaf(self, state: discord.VoiceState) -> bool:
        """Check if user is both self-muted and self-deafened."""
        return state.self_mute and state.self_deaf

    async def _end_session_and_track(self, member: discord.Member, voice_channel: discord.VoiceChannel | None):
        """End a voice session, award points, and update social graph co-presence."""
        points = await end_voice_session(member.id, VOICE_POINTS_PER_MINUTE)
        if points and points > 0:
            # Apply AFK penalty if user was muted+deafened for too long
            mute_since = self._mute_deaf_since.get(member.id)
            if mute_since:
                afk_duration_min = (time.time() - mute_since) / 60
                if afk_duration_min >= VOICE_AFK_DETECTION_MINUTES:
                    points *= VOICE_AFK_PENALTY_MULT
                    logger.debug(
                        "AFK penalty applied to %s: %.1f min mute+deaf, points halved",
                        member.id, afk_duration_min,
                    )

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

        # Clean up tracking
        self._active_sessions.discard(member.id)
        self._mute_deaf_since.pop(member.id, None)
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

        # ── Mute/deaf state tracking (even within same channel) ──────
        if after.channel and member.id in self._active_sessions:
            if self._is_mute_deaf(after):
                # Started being mute+deaf — record timestamp
                if member.id not in self._mute_deaf_since:
                    self._mute_deaf_since[member.id] = time.time()
            else:
                # No longer mute+deaf — clear tracking
                self._mute_deaf_since.pop(member.id, None)

        # ── User joined a voice channel ──────────────────────────────
        if before.channel is None and after.channel is not None:
            # Skip AFK channel
            if VOICE_AFK_CHANNEL_EXCLUDED and after.channel == member.guild.afk_channel:
                return
            # Require minimum participants
            if self._count_non_bot_members(after.channel) < VOICE_MIN_PARTICIPANTS:
                return
            await get_or_create_user(member.id, str(member))
            await start_voice_session(member.id, after.channel.id)
            self._active_sessions.add(member.id)
            # Track initial mute+deaf state
            if self._is_mute_deaf(after):
                self._mute_deaf_since[member.id] = time.time()

        # ── User left a voice channel ────────────────────────────────
        elif before.channel is not None and after.channel is None:
            if member.id in self._active_sessions:
                await self._end_session_and_track(member, before.channel)

        # ── User switched channels ───────────────────────────────────
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            # End old session
            if member.id in self._active_sessions:
                await self._end_session_and_track(member, before.channel)

            # Start new session (skip AFK)
            if VOICE_AFK_CHANNEL_EXCLUDED and after.channel == member.guild.afk_channel:
                self._active_sessions.discard(member.id)
            elif self._count_non_bot_members(after.channel) < VOICE_MIN_PARTICIPANTS:
                self._active_sessions.discard(member.id)
            else:
                await start_voice_session(member.id, after.channel.id)
                self._active_sessions.add(member.id)
                if self._is_mute_deaf(after):
                    self._mute_deaf_since[member.id] = time.time()

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
