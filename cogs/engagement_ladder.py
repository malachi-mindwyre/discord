"""
The Circle — Engagement Ladder Cog
Tracks user engagement tiers from lurker to evangelist.
Weekly recalculation based on 7-day activity. DMs on tier transitions.
"""

from __future__ import annotations

import discord
import aiosqlite
import logging
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from typing import Optional

from config import (
    ENGAGEMENT_TIERS_DEFINITION,
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
)
from database import get_user, get_all_users, DB_PATH

logger = logging.getLogger("circle.engagement_ladder")

# Ordered list of tiers from lowest to highest
TIER_ORDER = ["lurker", "newcomer", "casual", "regular", "power_user", "evangelist"]

TIER_EMOJI = {
    "lurker": "👻",
    "newcomer": "🌱",
    "casual": "☕",
    "regular": "🔥",
    "power_user": "⚡",
    "evangelist": "📣",
}

TIER_DISPLAY = {
    "lurker": "Lurker",
    "newcomer": "Newcomer",
    "casual": "Casual",
    "regular": "Regular",
    "power_user": "Power User",
    "evangelist": "Evangelist",
}

# DM messages for tier transitions
TIER_UP_MESSAGES = {
    "newcomer": (
        "You've broken the silence. The Circle notices those who speak.\n"
        "Keep chatting — the path ahead rewards the bold."
    ),
    "casual": (
        "You're becoming a familiar face around here.\n"
        "The Circle values consistency. Don't disappear on us."
    ),
    "regular": (
        "You're part of the furniture now. The Circle depends on people like you.\n"
        "Your presence shapes this place more than you know."
    ),
    "power_user": (
        "You're the backbone of The Circle. The engine that keeps it running.\n"
        "Few reach this level. Fewer stay. Will you?"
    ),
    "evangelist": (
        "You don't just participate — you *recruit*. You spread The Circle.\n"
        "The highest honor. You are the reason we grow. 📣"
    ),
}

TIER_DOWN_MESSAGES = {
    "lurker": "The Circle grows quiet without you. We noticed you've gone silent...",
    "newcomer": "You've been less active lately. The Circle remembers the fire you had.",
    "casual": "Your presence has faded. The regulars are wondering where you went.",
    "regular": "You were a power user. The Circle felt the shift when you slowed down.",
    "power_user": "You were spreading the word. The Circle needs its evangelists back.",
}


async def _get_user_messages_last_7_days(user_id: int) -> int:
    """Count messages from a user in the last 7 days."""
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM messages WHERE user_id = ? AND timestamp > ?",
            (user_id, cutoff),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def _get_user_invites_total(user_id: int) -> int:
    """Get total valid invites for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT invite_count FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def _get_current_tier(user_id: int) -> Optional[str]:
    """Get a user's current engagement tier from the DB."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT tier FROM user_engagement_tier WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def _set_tier(user_id: int, tier: str, msgs_week: int, invites: int):
    """Set a user's engagement tier."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO user_engagement_tier
               (user_id, tier, tier_since, messages_this_week, invites_total)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   tier = ?,
                   tier_since = CASE WHEN tier != ? THEN ? ELSE tier_since END,
                   messages_this_week = ?,
                   invites_total = ?""",
            (user_id, tier, now, msgs_week, invites,
             tier, tier, now, msgs_week, invites),
        )
        await db.commit()


def _calculate_tier(msgs_week: int, invites_total: int) -> str:
    """Determine engagement tier based on weekly messages and total invites."""
    # Check evangelist first (highest tier)
    evang = ENGAGEMENT_TIERS_DEFINITION.get("evangelist", {})
    if msgs_week >= evang.get("msgs_week", 100) and invites_total >= evang.get("invites_min", 3):
        return "evangelist"

    # Check from power_user down to lurker
    for tier_name in reversed(TIER_ORDER[:-1]):  # Skip evangelist, already checked
        tier_def = ENGAGEMENT_TIERS_DEFINITION.get(tier_name, {})
        threshold = tier_def.get("msgs_week", 0)
        if msgs_week >= threshold and tier_name != "lurker":
            return tier_name

    return "lurker"


