"""
The Circle — Moderation Cog
Auto-deletes @everyone/@here spam, rate-limits rapid-fire messages,
detects duplicate content, and provides admin purge/reset commands.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import timedelta

import discord
from discord.ext import commands

from config import (
    BOT_OWNER_ID,
    GUILD_ID,
    MOD_SPAM_RATE_LIMIT,
    MOD_SPAM_RATE_WINDOW,
    MOD_SPAM_TIMEOUT_SECONDS,
    MOD_DUPLICATE_WINDOW,
    MOD_DUPLICATE_COUNT,
    MOD_EVERYONE_TIMEOUT_SECONDS,
    MOD_MASS_MENTION_LIMIT,
    MOD_MASS_MENTION_TIMEOUT,
)

logger = logging.getLogger("circle.moderation")


def _collapse_repeats(s: str) -> str:
    """Collapse 3+ repeated chars to 1. 'AAAAAAA' -> 'A'"""
    return re.sub(r"(.)\1{2,}", r"\1", s.lower().strip())


class Moderation(commands.Cog):
    """Server moderation: spam filter, @everyone block, admin purge."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # {user_id: [timestamp, ...]} for rate limiting
        self._message_timestamps: dict[int, list[float]] = defaultdict(list)
        # {user_id: [(normalized_content, timestamp), ...]} for duplicate detection
        self._message_content: dict[int, list[tuple[str, float]]] = defaultdict(list)
        # Set of message IDs deleted by moderation (other cogs can check)
        self.deleted_message_ids: set[int] = set()

    # ── @everyone / @here filter ─────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        # Skip the bot owner — they can do anything
        if message.author.id == BOT_OWNER_ID:
            return

        # --- Check 1: @everyone / @here ---
        if message.mention_everyone or "@everyone" in message.content or "@here" in message.content:
            try:
                await message.delete()
                self.deleted_message_ids.add(message.id)
                logger.info(
                    "Deleted @everyone from %s (%s): %s",
                    message.author, message.author.id, message.content[:80],
                )
                # Timeout the user
                try:
                    until = discord.utils.utcnow() + timedelta(seconds=MOD_EVERYONE_TIMEOUT_SECONDS)
                    await message.author.timeout(until, reason="Unauthorized @everyone/@here ping")
                except discord.Forbidden:
                    pass
                # Warn in channel (auto-delete after 10s)
                try:
                    await message.channel.send(
                        f"🔕 {message.author.mention} — `@everyone` and `@here` are restricted. "
                        f"You've been timed out for {MOD_EVERYONE_TIMEOUT_SECONDS}s.",
                        delete_after=10,
                    )
                except discord.HTTPException:
                    pass
            except discord.Forbidden:
                logger.warning("Missing permissions to delete @everyone message from %s", message.author)
            return  # Don't process further checks for this message

        # --- Check 2: Mass mentions (5+ individual user pings) ---
        if len(message.mentions) >= MOD_MASS_MENTION_LIMIT:
            try:
                await message.delete()
                self.deleted_message_ids.add(message.id)
                logger.info(
                    "Mass mention spam from %s (%s): %d mentions",
                    message.author, message.author.id, len(message.mentions),
                )
                try:
                    until = discord.utils.utcnow() + timedelta(seconds=MOD_MASS_MENTION_TIMEOUT)
                    await message.author.timeout(until, reason="Spam: mass mentioning users")
                except discord.Forbidden:
                    pass
                try:
                    await message.channel.send(
                        f"🛑 {message.author.mention} — mass mentioning is not allowed. "
                        f"Timed out for {MOD_MASS_MENTION_TIMEOUT // 60} minutes.",
                        delete_after=10,
                    )
                except discord.HTTPException:
                    pass
            except discord.Forbidden:
                logger.warning("Missing permissions to delete mass mention from %s", message.author)
            return

        now = message.created_at.timestamp()

        # --- Check 3: Rate limiting (rapid-fire) ---
        timestamps = self._message_timestamps[message.author.id]
        timestamps.append(now)
        # Clean old timestamps
        cutoff = now - MOD_SPAM_RATE_WINDOW
        self._message_timestamps[message.author.id] = [t for t in timestamps if t > cutoff]
        timestamps = self._message_timestamps[message.author.id]

        if len(timestamps) >= MOD_SPAM_RATE_LIMIT:
            try:
                await message.delete()
                self.deleted_message_ids.add(message.id)
                logger.info("Rate limit: deleted message from %s (%s)", message.author, message.author.id)
            except discord.Forbidden:
                pass

            # Timeout on first trigger (check if not already timed out)
            if len(timestamps) == MOD_SPAM_RATE_LIMIT:
                try:
                    until = discord.utils.utcnow() + timedelta(seconds=MOD_SPAM_TIMEOUT_SECONDS)
                    await message.author.timeout(until, reason="Spam: too many messages too fast")
                    logger.info("Timed out %s for %ds (rate limit)", message.author, MOD_SPAM_TIMEOUT_SECONDS)
                except discord.Forbidden:
                    pass
                try:
                    await message.channel.send(
                        f"🛑 {message.author.mention} — slow down. "
                        f"You've been timed out for {MOD_SPAM_TIMEOUT_SECONDS // 60} minutes.",
                        delete_after=10,
                    )
                except discord.HTTPException:
                    pass
            return

        # --- Check 4: Duplicate/repetitive content ---
        normalized = _collapse_repeats(message.content)
        if len(normalized) < 2:
            return  # Too short to meaningfully check

        content_log = self._message_content[message.author.id]
        content_log.append((normalized, now))
        # Clean old entries
        dup_cutoff = now - MOD_DUPLICATE_WINDOW
        self._message_content[message.author.id] = [
            (c, t) for c, t in content_log if t > dup_cutoff
        ]
        content_log = self._message_content[message.author.id]

        # Count how many recent messages match this normalized content
        matches = sum(1 for c, _ in content_log if c == normalized)
        if matches >= MOD_DUPLICATE_COUNT:
            try:
                await message.delete()
                self.deleted_message_ids.add(message.id)
                logger.info("Duplicate spam: deleted from %s (%s)", message.author, message.author.id)
            except discord.Forbidden:
                pass

            # Timeout on first trigger
            if matches == MOD_DUPLICATE_COUNT:
                try:
                    until = discord.utils.utcnow() + timedelta(seconds=MOD_SPAM_TIMEOUT_SECONDS)
                    await message.author.timeout(until, reason="Spam: repeated messages")
                except discord.Forbidden:
                    pass
                try:
                    await message.channel.send(
                        f"🛑 {message.author.mention} — stop spamming. "
                        f"Timed out for {MOD_SPAM_TIMEOUT_SECONDS // 60} minutes.",
                        delete_after=10,
                    )
                except discord.HTTPException:
                    pass

        # Bounded cleanup
        if len(self.deleted_message_ids) > 500:
            self.deleted_message_ids = set(list(self.deleted_message_ids)[-250:])

    # ── Admin Commands ───────────────────────────────────────────────────

    @commands.command(name="purge")
    @commands.is_owner()
    async def purge_user(self, ctx: commands.Context, member: discord.Member, minutes: int = 30):
        """Delete all messages from a user in the last N minutes across all channels. Owner only. No cap."""
        cutoff = discord.utils.utcnow() - timedelta(minutes=minutes)
        status = await ctx.send(f"⚫ Purging messages from {member.mention} in the last {minutes} minutes...")

        total = 0
        target_id = member.id  # capture for lambda
        for channel in ctx.guild.text_channels:
            try:
                deleted = await channel.purge(
                    limit=None,
                    check=lambda m: m.author.id == target_id and m.created_at > cutoff,
                    oldest_first=False,
                )
                total += len(deleted)
            except (discord.Forbidden, discord.HTTPException):
                pass

        await status.edit(content=f"⚫ Purged **{total}** messages from {member.mention} across all channels.")

    @commands.command(name="nuke")
    @commands.is_owner()
    async def nuke_spam(self, ctx: commands.Context, minutes: int = 60):
        """Delete ALL messages that look like spam in the last N minutes. Owner only. No cap.
        Detects: @everyone spam, mass mentions, repeated 'AAA' content."""
        cutoff = discord.utils.utcnow() - timedelta(minutes=minutes)
        status = await ctx.send(f"⚫ Nuking spam across all channels from the last {minutes} minutes...")

        def is_spam(m: discord.Message) -> bool:
            if m.author.bot or m.author.id == BOT_OWNER_ID:
                return False
            if m.created_at < cutoff:
                return False
            content = m.content
            # @everyone or @here spam
            if "@everyone" in content or "@here" in content:
                return True
            # Mass mentions (5+ individual pings)
            if len(m.mentions) >= MOD_MASS_MENTION_LIMIT:
                return True
            # Repeated character spam (like "AAAAAAA")
            collapsed = _collapse_repeats(content)
            if len(content) > 10 and len(collapsed) < len(content) * 0.3:
                return True
            return False

        total = 0
        for channel in ctx.guild.text_channels:
            try:
                deleted = await channel.purge(limit=None, check=is_spam, oldest_first=False)
                total += len(deleted)
            except (discord.Forbidden, discord.HTTPException):
                pass

        await status.edit(content=f"⚫ Nuked **{total}** spam messages across all channels.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
