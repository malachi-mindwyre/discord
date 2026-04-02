"""
The Circle — Introductions Cog
Monitors #introductions, awards 50 pts + badge on first post.
"""

from __future__ import annotations

from datetime import datetime

import aiosqlite
import discord
from discord.ext import commands

from config import EMBED_COLOR_ACCENT, INTRO_POINTS_REWARD
from database import DB_PATH, get_or_create_user, update_user_score, unlock_achievement


class Introductions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.channel.name != "introductions":
            return

        user_id = message.author.id

        # Check if they already posted an intro
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id FROM introductions WHERE user_id = ?", (user_id,)
            )
            if await cursor.fetchone():
                return  # Already introduced

            # Record the introduction
            await db.execute(
                "INSERT INTO introductions (user_id, posted_at) VALUES (?, ?)",
                (user_id, datetime.utcnow().isoformat()),
            )
            await db.commit()

        # Award points
        await get_or_create_user(user_id, str(message.author))
        await update_user_score(user_id, INTRO_POINTS_REWARD)

        # Unlock achievement
        newly_unlocked = await unlock_achievement(user_id, "introduced")

        # Send congratulations
        embed = discord.Embed(
            title="⚫ INTRODUCTION RECEIVED",
            description=(
                f"Welcome to The Circle, {message.author.mention}!\n\n"
                f"🏆 **+{INTRO_POINTS_REWARD} points** awarded for introducing yourself.\n"
            ) + ("🏅 Badge unlocked: **Introduced**\n" if newly_unlocked else "") +
            "\nThe Circle sees you now. 👁️",
            color=EMBED_COLOR_ACCENT,
        )
        # Post to #achievements channel instead of inline
        ach_channel = discord.utils.get(message.guild.text_channels, name="achievements")
        target = ach_channel or message.channel
        try:
            await target.send(embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Introductions(bot))
