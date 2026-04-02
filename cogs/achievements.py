"""
The Circle — Achievements Cog
One-time badge unlocks for milestones. Checked on every scored message.
"""

from __future__ import annotations

import discord
from discord.ext import commands

from config import ACHIEVEMENTS, EMBED_COLOR_ACCENT, EXCLUDED_CHANNELS
from database import (
    unlock_achievement,
    get_user_achievements,
    count_user_achievements,
    get_user,
    get_streak,
    get_user_total_reactions,
    get_user_voice_minutes,
)


class AchievementChecker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Cache to avoid repeated DB checks per message
        self._checked_this_session: dict[int, set] = {}

    async def check_achievements(self, user_id: int, guild: discord.Guild, channel: discord.TextChannel):
        """Check all achievement conditions for a user. Call after scoring a message."""
        user = await get_user(user_id)
        if not user:
            return

        already_unlocked = set(await get_user_achievements(user_id))
        newly_unlocked = []

        score = user["total_score"]
        rank = user["current_rank"]
        invites = user["invite_count"]

        # ─── Message-based ─────────────────────────────────────────
        if "first_message" not in already_unlocked:
            newly_unlocked.append("first_message")

        # ─── Score milestones ──────────────────────────────────────
        score_checks = [
            ("score_1000", 1000),
            ("score_10000", 10000),
            ("score_100000", 100000),
        ]
        for key, threshold in score_checks:
            if key not in already_unlocked and score >= threshold:
                newly_unlocked.append(key)

        # ─── Rank milestones ───────────────────────────────────────
        rank_checks = [
            ("rank_regular", 11),
            ("rank_certified", 21),
            ("rank_respected", 31),
            ("rank_veteran", 41),
            ("rank_og", 51),
            ("rank_elite", 61),
            ("rank_legend", 71),
            ("rank_icon", 81),
            ("rank_immortal", 91),
        ]
        for key, min_tier in rank_checks:
            if key not in already_unlocked and rank >= min_tier:
                newly_unlocked.append(key)

        # ─── Streak milestones ─────────────────────────────────────
        streak_data = await get_streak(user_id)
        streak = streak_data["current_streak"]
        streak_checks = [
            ("streak_3", 3),
            ("streak_7", 7),
            ("streak_14", 14),
            ("streak_30", 30),
            ("streak_100", 100),
        ]
        for key, threshold in streak_checks:
            if key not in already_unlocked and streak >= threshold:
                newly_unlocked.append(key)

        # ─── Invite milestones ─────────────────────────────────────
        invite_checks = [
            ("invite_1", 1),
            ("invite_5", 5),
            ("invite_25", 25),
        ]
        for key, threshold in invite_checks:
            if key not in already_unlocked and invites >= threshold:
                newly_unlocked.append(key)

        # ─── Reaction milestones ───────────────────────────────────
        total_reactions = await get_user_total_reactions(user_id)
        reaction_checks = [
            ("reactions_100", 100),
            ("reactions_1000", 1000),
        ]
        for key, threshold in reaction_checks:
            if key not in already_unlocked and total_reactions >= threshold:
                newly_unlocked.append(key)

        # ─── Voice milestones ──────────────────────────────────────
        voice_minutes = await get_user_voice_minutes(user_id)
        voice_checks = [
            ("voice_60", 60),
            ("voice_600", 600),
        ]
        for key, threshold in voice_checks:
            if key not in already_unlocked and voice_minutes >= threshold:
                newly_unlocked.append(key)

        # ─── Message stat milestones (approximate via DB) ──────────
        import aiosqlite
        from database import DB_PATH
        async with aiosqlite.connect(DB_PATH) as db:
            # Media posts
            cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE user_id = ? AND has_media = 1", (user_id,)
            )
            media_count = (await cursor.fetchone())[0]
            if "media_first" not in already_unlocked and media_count >= 1:
                newly_unlocked.append("media_first")
            if "media_50" not in already_unlocked and media_count >= 50:
                newly_unlocked.append("media_50")

            # Replies
            cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE user_id = ? AND is_reply = 1", (user_id,)
            )
            reply_count = (await cursor.fetchone())[0]
            if "replies_50" not in already_unlocked and reply_count >= 50:
                newly_unlocked.append("replies_50")
            if "replies_500" not in already_unlocked and reply_count >= 500:
                newly_unlocked.append("replies_500")

            # Tags
            cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE user_id = ? AND has_mention = 1", (user_id,)
            )
            tag_count = (await cursor.fetchone())[0]
            if "tags_50" not in already_unlocked and tag_count >= 50:
                newly_unlocked.append("tags_50")

        # ─── Unlock and announce ───────────────────────────────────
        for key in newly_unlocked:
            was_new = await unlock_achievement(user_id, key)
            if was_new and key in ACHIEVEMENTS:
                await self._announce_achievement(guild, channel, user_id, key)

    async def _announce_achievement(self, guild: discord.Guild, channel: discord.TextChannel,
                                    user_id: int, achievement_key: str):
        """Announce an achievement unlock."""
        member = guild.get_member(user_id)
        if not member:
            return

        emoji, name, description = ACHIEVEMENTS[achievement_key]
        total = await count_user_achievements(user_id)

        embed = discord.Embed(
            title="🏅 ACHIEVEMENT UNLOCKED",
            description=(
                f"{emoji} **{name}**\n"
                f"*{description}*\n\n"
                f"{member.mention} now has **{total}** badge(s)"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    @commands.command(name="badges")
    async def badges_cmd(self, ctx: commands.Context, member: discord.Member = None):
        """View your or someone's achievement badges."""
        target = member or ctx.author
        unlocked = await get_user_achievements(target.id)
        total_possible = len(ACHIEVEMENTS)

        if not unlocked:
            await ctx.send(f"⚫ {target.display_name} has no badges yet. Start earning them!")
            return

        lines = []
        for key in unlocked:
            if key in ACHIEVEMENTS:
                emoji, name, description = ACHIEVEMENTS[key]
                lines.append(f"{emoji} **{name}** — *{description}*")

        # Show locked ones too
        locked_count = total_possible - len(unlocked)

        embed = discord.Embed(
            title=f"🏅 {target.display_name}'s Badges ({len(unlocked)}/{total_possible})",
            description="\n".join(lines),
            color=EMBED_COLOR_ACCENT,
        )
        if locked_count > 0:
            embed.set_footer(text=f"{locked_count} more badges to unlock...")
        else:
            embed.set_footer(text="ALL BADGES UNLOCKED. You absolute legend.")

        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AchievementChecker(bot))
