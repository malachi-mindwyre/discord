"""
The Circle — Factions Cog
4 teams (Inferno, Frost, Venom, Volt) with weekly competition.
Unlocks at Respected (rank 31). Permanent choice.
"""

from __future__ import annotations

from datetime import datetime, date, timedelta

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    FACTION_UNLOCK_RANK,
    FACTION_TEAMS,
    FACTION_WIN_BONUS,
)
from database import DB_PATH, get_user
from ranks import RANK_BY_TIER


class Factions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.weekly_faction_update.start()

    def cog_unload(self):
        self.weekly_faction_update.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track faction member scores for weekly competition."""
        if message.author.bot or not message.guild:
            return

        # Check if user has a faction
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT team_name FROM factions WHERE user_id = ?", (message.author.id,)
            )
            row = await cursor.fetchone()
            if not row:
                return

            team_name = row[0]
            week_key = self._get_week_key()

            # Get points earned for this message from the user's daily scores
            # We'll just track 1 point per message for simplicity in faction scoring
            await db.execute(
                """INSERT INTO faction_scores (team_name, week, total_score)
                   VALUES (?, ?, 1)
                   ON CONFLICT(team_name, week) DO UPDATE SET total_score = total_score + 1""",
                (team_name, week_key),
            )
            await db.commit()

    @commands.command(name="faction", aliases=["team"])
    async def faction_cmd(self, ctx: commands.Context):
        """View faction standings or join a faction."""
        user = await get_user(ctx.author.id)
        if not user:
            await ctx.send("⚫ You haven't entered The Circle yet.")
            return

        # Check if user already has a faction
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT team_name FROM factions WHERE user_id = ?", (ctx.author.id,)
            )
            row = await cursor.fetchone()

        if row:
            # Show standings
            await self._show_standings(ctx, row[0])
        elif user["current_rank"] >= FACTION_UNLOCK_RANK:
            # Offer to join
            await self._offer_faction_choice(ctx)
        else:
            rank_needed = RANK_BY_TIER.get(FACTION_UNLOCK_RANK)
            await ctx.send(
                f"⚫ Factions unlock at **{rank_needed.name}** (Rank {FACTION_UNLOCK_RANK}). "
                f"You're currently Rank {user['current_rank']}. Keep climbing."
            )

    @commands.command(name="joinfaction")
    async def join_faction_cmd(self, ctx: commands.Context, *, team: str = None):
        """Join a faction. Permanent choice! Usage: !joinfaction Inferno"""
        if not team:
            await ctx.send(
                "⚫ Usage: `!joinfaction <team name>`\n"
                "Teams: **Inferno** 🔴 | **Frost** 🔵 | **Venom** 🟢 | **Volt** 🟡\n"
                "⚠️ This choice is **permanent**."
            )
            return

        team = team.strip().title()
        if team not in FACTION_TEAMS:
            await ctx.send(f"⚫ Unknown team. Choose: **Inferno**, **Frost**, **Venom**, or **Volt**.")
            return

        user = await get_user(ctx.author.id)
        if not user or user["current_rank"] < FACTION_UNLOCK_RANK:
            await ctx.send(f"⚫ You need to reach Rank {FACTION_UNLOCK_RANK} to join a faction.")
            return

        # Check if already in a faction
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT team_name FROM factions WHERE user_id = ?", (ctx.author.id,)
            )
            if await cursor.fetchone():
                await ctx.send("⚫ You already belong to a faction. This allegiance is permanent.")
                return

            # Join
            await db.execute(
                "INSERT INTO factions (user_id, team_name, joined_at) VALUES (?, ?, ?)",
                (ctx.author.id, team, datetime.utcnow().isoformat()),
            )
            await db.commit()

        team_info = FACTION_TEAMS[team]

        # Assign team role
        role = discord.utils.get(ctx.guild.roles, name=f"Team {team}")
        if not role:
            try:
                role = await ctx.guild.create_role(
                    name=f"Team {team}",
                    color=discord.Color(team_info["color"]),
                    reason="Faction system",
                )
            except discord.HTTPException:
                pass
        if role:
            try:
                await ctx.author.add_roles(role, reason="Joined faction")
            except discord.HTTPException:
                pass

        embed = discord.Embed(
            title=f"{team_info['emoji']} WELCOME TO {team.upper()}",
            description=(
                f"{ctx.author.mention} has pledged allegiance to **{team}**.\n\n"
                f"*\"{team_info['motto']}\"*\n\n"
                f"Your team channel: #team-{team.lower()}\n"
                f"Fight for your faction in the weekly competition. ⚔️"
            ),
            color=team_info["color"],
        )

        await ctx.send(embed=embed)

        # Announce in faction-war
        war_ch = discord.utils.get(ctx.guild.text_channels, name="faction-war")
        if war_ch:
            try:
                await war_ch.send(
                    f"{team_info['emoji']} **{ctx.author.display_name}** has joined **{team}**!"
                )
            except discord.HTTPException:
                pass

    async def _show_standings(self, ctx: commands.Context, user_team: str):
        """Show current faction standings."""
        week_key = self._get_week_key()
        async with aiosqlite.connect(DB_PATH) as db:
            standings = []
            for team_name in FACTION_TEAMS:
                cursor = await db.execute(
                    "SELECT total_score FROM faction_scores WHERE team_name = ? AND week = ?",
                    (team_name, week_key),
                )
                row = await cursor.fetchone()
                score = row[0] if row else 0

                cursor = await db.execute(
                    "SELECT COUNT(*) FROM factions WHERE team_name = ?", (team_name,)
                )
                member_count = (await cursor.fetchone())[0]
                standings.append((team_name, score, member_count))

        standings.sort(key=lambda x: x[1], reverse=True)

        lines = []
        for i, (name, score, members) in enumerate(standings):
            info = FACTION_TEAMS[name]
            marker = " ← YOU" if name == user_team else ""
            prefix = "👑" if i == 0 and score > 0 else f"#{i+1}"
            lines.append(
                f"{prefix} {info['emoji']} **{name}** — {score:,.0f} pts ({members} members){marker}"
            )

        embed = discord.Embed(
            title="⚔️ FACTION WAR — WEEKLY STANDINGS",
            description="\n".join(lines),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="Standings reset weekly • Winning team gets 10% point bonus")
        await ctx.send(embed=embed)

    async def _offer_faction_choice(self, ctx: commands.Context):
        """Show available factions to an eligible user."""
        lines = []
        for name, info in FACTION_TEAMS.items():
            lines.append(f"{info['emoji']} **{name}** — *\"{info['motto']}\"*")

        embed = discord.Embed(
            title="⚔️ CHOOSE YOUR ALLEGIANCE",
            description=(
                "You've proven yourself. The factions beckon.\n\n"
                + "\n".join(lines) + "\n\n"
                "Use `!joinfaction <name>` to choose.\n"
                "⚠️ **This choice is permanent.**"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        await ctx.send(embed=embed)

    @tasks.loop(hours=24)
    async def weekly_faction_update(self):
        """Post standings to #faction-war and handle weekly reset."""
        now = datetime.utcnow()
        if now.weekday() != 0 or now.hour > 1:
            return  # Only Monday early morning

        last_week = self._get_week_key(offset=-1)

        async with aiosqlite.connect(DB_PATH) as db:
            # Find winner
            cursor = await db.execute(
                "SELECT team_name, total_score FROM faction_scores WHERE week = ? ORDER BY total_score DESC LIMIT 1",
                (last_week,),
            )
            winner = await cursor.fetchone()

        if not winner or winner[1] == 0:
            return

        winning_team = winner[0]
        team_info = FACTION_TEAMS.get(winning_team, {})

        for guild in self.bot.guilds:
            # Announce in faction-war
            war_ch = discord.utils.get(guild.text_channels, name="faction-war")
            if war_ch:
                embed = discord.Embed(
                    title=f"👑 WEEKLY FACTION WINNER: {winning_team.upper()}!",
                    description=(
                        f"{team_info.get('emoji', '')} **{winning_team}** dominates with **{winner[1]:,.0f}** points!\n\n"
                        f"All {winning_team} members get **10% bonus points** this week. ⚡\n\n"
                        f"New week, new war. Fight for your team. ⚔️"
                    ),
                    color=team_info.get("color", EMBED_COLOR_ACCENT),
                )
                try:
                    await war_ch.send(embed=embed)
                except discord.HTTPException:
                    pass

    @weekly_faction_update.before_loop
    async def before_faction_update(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def _get_week_key(offset: int = 0) -> str:
        d = date.today() + timedelta(weeks=offset)
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"


async def setup(bot: commands.Bot):
    await bot.add_cog(Factions(bot))
