"""
The Circle — Welcome Cog
Posts a rich embed in #welcome when someone joins. Keeper's voice.
"""

import discord
from discord.ext import commands

from config import EMBED_COLOR_PRIMARY
from ranks import RANK_BY_TIER
from database import get_or_create_user


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        # Create user in database
        await get_or_create_user(member.id, str(member))

        # Assign starting rank role (Rookie I)
        starting_rank = RANK_BY_TIER.get(1)
        if starting_rank:
            role = discord.utils.get(member.guild.roles, name=starting_rank.name)
            if role:
                try:
                    await member.add_roles(role, reason="New member — Rookie I")
                except discord.HTTPException:
                    pass

        # Find #welcome channel
        welcome_channel = discord.utils.get(member.guild.text_channels, name="welcome")
        if not welcome_channel:
            return

        # Find key channels for mentions
        info_channel = discord.utils.get(member.guild.text_channels, name="info")
        general_channel = discord.utils.get(member.guild.text_channels, name="general")
        info_mention = info_channel.mention if info_channel else "#info"
        general_mention = general_channel.mention if general_channel else "#general"

        embed = discord.Embed(
            title="⚫ ANOTHER SOUL ENTERS THE CIRCLE",
            description=(
                f"Welcome, {member.mention}. Your journey begins now.\n\n"
                f"You enter as **Rookie I** — but that can change.\n\n"
                f"**Here's what you need to know:**\n\n"
                f"💬 Talk in any channel → earn points\n"
                f"↩️ Reply to people → **3x points**\n"
                f"🏷️ Tag someone → **4x points**\n"
                f"📸 Share media → **+5 bonus**\n"
                f"📈 Points = rank ups = new name colors\n\n"
                f"**The more you interact with others, the faster you climb.**\n\n"
                f"📖 Read {info_mention} for the **full guide** — ranks, scoring, commands, everything\n"
                f"💬 Jump into {general_mention} and say hi\n"
                f"🤖 Type `!rank` anytime to check your progress\n\n"
                f"The Circle watches. 👁️"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="The Circle • Your rank is your legacy")

        try:
            await welcome_channel.send(embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
