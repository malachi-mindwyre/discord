"""
The Circle — Daily Prompts Cog
Posts a random discussion prompt to #general every day.
Pulls from user-submitted prompts first (UGC pipeline), then falls back to config.
"""

from __future__ import annotations

import logging
import random

import discord
from discord.ext import commands, tasks

from config import (
    DAILY_PROMPTS,
    DAILY_PROMPT_HOUR,
    DAILY_PROMPT_CHANNEL,
    EMBED_COLOR_PRIMARY,
    UGC_USED_REWARD_COINS,
)
from database import (
    get_approved_ugc_prompt,
    mark_ugc_prompt_used,
    add_coins,
)

logger = logging.getLogger("circle.daily_prompts")


class DailyPrompts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._used_prompts: list[int] = []  # Track used config indices to avoid repeats
        self.post_daily_prompt.start()

    def cog_unload(self):
        self.post_daily_prompt.cancel()

    def _pick_config_prompt(self) -> str:
        """Pick a random prompt from the hardcoded config list, avoiding recent repeats."""
        available = [i for i in range(len(DAILY_PROMPTS)) if i not in self._used_prompts]
        if not available:
            self._used_prompts.clear()
            available = list(range(len(DAILY_PROMPTS)))

        idx = random.choice(available)
        self._used_prompts.append(idx)
        if len(self._used_prompts) > 20:
            self._used_prompts = self._used_prompts[-20:]
        return DAILY_PROMPTS[idx]

    @tasks.loop(hours=24)
    async def post_daily_prompt(self):
        """Post a daily prompt — UGC first, then fallback to config."""
        # Try UGC pipeline first
        ugc = await get_approved_ugc_prompt()
        ugc_submitter_id = None
        if ugc:
            prompt = ugc["content"]
            ugc_submitter_id = ugc["user_id"]
            await mark_ugc_prompt_used(ugc["id"])
            await add_coins(ugc_submitter_id, UGC_USED_REWARD_COINS)
            logger.info("Daily prompt from UGC #%d (user %s): %s", ugc["id"], ugc_submitter_id, prompt[:50])
        else:
            prompt = self._pick_config_prompt()

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

            if ugc_submitter_id:
                member = guild.get_member(ugc_submitter_id)
                credit = member.display_name if member else f"User #{ugc_submitter_id}"
                embed.set_footer(text=f"Submitted by {credit} • The Circle • A new question every day")
            else:
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
