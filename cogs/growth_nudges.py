"""
The Circle — Growth Nudges Cog
Rank teasers when close to next tier group + stagnation nudges for stuck users.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite
import discord
from discord.ext import commands

from config import (
    EMBED_COLOR_ACCENT,
    EMBED_COLOR_PRIMARY,
    EXCLUDED_CHANNELS,
    RANK_TEASE_COOLDOWN_DAYS,
    RANK_TEASE_THRESHOLD,
    STAGNATION_NUDGE_DAYS,
    STAGNATION_NUDGE_COOLDOWN_DAYS,
    FACTION_UNLOCK_RANK,
    RANK_GROUPS,
)
from database import DB_PATH, get_user
from ranks import RANK_BY_TIER, get_rank_for_score, get_next_rank


class GrowthNudges(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.channel.name in EXCLUDED_CHANNELS:
            return

        user = await get_user(message.author.id)
        if not user:
            return

        # Try rank teaser first, then stagnation nudge
        sent = await self._try_rank_teaser(message, user)
        if not sent:
            await self._try_stagnation_nudge(message, user)

    async def _try_rank_teaser(self, message: discord.Message, user: dict) -> bool:
        """Show a teaser if user is close to the next tier group boundary."""
        current_tier = user["current_rank"]
        score = user["total_score"]
        user_id = message.author.id

        # Only tease at tier group boundaries (every 10 ranks)
        current_group = (current_tier - 1) // 10  # 0-9
        next_group_start_tier = (current_group + 1) * 10 + 1
        if next_group_start_tier > 100:
            return False

        next_group_rank = RANK_BY_TIER.get(next_group_start_tier)
        if not next_group_rank:
            return False

        # Check if within threshold of next group
        current_rank = RANK_BY_TIER.get(current_tier)
        if not current_rank:
            return False

        gap = next_group_rank.threshold - current_rank.threshold
        if gap <= 0:
            return False

        progress = (score - current_rank.threshold) / gap
        # Only show when 80%+ through current group toward next
        remaining_to_group = next_group_rank.threshold - score
        total_group_range = next_group_rank.threshold - RANK_BY_TIER.get((current_group * 10) + 1, current_rank).threshold
        if total_group_range <= 0:
            return False
        group_progress = 1.0 - (remaining_to_group / total_group_range)
        if group_progress < RANK_TEASE_THRESHOLD:
            return False

        # Check cooldown
        cutoff = (datetime.utcnow() - timedelta(days=RANK_TEASE_COOLDOWN_DAYS)).isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id FROM rank_tease_log WHERE user_id = ? AND sent_at > ?",
                (user_id, cutoff),
            )
            if await cursor.fetchone():
                return False

        # Build teaser
        pts_remaining = int(next_group_rank.threshold - score)
        group_name = next_group_rank.group_name
        group_idx = (next_group_start_tier - 1) // 10
        group_color_emoji = ["⬜", "🟢", "🔵", "🟠", "🔴", "🟣", "🩵", "🟡", "🩷", "⚪"][group_idx]

        teaser_lines = [
            f"👀 You're **{pts_remaining:,}** pts from **{group_name}**. Here's what's waiting:\n",
            f"{group_color_emoji} **{group_name}** name color",
            f"💬 New tagline: *\"{next_group_rank.tagline}\"*",
        ]

        # Special teasers
        if next_group_start_tier == FACTION_UNLOCK_RANK:
            teaser_lines.append("⚔️ **FACTION ACCESS** — Choose your allegiance: Inferno / Frost / Venom / Volt")

        teaser_lines.append("\nKeep pushing. 🔥")

        embed = discord.Embed(
            description="\n".join(teaser_lines),
            color=EMBED_COLOR_ACCENT,
        )

        try:
            await message.channel.send(embed=embed)
        except discord.HTTPException:
            return False

        # Log it
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO rank_tease_log (user_id, teased_rank, sent_at) VALUES (?, ?, ?)",
                (user_id, next_group_start_tier, datetime.utcnow().isoformat()),
            )
            await db.commit()

        return True

    async def _try_stagnation_nudge(self, message: discord.Message, user: dict) -> bool:
        """Nudge if user has been at the same rank for 14+ days."""
        user_id = message.author.id
        current_tier = user["current_rank"]
        score = user["total_score"]

        # Check how long they've been at this rank
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT timestamp FROM rank_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1",
                (user_id,),
            )
            last_rankup = await cursor.fetchone()

        if not last_rankup:
            # Use join date
            last_change = datetime.fromisoformat(user["joined_at"])
        else:
            last_change = datetime.fromisoformat(last_rankup[0])

        days_stuck = (datetime.utcnow() - last_change).days
        if days_stuck < STAGNATION_NUDGE_DAYS:
            return False

        # Check cooldown
        cutoff = (datetime.utcnow() - timedelta(days=STAGNATION_NUDGE_COOLDOWN_DAYS)).isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id FROM stagnation_log WHERE user_id = ? AND nudged_at > ?",
                (user_id, cutoff),
            )
            if await cursor.fetchone():
                return False

        # Build nudge
        current_rank = RANK_BY_TIER.get(current_tier)
        next_rank = get_next_rank(current_tier)
        if not current_rank or not next_rank:
            return False

        pts_needed = int(next_rank.threshold - score)

        embed = discord.Embed(
            description=(
                f"💭 {message.author.mention}, you've been **{current_rank.name}** for {days_stuck} days.\n"
                f"You're only **{pts_needed:,}** pts from **{next_rank.name}**.\n\n"
                f"**Quick wins:**\n"
                f"• Reply to 3 people (3x pts each)\n"
                f"• Post a meme with a tag\n"
                f"• Drop into voice for 30 min\n\n"
                f"The next rank is right there. 🎯"
            ),
            color=EMBED_COLOR_PRIMARY,
        )

        try:
            await message.channel.send(embed=embed)
        except discord.HTTPException:
            return False

        # Log it
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO stagnation_log (user_id, nudged_at, rank_at_nudge) VALUES (?, ?, ?)",
                (user_id, datetime.utcnow().isoformat(), current_tier),
            )
            await db.commit()

        return True


async def setup(bot: commands.Bot):
    await bot.add_cog(GrowthNudges(bot))
