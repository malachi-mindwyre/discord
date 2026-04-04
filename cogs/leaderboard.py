"""
The Circle — Leaderboard Cog
Auto-updating embed in #leaderboard, refreshes every hour. Also handles !rank, !top, !stats commands.
"""

import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    LEADERBOARD_TOP_COUNT,
    LEADERBOARD_REFRESH_MINUTES,
    KEEPER_LEADERBOARD_HEADER,
    KEEPER_HELP,
)
from database import get_top_users, get_user, get_or_create_user, get_today_top_user, get_top_inviters
from ranks import ALL_RANKS, RANK_BY_TIER, get_rank_for_score, get_next_rank, get_progress_to_next, make_progress_bar


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._leaderboard_message_id: int | None = None
        self._leaderboard_channel_id: int | None = None
        self.refresh_leaderboard.start()

    def cog_unload(self):
        self.refresh_leaderboard.cancel()

    @tasks.loop(minutes=LEADERBOARD_REFRESH_MINUTES)
    async def refresh_leaderboard(self):
        """Update the leaderboard embed every hour."""
        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name="leaderboard")
            if not channel:
                continue

            embed = await self._build_leaderboard_embed()

            # Try to edit existing message, or send a new one
            if self._leaderboard_message_id and self._leaderboard_channel_id == channel.id:
                try:
                    msg = await channel.fetch_message(self._leaderboard_message_id)
                    await msg.edit(embed=embed)
                    continue
                except (discord.NotFound, discord.HTTPException):
                    pass

            # Try to find and edit the last bot message in the channel (survives restarts)
            found_existing = False
            async for old_msg in channel.history(limit=20):
                if old_msg.author == self.bot.user and old_msg.embeds:
                    first_embed = old_msg.embeds[0]
                    if first_embed.title and "LEADERBOARD" in first_embed.title:
                        try:
                            await old_msg.edit(embed=embed)
                            self._leaderboard_message_id = old_msg.id
                            self._leaderboard_channel_id = channel.id
                            found_existing = True
                        except discord.HTTPException:
                            pass
                        break

            if not found_existing:
                try:
                    msg = await channel.send(embed=embed)
                    self._leaderboard_message_id = msg.id
                    self._leaderboard_channel_id = channel.id
                    await msg.pin()
                except discord.HTTPException:
                    pass

    @refresh_leaderboard.before_loop
    async def before_refresh(self):
        await self.bot.wait_until_ready()

    async def _build_leaderboard_embed(self) -> discord.Embed:
        """Build the full leaderboard embed."""
        top_users = await get_top_users(LEADERBOARD_TOP_COUNT)
        today_top = await get_today_top_user()
        top_inviters = await get_top_inviters(5)

        embed = discord.Embed(
            title="🏆 THE CIRCLE — LEADERBOARD",
            description=KEEPER_LEADERBOARD_HEADER,
            color=EMBED_COLOR_PRIMARY,
        )

        # Main leaderboard
        if top_users:
            medals = ["🥇", "🥈", "🥉"]
            lines = []
            for i, user in enumerate(top_users):
                rank = RANK_BY_TIER.get(user["current_rank"])
                rank_name = rank.name if rank else "Unknown"
                prefix = medals[i] if i < 3 else f"#{i+1}"
                lines.append(
                    f"{prefix}  **{user['username']}** — {user['total_score']:,.0f} pts  `{rank_name}`"
                )
            embed.add_field(
                name="👑 TOP MEMBERS",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="👑 TOP MEMBERS",
                value="*The Circle awaits its first chosen...*",
                inline=False,
            )

        # Most active today
        if today_top:
            embed.add_field(
                name="🔥 MOST ACTIVE TODAY",
                value=f"**{today_top['username']}** — {today_top['points_today']:,.0f} pts",
                inline=True,
            )

        # Top inviters
        if top_inviters:
            invite_lines = []
            for i, user in enumerate(top_inviters):
                invite_lines.append(f"#{i+1} **{user['username']}** — {user['invite_count']} invites")
            embed.add_field(
                name="📨 TOP RECRUITERS",
                value="\n".join(invite_lines),
                inline=True,
            )

        embed.set_footer(text=f"Updated every {LEADERBOARD_REFRESH_MINUTES} minutes • Use !rank to check your stats")

        return embed

    # ─── User Commands ─────────────────────────────────────────────────────

    @commands.command(name="rank")
    async def rank_cmd(self, ctx: commands.Context):
        """Show your current rank, score, and progress."""
        user = await get_or_create_user(ctx.author.id, str(ctx.author))
        rank = get_rank_for_score(user["total_score"])
        next_rank = get_next_rank(rank.tier)
        progress = get_progress_to_next(user["total_score"], rank.tier)

        embed = discord.Embed(
            title=f"👁️ {ctx.author.display_name}",
            color=rank.color,
        )
        embed.add_field(name="🏷️ Rank", value=f"**{rank.name}**", inline=True)
        embed.add_field(name="🏆 Score", value=f"**{user['total_score']:,.0f}** pts", inline=True)
        embed.add_field(name="📨 Invites", value=f"**{user['invite_count']}**", inline=True)

        if next_rank:
            embed.add_field(
                name="📊 Progress",
                value=f"{make_progress_bar(progress)}\nNext: **{next_rank.name}** ({next_rank.threshold:,.0f} pts)",
                inline=False,
            )
        else:
            embed.add_field(name="📊 Progress", value="**MAX RANK** — This IS your grass.", inline=False)

        embed.add_field(name="💬 Tagline", value=f"*\"{rank.tagline}\"*", inline=False)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)

    @commands.command(name="top")
    async def top_cmd(self, ctx: commands.Context):
        """Show the top 10 leaderboard."""
        top_users = await get_top_users(10)
        if not top_users:
            await ctx.send("⚫ The Circle is empty. Be the first to rise.")
            return

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, user in enumerate(top_users):
            rank = RANK_BY_TIER.get(user["current_rank"])
            rank_name = rank.name if rank else "?"
            prefix = medals[i] if i < 3 else f"#{i+1}"
            lines.append(f"{prefix}  **{user['username']}** — {user['total_score']:,.0f} pts  `{rank_name}`")

        embed = discord.Embed(
            title="🏆 TOP 10 — THE CIRCLE",
            description="\n".join(lines),
            color=EMBED_COLOR_PRIMARY,
        )
        await ctx.send(embed=embed)

    @commands.command(name="stats")
    async def stats_cmd(self, ctx: commands.Context, member: discord.Member = None):
        """View someone else's stats."""
        target = member or ctx.author
        user = await get_user(target.id)
        if not user:
            await ctx.send(f"⚫ {target.display_name} has not yet entered The Circle.")
            return

        rank = RANK_BY_TIER.get(user["current_rank"])
        embed = discord.Embed(
            title=f"👁️ {target.display_name}",
            color=rank.color if rank else EMBED_COLOR_PRIMARY,
        )
        embed.add_field(name="🏷️ Rank", value=f"**{rank.name}**" if rank else "Unknown", inline=True)
        embed.add_field(name="🏆 Score", value=f"**{user['total_score']:,.0f}** pts", inline=True)
        embed.add_field(name="📨 Invites", value=f"**{user['invite_count']}**", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="invites")
    async def invites_cmd(self, ctx: commands.Context):
        """Show the invite leaderboard."""
        top_inviters = await get_top_inviters(10)
        if not top_inviters:
            await ctx.send("⚫ No recruiters yet. Bring souls to The Circle.")
            return

        lines = []
        for i, user in enumerate(top_inviters):
            lines.append(f"#{i+1} **{user['username']}** — {user['invite_count']} invites")

        embed = discord.Embed(
            title="📨 RECRUITER LEADERBOARD",
            description="\n".join(lines),
            color=EMBED_COLOR_ACCENT,
        )
        await ctx.send(embed=embed)

    @commands.command(name="help")
    async def help_cmd(self, ctx: commands.Context):
        """Keeper's help message."""
        embed = discord.Embed(
            title="⚫ KEEPER'S GUIDANCE",
            description=KEEPER_HELP,
            color=EMBED_COLOR_PRIMARY,
        )
        await ctx.send(embed=embed)

    @commands.command(name="admin")
    @commands.is_owner()
    async def admin_cmd(self, ctx: commands.Context):
        """List all admin commands. Owner only."""
        lines = [
            "**Server Setup**",
            "`!setup` — Create all channels, categories, 100 rank roles + lockdown",
            "`!lockdown` — Strip mention perms, hide #bot-commands, create AutoMod rule",
            "`!cleanup` — Fix orphaned channels, remove duplicate categories",
            "`!purgeall` — Delete ALL messages in ALL text channels (irreversible)",
            "`!postinfo` — Post/refresh guide embeds in #info",
            "",
            "**User Management**",
            "`!reset @user` — Reset score to 0, strip rank roles, assign Rookie I",
            "`!setrank @user <1-100>` — Set a user's rank + update their role",
            "`!fixroles` — Scan all members, fix any mismatched rank roles",
            "",
            "**Moderation**",
            "`!purge @user [minutes]` — Delete a user's messages (default 30min, no cap)",
            "`!nuke [minutes]` — Delete all detected spam across all channels (no cap)",
            "",
            "**Analytics & Diagnostics**",
            "`!healthcheck` / `!hc` — Run 23 system checks",
            "`!metrics` — Retention dashboard (DAU/MAU, D1/D7/D30)",
            "`!recap` — Manually trigger weekly recap",
            "",
            "**Engagement**",
            "`!debate start <topic>` — Start a structured debate",
            "`!approve <id>` / `!reject <id>` — Approve/reject UGC submissions",
        ]
        embed = discord.Embed(
            title="⚫ ADMIN COMMANDS",
            description="\n".join(lines),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="Owner only — all commands restricted to BOT_OWNER_ID")
        await ctx.send(embed=embed)

    # ─── Admin Commands ────────────────────────────────────────────────────

    @commands.command(name="reset")
    @commands.is_owner()
    async def reset_cmd(self, ctx: commands.Context, member: discord.Member = None):
        """Reset a user's score, rank role, and assign Rookie I. Admin only."""
        if not member:
            await ctx.send("⚫ Usage: `!reset @user`")
            return
        from database import reset_user
        await reset_user(member.id)

        # Remove all rank roles and assign Rookie I
        rank_role_names = {r.name for r in ALL_RANKS}
        roles_to_remove = [r for r in member.roles if r.name in rank_role_names]
        rookie_role = discord.utils.get(ctx.guild.roles, name="Rookie I")

        try:
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Score reset")
            if rookie_role and rookie_role not in member.roles:
                await member.add_roles(rookie_role, reason="Score reset — back to Rookie I")
        except discord.Forbidden:
            await ctx.send("⚠️ Missing permissions to update roles.")

        await ctx.send(f"⚫ {member.display_name}'s journey has been reset. The Circle forgets.")

    @commands.command(name="setrank")
    @commands.is_owner()
    async def setrank_cmd(self, ctx: commands.Context, member: discord.Member = None, tier: int = None):
        """Manually set a user's rank. Admin only."""
        if not member or not tier or tier < 1 or tier > 100:
            await ctx.send("⚫ Usage: `!setrank @user <1-100>`")
            return

        rank = RANK_BY_TIER.get(tier)
        if not rank:
            await ctx.send("⚫ Invalid tier.")
            return

        from database import set_user_score
        await set_user_score(member.id, float(rank.threshold), tier)

        # Update Discord roles to match
        rank_role_names = {r.name for r in ALL_RANKS}
        roles_to_remove = [r for r in member.roles if r.name in rank_role_names]
        new_role = discord.utils.get(ctx.guild.roles, name=rank.name)

        try:
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason=f"Rank set to {rank.name}")
            if new_role and new_role not in member.roles:
                await member.add_roles(new_role, reason=f"Rank set to {rank.name}")
        except discord.Forbidden:
            await ctx.send("⚠️ Missing permissions to update roles.")

        await ctx.send(f"⚫ {member.display_name} has been placed at **{rank.name}** by decree.")


    @commands.command(name="fixroles")
    @commands.is_owner()
    async def fixroles_cmd(self, ctx: commands.Context):
        """Scan all members and ensure their Discord role matches their DB rank. Owner only."""
        from database import get_or_create_user
        guild = ctx.guild
        if not guild:
            return

        status = await ctx.send("⚫ Scanning all members and fixing roles...")
        rank_role_names = {r.name for r in ALL_RANKS}
        fixed = 0

        for member in guild.members:
            if member.bot:
                continue

            user = await get_or_create_user(member.id, str(member))
            expected_rank = RANK_BY_TIER.get(user["current_rank"], ALL_RANKS[0])

            # Get their current rank roles
            current_rank_roles = [r for r in member.roles if r.name in rank_role_names]
            expected_role = discord.utils.get(guild.roles, name=expected_rank.name)

            if not expected_role:
                continue

            # Check if they already have the correct role and only that role
            has_correct = expected_role in member.roles
            has_extra = any(r != expected_role for r in current_rank_roles)

            if has_correct and not has_extra:
                continue  # Already correct

            try:
                if current_rank_roles:
                    await member.remove_roles(*current_rank_roles, reason="fixroles: cleanup")
                await member.add_roles(expected_role, reason=f"fixroles: set to {expected_rank.name}")
                fixed += 1
            except discord.Forbidden:
                pass

        await status.edit(content=f"⚫ Fixed roles for **{fixed}** members.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Leaderboard(bot))
