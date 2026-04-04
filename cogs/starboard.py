"""
The Circle — Starboard / Hall of Fame Cog
Auto-posts messages with enough reactions to #hall-of-fame.
"""

from __future__ import annotations

from datetime import datetime

import aiosqlite
import discord
from discord.ext import commands

from config import (
    EMBED_COLOR_ACCENT,
    STARBOARD_CHANNEL,
    STARBOARD_EMOJI,
    STARBOARD_THRESHOLDS,
    EXCLUDED_CHANNELS,
)
from database import DB_PATH


class Starboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_threshold(self, member_count: int) -> int:
        """Get the required reaction count based on server size."""
        threshold = 3
        for count, required in sorted(STARBOARD_THRESHOLDS.items()):
            if member_count >= count:
                threshold = required
        return threshold

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = guild.get_channel(payload.channel_id)
        if not channel or channel.name in EXCLUDED_CHANNELS or channel.name == STARBOARD_CHANNEL:
            return

        # Only count star emoji (or any emoji for broader appeal)
        # We'll count ALL unique reactions on the message
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.HTTPException:
            return

        if message.author.bot:
            return

        # Count unique users who reacted (one user with 5 emojis = 1, not 5)
        unique_reactors: set[int] = set()
        for reaction in message.reactions:
            try:
                async for user in reaction.users():
                    if not user.bot and user.id != message.author.id:
                        unique_reactors.add(user.id)
            except discord.HTTPException:
                pass
        total_reactions = len(unique_reactors)

        threshold = self._get_threshold(guild.member_count)
        if total_reactions < threshold:
            return

        # Check if already on starboard
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT starboard_message_id, star_count FROM starboard WHERE message_id = ?",
                (message.id,),
            )
            existing = await cursor.fetchone()

            starboard_channel = discord.utils.get(guild.text_channels, name=STARBOARD_CHANNEL)
            if not starboard_channel:
                return

            embed = self._build_starboard_embed(message, total_reactions)

            if existing:
                # Update existing starboard entry
                sb_msg_id, old_count = existing
                if total_reactions > old_count:
                    await db.execute(
                        "UPDATE starboard SET star_count = ? WHERE message_id = ?",
                        (total_reactions, message.id),
                    )
                    await db.commit()
                    # Try to edit the starboard message
                    try:
                        sb_msg = await starboard_channel.fetch_message(sb_msg_id)
                        await sb_msg.edit(embed=embed)
                    except discord.HTTPException:
                        pass
            else:
                # New starboard entry
                try:
                    sb_msg = await starboard_channel.send(embed=embed)
                    await db.execute(
                        """INSERT INTO starboard (message_id, author_id, channel_id, star_count,
                           starboard_message_id, content, timestamp)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (message.id, message.author.id, channel.id, total_reactions,
                         sb_msg.id, message.content[:500] if message.content else "",
                         datetime.utcnow().isoformat()),
                    )
                    await db.commit()
                except discord.HTTPException:
                    pass

    def _build_starboard_embed(self, message: discord.Message, reaction_count: int) -> discord.Embed:
        """Build the hall of fame embed for a message."""
        embed = discord.Embed(
            title="⭐ HALL OF FAME",
            description=message.content[:2000] if message.content else "*[Media/Embed]*",
            color=EMBED_COLOR_ACCENT,
        )
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        embed.add_field(name="Channel", value=f"#{message.channel.name}", inline=True)
        embed.add_field(name="Reactions", value=f"**{reaction_count}** unique users", inline=True)
        embed.add_field(
            name="Jump to Message",
            value=f"[Click here]({message.jump_url})",
            inline=False,
        )

        # Attach first image if present
        if message.attachments:
            for att in message.attachments:
                if att.content_type and att.content_type.startswith("image"):
                    embed.set_image(url=att.url)
                    break

        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text="The Circle • Quality rises to the top")
        embed.timestamp = message.created_at
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(Starboard(bot))
