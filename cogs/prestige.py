"""
The Circle — Prestige Cog
Endgame content for players who reach Veteran I (rank 41+).
Prestige resets your score and rank but grants permanent bonuses and coin rewards.
"""

from __future__ import annotations

import discord
import aiosqlite
from discord.ext import commands
from datetime import datetime
from typing import Optional

from config import (
    PRESTIGE_MIN_RANK,
    PRESTIGE_MAX_LEVEL,
    PRESTIGE_REWARDS,
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    EMBED_COLOR_WARNING,
)
from database import get_user, set_user_score, add_coins, get_prestige_level, DB_PATH
from ranks import RANK_BY_TIER


PRESTIGE_STARS = {0: "", 1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "🌟🌟🌟🌟", 5: "💫💫💫💫💫"}

PRESTIGE_TITLES = {
    1: "Reborn",
    2: "Ascended",
    3: "Transcendent",
    4: "Mythic",
    5: "Eternal",
}


async def _set_prestige_level(user_id: int, level: int, score_before: float):
    """Set a user's prestige level in the prestige table."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO prestige (user_id, prestige_level, last_prestige_at, total_score_before_prestige)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   prestige_level = ?,
                   last_prestige_at = ?,
                   total_score_before_prestige = total_score_before_prestige + ?""",
            (user_id, level, now, score_before, level, now, score_before),
        )
        await db.commit()


