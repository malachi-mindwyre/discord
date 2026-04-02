"""
The Circle — Keeper Personality Cog
Keeper sends 2-4 random contextual messages per day in #general,
making the bot feel alive and the server active even at low member counts.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime

import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    KEEPER_PERSONALITY_MIN_INTERVAL,
    KEEPER_PERSONALITY_MAX_INTERVAL,
    KEEPER_PERSONALITY_MESSAGES,
    GUILD_ID,
)

logger = logging.getLogger("circle.keeper_personality")


class KeeperPersonality(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._recent_messages: list[str] = []  # Track last 5 sent to avoid repeats
        self._personality_loop.start()

    def cog_unload(self):
        self._personality_loop.cancel()

    def _find_general_channel(self) -> discord.TextChannel | None:
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return None
        return discord.utils.get(guild.text_channels, name="general")

    async def _get_context_hint(self, channel: discord.TextChannel) -> str | None:
        """Fetch recent messages to optionally reference in Keeper's comment."""
        try:
            messages = []
            async for msg in channel.history(limit=10):
                if not msg.author.bot and msg.content:
                    messages.append(msg)
            if not messages:
                return None

            # Pick a random recent non-bot message to vaguely reference
            target = random.choice(messages[:5])
            author_name = target.author.display_name

            # Contextual reactions based on message content
            content_lower = target.content.lower()
            if any(w in content_lower for w in ["streak", "rank", "level", "grind"]):
                return f"I see {author_name} is focused on the grind. The Circle rewards persistence."
            if any(w in content_lower for w in ["meme", "lol", "lmao", "funny"]):
                return f"The Circle appreciates humor. Keep the energy alive."
            if any(w in content_lower for w in ["help", "how", "what", "?"]):
                return f"Questions are the beginning of wisdom. The Circle provides answers to those who seek."
            if len(target.content) > 100:
                return f"Long messages carry weight in The Circle. Quality is rewarded."

            return None
        except Exception:
            return None

    @tasks.loop(hours=1)
    async def _personality_loop(self):
        """Core loop — runs hourly, randomly decides whether to post."""
        # Random chance based on configured interval
        # With 3-8h interval and hourly checks, fire ~20-33% of the time
        target_avg = (KEEPER_PERSONALITY_MIN_INTERVAL + KEEPER_PERSONALITY_MAX_INTERVAL) / 2
        fire_chance = 1.0 / target_avg

        if random.random() > fire_chance:
            return

        # Don't post during very late hours (04-08 UTC)
        hour = datetime.utcnow().hour
        if 4 <= hour < 8:
            return

        channel = self._find_general_channel()
        if not channel:
            return

        # Try contextual message first (30% chance), fallback to random
        message = None
        if random.random() < 0.3:
            message = await self._get_context_hint(channel)

        if not message:
            # Pick from config, avoiding recent repeats
            available = [m for m in KEEPER_PERSONALITY_MESSAGES if m not in self._recent_messages]
            if not available:
                self._recent_messages.clear()
                available = KEEPER_PERSONALITY_MESSAGES
            message = random.choice(available)

        # Track to avoid repeats
        self._recent_messages.append(message)
        if len(self._recent_messages) > 5:
            self._recent_messages.pop(0)

        # Small random delay so it doesn't always post on the hour
        await asyncio.sleep(random.randint(30, 300))

        try:
            embed = discord.Embed(
                description=f"*{message}*",
                color=EMBED_COLOR_PRIMARY,
            )
            embed.set_footer(text="Keeper observes.")
            await channel.send(embed=embed)
            logger.info("Keeper personality: %s", message[:50])
        except discord.HTTPException:
            pass

    @_personality_loop.before_loop
    async def _before_personality(self):
        await self.bot.wait_until_ready()
        # Initial random delay so it doesn't fire immediately on startup
        await asyncio.sleep(random.randint(600, 1800))


async def setup(bot: commands.Bot):
    await bot.add_cog(KeeperPersonality(bot))
