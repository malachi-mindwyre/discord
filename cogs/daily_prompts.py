"""
The Circle — Daily Prompts Cog
Posts a random discussion prompt to #general every day.
"""

from __future__ import annotations

import random

import discord
from discord.ext import commands, tasks

from config import (
    DAILY_PROMPTS,
    DAILY_PROMPT_HOUR,
    DAILY_PROMPT_CHANNEL,
    EMBED_COLOR_PRIMARY,
)


class DailyPrompts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._used_prompts: list[int] = []  # Track used indices to avoid repeats
        self.post_daily_prompt.start()

    def cog_unload(self):
        self.post_daily_prompt.cancel()

    def _pick_prompt(self) -> str:
        """Pick a random prompt, avoiding recent repeats."""
        available = [i for i in range(len(DAILY_PROMPTS)) if i not in self._used_prompts]
        if not available:
            # All used — reset
            self._used_prompts.clear()
            available = list(range(len(DAILY_PROMPTS)))

        idx = random.choice(available)
        self._used_prompts.append(idx)
        # Keep last 20 to avoid repeats
        if len(self._used_prompts) > 20:
            self._used_prompts = self._used_prompts[-20:]
        return DAILY_PROMPTS[idx]

    @tasks.loop(hours=24)
    async def post_daily_prompt(self):
        """Post a daily prompt."""
        prompt = self._pick_prompt()

        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name=DAILY_PROMPT_CHANNEL)
            if not channel:
                continue

            embed = discord.Embed(
                title="💭 DAILY QUESTION",
                description=(
                    f"{prompt}\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "*Reply to this message for **3x points**. Tag someone for **4x**.*"
                ),
                color=EMBED_COLOR_PRIMARY,
            )
            embed.set_footer(text="The Circle • A new question every day")

            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

    @tasks.loop(count=1)
    async def _align_to_hour(self):
        """Wait until the target hour to start the daily loop."""
        pass

    @post_daily_prompt.before_loop
    async def before_prompt(self):
        """Wait until bot is ready, then align to the target hour."""
        await self.bot.wait_until_ready()
        # Wait until the target hour
        from datetime import datetime, timedelta
        import asyncio
        now = datetime.utcnow()
        target = now.replace(hour=DAILY_PROMPT_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)


async def setup(bot: commands.Bot):
    await bot.add_cog(DailyPrompts(bot))
