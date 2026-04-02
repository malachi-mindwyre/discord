"""
The Circle — Member Profiles Cog
Rich !profile command with stats, badges, bio, team, and customization.
"""

from __future__ import annotations

from datetime import datetime

import aiosqlite
import discord
from discord.ext import commands

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    ECONOMY_CURRENCY_EMOJI,
    ACHIEVEMENTS,
    DISPLAY_TITLES,
)
from database import (
    DB_PATH,
    get_user,
    get_or_create_user,
    get_user_achievements,
    get_user_voice_minutes,
    get_user_total_reactions,
    get_streak,
)
from ranks import RANK_BY_TIER, get_rank_for_score, get_next_rank, get_progress_to_next, make_progress_bar


class Profiles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="profile")
    async def profile_cmd(self, ctx: commands.Context, member: discord.Member = None):
        """View your (or someone's) full profile."""
        target = member or ctx.author
        user = await get_or_create_user(target.id, str(target))

        rank = RANK_BY_TIER.get(user["current_rank"])
        next_rank = get_next_rank(user["current_rank"])
        progress = get_progress_to_next(user["total_score"], user["current_rank"])

        # Get additional data
        streak_data = await get_streak(target.id)
        voice_mins = await get_user_voice_minutes(target.id)
        total_reactions = await get_user_total_reactions(target.id)
        achievements = await get_user_achievements(target.id)

        # Economy
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT coins FROM economy WHERE user_id = ?", (target.id,)
            )
            row = await cursor.fetchone()
            coins = row[0] if row else 0

            # Profile customization
            cursor = await db.execute(
                "SELECT bio, accent_color, banner_url FROM profiles WHERE user_id = ?", (target.id,)
            )
            profile = await cursor.fetchone()
            bio = profile[0] if profile and profile[0] else ""
            accent_color = profile[1] if profile and profile[1] else ""
            banner_url = profile[2] if profile and profile[2] else ""

            # Faction
            cursor = await db.execute(
                "SELECT team_name FROM factions WHERE user_id = ?", (target.id,)
            )
            faction = await cursor.fetchone()
            team_name = faction[0] if faction else None

            # Message count
            cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE user_id = ?", (target.id,)
            )
            msg_count = (await cursor.fetchone())[0]

        # Prestige level
        prestige_level = 0
        async with aiosqlite.connect(DB_PATH) as db2:
            cursor2 = await db2.execute(
                "SELECT prestige_level FROM prestige WHERE user_id = ?", (target.id,)
            )
            prow = await cursor2.fetchone()
            if prow:
                prestige_level = prow[0]

        # Auto-derive display title from achievements
        display_title = None
        # Check in priority order (highest-value titles first)
        title_priority = ["rank_immortal", "rank_legend", "score_100000", "streak_100",
                          "event_purge", "event_circle_games", "event_community"]
        for key in title_priority:
            if key in achievements and key in DISPLAY_TITLES:
                display_title = DISPLAY_TITLES[key]
                break

        # Build embed
        embed_color = int(accent_color, 16) if accent_color else (rank.color if rank else EMBED_COLOR_PRIMARY)
        embed = discord.Embed(
            title=f"👁️ {target.display_name}'s PROFILE",
            color=embed_color,
        )

        if display_title:
            embed.description = f"{display_title['emoji']} *{display_title['title']}*"
            if bio:
                embed.description += f"\n\n*{bio}*"
        elif bio:
            embed.description = f"*{bio}*"

        # Core stats
        rank_value = f"**{rank.name}**" if rank else "Unknown"
        if prestige_level > 0:
            rank_value += f" ✨P{prestige_level}"
        embed.add_field(name="🏷️ Rank", value=rank_value, inline=True)
        embed.add_field(name="🏆 Score", value=f"**{user['total_score']:,.0f}** pts", inline=True)
        embed.add_field(name=f"{ECONOMY_CURRENCY_EMOJI} Coins", value=f"**{coins:,}**", inline=True)

        # Progress
        if next_rank:
            embed.add_field(
                name="📊 Progress",
                value=f"{make_progress_bar(progress)}\nNext: **{next_rank.name}** ({next_rank.threshold:,.0f} pts)",
                inline=False,
            )

        # Activity
        embed.add_field(name="💬 Messages", value=f"**{msg_count:,}**", inline=True)
        embed.add_field(name="🔥 Streak", value=f"**{streak_data['current_streak']}** days", inline=True)
        embed.add_field(name="📨 Invites", value=f"**{user['invite_count']}**", inline=True)

        embed.add_field(name="🎤 Voice Time", value=f"**{voice_mins:.0f}** min", inline=True)
        embed.add_field(name="❤️ Reactions", value=f"**{total_reactions}**", inline=True)

        # Team
        if team_name:
            from config import FACTION_TEAMS
            team = FACTION_TEAMS.get(team_name, {})
            embed.add_field(
                name="⚔️ Faction",
                value=f"{team.get('emoji', '')} **{team_name}** — *{team.get('motto', '')}*",
                inline=True,
            )

        # Badges (show up to 15)
        if achievements:
            badge_text = ""
            for key in achievements[:15]:
                if key in ACHIEVEMENTS:
                    emoji, name, _ = ACHIEVEMENTS[key]
                    badge_text += f"{emoji} "
            if len(achievements) > 15:
                badge_text += f"(+{len(achievements)-15} more)"
            embed.add_field(name=f"🏅 Badges ({len(achievements)})", value=badge_text, inline=False)

        # Tagline
        if rank:
            embed.add_field(name="", value=f"*\"{rank.tagline}\"*", inline=False)

        # Thumbnail and banner
        embed.set_thumbnail(url=target.display_avatar.url)
        if banner_url:
            embed.set_image(url=banner_url)

        # Join date
        embed.set_footer(text=f"Joined: {user['joined_at'][:10]} • The Circle")

        await ctx.send(embed=embed)

    @commands.command(name="setbio")
    async def setbio_cmd(self, ctx: commands.Context, *, text: str = None):
        """Set your profile bio (max 100 chars)."""
        if not text:
            await ctx.send("⚫ Usage: `!setbio <your bio text>`")
            return
        if len(text) > 100:
            await ctx.send("⚫ Bio must be 100 characters or less.")
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO profiles (user_id, bio) VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET bio = ?""",
                (ctx.author.id, text, text),
            )
            await db.commit()

        await ctx.send(f"⚫ Bio updated: *{text}*")

    @commands.command(name="setcolor")
    async def setcolor_cmd(self, ctx: commands.Context, hex_color: str = None):
        """Set your profile accent color. Costs 100 Circles."""
        if not hex_color:
            await ctx.send("⚫ Usage: `!setcolor #FF5733` (costs 100 🪙)")
            return

        # Validate hex
        color = hex_color.lstrip("#")
        if len(color) != 6:
            await ctx.send("⚫ Invalid hex color. Use format: `#FF5733`")
            return
        try:
            int(color, 16)
        except ValueError:
            await ctx.send("⚫ Invalid hex color. Use format: `#FF5733`")
            return

        # Check/spend coins
        economy_cog = self.bot.get_cog("Economy")
        if economy_cog:
            success = await economy_cog._spend_coins(ctx.author.id, 100)
            if not success:
                await ctx.send(f"⚫ Not enough coins. You need **100** {ECONOMY_CURRENCY_EMOJI}.")
                return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO profiles (user_id, accent_color) VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET accent_color = ?""",
                (ctx.author.id, color, color),
            )
            await db.commit()

        await ctx.send(f"⚫ Profile accent color set to `#{color}`. Check it with `!profile`.")

    @commands.command(name="setbanner")
    async def setbanner_cmd(self, ctx: commands.Context, url: str = None):
        """Set your profile banner image. Costs 200 Circles."""
        if not url:
            await ctx.send("⚫ Usage: `!setbanner <image_url>` (costs 200 🪙)")
            return

        # Check/spend coins
        economy_cog = self.bot.get_cog("Economy")
        if economy_cog:
            success = await economy_cog._spend_coins(ctx.author.id, 200)
            if not success:
                await ctx.send(f"⚫ Not enough coins. You need **200** {ECONOMY_CURRENCY_EMOJI}.")
                return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO profiles (user_id, banner_url) VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET banner_url = ?""",
                (ctx.author.id, url, url),
            )
            await db.commit()

        await ctx.send("⚫ Profile banner updated. Check it with `!profile`.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Profiles(bot))
