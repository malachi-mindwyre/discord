"""
The Circle — Debates Cog
Structured debate system with safety thermostat.
Minority-side bonus, MVP tracking, and automatic heat management.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta

import aiosqlite
import discord
from discord.ext import commands, tasks

from database import DB_PATH, add_coins

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────
DEBATE_DURATION_HOURS = 4
DEBATE_MINORITY_BONUS = 2.0
DEBATE_MVP_COINS = 50
HEAT_THRESHOLD_WARN = 15
HEAT_THRESHOLD_SLOW = 25
HEAT_THRESHOLD_LOCK = 35
HEAT_SLOW_MODE_SECONDS = 30
HEAT_SLOW_MODE_DURATION = 900  # 15 minutes
EMBED_COLOR_PRIMARY = 0x1A1A2E
EMBED_COLOR_ACCENT = 0xE94560
EMBED_COLOR_WARNING = 0xF1C40F

VOTE_WINDOW_MINUTES = 30


class Debates(commands.Cog):
    """Structured debates with heat-based safety controls."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Active debate state: channel_id -> debate info dict
        self.active_debates: dict[int, dict] = {}
        # Heat tracking: channel_id -> list of (timestamp, caps_ratio) tuples
        self.channel_messages: dict[int, list[tuple[datetime, float]]] = defaultdict(list)
        # Track which channels had slow mode applied by us
        self.managed_slowmode: dict[int, datetime] = {}
        # Track locked channels
        self.locked_channels: dict[int, datetime] = {}

        self.heat_monitor.start()
        self.debate_lifecycle.start()

    def cog_unload(self):
        self.heat_monitor.cancel()
        self.debate_lifecycle.cancel()

    # ─── DB Init ─────────────────────────────────────────────────────────────

    async def cog_load(self):
        """Create debate tables on load."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS debate_scores (
                    user_id INTEGER NOT NULL,
                    debate_id TEXT NOT NULL,
                    side TEXT,
                    messages_sent INTEGER DEFAULT 0,
                    reactions_received INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, debate_id)
                );

                CREATE TABLE IF NOT EXISTS debate_history (
                    debate_id TEXT PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    side_a TEXT NOT NULL,
                    side_b TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    votes_a INTEGER DEFAULT 0,
                    votes_b INTEGER DEFAULT 0,
                    mvp_user_id INTEGER,
                    status TEXT DEFAULT 'voting'
                );
            """)
            await db.commit()
        logger.info("Debates tables ready  ✓")

    # ─── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _debate_id(channel_id: int, timestamp: datetime) -> str:
        return f"debate-{channel_id}-{timestamp.strftime('%Y%m%d%H%M%S')}"

    def _get_heat(self, channel_id: int) -> float:
        """Calculate channel heat level: (msgs_per_min * 1) + (caps_ratio * 5)."""
        now = datetime.utcnow()
        window = timedelta(minutes=2)
        # Prune old entries
        recent = [
            (ts, caps) for ts, caps in self.channel_messages[channel_id]
            if now - ts < window
        ]
        self.channel_messages[channel_id] = recent

        if not recent:
            return 0.0

        msgs_per_min = len(recent) / 2.0  # 2-minute window
        avg_caps = sum(c for _, c in recent) / len(recent) if recent else 0.0
        return (msgs_per_min * 1.0) + (avg_caps * 5.0)

    # ─── Message Tracking ────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track messages for heat + debate scoring."""
        if message.author.bot or not message.guild:
            return

        channel_id = message.channel.id

        # Heat tracking for channels with active debates
        if channel_id in self.active_debates:
            text = message.content
            alpha_chars = [c for c in text if c.isalpha()]
            caps_ratio = (
                sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
                if alpha_chars else 0.0
            )
            self.channel_messages[channel_id].append((datetime.utcnow(), caps_ratio))

            # Track debate participation
            debate = self.active_debates[channel_id]
            if debate["status"] == "active":
                debate_id = debate["debate_id"]
                user_side = debate["votes"].get(message.author.id)
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        """INSERT INTO debate_scores (user_id, debate_id, side, messages_sent, reactions_received)
                           VALUES (?, ?, ?, 1, 0)
                           ON CONFLICT(user_id, debate_id) DO UPDATE SET
                           messages_sent = messages_sent + 1,
                           side = COALESCE(?, side)""",
                        (message.author.id, debate_id, user_side, user_side),
                    )
                    await db.commit()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Track reactions on debate messages for MVP calculation."""
        if not payload.guild_id:
            return
        if payload.channel_id not in self.active_debates:
            return

        debate = self.active_debates[payload.channel_id]

        # Handle vote reactions on the debate post
        if debate["status"] == "voting" and payload.message_id == debate.get("vote_message_id"):
            emoji = str(payload.emoji)
            if emoji == "\U0001f44d":  # thumbsup
                debate["votes"][payload.user_id] = "A"
            elif emoji == "\U0001f44e":  # thumbsdown
                debate["votes"][payload.user_id] = "B"
            return

        # Track reactions on debate replies for MVP
        if debate["status"] != "active":
            return

        try:
            channel = self.bot.get_channel(payload.channel_id)
            if not channel:
                return
            msg = await channel.fetch_message(payload.message_id)
            if msg.author.bot:
                return
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

        debate_id = debate["debate_id"]
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO debate_scores (user_id, debate_id, side, messages_sent, reactions_received)
                   VALUES (?, ?, NULL, 0, 1)
                   ON CONFLICT(user_id, debate_id) DO UPDATE SET
                   reactions_received = reactions_received + 1""",
                (msg.author.id, debate_id),
            )
            await db.commit()

    # ─── Commands ────────────────────────────────────────────────────────────

    @commands.group(name="debate", invoke_without_command=True)
    async def debate_cmd(self, ctx: commands.Context):
        """Debate commands. Use !debate start <topic> or !debate vote <side>."""
        if ctx.channel.id in self.active_debates:
            debate = self.active_debates[ctx.channel.id]
            status = debate["status"]
            await ctx.send(
                f"Active debate: **{debate['topic']}** | Status: `{status}`\n"
                f"Side A: {debate['side_a']} | Side B: {debate['side_b']}"
            )
        else:
            await ctx.send("No active debate here. Admins can start one with `!debate start <topic>`.")

    @debate_cmd.command(name="start")
    @commands.has_permissions(administrator=True)
    async def debate_start(self, ctx: commands.Context, *, topic: str):
        """Admin only: Start a structured debate."""
        if ctx.channel.id in self.active_debates:
            await ctx.send("A debate is already active in this channel. Wait for it to end.")
            return

        # Parse topic — support "Topic | Side A | Side B" format
        parts = [p.strip() for p in topic.split("|")]
        if len(parts) >= 3:
            topic_text, side_a, side_b = parts[0], parts[1], parts[2]
        else:
            topic_text = topic
            side_a = "For"
            side_b = "Against"

        now = datetime.utcnow()
        debate_id = self._debate_id(ctx.channel.id, now)

        # Store in DB
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO debate_history
                   (debate_id, channel_id, topic, side_a, side_b, started_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'voting')""",
                (debate_id, ctx.channel.id, topic_text, side_a, side_b, now.isoformat()),
            )
            await db.commit()

        # Build voting embed
        vote_end = now + timedelta(minutes=VOTE_WINDOW_MINUTES)
        embed = discord.Embed(
            title="THE CIRCLE DEMANDS DISCOURSE",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"**{topic_text}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"\U0001f44d **Side A:** {side_a}\n"
                f"\U0001f44e **Side B:** {side_b}\n\n"
                f"Vote with reactions below. Voting closes in **{VOTE_WINDOW_MINUTES} minutes**.\n"
                f"The minority side will receive a **{DEBATE_MINORITY_BONUS}x point bonus** "
                f"on their replies for {DEBATE_DURATION_HOURS} hours."
            ),
            color=EMBED_COLOR_ACCENT,
            timestamp=vote_end,
        )
        embed.set_footer(text="Voting ends")

        try:
            vote_msg = await ctx.send(embed=embed)
            await vote_msg.add_reaction("\U0001f44d")
            await vote_msg.add_reaction("\U0001f44e")
        except discord.HTTPException as e:
            logger.error(f"Failed to post debate embed: {e}")
            return

        # Register active debate
        self.active_debates[ctx.channel.id] = {
            "debate_id": debate_id,
            "topic": topic_text,
            "side_a": side_a,
            "side_b": side_b,
            "started_at": now,
            "vote_end": vote_end,
            "debate_end": now + timedelta(hours=DEBATE_DURATION_HOURS),
            "status": "voting",
            "votes": {},  # user_id -> "A" or "B"
            "vote_message_id": vote_msg.id,
            "minority_side": None,
            "channel_id": ctx.channel.id,
        }

    @debate_cmd.command(name="vote")
    async def debate_vote(self, ctx: commands.Context, side: str):
        """Vote for a side (A or B)."""
        if ctx.channel.id not in self.active_debates:
            await ctx.send("No active debate in this channel.")
            return

        debate = self.active_debates[ctx.channel.id]
        if debate["status"] != "voting":
            await ctx.send("Voting has already ended for this debate.")
            return

        side = side.upper()
        if side not in ("A", "B"):
            await ctx.send("Vote `A` or `B`. Example: `!debate vote A`")
            return

        debate["votes"][ctx.author.id] = side
        side_name = debate["side_a"] if side == "A" else debate["side_b"]
        try:
            await ctx.message.add_reaction("✅")
        except discord.HTTPException:
            pass

    # ─── Lifecycle Task ──────────────────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def debate_lifecycle(self):
        """Manage debate phases: voting -> active -> results."""
        now = datetime.utcnow()
        to_remove = []

        for channel_id, debate in self.active_debates.items():
            try:
                # Phase transition: voting -> active
                if debate["status"] == "voting" and now >= debate["vote_end"]:
                    await self._transition_to_active(channel_id, debate)

                # Phase transition: active -> results
                elif debate["status"] == "active" and now >= debate["debate_end"]:
                    await self._post_results(channel_id, debate)
                    to_remove.append(channel_id)

            except Exception as e:
                logger.error(f"Debate lifecycle error for channel {channel_id}: {e}")

        for cid in to_remove:
            self.active_debates.pop(cid, None)
            self.channel_messages.pop(cid, None)

    @debate_lifecycle.before_loop
    async def before_debate_lifecycle(self):
        await self.bot.wait_until_ready()

    async def _transition_to_active(self, channel_id: int, debate: dict):
        """End voting, determine minority side, announce."""
        votes = debate["votes"]
        votes_a = sum(1 for v in votes.values() if v == "A")
        votes_b = sum(1 for v in votes.values() if v == "B")
        total = votes_a + votes_b

        if total == 0:
            debate["minority_side"] = None
        elif votes_a <= votes_b:
            debate["minority_side"] = "A"
        else:
            debate["minority_side"] = "B"

        debate["status"] = "active"

        # Update DB
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE debate_history SET votes_a = ?, votes_b = ?, status = 'active' WHERE debate_id = ?",
                (votes_a, votes_b, debate["debate_id"]),
            )
            await db.commit()

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        minority_name = (
            debate["side_a"] if debate["minority_side"] == "A"
            else debate["side_b"] if debate["minority_side"] == "B"
            else "None"
        )

        hours_left = DEBATE_DURATION_HOURS
        embed = discord.Embed(
            title="VOTING HAS CLOSED",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"**{debate['topic']}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"\U0001f44d **{debate['side_a']}:** {votes_a} votes\n"
                f"\U0001f44e **{debate['side_b']}:** {votes_b} votes\n\n"
                f"Minority side: **{minority_name}** — replies get **{DEBATE_MINORITY_BONUS}x points** "
                f"for the next **{hours_left} hours**.\n\n"
                f"Debate wisely. The Circle is watching."
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        try:
            await channel.send(embed=embed)
        except discord.HTTPException as e:
            logger.error(f"Failed to post voting results: {e}")

    async def _post_results(self, channel_id: int, debate: dict):
        """Post final results and award MVP."""
        debate_id = debate["debate_id"]
        votes = debate["votes"]
        votes_a = sum(1 for v in votes.values() if v == "A")
        votes_b = sum(1 for v in votes.values() if v == "B")

        # Find MVP (most reactions received during debate)
        mvp_user_id = None
        mvp_reactions = 0
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT user_id, reactions_received, messages_sent
                   FROM debate_scores
                   WHERE debate_id = ?
                   ORDER BY reactions_received DESC, messages_sent DESC
                   LIMIT 1""",
                (debate_id,),
            )
            row = await cursor.fetchone()
            if row and row[1] > 0:
                mvp_user_id = row[0]
                mvp_reactions = row[1]
                await add_coins(mvp_user_id, DEBATE_MVP_COINS)

            # Participation count
            cursor = await db.execute(
                "SELECT COUNT(DISTINCT user_id) FROM debate_scores WHERE debate_id = ?",
                (debate_id,),
            )
            participant_count = (await cursor.fetchone())[0]

            # Update history
            await db.execute(
                """UPDATE debate_history
                   SET ended_at = ?, votes_a = ?, votes_b = ?, mvp_user_id = ?, status = 'ended'
                   WHERE debate_id = ?""",
                (datetime.utcnow().isoformat(), votes_a, votes_b, mvp_user_id, debate_id),
            )
            await db.commit()

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        # MVP mention
        if mvp_user_id:
            mvp_user = self.bot.get_user(mvp_user_id)
            mvp_text = (
                f"👑 **MVP Debater:** {mvp_user.mention if mvp_user else f'User {mvp_user_id}'} "
                f"({mvp_reactions} reactions received) — earned **{DEBATE_MVP_COINS}** Circles"
            )
        else:
            mvp_text = "No MVP this debate — reactions determine the winner of words."

        # Determine winner
        if votes_a > votes_b:
            winner = f"\U0001f44d **{debate['side_a']}** wins the popular vote"
        elif votes_b > votes_a:
            winner = f"\U0001f44e **{debate['side_b']}** wins the popular vote"
        else:
            winner = "A perfect split. The Circle is divided."

        embed = discord.Embed(
            title="DEBATE CONCLUDED",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"**{debate['topic']}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"\U0001f44d **{debate['side_a']}:** {votes_a} votes\n"
                f"\U0001f44e **{debate['side_b']}:** {votes_b} votes\n\n"
                f"{winner}\n"
                f"Participants: **{participant_count}**\n\n"
                f"{mvp_text}"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="The Circle remembers all positions taken.")

        try:
            await channel.send(embed=embed)
        except discord.HTTPException as e:
            logger.error(f"Failed to post debate results: {e}")

    # ─── Heat Monitor (Safety Thermostat) ────────────────────────────────────

    @tasks.loop(minutes=2)
    async def heat_monitor(self):
        """Check heat levels in channels with active debates."""
        now = datetime.utcnow()

        # Restore slow mode for channels where the timer expired
        for channel_id, expire_time in list(self.managed_slowmode.items()):
            if now >= expire_time:
                try:
                    channel = self.bot.get_channel(channel_id)
                    if channel and isinstance(channel, discord.TextChannel):
                        await channel.edit(slowmode_delay=0, reason="Debate heat cooldown expired")
                except discord.HTTPException:
                    pass
                self.managed_slowmode.pop(channel_id, None)

        # Unlock channels where lock timer expired
        for channel_id, expire_time in list(self.locked_channels.items()):
            if now >= expire_time:
                try:
                    channel = self.bot.get_channel(channel_id)
                    if channel and isinstance(channel, discord.TextChannel) and channel.guild:
                        overwrite = channel.overwrites_for(channel.guild.default_role)
                        overwrite.send_messages = None
                        await channel.set_permissions(
                            channel.guild.default_role, overwrite=overwrite,
                            reason="Debate lock expired"
                        )
                        await channel.send(
                            embed=discord.Embed(
                                title="CHANNEL REOPENED",
                                description="The Circle has cooled. You may speak again.",
                                color=EMBED_COLOR_PRIMARY,
                            )
                        )
                except discord.HTTPException:
                    pass
                self.locked_channels.pop(channel_id, None)

        # Check heat for active debate channels
        for channel_id in list(self.active_debates.keys()):
            heat = self._get_heat(channel_id)
            if heat <= 0:
                continue

            channel = self.bot.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                continue

            try:
                if heat > HEAT_THRESHOLD_LOCK and channel_id not in self.locked_channels:
                    # Lock for 1 hour
                    if channel.guild:
                        overwrite = channel.overwrites_for(channel.guild.default_role)
                        overwrite.send_messages = False
                        await channel.set_permissions(
                            channel.guild.default_role, overwrite=overwrite,
                            reason=f"Debate heat critical ({heat:.1f})"
                        )
                    self.locked_channels[channel_id] = now + timedelta(hours=1)
                    await channel.send(
                        embed=discord.Embed(
                            title="CHANNEL LOCKED",
                            description=(
                                "Heat level critical. This channel is locked for **1 hour**.\n"
                                "The Circle does not tolerate chaos."
                            ),
                            color=discord.Color.red(),
                        )
                    )
                    logger.warning(f"Debate channel {channel_id} locked — heat {heat:.1f}")

                elif heat > HEAT_THRESHOLD_SLOW and channel_id not in self.managed_slowmode:
                    # Enable slow mode
                    await channel.edit(
                        slowmode_delay=HEAT_SLOW_MODE_SECONDS,
                        reason=f"Debate heat elevated ({heat:.1f})"
                    )
                    self.managed_slowmode[channel_id] = now + timedelta(seconds=HEAT_SLOW_MODE_DURATION)
                    await channel.send(
                        embed=discord.Embed(
                            title="SLOW MODE ENGAGED",
                            description=(
                                f"The discourse runs hot. **{HEAT_SLOW_MODE_SECONDS}s slow mode** "
                                f"activated for 15 minutes.\n"
                                f"Choose your words carefully."
                            ),
                            color=EMBED_COLOR_WARNING,
                        )
                    )
                    logger.info(f"Debate channel {channel_id} slow mode — heat {heat:.1f}")

                elif heat > HEAT_THRESHOLD_WARN:
                    # Warning message (only send once per cycle, tracked by not re-warning
                    # if slow mode or lock is already active)
                    if channel_id not in self.managed_slowmode and channel_id not in self.locked_channels:
                        await channel.send(
                            embed=discord.Embed(
                                description="**The Circle demands balance.** Keep it civil.",
                                color=EMBED_COLOR_WARNING,
                            )
                        )

            except discord.HTTPException as e:
                logger.error(f"Heat management error for channel {channel_id}: {e}")

    @heat_monitor.before_loop
    async def before_heat_monitor(self):
        await self.bot.wait_until_ready()

    # ─── Error Handling ──────────────────────────────────────────────────────

    @debate_start.error
    async def debate_start_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Only administrators can start debates.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "Usage: `!debate start <topic>` or `!debate start Topic | Side A | Side B`"
            )
        else:
            logger.error(f"Debate start error: {error}")
            await ctx.send("Something went wrong. The Circle is confused.")

    @debate_vote.error
    async def debate_vote_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `!debate vote A` or `!debate vote B`")
        else:
            logger.error(f"Debate vote error: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Debates(bot))
