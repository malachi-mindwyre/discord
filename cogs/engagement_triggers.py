"""
The Circle — Engagement Triggers Cog
Cliffhangers, social proof, loss aversion, countdowns, celebrations, tip drops.
"""

from __future__ import annotations

import random
from datetime import datetime, date, timedelta

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    EXCLUDED_CHANNELS,
    ENGAGEMENT_MAX_PER_DAY,
    ENGAGEMENT_TIP_CHANCE,
    ENGAGEMENT_TIPS,
    ENGAGEMENT_SOCIAL_PROOF,
    ENGAGEMENT_CLIFFHANGERS,
)
from database import DB_PATH


class EngagementTriggers(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track per-channel daily trigger counts (resets with restart, which is fine)
        self._daily_triggers: dict[int, int] = {}  # channel_id -> count today
        self._last_reset_date: str = date.today().isoformat()
        self.social_proof_loop.start()

    def cog_unload(self):
        self.social_proof_loop.cancel()

    def _check_daily_limit(self, channel_id: int) -> bool:
        """Returns True if we can still post triggers in this channel today."""
        today = date.today().isoformat()
        if today != self._last_reset_date:
            self._daily_triggers.clear()
            self._last_reset_date = today

        count = self._daily_triggers.get(channel_id, 0)
        return count < ENGAGEMENT_MAX_PER_DAY

    def _increment_trigger(self, channel_id: int):
        today = date.today().isoformat()
        if today != self._last_reset_date:
            self._daily_triggers.clear()
            self._last_reset_date = today
        self._daily_triggers[channel_id] = self._daily_triggers.get(channel_id, 0) + 1

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Randomly drop engagement tips after messages."""
        if message.author.bot or not message.guild:
            return
        if message.channel.name in EXCLUDED_CHANNELS:
            return

        # Random tip drop
        if random.random() < ENGAGEMENT_TIP_CHANCE:
            if not self._check_daily_limit(message.channel.id):
                return

            tip = random.choice(ENGAGEMENT_TIPS)
            try:
                await message.channel.send(tip)
                self._increment_trigger(message.channel.id)

                # Log
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "INSERT INTO engagement_trigger_log (trigger_type, channel_id, posted_at) VALUES (?, ?, ?)",
                        ("tip", message.channel.id, datetime.utcnow().isoformat()),
                    )
                    await db.commit()
            except discord.HTTPException:
                pass

    @tasks.loop(hours=6)
    async def social_proof_loop(self):
        """Post social proof / cliffhanger messages periodically in active channels."""
        for guild in self.bot.guilds:
            # Find an active channel (general is always a good bet)
            channel = discord.utils.get(guild.text_channels, name="general")
            if not channel:
                continue

            if not self._check_daily_limit(channel.id):
                continue

            # 50/50 between social proof and cliffhanger
            if random.random() < 0.5:
                await self._post_social_proof(guild, channel)
            else:
                await self._post_cliffhanger(channel)

    async def _post_social_proof(self, guild: discord.Guild, channel: discord.TextChannel):
        """Post a social proof message with real stats."""
        today = date.today().isoformat()
        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

        async with aiosqlite.connect(DB_PATH) as db:
            # Rank-ups this week
            cursor = await db.execute(
                "SELECT COUNT(*) FROM rank_history WHERE timestamp > ?", (week_ago,)
            )
            rankup_count = (await cursor.fetchone())[0]

            # Active users today
            cursor = await db.execute(
                "SELECT COUNT(DISTINCT user_id) FROM messages WHERE timestamp > ?",
                (datetime.utcnow().replace(hour=0, minute=0, second=0).isoformat(),),
            )
            active_count = (await cursor.fetchone())[0]

            # Messages today
            cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE timestamp > ?",
                (datetime.utcnow().replace(hour=0, minute=0, second=0).isoformat(),),
            )
            msg_count = (await cursor.fetchone())[0]

            # Active streaks
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            cursor = await db.execute(
                "SELECT COUNT(*) FROM streaks WHERE last_streak_date IN (?, ?) AND current_streak > 0",
                (today, yesterday),
            )
            streak_count = (await cursor.fetchone())[0]

        if msg_count == 0 and active_count == 0:
            return  # Don't post to dead server

        template = random.choice(ENGAGEMENT_SOCIAL_PROOF)
        text = template.format(
            rankup_count=rankup_count,
            active_count=active_count,
            msg_count=msg_count,
            user_count=active_count,
            streak_count=streak_count,
        )

        try:
            await channel.send(text)
            self._increment_trigger(channel.id)
        except discord.HTTPException:
            pass

    async def _post_cliffhanger(self, channel: discord.TextChannel):
        """Post a cliffhanger / anticipation message."""
        text = random.choice(ENGAGEMENT_CLIFFHANGERS)
        try:
            await channel.send(text)
            self._increment_trigger(channel.id)
        except discord.HTTPException:
            pass

    @social_proof_loop.before_loop
    async def before_social_proof(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(EngagementTriggers(bot))
