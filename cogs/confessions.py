"""
The Circle — Confessions Cog
Anonymous confession posting via DM (!confess) or slash command.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite
import discord
from discord.ext import commands

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    CONFESSION_COOLDOWN_HOURS,
    CONFESSION_CHANNEL,
    CONFESSION_DISCUSSION_CHANNEL,
    CONFESSION_AUTO_REACTIONS,
    GUILD_ID,
)
from database import DB_PATH


class Confessions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_next_confession_number(self) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT MAX(number) FROM confessions")
            row = await cursor.fetchone()
            return (row[0] or 0) + 1

    async def _check_cooldown(self, user_id: int) -> bool:
        """Returns True if user is on cooldown."""
        cutoff = (datetime.utcnow() - timedelta(hours=CONFESSION_COOLDOWN_HOURS)).isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id FROM confessions WHERE user_id = ? AND timestamp > ?",
                (user_id, cutoff),
            )
            return await cursor.fetchone() is not None

    async def _post_confession(self, user_id: int, content: str) -> tuple[bool, str]:
        """Post a confession. Returns (success, message)."""
        # Check cooldown
        if await self._check_cooldown(user_id):
            return False, f"You can only confess once every {CONFESSION_COOLDOWN_HOURS} hours. Be patient."

        # Get confession number
        number = await self._get_next_confession_number()

        # Store in DB
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO confessions (user_id, content, number, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, content, number, now),
            )
            await db.commit()

        # Find the confessions channel
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return False, "Could not find The Circle."

        channel = discord.utils.get(guild.text_channels, name=CONFESSION_CHANNEL)
        if not channel:
            return False, f"#{CONFESSION_CHANNEL} channel not found."

        # Post the confession
        embed = discord.Embed(
            title=f"🔮 CONFESSION #{number}",
            description=content,
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="Anonymous • The Circle keeps your secrets")
        embed.timestamp = datetime.utcnow()

        try:
            msg = await channel.send(embed=embed)
            # Add auto-reactions
            for emoji in CONFESSION_AUTO_REACTIONS:
                try:
                    await msg.add_reaction(emoji)
                except discord.HTTPException:
                    pass

            # Post discussion prompt
            discuss_ch = discord.utils.get(guild.text_channels, name=CONFESSION_DISCUSSION_CHANNEL)
            if discuss_ch:
                try:
                    await discuss_ch.send(
                        f"💭 **Confession #{number}** just dropped in {channel.mention}. Thoughts?"
                    )
                except discord.HTTPException:
                    pass

        except discord.HTTPException:
            return False, "Failed to post confession."

        return True, f"Your confession has been posted as **#{number}**. The Circle keeps your secret. 🔮"

    @commands.command(name="confess")
    async def confess_cmd(self, ctx: commands.Context, *, content: str = None):
        """Submit an anonymous confession. Use in DMs or any channel."""
        if not content:
            await ctx.send("⚫ Usage: `!confess <your confession>`\nDM Keeper for full anonymity.")
            return

        # If used in a guild channel, delete the original message for privacy
        if ctx.guild:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass

        success, response = await self._post_confession(ctx.author.id, content)

        # Always respond in DM for privacy
        try:
            await ctx.author.send(f"⚫ {response}")
        except (discord.HTTPException, discord.Forbidden):
            if ctx.guild:
                # Can't DM, so whisper in channel (ephemeral-like)
                try:
                    await ctx.send(f"⚫ {response}", delete_after=10)
                except discord.HTTPException:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle DM confessions (messages starting with !confess in DMs)."""
        # Only process DMs that aren't commands (the command handler gets !confess already)
        if message.guild or message.author.bot:
            return
        # If someone DMs without the command prefix, ignore
        # The !confess command already handles DMs via the command system


async def setup(bot: commands.Bot):
    await bot.add_cog(Confessions(bot))
