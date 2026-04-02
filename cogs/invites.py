"""
The Circle — Invite Tracker Cog
Tracks who invited who, validates invites after 24h + 5 messages.
"""

from __future__ import annotations

import discord
from discord.ext import commands, tasks

from config import INVITE_MIN_STAY_HOURS, INVITE_MIN_MESSAGES, SCORE_INVITE_BONUS
from database import (
    log_invite,
    validate_invite,
    increment_invitee_messages,
    update_user_score,
    get_or_create_user,
)


class InviteTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Cache of guild invites: {guild_id: {invite_code: uses}}
        self._invite_cache: dict[int, dict[str, int]] = {}
        self.check_invite_validity.start()

    def cog_unload(self):
        self.check_invite_validity.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """Cache all current invite counts on startup."""
        for guild in self.bot.guilds:
            await self._cache_invites(guild)

    async def _cache_invites(self, guild: discord.Guild):
        """Refresh the invite cache for a guild."""
        try:
            invites = await guild.invites()
            self._invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
        except discord.HTTPException:
            self._invite_cache[guild.id] = {}

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Detect which invite was used when a member joins."""
        if member.bot:
            return

        guild = member.guild
        old_cache = self._invite_cache.get(guild.id, {})

        # Get current invites
        try:
            current_invites = await guild.invites()
        except discord.HTTPException:
            return

        # Find which invite's use count increased
        inviter_id = None
        for invite in current_invites:
            old_uses = old_cache.get(invite.code, 0)
            if invite.uses > old_uses and invite.inviter:
                inviter_id = invite.inviter.id
                break

        # Update cache
        self._invite_cache[guild.id] = {inv.code: inv.uses for inv in current_invites}

        # Log the invite if we found the inviter
        if inviter_id and inviter_id != member.id:
            await get_or_create_user(inviter_id, str(invite.inviter))
            await log_invite(inviter_id, member.id)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """Update cache when a new invite is created."""
        if invite.guild:
            guild_cache = self._invite_cache.setdefault(invite.guild.id, {})
            guild_cache[invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """Update cache when an invite is deleted."""
        if invite.guild and invite.guild.id in self._invite_cache:
            self._invite_cache[invite.guild.id].pop(invite.code, None)

    @tasks.loop(hours=1)
    async def check_invite_validity(self):
        """
        Check if any pending invites should be validated.
        An invite is valid when the invitee has been in the server 24h+ and sent 5+ messages.
        This is checked via the database — invitee message counts are incremented by the scoring handler.
        """
        import aiosqlite
        from database import DB_PATH
        from datetime import datetime, timedelta

        cutoff = (datetime.utcnow() - timedelta(hours=INVITE_MIN_STAY_HOURS)).isoformat()

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT invitee_id, inviter_id FROM invites
                   WHERE is_valid = 0 AND joined_at < ? AND message_count >= ?""",
                (cutoff, INVITE_MIN_MESSAGES),
            )
            rows = await cursor.fetchall()

        for invitee_id, inviter_id in rows:
            validated_inviter = await validate_invite(invitee_id)
            if validated_inviter:
                # Award invite bonus points
                await update_user_score(validated_inviter, SCORE_INVITE_BONUS)

    @check_invite_validity.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(InviteTracker(bot))
