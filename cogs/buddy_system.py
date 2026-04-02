"""
The Circle — Buddy/Mentor System Cog
Auto-pairs new members with active Certified+ mentors.
Both earn 50 pts if mentee sends 10 msgs in 48h.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, date

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    BUDDY_MIN_RANK,
    BUDDY_MENTEE_MSG_GOAL,
    BUDDY_TIME_LIMIT_HOURS,
    BUDDY_REWARD_POINTS,
)
from database import DB_PATH, get_user, update_user_score, unlock_achievement


class BuddySystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.buddy_check.start()

    def cog_unload(self):
        self.buddy_check.cancel()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Assign a buddy to new members after a short delay."""
        if member.bot:
            return

        # Wait a bit for the welcome and onboarding DMs to go first
        import asyncio
        await asyncio.sleep(60)

        guild = member.guild

        # Find eligible mentors: Certified+ rank, active in last 48h, online or idle
        async with aiosqlite.connect(DB_PATH) as db:
            cutoff = (datetime.utcnow() - timedelta(hours=48)).isoformat()
            cursor = await db.execute(
                """SELECT user_id FROM users
                   WHERE current_rank >= ? AND last_active > ? AND user_id != ?""",
                (BUDDY_MIN_RANK, cutoff, member.id),
            )
            eligible = [row[0] for row in await cursor.fetchall()]

        if not eligible:
            return  # No eligible mentors

        # Filter to currently online/idle members
        online_mentors = []
        for uid in eligible:
            m = guild.get_member(uid)
            if m and m.status in (discord.Status.online, discord.Status.idle):
                # Check they're not already mentoring someone actively
                async with aiosqlite.connect(DB_PATH) as db:
                    cursor = await db.execute(
                        "SELECT id FROM buddies WHERE mentor_id = ? AND completed = 0",
                        (uid,),
                    )
                    if not await cursor.fetchone():
                        online_mentors.append(uid)

        if not online_mentors:
            # Fall back to any eligible
            online_mentors = eligible[:5]

        mentor_id = random.choice(online_mentors)
        mentor_member = guild.get_member(mentor_id)
        if not mentor_member:
            return

        # Record the buddy pairing
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO buddies (mentor_id, mentee_id, assigned_at) VALUES (?, ?, ?)",
                (mentor_id, member.id, datetime.utcnow().isoformat()),
            )
            await db.commit()

        # DM the mentor
        try:
            embed = discord.Embed(
                title="⚫ BUDDY ASSIGNMENT",
                description=(
                    f"A new soul has entered The Circle. **{member.display_name}** needs guidance.\n\n"
                    f"**Your mission:** Help them send **{BUDDY_MENTEE_MSG_GOAL} messages** within 48 hours.\n\n"
                    f"**Reward:** You both earn **{BUDDY_REWARD_POINTS} pts** + you get the **Mentor** badge.\n\n"
                    f"Say hi to them. Show them around. The Circle rewards those who guide. 👁️"
                ),
                color=EMBED_COLOR_ACCENT,
            )
            await mentor_member.send(embed=embed)
        except (discord.HTTPException, discord.Forbidden):
            pass

        # DM the mentee
        try:
            embed = discord.Embed(
                title="⚫ YOUR GUIDE IN THE CIRCLE",
                description=(
                    f"**{mentor_member.display_name}** has been assigned as your guide.\n\n"
                    f"They'll help you get started. Feel free to ask them anything!\n\n"
                    f"**Goal:** Send {BUDDY_MENTEE_MSG_GOAL} messages in the next 48 hours "
                    f"and you both earn **{BUDDY_REWARD_POINTS} bonus points**. 🎯"
                ),
                color=EMBED_COLOR_PRIMARY,
            )
            await member.send(embed=embed)
        except (discord.HTTPException, discord.Forbidden):
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track mentee messages for buddy system completion."""
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        async with aiosqlite.connect(DB_PATH) as db:
            # Check if this user is a mentee with an active buddy
            cursor = await db.execute(
                "SELECT id, mentor_id, assigned_at, mentee_msg_count FROM buddies WHERE mentee_id = ? AND completed = 0",
                (user_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return

            buddy_id, mentor_id, assigned_at, msg_count = row
            assigned_time = datetime.fromisoformat(assigned_at)

            # Check if expired
            if datetime.utcnow() - assigned_time > timedelta(hours=BUDDY_TIME_LIMIT_HOURS):
                await db.execute("UPDATE buddies SET completed = -1 WHERE id = ?", (buddy_id,))
                await db.commit()
                return

            # Increment message count
            new_count = msg_count + 1
            await db.execute(
                "UPDATE buddies SET mentee_msg_count = ? WHERE id = ?",
                (new_count, buddy_id),
            )

            # Check if goal reached
            if new_count >= BUDDY_MENTEE_MSG_GOAL:
                await db.execute("UPDATE buddies SET completed = 1 WHERE id = ?", (buddy_id,))
                await db.commit()

                # Award both
                await update_user_score(user_id, BUDDY_REWARD_POINTS)
                await update_user_score(mentor_id, BUDDY_REWARD_POINTS)
                await unlock_achievement(mentor_id, "mentor")

                # Notify
                guild = message.guild
                mentor = guild.get_member(mentor_id)
                try:
                    await message.channel.send(
                        f"🤝 **Buddy mission complete!** {message.author.mention} and "
                        f"{mentor.mention if mentor else 'their mentor'} both earned "
                        f"**{BUDDY_REWARD_POINTS} pts**! The Circle grows stronger."
                    )
                except discord.HTTPException:
                    pass
            else:
                await db.commit()

    @tasks.loop(hours=6)
    async def buddy_check(self):
        """Expire old buddy pairings that didn't complete."""
        cutoff = (datetime.utcnow() - timedelta(hours=BUDDY_TIME_LIMIT_HOURS)).isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE buddies SET completed = -1 WHERE completed = 0 AND assigned_at < ?",
                (cutoff,),
            )
            await db.commit()

    @buddy_check.before_loop
    async def before_buddy_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(BuddySystem(bot))
