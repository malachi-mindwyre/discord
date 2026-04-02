"""
The Circle — Onboarding Cog
Enhanced welcome DM flow on join + 24h check-in DM.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    ONBOARDING_DM_DELAY_SECONDS,
    ONBOARDING_CHECKIN_HOURS,
)


class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track who we've sent check-ins to (persists per restart)
        self._pending_checkins: dict[int, datetime] = {}  # user_id -> join_time
        self.checkin_loop.start()

    def cog_unload(self):
        self.checkin_loop.cancel()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        # Wait a few seconds so the welcome embed lands first
        await asyncio.sleep(ONBOARDING_DM_DELAY_SECONDS)

        # Schedule 24h check-in
        self._pending_checkins[member.id] = datetime.utcnow()

        # Build the welcome DM
        guild = member.guild
        info_ch = discord.utils.get(guild.text_channels, name="info")
        general_ch = discord.utils.get(guild.text_channels, name="general")
        intro_ch = discord.utils.get(guild.text_channels, name="introductions")

        info_mention = info_ch.mention if info_ch else "#info"
        general_mention = general_ch.mention if general_ch else "#general"
        intro_mention = intro_ch.mention if intro_ch else "#introductions"

        embed = discord.Embed(
            title="⚫ WELCOME TO THE CIRCLE",
            description=(
                f"Hey {member.display_name}, glad you're here.\n\n"
                f"The Circle is a social server where **everything you do earns points**. "
                f"Talk, reply, tag people, share media — it all counts toward your rank.\n\n"
                f"**Here's your quick-start guide:**\n\n"
                f"1️⃣ Read {info_mention} for the full breakdown\n"
                f"2️⃣ Post an intro in {intro_mention} → **+50 pts + badge!**\n"
                f"3️⃣ Jump into {general_mention} and say hi\n"
                f"4️⃣ Reply to someone → **3x points**\n"
                f"5️⃣ Tag someone → **4x points**\n\n"
                f"You start as **Rookie I**. The climb to Immortal is long — "
                f"but every message gets you closer.\n\n"
                f"Type `!rank` anytime to check your progress. 🏆"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else member.display_avatar.url)
        embed.set_footer(text="The Circle • Your rank is your legacy")

        try:
            await member.send(embed=embed)
        except (discord.HTTPException, discord.Forbidden):
            pass  # DMs disabled

    @tasks.loop(minutes=30)
    async def checkin_loop(self):
        """Check for members who joined 24h ago and send a check-in DM."""
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=ONBOARDING_CHECKIN_HOURS)
        to_remove = []

        for user_id, join_time in self._pending_checkins.items():
            if join_time > cutoff:
                continue  # Not yet 24h

            to_remove.append(user_id)

            for guild in self.bot.guilds:
                member = guild.get_member(user_id)
                if not member:
                    continue

                general_ch = discord.utils.get(guild.text_channels, name="general")
                general_mention = general_ch.mention if general_ch else "#general"

                embed = discord.Embed(
                    title="⚫ HOW'S YOUR FIRST DAY?",
                    description=(
                        f"Hey {member.display_name}, you've been in The Circle for 24 hours now.\n\n"
                        f"**Here's what you might have missed:**\n"
                        f"💬 Conversations happening in {general_mention}\n"
                        f"🔥 Your daily streak starts building when you post\n"
                        f"📈 Every reply and tag earns bonus points\n\n"
                        f"**Quick tip:** Reply to someone's message for an instant **3x score boost**.\n\n"
                        f"The Circle rewards those who engage. Your rank is waiting. 👁️"
                    ),
                    color=EMBED_COLOR_ACCENT,
                )
                embed.set_footer(text="The Circle • Keep climbing")

                try:
                    await member.send(embed=embed)
                except (discord.HTTPException, discord.Forbidden):
                    pass
                break

        for uid in to_remove:
            self._pending_checkins.pop(uid, None)

    @checkin_loop.before_loop
    async def before_checkin(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))