class EngagementLadder(commands.Cog):
    """Tracks engagement tiers from lurker to evangelist."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.weekly_recalculate.start()

    async def cog_unload(self):
        self.weekly_recalculate.cancel()

    @tasks.loop(hours=168)  # Weekly (7 days)
    async def weekly_recalculate(self):
        """Recalculate all user engagement tiers based on last 7 days."""
        logger.info("🔄 Engagement ladder: starting weekly recalculation")

        all_users = await get_all_users()
        transitions_up = 0
        transitions_down = 0

        for user_data in all_users:
            user_id = user_data["user_id"]
            try:
                msgs_week = await _get_user_messages_last_7_days(user_id)
                invites = await _get_user_invites_total(user_id)
                new_tier = _calculate_tier(msgs_week, invites)
                old_tier = await _get_current_tier(user_id)

                await _set_tier(user_id, new_tier, msgs_week, invites)

                # Handle transitions
                if old_tier and old_tier != new_tier:
                    old_idx = TIER_ORDER.index(old_tier) if old_tier in TIER_ORDER else 0
                    new_idx = TIER_ORDER.index(new_tier)

                    if new_idx > old_idx:
                        transitions_up += 1
                        await self._notify_tier_change(user_id, old_tier, new_tier, up=True)
                    elif new_idx < old_idx:
                        transitions_down += 1
                        await self._notify_tier_change(user_id, old_tier, new_tier, up=False)

            except Exception as e:
                logger.error(f"Engagement ladder error for user {user_id}: {e}")

        logger.info(
            f"✅ Engagement ladder: recalculated {len(all_users)} users. "
            f"⬆️ {transitions_up} promoted, ⬇️ {transitions_down} demoted."
        )

    @weekly_recalculate.before_loop
    async def before_weekly(self):
        await self.bot.wait_until_ready()

    async def _notify_tier_change(self, user_id: int, old_tier: str, new_tier: str, up: bool):
        """DM a user about their tier transition."""
        try:
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            if not user:
                return

            old_emoji = TIER_EMOJI.get(old_tier, "")
            new_emoji = TIER_EMOJI.get(new_tier, "")
            old_display = TIER_DISPLAY.get(old_tier, old_tier)
            new_display = TIER_DISPLAY.get(new_tier, new_tier)

            if up:
                message = TIER_UP_MESSAGES.get(new_tier, "You've moved up. The Circle is watching.")
                embed = discord.Embed(
                    title=f"⬆️ ENGAGEMENT TIER UP",
                    description=(
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{old_emoji} {old_display} → {new_emoji} **{new_display}**\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"{message}"
                    ),
                    color=EMBED_COLOR_ACCENT,
                )
            else:
                message = TIER_DOWN_MESSAGES.get(new_tier, "Your activity has dropped. The Circle notices.")
                embed = discord.Embed(
                    title=f"⬇️ ENGAGEMENT TIER DROP",
                    description=(
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{old_emoji} {old_display} → {new_emoji} **{new_display}**\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"{message}"
                    ),
                    color=EMBED_COLOR_PRIMARY,
                )

            embed.set_footer(text="The Circle • Your engagement shapes your destiny")
            await user.send(embed=embed)

        except (discord.Forbidden, discord.HTTPException):
            # User has DMs disabled or other issue — silently skip
            pass
        except Exception as e:
            logger.error(f"Failed to notify user {user_id} of tier change: {e}")

    @commands.command(name="ladder")
    async def ladder_cmd(self, ctx: commands.Context):
        """Show your current engagement tier and what the next tier requires."""
        user_id = ctx.author.id

        user = await get_user(user_id)
        if not user:
            embed = discord.Embed(
                title="👁️ THE CIRCLE DOES NOT KNOW YOU",
                description="Send some messages first. The Circle is watching.",
                color=EMBED_COLOR_PRIMARY,
            )
            await ctx.send(embed=embed)
            return

        msgs_week = await _get_user_messages_last_7_days(user_id)
        invites = await _get_user_invites_total(user_id)
        current_tier = _calculate_tier(msgs_week, invites)

        # Also update the stored tier while we're at it
        await _set_tier(user_id, current_tier, msgs_week, invites)

        tier_emoji = TIER_EMOJI.get(current_tier, "")
        tier_display = TIER_DISPLAY.get(current_tier, current_tier)
        tier_def = ENGAGEMENT_TIERS_DEFINITION.get(current_tier, {})
        tier_desc = tier_def.get("description", "")

        embed = discord.Embed(
            title="📊 ENGAGEMENT LADDER",
            description=(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "*The Circle measures more than just score.*\n"
                "*It watches how deeply you engage.*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_ACCENT,
        )

        embed.add_field(
            name=f"{tier_emoji} Your Tier: {tier_display}",
            value=f"*{tier_desc}*",
            inline=False,
        )

        embed.add_field(
            name="📈 This Week",
            value=f"Messages: **{msgs_week}**\nTotal Invites: **{invites}**",
            inline=True,
        )

        # Find next tier
        current_idx = TIER_ORDER.index(current_tier) if current_tier in TIER_ORDER else 0
        if current_idx < len(TIER_ORDER) - 1:
            next_tier = TIER_ORDER[current_idx + 1]
            next_def = ENGAGEMENT_TIERS_DEFINITION.get(next_tier, {})
            next_emoji = TIER_EMOJI.get(next_tier, "")
            next_display = TIER_DISPLAY.get(next_tier, next_tier)
            next_msgs = next_def.get("msgs_week", 0)
            msgs_needed = max(0, next_msgs - msgs_week)

            req_text = f"**{next_msgs}** messages/week"
            if "invites_min" in next_def:
                invites_min = next_def["invites_min"]
                req_text += f" + **{invites_min}** total invites"
                if invites < invites_min:
                    req_text += f"\n*(Need {invites_min - invites} more invites)*"

            if msgs_needed > 0:
                req_text += f"\n*(Need {msgs_needed} more messages this week)*"

            embed.add_field(
                name=f"🔜 Next: {next_emoji} {next_display}",
                value=req_text,
                inline=True,
            )
        else:
            embed.add_field(
                name="🏆 MAX TIER",
                value="You are an **Evangelist**. The Circle's highest honor.\n*You don't just play — you spread the word.*",
                inline=True,
            )

        # Show all tiers
        ladder_text = ""
        for tier_name in TIER_ORDER:
            t_def = ENGAGEMENT_TIERS_DEFINITION.get(tier_name, {})
            t_emoji = TIER_EMOJI.get(tier_name, "")
            t_display = TIER_DISPLAY.get(tier_name, tier_name)
            t_msgs = t_def.get("msgs_week", 0)
            marker = " ◀️ **YOU**" if tier_name == current_tier else ""

            req = f"{t_msgs}+ msgs/wk"
            if "invites_min" in t_def:
                req += f" + {t_def['invites_min']}+ invites"

            ladder_text += f"{t_emoji} **{t_display}** — {req}{marker}\n"

        embed.add_field(
            name="🪜 All Tiers",
            value=ladder_text,
            inline=False,
        )

        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="The Circle • Recalculated weekly")

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(EngagementLadder(bot))