async def _reset_streak(user_id: int):
    """Reset personal streaks on prestige."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE streaks SET current_streak = 0, last_streak_date = NULL WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


class Prestige(commands.Cog):
    """Prestige system — sacrifice your rank for permanent power."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track users who typed !prestige confirm within the last interaction
        self._pending_confirm: dict[int, datetime] = {}

    @commands.command(name="prestige")
    async def prestige_cmd(self, ctx: commands.Context, action: Optional[str] = None):
        """Show prestige info or execute prestige with 'confirm'."""
        user_id = ctx.author.id
        user = await get_user(user_id)

        if not user:
            embed = discord.Embed(
                title="👁️ THE CIRCLE DOES NOT KNOW YOU",
                description="You must first be known to The Circle before you can be reborn.\nSend some messages to get started.",
                color=EMBED_COLOR_WARNING,
            )
            await ctx.send(embed=embed)
            return

        current_rank = user["current_rank"]
        current_score = user["total_score"]
        prestige_level = await get_prestige_level(user_id)

        if action and action.lower() == "confirm":
            await self._execute_prestige(ctx, user, prestige_level, current_rank, current_score)
            return

        # ── Show prestige info ──
        await self._show_prestige_info(ctx, user, prestige_level, current_rank, current_score)

    async def _show_prestige_info(
        self,
        ctx: commands.Context,
        user: dict,
        prestige_level: int,
        current_rank: int,
        current_score: float,
    ):
        """Display prestige info embed."""
        stars = PRESTIGE_STARS.get(prestige_level, "")
        rank_info = RANK_BY_TIER.get(current_rank)
        rank_name = rank_info.name if rank_info else f"Tier {current_rank}"

        embed = discord.Embed(
            title="💀 PRESTIGE SYSTEM",
            description=(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "*To ascend, one must first descend.*\n"
                "*Sacrifice everything. Gain power eternal.*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_ACCENT,
        )

        # Current status
        if prestige_level > 0:
            title = PRESTIGE_TITLES.get(prestige_level, "Unknown")
            total_bonus = int(PRESTIGE_REWARDS[prestige_level]["permanent_bonus"] * 100)
            embed.add_field(
                name="🌀 Current Prestige",
                value=f"**Level {prestige_level}** — *{title}* {stars}\n+**{total_bonus}%** permanent bonus on all points",
                inline=False,
            )
        else:
            embed.add_field(
                name="🌀 Current Prestige",
                value="**Level 0** — *Not yet reborn*\nNo permanent bonuses active.",
                inline=False,
            )

        embed.add_field(
            name="📊 Your Status",
            value=f"Rank: **{rank_name}** (Tier {current_rank})\nScore: **{current_score:,.0f}**",
            inline=False,
        )

        # Eligibility
        if prestige_level >= PRESTIGE_MAX_LEVEL:
            embed.add_field(
                name="🏆 MAX PRESTIGE",
                value="You have reached the pinnacle. There is nothing left to sacrifice.\n*The Circle bows to you.*",
                inline=False,
            )
        elif current_rank < PRESTIGE_MIN_RANK:
            needed_rank = RANK_BY_TIER.get(PRESTIGE_MIN_RANK)
            needed_name = needed_rank.name if needed_rank else f"Tier {PRESTIGE_MIN_RANK}"
            embed.add_field(
                name="🔒 Not Eligible",
                value=(
                    f"You need **{needed_name}** (Tier {PRESTIGE_MIN_RANK}) to prestige.\n"
                    f"You are **{PRESTIGE_MIN_RANK - current_rank} tiers** away."
                ),
                inline=False,
            )
        else:
            next_level = prestige_level + 1
            rewards = PRESTIGE_REWARDS[next_level]
            bonus_pct = int(rewards["permanent_bonus"] * 100)
            embed.add_field(
                name=f"⚡ Next Prestige — Level {next_level}",
                value=(
                    f"**Reward:** 🪙 {rewards['coins']:,} Circles + **+{bonus_pct}%** permanent bonus\n\n"
                    f"**What resets:**\n"
                    f"• Score → 0\n"
                    f"• Rank → Rookie I\n"
                    f"• Personal streaks → 0\n\n"
                    f"**What stays:**\n"
                    f"• 🪙 Coins & purchases\n"
                    f"• 🏅 Achievements & badges\n"
                    f"• ⚔️ Faction membership\n"
                    f"• 👤 Profile customization\n"
                    f"• 🤝 Buddy streaks"
                ),
                inline=False,
            )
            embed.add_field(
                name="⚠️ HOW TO PRESTIGE",
                value="Type `!prestige confirm` to sacrifice your rank and ascend.\n**This cannot be undone.**",
                inline=False,
            )

        # Show all prestige levels
        levels_text = ""
        for lvl in range(1, PRESTIGE_MAX_LEVEL + 1):
            r = PRESTIGE_REWARDS[lvl]
            bonus = int(r["permanent_bonus"] * 100)
            title = PRESTIGE_TITLES.get(lvl, "")
            marker = " ◀️ YOU" if lvl == prestige_level else ""
            check = "✅" if lvl <= prestige_level else "⬜"
            levels_text += f"{check} **Lv.{lvl}** *{title}* — 🪙 {r['coins']:,} + {bonus}% bonus{marker}\n"

        embed.add_field(name="📜 All Prestige Levels", value=levels_text, inline=False)

        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="The Circle • Those who sacrifice everything gain everything")

        await ctx.send(embed=embed)

    async def _execute_prestige(
        self,
        ctx: commands.Context,
        user: dict,
        prestige_level: int,
        current_rank: int,
        current_score: float,
    ):
        """Execute the prestige: reset score/rank/streaks, grant rewards."""
        user_id = ctx.author.id

        # ── Validation ──
        if prestige_level >= PRESTIGE_MAX_LEVEL:
            embed = discord.Embed(
                title="🏆 ALREADY AT MAX PRESTIGE",
                description="You have already reached the highest prestige level.\n*The Circle has no more to offer you... for now.*",
                color=EMBED_COLOR_WARNING,
            )
            await ctx.send(embed=embed)
            return

        if current_rank < PRESTIGE_MIN_RANK:
            needed_rank = RANK_BY_TIER.get(PRESTIGE_MIN_RANK)
            needed_name = needed_rank.name if needed_rank else f"Tier {PRESTIGE_MIN_RANK}"
            embed = discord.Embed(
                title="🔒 NOT WORTHY... YET",
                description=(
                    f"You need **{needed_name}** (Tier {PRESTIGE_MIN_RANK}) to prestige.\n"
                    f"Current rank: Tier {current_rank}. Keep grinding."
                ),
                color=EMBED_COLOR_WARNING,
            )
            await ctx.send(embed=embed)
            return

        new_level = prestige_level + 1
        rewards = PRESTIGE_REWARDS[new_level]
        title = PRESTIGE_TITLES.get(new_level, "Unknown")

        # ── Execute prestige ──
        # 1. Reset score and rank
        await set_user_score(user_id, 0.0, 1)

        # 2. Reset personal streaks
        await _reset_streak(user_id)

        # 3. Set new prestige level
        await _set_prestige_level(user_id, new_level, current_score)

        # 4. Grant coin reward
        await add_coins(user_id, rewards["coins"])

        # ── Announcement embed ──
        stars = PRESTIGE_STARS.get(new_level, "")
        bonus_pct = int(rewards["permanent_bonus"] * 100)

        embed = discord.Embed(
            title="💀⚡ PRESTIGE ACHIEVED ⚡💀",
            description=(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"**{ctx.author.mention}** has been **reborn.**\n\n"
                f"Prestige **Level {new_level}** — *{title}* {stars}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_ACCENT,
        )

        embed.add_field(
            name="🎁 Rewards Granted",
            value=(
                f"🪙 **{rewards['coins']:,} Circles** deposited\n"
                f"📈 **+{bonus_pct}%** permanent bonus on ALL points"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔄 Reset",
            value=(
                f"Score: {current_score:,.0f} → **0**\n"
                f"Rank: Tier {current_rank} → **Rookie I**\n"
                f"Streaks: **Reset**"
            ),
            inline=False,
        )

        embed.add_field(
            name="💎 Preserved",
            value="Coins, achievements, faction, profile, buddy streaks",
            inline=False,
        )

        if new_level < PRESTIGE_MAX_LEVEL:
            next_rewards = PRESTIGE_REWARDS[new_level + 1]
            next_bonus = int(next_rewards["permanent_bonus"] * 100)
            embed.add_field(
                name="👁️ The Path Continues",
                value=f"Next prestige at Veteran I again... for **+{next_bonus}%** and 🪙 {next_rewards['coins']:,}",
                inline=False,
            )
        else:
            embed.add_field(
                name="👑 FINAL FORM",
                value="*There is nothing beyond this. You are eternal.*",
                inline=False,
            )

        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="The Circle • Death is just the beginning")

        await ctx.send(embed=embed)

        # Try to announce in rank-ups channel
        for channel in ctx.guild.text_channels:
            if channel.name == "rank-ups":
                announce_embed = discord.Embed(
                    title="💀 A SOUL HAS BEEN REBORN",
                    description=(
                        f"{ctx.author.mention} has prestiged to **Level {new_level}** — *{title}* {stars}\n\n"
                        f"They sacrificed **{current_score:,.0f} points** and **Tier {current_rank}** "
                        f"for **+{bonus_pct}%** permanent power.\n\n"
                        f"*The Circle remembers all who dare to fall.*"
                    ),
                    color=EMBED_COLOR_ACCENT,
                )
                try:
                    await channel.send(embed=announce_embed)
                except discord.HTTPException:
                    pass
                break


async def setup(bot: commands.Bot):
    await bot.add_cog(Prestige(bot))
