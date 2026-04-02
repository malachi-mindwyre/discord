"""
The Circle — Circles (Friend Groups) Cog
Small groups of 3-8 members that create social accountability.
Weekly leaderboard with rewards for top-performing Circle.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import aiosqlite
import discord
from discord.ext import commands, tasks

from database import DB_PATH, get_user, spend_coins, add_coins

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────
CIRCLE_MIN_RANK = 21
CIRCLE_CREATE_COST = 200
CIRCLE_MIN_MEMBERS = 3
CIRCLE_MAX_MEMBERS = 8
CIRCLE_WEEKLY_WINNER_COINS = 50
EMBED_COLOR_PRIMARY = 0x1A1A2E
EMBED_COLOR_ACCENT = 0xE94560


class Circles(commands.Cog):
    """Friend-group system for social accountability."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.weekly_circle_reset.start()

    def cog_unload(self):
        self.weekly_circle_reset.cancel()

    # ─── DB Init ─────────────────────────────────────────────────────────────

    async def cog_load(self):
        """Create circles tables on load."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS circles (
                    circle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    leader_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    role_id INTEGER DEFAULT NULL
                );

                CREATE TABLE IF NOT EXISTS circle_members (
                    circle_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    joined_at TEXT NOT NULL,
                    PRIMARY KEY (circle_id, user_id),
                    FOREIGN KEY (circle_id) REFERENCES circles(circle_id)
                );

                CREATE TABLE IF NOT EXISTS circle_weekly_stats (
                    circle_id INTEGER NOT NULL,
                    week TEXT NOT NULL,
                    total_messages INTEGER DEFAULT 0,
                    total_reactions INTEGER DEFAULT 0,
                    PRIMARY KEY (circle_id, week),
                    FOREIGN KEY (circle_id) REFERENCES circles(circle_id)
                );
            """)
            await db.commit()
        logger.info("Circles tables ready  ✓")

    # ─── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _week_key() -> str:
        """Return ISO week string like '2026-W14'."""
        now = datetime.utcnow()
        year, week, _ = now.isocalendar()
        return f"{year}-W{week:02d}"

    async def _get_user_circle(self, user_id: int) -> dict | None:
        """Return the circle dict a user belongs to, or None."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT c.* FROM circles c
                   JOIN circle_members cm ON c.circle_id = cm.circle_id
                   WHERE cm.user_id = ?""",
                (user_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def _get_circle_members(self, circle_id: int) -> list[int]:
        """Return list of user IDs in a circle."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id FROM circle_members WHERE circle_id = ?",
                (circle_id,),
            )
            return [r[0] for r in await cursor.fetchall()]

    async def _get_member_count(self, circle_id: int) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM circle_members WHERE circle_id = ?",
                (circle_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    # ─── Activity Tracking ───────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track messages for circle weekly stats."""
        if message.author.bot or not message.guild:
            return
        circle = await self._get_user_circle(message.author.id)
        if not circle:
            return
        week = self._week_key()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO circle_weekly_stats (circle_id, week, total_messages, total_reactions)
                   VALUES (?, ?, 1, 0)
                   ON CONFLICT(circle_id, week) DO UPDATE SET total_messages = total_messages + 1""",
                (circle["circle_id"], week),
            )
            await db.commit()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Track reactions for circle weekly stats."""
        if payload.member and payload.member.bot:
            return
        if not payload.guild_id:
            return
        # Credit the circle of the person whose message got the reaction
        try:
            channel = self.bot.get_channel(payload.channel_id)
            if not channel:
                return
            msg = await channel.fetch_message(payload.message_id)
            if msg.author.bot:
                return
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

        circle = await self._get_user_circle(msg.author.id)
        if not circle:
            return
        week = self._week_key()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO circle_weekly_stats (circle_id, week, total_messages, total_reactions)
                   VALUES (?, ?, 0, 1)
                   ON CONFLICT(circle_id, week) DO UPDATE SET total_reactions = total_reactions + 1""",
                (circle["circle_id"], week),
            )
            await db.commit()

    # ─── Commands ────────────────────────────────────────────────────────────

    @commands.group(name="circle", invoke_without_command=True)
    async def circle_cmd(self, ctx: commands.Context):
        """Circle commands hub. Use !circle info, !circle create, etc."""
        await ctx.send(
            "**Available:** `!circle create <name>` | `!circle invite @user` | "
            "`!circle leave` | `!circle info` | `!circle leaderboard` | `!circle kick @user`"
        )

    @circle_cmd.command(name="create")
    async def circle_create(self, ctx: commands.Context, *, name: str):
        """Create a new Circle (rank 21+, costs 200 Circles)."""
        user = await get_user(ctx.author.id)
        if not user:
            await ctx.send("You haven't entered The Circle yet.")
            return

        if user["current_rank"] < CIRCLE_MIN_RANK:
            await ctx.send(
                f"You must be **rank {CIRCLE_MIN_RANK}+** (Certified) to create a Circle. "
                f"You're rank {user['current_rank']}."
            )
            return

        # Check if already in a circle
        existing = await self._get_user_circle(ctx.author.id)
        if existing:
            await ctx.send(f"You're already in **{existing['name']}**. Leave first with `!circle leave`.")
            return

        # Validate name length
        if len(name) > 32 or len(name) < 2:
            await ctx.send("Circle name must be 2-32 characters.")
            return

        # Check name uniqueness
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT circle_id FROM circles WHERE name = ? COLLATE NOCASE", (name,)
            )
            if await cursor.fetchone():
                await ctx.send("A Circle with that name already exists. Pick another.")
                return

        # Spend coins
        success = await spend_coins(ctx.author.id, CIRCLE_CREATE_COST)
        if not success:
            await ctx.send(
                f"Creating a Circle costs **{CIRCLE_CREATE_COST}** Circles. You don't have enough."
            )
            return

        # Create circle + add leader as member
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO circles (name, leader_id, created_at) VALUES (?, ?, ?)",
                (name, ctx.author.id, now),
            )
            circle_id = cursor.lastrowid
            await db.execute(
                "INSERT INTO circle_members (circle_id, user_id, joined_at) VALUES (?, ?, ?)",
                (circle_id, ctx.author.id, now),
            )
            await db.commit()

        embed = discord.Embed(
            title="A NEW CIRCLE FORMS",
            description=(
                f"**{name}** has been forged by {ctx.author.mention}.\n\n"
                f"Invite members with `!circle invite @user`\n"
                f"You need at least **{CIRCLE_MIN_MEMBERS}** members to compete on the leaderboard."
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text=f"Cost: {CIRCLE_CREATE_COST} Circles")
        try:
            await ctx.send(embed=embed)
        except discord.HTTPException:
            logger.error("Failed to send circle create embed")

    @circle_cmd.command(name="invite")
    async def circle_invite(self, ctx: commands.Context, member: discord.Member):
        """Invite someone to your Circle."""
        circle = await self._get_user_circle(ctx.author.id)
        if not circle:
            await ctx.send("You're not in a Circle. Create one with `!circle create <name>`.")
            return

        if circle["leader_id"] != ctx.author.id:
            await ctx.send("Only the Circle leader can invite members.")
            return

        if member.bot:
            await ctx.send("Bots cannot join Circles.")
            return

        count = await self._get_member_count(circle["circle_id"])
        if count >= CIRCLE_MAX_MEMBERS:
            await ctx.send(f"Your Circle is full ({CIRCLE_MAX_MEMBERS}/{CIRCLE_MAX_MEMBERS}).")
            return

        # Check target isn't already in a circle
        target_circle = await self._get_user_circle(member.id)
        if target_circle:
            await ctx.send(f"{member.display_name} is already in **{target_circle['name']}**.")
            return

        # Add them
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO circle_members (circle_id, user_id, joined_at) VALUES (?, ?, ?)",
                (circle["circle_id"], member.id, now),
            )
            await db.commit()

        embed = discord.Embed(
            title="CIRCLE GROWS STRONGER",
            description=(
                f"{member.mention} has joined **{circle['name']}**.\n"
                f"Members: **{count + 1}/{CIRCLE_MAX_MEMBERS}**"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        try:
            await ctx.send(embed=embed)
        except discord.HTTPException:
            logger.error("Failed to send circle invite embed")

    @circle_cmd.command(name="leave")
    async def circle_leave(self, ctx: commands.Context):
        """Leave your Circle."""
        circle = await self._get_user_circle(ctx.author.id)
        if not circle:
            await ctx.send("You're not in a Circle.")
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM circle_members WHERE circle_id = ? AND user_id = ?",
                (circle["circle_id"], ctx.author.id),
            )
            await db.commit()

            # If leader left, reassign or dissolve
            if circle["leader_id"] == ctx.author.id:
                members = await self._get_circle_members(circle["circle_id"])
                if members:
                    new_leader = members[0]
                    await db.execute(
                        "UPDATE circles SET leader_id = ? WHERE circle_id = ?",
                        (new_leader, circle["circle_id"]),
                    )
                    await db.commit()
                    leader_user = self.bot.get_user(new_leader)
                    leader_name = leader_user.display_name if leader_user else str(new_leader)
                    await ctx.send(
                        f"You left **{circle['name']}**. Leadership transferred to **{leader_name}**."
                    )
                else:
                    # Dissolve empty circle
                    await db.execute(
                        "DELETE FROM circle_weekly_stats WHERE circle_id = ?",
                        (circle["circle_id"],),
                    )
                    await db.execute(
                        "DELETE FROM circles WHERE circle_id = ?",
                        (circle["circle_id"],),
                    )
                    await db.commit()
                    await ctx.send(f"You left **{circle['name']}**. The Circle has been dissolved.")
                    return

        await ctx.send(f"You left **{circle['name']}**.")

    @circle_cmd.command(name="kick")
    async def circle_kick(self, ctx: commands.Context, member: discord.Member):
        """Leader only: kick a member from your Circle."""
        circle = await self._get_user_circle(ctx.author.id)
        if not circle:
            await ctx.send("You're not in a Circle.")
            return

        if circle["leader_id"] != ctx.author.id:
            await ctx.send("Only the Circle leader can kick members.")
            return

        if member.id == ctx.author.id:
            await ctx.send("You can't kick yourself. Use `!circle leave`.")
            return

        target_circle = await self._get_user_circle(member.id)
        if not target_circle or target_circle["circle_id"] != circle["circle_id"]:
            await ctx.send(f"{member.display_name} is not in your Circle.")
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM circle_members WHERE circle_id = ? AND user_id = ?",
                (circle["circle_id"], member.id),
            )
            await db.commit()

        count = await self._get_member_count(circle["circle_id"])
        await ctx.send(
            f"{member.display_name} has been removed from **{circle['name']}**. "
            f"Members: **{count}/{CIRCLE_MAX_MEMBERS}**"
        )

    @circle_cmd.command(name="info")
    async def circle_info(self, ctx: commands.Context):
        """Show your Circle's members, stats, and weekly ranking."""
        circle = await self._get_user_circle(ctx.author.id)
        if not circle:
            await ctx.send("You're not in a Circle. Create one with `!circle create <name>` (rank 21+).")
            return

        members = await self._get_circle_members(circle["circle_id"])
        week = self._week_key()

        # Get weekly stats
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT total_messages, total_reactions FROM circle_weekly_stats WHERE circle_id = ? AND week = ?",
                (circle["circle_id"], week),
            )
            stats_row = await cursor.fetchone()

        total_msgs = stats_row[0] if stats_row else 0
        total_reacts = stats_row[1] if stats_row else 0
        activity_score = total_msgs + total_reacts

        # Build member list
        member_lines = []
        for uid in members:
            user_obj = self.bot.get_user(uid)
            name = user_obj.display_name if user_obj else str(uid)
            leader_tag = " (Leader)" if uid == circle["leader_id"] else ""
            member_lines.append(f"{'👑' if leader_tag else '•'} {name}{leader_tag}")

        # Get weekly rank
        rank_text = await self._get_circle_rank(circle["circle_id"], week)

        embed = discord.Embed(
            title=f"CIRCLE: {circle['name'].upper()}",
            color=EMBED_COLOR_PRIMARY,
        )
        embed.add_field(
            name=f"Members ({len(members)}/{CIRCLE_MAX_MEMBERS})",
            value="\n".join(member_lines) or "Empty",
            inline=False,
        )
        embed.add_field(
            name=f"This Week ({week})",
            value=(
                f"Messages: **{total_msgs}**\n"
                f"Reactions: **{total_reacts}**\n"
                f"Activity Score: **{activity_score}**"
            ),
            inline=True,
        )
        embed.add_field(name="Weekly Rank", value=rank_text, inline=True)

        if len(members) < CIRCLE_MIN_MEMBERS:
            embed.set_footer(
                text=f"Need {CIRCLE_MIN_MEMBERS - len(members)} more member(s) to qualify for leaderboard"
            )

        try:
            await ctx.send(embed=embed)
        except discord.HTTPException:
            logger.error("Failed to send circle info embed")

    async def _get_circle_rank(self, circle_id: int, week: str) -> str:
        """Get this circle's rank on the weekly leaderboard."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT c.circle_id,
                          COALESCE(s.total_messages, 0) + COALESCE(s.total_reactions, 0) AS score
                   FROM circles c
                   JOIN circle_members cm ON c.circle_id = cm.circle_id
                   LEFT JOIN circle_weekly_stats s ON c.circle_id = s.circle_id AND s.week = ?
                   GROUP BY c.circle_id
                   HAVING COUNT(cm.user_id) >= ?
                   ORDER BY score DESC""",
                (week, CIRCLE_MIN_MEMBERS),
            )
            rows = await cursor.fetchall()

        for i, row in enumerate(rows, 1):
            if row[0] == circle_id:
                return f"**#{i}** of {len(rows)}"
        return "Unranked (need 3+ members)"

    @circle_cmd.command(name="leaderboard", aliases=["lb"])
    async def circle_leaderboard(self, ctx: commands.Context):
        """Weekly ranking of all Circles by collective activity."""
        week = self._week_key()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT c.circle_id, c.name, c.leader_id,
                          COUNT(cm.user_id) AS member_count,
                          COALESCE(s.total_messages, 0) AS msgs,
                          COALESCE(s.total_reactions, 0) AS reacts,
                          COALESCE(s.total_messages, 0) + COALESCE(s.total_reactions, 0) AS score
                   FROM circles c
                   JOIN circle_members cm ON c.circle_id = cm.circle_id
                   LEFT JOIN circle_weekly_stats s ON c.circle_id = s.circle_id AND s.week = ?
                   GROUP BY c.circle_id
                   HAVING member_count >= ?
                   ORDER BY score DESC
                   LIMIT 15""",
                (week, CIRCLE_MIN_MEMBERS),
            )
            rows = await cursor.fetchall()

        if not rows:
            await ctx.send("No qualifying Circles this week. Circles need 3+ members to rank.")
            return

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, row in enumerate(rows):
            circle_id, name, leader_id, member_count, msgs, reacts, score = row
            prefix = medals[i] if i < 3 else f"**{i + 1}.**"
            lines.append(
                f"{prefix} **{name}** — {score} pts ({msgs} msgs, {reacts} reacts) [{member_count} members]"
            )

        embed = discord.Embed(
            title="CIRCLE LEADERBOARD",
            description=f"**Week {week}** — Top Circles by collective activity\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text=f"Top Circle wins {CIRCLE_WEEKLY_WINNER_COINS} Circles per member | Resets Monday")

        try:
            await ctx.send(embed=embed)
        except discord.HTTPException:
            logger.error("Failed to send circle leaderboard embed")

    # ─── Weekly Reset + Reward ───────────────────────────────────────────────

    @tasks.loop(hours=1)
    async def weekly_circle_reset(self):
        """Check if it's Monday 00:xx UTC — reward last week's winner and announce."""
        now = datetime.utcnow()
        if now.weekday() != 0 or now.hour != 0:
            return

        # Last week's key
        last_week = now - timedelta(days=7)
        year, week_num, _ = last_week.isocalendar()
        last_week_key = f"{year}-W{week_num:02d}"

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT c.circle_id, c.name, c.role_id,
                          COALESCE(s.total_messages, 0) + COALESCE(s.total_reactions, 0) AS score
                   FROM circles c
                   JOIN circle_members cm ON c.circle_id = cm.circle_id
                   LEFT JOIN circle_weekly_stats s ON c.circle_id = s.circle_id AND s.week = ?
                   GROUP BY c.circle_id
                   HAVING COUNT(cm.user_id) >= ?
                   ORDER BY score DESC
                   LIMIT 1""",
                (last_week_key, CIRCLE_MIN_MEMBERS),
            )
            winner = await cursor.fetchone()

        if not winner or winner[3] == 0:
            return

        circle_id, circle_name, role_id, score = winner

        # Award coins to all members
        members = await self._get_circle_members(circle_id)
        for uid in members:
            await add_coins(uid, CIRCLE_WEEKLY_WINNER_COINS)

        # Remove old winner role color if exists, create/update new one
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return

        try:
            # Clean up old winner role
            if role_id:
                old_role = guild.get_role(role_id)
                if old_role:
                    await old_role.delete(reason="Circle weekly reset")

            # Create fresh winner role with accent color
            new_role = await guild.create_role(
                name=f"Top Circle: {circle_name}",
                color=discord.Color(EMBED_COLOR_ACCENT),
                reason="Weekly Circle winner",
            )

            # Store new role ID
            async with aiosqlite.connect(DB_PATH) as db:
                # Clear all circle role_ids first
                await db.execute("UPDATE circles SET role_id = NULL")
                await db.execute(
                    "UPDATE circles SET role_id = ? WHERE circle_id = ?",
                    (new_role.id, circle_id),
                )
                await db.commit()

            # Assign role to members
            for uid in members:
                member_obj = guild.get_member(uid)
                if member_obj:
                    try:
                        await member_obj.add_roles(new_role, reason="Weekly Circle winner")
                    except discord.HTTPException:
                        pass

            # Announce
            announce_channel = discord.utils.get(guild.text_channels, name="general")
            if announce_channel:
                embed = discord.Embed(
                    title="CIRCLE OF THE WEEK",
                    description=(
                        f"**{circle_name}** dominated last week with **{score}** activity points.\n\n"
                        f"Each member earns **{CIRCLE_WEEKLY_WINNER_COINS}** Circles "
                        f"and a temporary group role color.\n\n"
                        f"The ledger resets. Prove yourselves again."
                    ),
                    color=EMBED_COLOR_ACCENT,
                )
                await announce_channel.send(embed=embed)

        except discord.HTTPException as e:
            logger.error(f"Circle weekly reward failed: {e}")

    @weekly_circle_reset.before_loop
    async def before_weekly_circle_reset(self):
        await self.bot.wait_until_ready()

    # ─── Suggestion Engine ───────────────────────────────────────────────────

    @tasks.loop(hours=24)
    async def suggest_circles(self):
        """
        Check for clusters of 3+ mutual active users not in circles.
        DM the highest-ranked suggesting they form one.
        Called externally by social_graph if it exists, or runs daily.
        """
        # This is a placeholder — full social graph integration would
        # query recent message co-occurrence. For now, skip silently.
        pass

    # ─── Error Handling ──────────────────────────────────────────────────────

    @circle_create.error
    @circle_invite.error
    @circle_kick.error
    async def circle_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing argument: `{error.param.name}`. Check `!circle` for usage.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("Could not find that member. Make sure to @mention them.")
        else:
            logger.error(f"Circle command error: {error}")
            await ctx.send("Something went wrong. The Circle is displeased.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Circles(bot))
