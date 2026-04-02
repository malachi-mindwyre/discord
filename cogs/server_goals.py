"""
The Circle — Server Goals Cog
Member milestones + weekly community message goals with progress tracking.
"""

from __future__ import annotations

from datetime import datetime, date, timedelta

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    MEMBER_MILESTONES,
    WEEKLY_GOAL_MESSAGE_TARGET,
    ECONOMY_CURRENCY_EMOJI,
)
from database import DB_PATH
from ranks import make_progress_bar


class ServerGoals(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.milestone_check.start()
        self.weekly_goal_update.start()

    def cog_unload(self):
        self.milestone_check.cancel()
        self.weekly_goal_update.cancel()

    # ─── Member Milestones ─────────────────────────────────────────────────

    @tasks.loop(hours=1)
    async def milestone_check(self):
        """Check if server has hit any member milestones."""
        for guild in self.bot.guilds:
            member_count = guild.member_count
            for threshold, reward_info in sorted(MEMBER_MILESTONES.items()):
                if member_count < threshold:
                    break

                milestone_key = f"members_{threshold}"
                async with aiosqlite.connect(DB_PATH) as db:
                    cursor = await db.execute(
                        "SELECT rewarded FROM server_milestones WHERE milestone_key = ?",
                        (milestone_key,),
                    )
                    row = await cursor.fetchone()
                    if row and row[0]:
                        continue  # Already rewarded

                    # Record and reward
                    await db.execute(
                        """INSERT INTO server_milestones (milestone_key, reached_at, rewarded)
                           VALUES (?, ?, 1)
                           ON CONFLICT(milestone_key) DO UPDATE SET reached_at = ?, rewarded = 1""",
                        (milestone_key, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
                    )
                    await db.commit()

                # Award coins if applicable
                coins = reward_info.get("coins", 0)
                if coins > 0:
                    async with aiosqlite.connect(DB_PATH) as db:
                        cursor = await db.execute("SELECT user_id FROM users")
                        all_users = await cursor.fetchall()
                        for (uid,) in all_users:
                            await db.execute(
                                """INSERT INTO economy (user_id, coins, total_earned)
                                   VALUES (?, ?, ?)
                                   ON CONFLICT(user_id) DO UPDATE SET
                                   coins = coins + ?, total_earned = total_earned + ?""",
                                (uid, coins, coins, coins, coins),
                            )
                        await db.commit()

                # Announce
                channel = discord.utils.get(guild.text_channels, name="general")
                if channel:
                    embed = discord.Embed(
                        title=f"🎉 MILESTONE: {threshold} MEMBERS!",
                        description=(
                            f"The Circle has reached **{threshold} members**!\n\n"
                            f"🎁 **Reward:** {reward_info['reward']}\n\n"
                            f"The Circle grows stronger. 🔥"
                        ),
                        color=EMBED_COLOR_ACCENT,
                    )
                    try:
                        await channel.send(embed=embed)
                    except discord.HTTPException:
                        pass

    @milestone_check.before_loop
    async def before_milestone(self):
        await self.bot.wait_until_ready()

    # ─── Weekly Community Goal ─────────────────────────────────────────────

    @tasks.loop(hours=6)
    async def weekly_goal_update(self):
        """Post/update weekly community goal progress."""
        now = datetime.utcnow()

        # Start new goal on Monday
        if now.weekday() == 0 and now.hour < 6:
            await self._start_weekly_goal()
            return

        # Post progress updates
        week_key = self._get_week_key()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT target_value, current_value, completed FROM weekly_goals WHERE week = ? AND target_type = 'messages'",
                (week_key,),
            )
            row = await cursor.fetchone()

        if not row:
            return

        target, current, completed = row

        # Update current message count
        week_start = self._get_week_start().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE timestamp > ?", (week_start,)
            )
            actual_count = (await cursor.fetchone())[0]
            await db.execute(
                "UPDATE weekly_goals SET current_value = ? WHERE week = ? AND target_type = 'messages'",
                (actual_count, week_key),
            )

            # Check if goal just completed
            if actual_count >= target and not completed:
                await db.execute(
                    "UPDATE weekly_goals SET completed = 1 WHERE week = ? AND target_type = 'messages'",
                    (week_key,),
                )
                await db.commit()

                # Announce completion
                for guild in self.bot.guilds:
                    channel = discord.utils.get(guild.text_channels, name="general")
                    if channel:
                        try:
                            await channel.send(
                                f"🎉 **WEEKLY GOAL COMPLETE!** The Circle hit **{target:,} messages** this week! "
                                f"Everyone benefits. The grind pays off. 🔥"
                            )
                        except discord.HTTPException:
                            pass
            else:
                await db.commit()

    async def _start_weekly_goal(self):
        """Create a new weekly goal and announce it."""
        week_key = self._get_week_key()
        target = WEEKLY_GOAL_MESSAGE_TARGET

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id FROM weekly_goals WHERE week = ? AND target_type = 'messages'",
                (week_key,),
            )
            if await cursor.fetchone():
                return  # Already created

            await db.execute(
                "INSERT INTO weekly_goals (week, target_type, target_value) VALUES (?, 'messages', ?)",
                (week_key, target),
            )
            await db.commit()

        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name="general")
            if channel:
                progress = make_progress_bar(0.0, 10)
                embed = discord.Embed(
                    title="📊 THIS WEEK'S COMMUNITY GOAL",
                    description=(
                        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"**Target:** {target:,} total messages this week\n"
                        f"**Reward:** 2x points weekend for EVERYONE\n\n"
                        f"**Progress:** {progress}\n\n"
                        f"Every message counts. Tag a friend. 🎯"
                    ),
                    color=EMBED_COLOR_PRIMARY,
                )
                try:
                    await channel.send(embed=embed)
                except discord.HTTPException:
                    pass

    @weekly_goal_update.before_loop
    async def before_weekly_goal(self):
        await self.bot.wait_until_ready()

    @commands.command(name="goal")
    async def goal_cmd(self, ctx: commands.Context):
        """Check this week's community goal progress."""
        week_key = self._get_week_key()
        week_start = self._get_week_start().isoformat()

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT target_value, completed FROM weekly_goals WHERE week = ? AND target_type = 'messages'",
                (week_key,),
            )
            row = await cursor.fetchone()

            cursor2 = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE timestamp > ?", (week_start,)
            )
            current = (await cursor2.fetchone())[0]

        if not row:
            await ctx.send("⚫ No community goal this week.")
            return

        target, completed = row
        pct = min(current / target, 1.0) if target > 0 else 0
        progress = make_progress_bar(pct, 10)

        status = "✅ **COMPLETED!**" if completed else f"**{current:,} / {target:,}**"

        embed = discord.Embed(
            title="📊 WEEKLY COMMUNITY GOAL",
            description=(
                f"**Target:** {target:,} messages\n"
                f"**Progress:** {progress}\n"
                f"**Status:** {status}"
            ),
            color=EMBED_COLOR_ACCENT if completed else EMBED_COLOR_PRIMARY,
        )
        await ctx.send(embed=embed)

    @staticmethod
    def _get_week_key() -> str:
        today = date.today()
        return today.isocalendar()[0:2].__repr__()  # e.g. "(2026, 14)"

    @staticmethod
    def _get_week_start() -> datetime:
        today = date.today()
        return datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerGoals(bot))
