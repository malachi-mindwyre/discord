"""
The Circle — Invite Reminders Cog
Rotating invite reminders 2-3x/week + monthly recruiter race.
"""

from __future__ import annotations

import random
from datetime import datetime, date

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    INVITE_REMINDER_DAYS,
    INVITE_REMINDER_HOUR,
    INVITE_LINK,
    INVITE_REMINDER_TEMPLATES,
    ECONOMY_CURRENCY_EMOJI,
)
from database import DB_PATH, get_top_inviters


class InviteReminders(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._invite_link = INVITE_LINK
        self._last_template_idx = -1
        self.reminder_loop.start()
        self.monthly_race_check.start()

    def cog_unload(self):
        self.reminder_loop.cancel()
        self.monthly_race_check.cancel()

    @commands.command(name="setinvite")
    @commands.has_permissions(administrator=True)
    async def set_invite(self, ctx: commands.Context, link: str = None):
        """Set the server invite link used in reminders."""
        if not link:
            await ctx.send(f"⚫ Current invite link: `{self._invite_link}`\nUsage: `!setinvite <url>`")
            return
        self._invite_link = link
        await ctx.send(f"⚫ Invite link updated to: `{link}`")

    @tasks.loop(hours=1)
    async def reminder_loop(self):
        """Post invite reminders on scheduled days."""
        now = datetime.utcnow()
        if now.weekday() not in INVITE_REMINDER_DAYS:
            return
        if now.hour != INVITE_REMINDER_HOUR:
            return

        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name="general")
            if not channel:
                continue

            # Pick a template (never same as last)
            available = list(range(len(INVITE_REMINDER_TEMPLATES)))
            if self._last_template_idx in available and len(available) > 1:
                available.remove(self._last_template_idx)
            idx = random.choice(available)
            self._last_template_idx = idx

            template = INVITE_REMINDER_TEMPLATES[idx]

            # Gather dynamic data
            top_inviters = await get_top_inviters(1)
            top_inviter = top_inviters[0]["username"] if top_inviters else "nobody yet"
            invite_count = top_inviters[0]["invite_count"] if top_inviters else 0

            # Count recent joins (last 7 days)
            week_ago = (datetime.utcnow() - __import__("datetime").timedelta(days=7)).isoformat()
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM users WHERE joined_at > ?", (week_ago,)
                )
                recent_joins = (await cursor.fetchone())[0]

            text = template.format(
                link=self._invite_link,
                member_count=guild.member_count,
                top_inviter=top_inviter,
                invite_count=invite_count,
                recent_joins=recent_joins,
            )

            try:
                msg = await channel.send(text)
                # Log it
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "INSERT INTO invite_reminders_log (message_id, template_index, posted_at) VALUES (?, ?, ?)",
                        (msg.id, idx, datetime.utcnow().isoformat()),
                    )
                    await db.commit()
            except discord.HTTPException:
                pass

    @reminder_loop.before_loop
    async def before_reminder(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=24)
    async def monthly_race_check(self):
        """Check if it's the 1st of the month — announce race or award winner."""
        today = date.today()

        if today.day == 1:
            # End previous month's race and start new one
            last_month = (today.replace(day=1) - __import__("datetime").timedelta(days=1))
            month_key = last_month.strftime("%Y-%m")

            async with aiosqlite.connect(DB_PATH) as db:
                # Find winner of last month
                cursor = await db.execute(
                    """SELECT user_id, invite_count FROM monthly_invite_race
                       WHERE month = ? ORDER BY invite_count DESC LIMIT 1""",
                    (month_key,),
                )
                winner = await cursor.fetchone()

            for guild in self.bot.guilds:
                channel = discord.utils.get(guild.text_channels, name="general")
                if not channel:
                    continue

                # Announce winner if exists
                if winner and winner[1] > 0:
                    member = guild.get_member(winner[0])
                    if member:
                        # Award coins
                        async with aiosqlite.connect(DB_PATH) as db:
                            await db.execute(
                                """INSERT INTO economy (user_id, coins, total_earned)
                                   VALUES (?, 500, 500)
                                   ON CONFLICT(user_id) DO UPDATE SET
                                   coins = coins + 500, total_earned = total_earned + 500""",
                                (winner[0],),
                            )
                            await db.execute(
                                "UPDATE monthly_invite_race SET winner = 1 WHERE user_id = ? AND month = ?",
                                (winner[0], month_key),
                            )
                            await db.commit()

                        embed = discord.Embed(
                            title="👑 MONTHLY RECRUITER CHAMPION",
                            description=(
                                f"The recruiting race for **{last_month.strftime('%B %Y')}** has ended!\n\n"
                                f"🏆 **{member.mention}** wins with **{winner[1]} invites**!\n"
                                f"💰 Prize: **500** {ECONOMY_CURRENCY_EMOJI}\n\n"
                                f"A new race begins today. Start inviting! `{self._invite_link}`"
                            ),
                            color=EMBED_COLOR_ACCENT,
                        )
                        try:
                            await channel.send(embed=embed)
                        except discord.HTTPException:
                            pass
                else:
                    # Just announce new race
                    try:
                        await channel.send(
                            f"📨 **MONTHLY RECRUITER RACE** has begun!\n"
                            f"Invite the most people this month → win **500** {ECONOMY_CURRENCY_EMOJI} + exclusive role.\n"
                            f"Share: `{self._invite_link}`"
                        )
                    except discord.HTTPException:
                        pass

    @monthly_race_check.before_loop
    async def before_monthly(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(InviteReminders(bot))
