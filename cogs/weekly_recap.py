"""
The Circle — Weekly Recap Cog (Sunday Ceremony)
Multi-embed ceremony every Sunday: stats, streaks, social bonds, faction standings.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks

from config import (
    WEEKLY_RECAP_DAY,
    WEEKLY_RECAP_HOUR,
    WEEKLY_RECAP_CHANNEL,
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
)
import aiosqlite
from database import (
    DB_PATH,
    get_weekly_stats,
    get_top_streaks,
    get_weekly_voice_minutes,
    get_weekly_best_friend_pair,
    get_weekly_achievements_count,
    get_weekly_faction_standings,
    get_user,
    get_streak,
)
from ranks import RANK_BY_TIER, get_rank_for_score
from dm_coordinator import record_dm as global_record_dm

logger = logging.getLogger("circle.weekly_recap")


class WeeklyRecap(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.post_weekly_recap.start()

    def cog_unload(self):
        self.post_weekly_recap.cancel()

    @tasks.loop(hours=168)  # Weekly
    async def post_weekly_recap(self):
        """Post the Sunday Ceremony — a multi-embed weekly summary."""
        stats = await get_weekly_stats()
        top_streaks = await get_top_streaks(5)
        voice_minutes = await get_weekly_voice_minutes()
        best_pair = await get_weekly_best_friend_pair()
        badges_count = await get_weekly_achievements_count()
        faction_standings = await get_weekly_faction_standings()

        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name=WEEKLY_RECAP_CHANNEL)
            if not channel:
                continue

            embeds = []

            # ── Embed 1: Stats Overview ───────────────────────────────────
            embed1 = discord.Embed(
                title="📊 SUNDAY CEREMONY — THE CIRCLE",
                description=(
                    "The Circle never sleeps. Here's what happened this week.\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=EMBED_COLOR_ACCENT,
            )

            embed1.add_field(
                name="📈 THIS WEEK",
                value=(
                    f"💬 **{stats['total_messages']:,}** messages sent\n"
                    f"👥 **{stats['active_users']}** active members\n"
                    f"❤️ **{stats['total_reactions']:,}** reactions given\n"
                    f"🎤 **{voice_minutes / 60:.1f}** hours in voice\n"
                    f"🏅 **{badges_count}** badges unlocked"
                ),
                inline=False,
            )

            if stats["top_poster"]:
                tp = stats["top_poster"]
                embed1.add_field(
                    name="👑 TOP POSTER",
                    value=f"**{tp['username']}** — {tp['week_points']:,.0f} pts ({tp['msg_count']} msgs)",
                    inline=True,
                )

            if stats["most_social"]:
                ms = stats["most_social"]
                embed1.add_field(
                    name="🗣️ MOST SOCIAL",
                    value=f"**{ms['username']}** — {ms['reply_count']} replies",
                    inline=True,
                )

            if stats["biggest_climber"]:
                bc = stats["biggest_climber"]
                embed1.add_field(
                    name="🚀 BIGGEST CLIMBER",
                    value=f"**{bc['username']}** — gained {bc['tiers_gained']} rank(s)",
                    inline=True,
                )

            if stats["top_poster"] and stats["total_messages"] > 0:
                msgs_per_person = stats["total_messages"] / max(stats["active_users"], 1)
                embed1.add_field(
                    name="📱 FUN STAT",
                    value=f"Average member sent **{msgs_per_person:.0f}** messages this week.",
                    inline=False,
                )

            embeds.append(embed1)

            # ── Embed 2: Streak Hall ──────────────────────────────────────
            if top_streaks:
                streak_lines = []
                medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
                for i, s in enumerate(top_streaks):
                    medal = medals[i] if i < len(medals) else f"#{i+1}"
                    streak_lines.append(f"{medal} **{s['username']}** — {s['current_streak']} days")

                # Get paired streaks info
                import aiosqlite
                from database import DB_PATH
                paired_lines = []
                try:
                    async with aiosqlite.connect(DB_PATH) as db:
                        db.row_factory = aiosqlite.Row
                        cursor = await db.execute(
                            """SELECT user_a, user_b, current_streak
                               FROM paired_streaks
                               WHERE status = 'active' AND current_streak > 0
                               ORDER BY current_streak DESC LIMIT 3"""
                        )
                        for row in await cursor.fetchall():
                            member_a = guild.get_member(row["user_a"])
                            member_b = guild.get_member(row["user_b"])
                            name_a = member_a.display_name if member_a else f"User#{row['user_a']}"
                            name_b = member_b.display_name if member_b else f"User#{row['user_b']}"
                            paired_lines.append(f"🔗 **{name_a}** & **{name_b}** — {row['current_streak']} days")
                except Exception:
                    pass

                embed2 = discord.Embed(
                    title="🔥 STREAK HALL",
                    description="━━━━━━━━━━━━━━━━━━━━━",
                    color=EMBED_COLOR_ACCENT,
                )
                embed2.add_field(
                    name="🏆 Top Daily Streaks",
                    value="\n".join(streak_lines),
                    inline=False,
                )
                if paired_lines:
                    embed2.add_field(
                        name="🔗 Top Paired Streaks",
                        value="\n".join(paired_lines),
                        inline=False,
                    )
                embeds.append(embed2)

            # ── Embed 3: Social Bonds (suppress if empty/weak) ────────────
            social_parts = []
            if best_pair:
                user_a, user_b, score = best_pair
                # Only show best friend pair if score is meaningful (>= 25)
                if score >= 25:
                    member_a = guild.get_member(user_a)
                    member_b = guild.get_member(user_b)
                    name_a = member_a.display_name if member_a else f"User#{user_a}"
                    name_b = member_b.display_name if member_b else f"User#{user_b}"
                    social_parts.append(f"🤝 **Best Friends of the Week:** {name_a} & {name_b} (score: {score:.1f})")

            voice_hours = voice_minutes / 60
            # Only show voice stats if meaningful (>= 0.5 hours)
            if voice_hours >= 0.5:
                social_parts.append(f"🎤 **{voice_hours:.1f} hours** spent together in voice")

            if social_parts:
                embed3 = discord.Embed(
                    title="🤝 SOCIAL BONDS",
                    description="━━━━━━━━━━━━━━━━━━━━━\n\n" + "\n\n".join(social_parts),
                    color=EMBED_COLOR_PRIMARY,
                )
                embeds.append(embed3)

            # ── Embed 4: Faction Standings (suppress if < 2 active teams) ──
            if faction_standings:
                faction_teams_with_activity = sum(1 for f in faction_standings if f.get("total_score", 0) > 0)

                if faction_teams_with_activity >= 2:
                    faction_emojis = {"Inferno": "🔴", "Frost": "🔵", "Venom": "🟢", "Volt": "🟡"}
                    faction_lines = []
                    for i, f in enumerate(faction_standings):
                        if f.get("total_score", 0) <= 0:
                            continue
                        emoji = faction_emojis.get(f["team_name"], "⚔️")
                        prefix = "👑" if i == 0 else f"#{i+1}"
                        faction_lines.append(f"{prefix} {emoji} **{f['team_name']}** — {f['total_score']:,.0f} pts")

                    if faction_lines:
                        embed4 = discord.Embed(
                            title="⚔️ FACTION STANDINGS",
                            description="━━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(faction_lines),
                            color=EMBED_COLOR_ACCENT,
                        )
                        embeds.append(embed4)

            # ── Send all embeds ───────────────────────────────────────────
            for embed in embeds:
                try:
                    await channel.send(embed=embed)
                except discord.HTTPException:
                    pass

            # Sign-off
            try:
                await channel.send("*The Circle has spoken. See you next Sunday.* ⚫")
            except discord.HTTPException:
                pass

            # ── Personal Highlight DMs ───────────────────────────────────
            await self._send_personal_highlights(guild)

    async def _send_personal_highlights(self, guild: discord.Guild):
        """Send personalized weekly highlight DMs to active users."""
        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                # Get all users active this week with their weekly points
                cursor = await db.execute(
                    """SELECT ds.user_id,
                              SUM(ds.points) as week_points,
                              COUNT(DISTINCT ds.date) as active_days,
                              MAX(ds.points) as best_day_points,
                              (SELECT date FROM daily_scores WHERE user_id = ds.user_id
                               ORDER BY points DESC LIMIT 1) as best_day
                       FROM daily_scores ds
                       WHERE ds.date >= ?
                       GROUP BY ds.user_id
                       ORDER BY week_points DESC""",
                    (week_ago[:10],),
                )
                active_users = await cursor.fetchall()

            dm_count = 0
            for row in active_users:
                if dm_count >= 50:  # Safety cap
                    break

                member = guild.get_member(row["user_id"])
                if not member or member.bot:
                    continue

                user_data = await get_user(row["user_id"])
                if not user_data:
                    continue

                streak_data = await get_streak(row["user_id"])
                rank = RANK_BY_TIER.get(user_data["current_rank"])
                rank_name = rank.name if rank else "Unknown"

                embed = discord.Embed(
                    title="📊 YOUR WEEKLY HIGHLIGHTS",
                    description="Here's how you did in The Circle this week.",
                    color=EMBED_COLOR_ACCENT,
                )
                embed.add_field(
                    name="📈 This Week",
                    value=(
                        f"**{row['week_points']:,.0f}** points earned\n"
                        f"**{row['active_days']}** active days\n"
                        f"Best day: **{row['best_day_points']:,.0f}** pts"
                    ),
                    inline=True,
                )
                embed.add_field(
                    name="🏷️ Status",
                    value=(
                        f"Rank: **{rank_name}**\n"
                        f"Score: **{user_data['total_score']:,.0f}** pts\n"
                        f"Streak: **{streak_data['current_streak']}** days 🔥"
                    ),
                    inline=True,
                )
                embed.set_footer(text="The Circle sees your effort. Keep it up.")

                try:
                    from dm_coordinator import get_dm_optout_view
                    await member.send(embed=embed, view=get_dm_optout_view())
                    await global_record_dm(row["user_id"], "weekly_recap")
                    dm_count += 1
                    await asyncio.sleep(1)  # Rate limit protection
                except (discord.HTTPException, discord.Forbidden):
                    pass  # DMs disabled

            logger.info("Sent %d personal highlight DMs", dm_count)

        except Exception as e:
            logger.error("Failed to send personal highlights: %s", e)

    @post_weekly_recap.before_loop
    async def before_recap(self):
        """Wait until the target day and hour."""
        await self.bot.wait_until_ready()
        now = datetime.utcnow()
        days_ahead = WEEKLY_RECAP_DAY - now.weekday()
        if days_ahead < 0 or (days_ahead == 0 and now.hour >= WEEKLY_RECAP_HOUR):
            days_ahead += 7
        target = (now + timedelta(days=days_ahead)).replace(
            hour=WEEKLY_RECAP_HOUR, minute=0, second=0, microsecond=0
        )
        wait_seconds = (target - now).total_seconds()
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

    @commands.command(name="recap")
    @commands.has_permissions(administrator=True)
    async def force_recap(self, ctx: commands.Context):
        """Force post a weekly recap now. Admin only."""
        stats = await get_weekly_stats()
        if stats["total_messages"] == 0:
            await ctx.send("⚫ No data to recap yet. The Circle needs more activity.")
            return
        await self.post_weekly_recap()
        await ctx.send("⚫ Sunday Ceremony posted.")


async def setup(bot: commands.Bot):
    await bot.add_cog(WeeklyRecap(bot))
