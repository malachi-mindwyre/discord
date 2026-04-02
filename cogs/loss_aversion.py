"""
The Circle — Loss Aversion Cog
Graduated decay, rank demotion, streak-at-risk notifications,
competitive displacement alerts, and faction relegation.
"""

from __future__ import annotations

import logging
from datetime import datetime, date, timedelta

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    GRADUATED_DECAY_SCHEDULE,
    RANK_DEMOTION_GRACE_DAYS,
    RANK_DEMOTION_ENABLED,
    DISPLACEMENT_PROXIMITY,
    DISPLACEMENT_COOLDOWN_HOURS,
    DISPLACEMENT_MIN_MEMBERS,
    FACTION_LOSING_PENALTY,
    FACTION_RELEGATION_MIN_MEMBERS,
    STREAK_AT_RISK_MIN_STREAK,
    STREAK_AT_RISK_DMS_PER_DAY,
    EMBED_COLOR_ERROR,
    EMBED_COLOR_WARNING,
)
from database import (
    DB_PATH,
    get_inactive_users,
    apply_score_decay,
    get_user,
    get_top_users,
    get_streak,
    update_user_score,
    set_user_score,
    get_messages_today_count,
)
from dm_coordinator import can_dm as global_can_dm, record_dm as global_record_dm
from ranks import get_rank_for_score, RANK_BY_TIER, ALL_RANKS

logger = logging.getLogger(__name__)


# ─── Local DB helpers (demotion_watch, displacement_log) ─────────────────────

async def _ensure_tables():
    """Create loss-aversion-specific tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS demotion_watch (
                user_id INTEGER PRIMARY KEY,
                days_below INTEGER DEFAULT 0,
                first_seen TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS displacement_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                displaced_by INTEGER NOT NULL,
                old_position INTEGER NOT NULL,
                new_position INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_displacement_user
                ON displacement_log(user_id, timestamp);
        """)
        await db.commit()


async def _get_demotion_watch(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM demotion_watch WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def _set_demotion_watch(user_id: int, days: int):
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO demotion_watch (user_id, days_below, first_seen)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET days_below = ?""",
            (user_id, days, now, days),
        )
        await db.commit()


async def _clear_demotion_watch(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM demotion_watch WHERE user_id = ?", (user_id,))
        await db.commit()


async def _get_last_displacement(user_id: int) -> str | None:
    """Return ISO timestamp of the last displacement alert for this user."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT timestamp FROM displacement_log WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def _log_displacement(user_id: int, displaced_by: int, old_pos: int, new_pos: int):
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO displacement_log (user_id, displaced_by, old_position, new_position, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, displaced_by, old_pos, new_pos, now),
        )
        await db.commit()


# ─── Cog ─────────────────────────────────────────────────────────────────────

class LossAversion(commands.Cog):
    """Keeper's darker side — decay, demotion, displacement, and streak warnings."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._tables_ready = False
        self._streak_dm_sent_today: dict[int, int] = {}  # user_id -> count
        self._streak_dm_date: str = ""

    @commands.Cog.listener()
    async def on_ready(self):
        """Start background tasks (guard against double-start on reconnect)."""
        if not self.daily_decay_and_demotion.is_running():
            self.daily_decay_and_demotion.start()
        if not self.streak_at_risk_check.is_running():
            self.streak_at_risk_check.start()
        if not self.faction_relegation.is_running():
            self.faction_relegation.start()

    def cog_unload(self):
        self.daily_decay_and_demotion.cancel()
        self.streak_at_risk_check.cancel()
        self.faction_relegation.cancel()

    async def _ensure_ready(self):
        if not self._tables_ready:
            await _ensure_tables()
            self._tables_ready = True

    # ── Helper: resolve guild ────────────────────────────────────────────────

    def _get_guild(self) -> discord.Guild | None:
        """Return the first guild the bot is in (The Circle)."""
        return self.bot.guilds[0] if self.bot.guilds else None

    # ═════════════════════════════════════════════════════════════════════════
    # 1. GRADUATED DECAY  (daily)
    # ═════════════════════════════════════════════════════════════════════════

    @tasks.loop(hours=24)
    async def daily_decay_and_demotion(self):
        """Apply graduated decay to inactive users, then check for rank demotions."""
        await self._ensure_ready()

        # --- Graduated decay ---
        # Sort schedule so we process the longest absence tier first
        sorted_schedule = sorted(GRADUATED_DECAY_SCHEDULE.items(), reverse=True)

        for days_threshold, rate in sorted_schedule:
            inactive_users = await get_inactive_users(days_threshold)
            for user_data in inactive_users:
                user_id = user_data["user_id"]
                if user_data["total_score"] <= 0:
                    continue

                # Determine exact days inactive for graduated rate
                last_active = datetime.fromisoformat(user_data["last_active"])
                days_inactive = (datetime.utcnow() - last_active).days

                # Find the correct rate for this user's inactivity duration
                applicable_rate = 0.0
                for threshold in sorted(GRADUATED_DECAY_SCHEDULE.keys()):
                    if days_inactive >= threshold:
                        applicable_rate = GRADUATED_DECAY_SCHEDULE[threshold]

                if applicable_rate > 0:
                    await apply_score_decay(user_id, applicable_rate)
                    logger.info(
                        "Decay applied: user %s — %d days inactive — %.1f%% decay",
                        user_id, days_inactive, applicable_rate * 100,
                    )

        # --- Rank demotion check ---
        if RANK_DEMOTION_ENABLED:
            await self._check_demotions()

    @daily_decay_and_demotion.before_loop
    async def before_daily_decay(self):
        await self.bot.wait_until_ready()

    # ═════════════════════════════════════════════════════════════════════════
    # 2. RANK DEMOTION
    # ═════════════════════════════════════════════════════════════════════════

    async def _check_demotions(self):
        """Check all users whose score has fallen below their rank threshold."""
        guild = self._get_guild()
        if not guild:
            return

        # Get all users who have decayed (score > 0 ensures they exist)
        min_days = min(GRADUATED_DECAY_SCHEDULE.keys())
        decayed_users = await get_inactive_users(min_days)

        for user_data in decayed_users:
            user_id = user_data["user_id"]
            current_tier = user_data["current_rank"]
            score = user_data["total_score"]

            if current_tier <= 1:
                await _clear_demotion_watch(user_id)
                continue

            current_rank = RANK_BY_TIER.get(current_tier)
            if not current_rank:
                continue

            # Is the user's score below their current rank's threshold?
            if score < current_rank.threshold:
                watch = await _get_demotion_watch(user_id)
                days_below = (watch["days_below"] + 1) if watch else 1
                await _set_demotion_watch(user_id, days_below)

                if days_below >= RANK_DEMOTION_GRACE_DAYS:
                    # Demote: find the correct rank for their current score
                    new_rank = get_rank_for_score(score)
                    await set_user_score(user_id, score, new_rank.tier)
                    await _clear_demotion_watch(user_id)

                    # Announce demotion
                    await self._announce_demotion(guild, user_id, current_rank, new_rank, score)
                    logger.info(
                        "Demotion: user %s — %s → %s (score: %.0f)",
                        user_id, current_rank.name, new_rank.name, score,
                    )
            else:
                # Score is back above threshold — clear the watch
                await _clear_demotion_watch(user_id)

    async def _announce_demotion(
        self,
        guild: discord.Guild,
        user_id: int,
        old_rank,
        new_rank,
        score: float,
    ):
        """Post demotion embed in #rank-ups and DM the user."""
        member = guild.get_member(user_id)
        mention = member.mention if member else f"<@{user_id}>"
        display_name = member.display_name if member else str(user_id)

        embed = discord.Embed(
            title="💀 RANK LOST",
            description=(
                f"The Circle giveth... and The Circle taketh away.\n\n"
                f"{mention} has fallen from **{old_rank.name}** to **{new_rank.name}**.\n\n"
                f"*Inactivity claims another. Return before more is lost.*"
            ),
            color=EMBED_COLOR_ERROR,
        )
        embed.add_field(
            name="Score",
            value=f"**{score:,.0f}** pts",
            inline=True,
        )
        embed.add_field(
            name="New Rank",
            value=f"**{new_rank.name}**\n*{new_rank.tagline}*",
            inline=True,
        )
        embed.set_footer(text="The Circle • Absence has consequences")

        if member:
            embed.set_thumbnail(url=member.display_avatar.url)

        # Post in #rank-ups
        rank_ups = discord.utils.get(guild.text_channels, name="rank-ups")
        if rank_ups:
            try:
                await rank_ups.send(embed=embed)
            except discord.HTTPException:
                pass

        # Update roles
        if member:
            old_role = discord.utils.get(guild.roles, name=old_rank.name)
            new_role = discord.utils.get(guild.roles, name=new_rank.name)
            if old_role and old_role in member.roles:
                try:
                    await member.remove_roles(old_role, reason="Rank demotion")
                except discord.HTTPException:
                    pass
            if new_role:
                try:
                    await member.add_roles(new_role, reason="Rank demotion")
                except discord.HTTPException:
                    pass

        # DM the user
        if member:
            dm_embed = discord.Embed(
                title="💀 YOU'VE BEEN DEMOTED",
                description=(
                    f"Your absence has cost you, **{display_name}**.\n\n"
                    f"**{old_rank.name}** → **{new_rank.name}**\n\n"
                    f"Your score has decayed to **{score:,.0f}** pts. "
                    f"Return to The Circle and reclaim what was yours — "
                    f"before more is taken."
                ),
                color=EMBED_COLOR_ERROR,
            )
            dm_embed.set_footer(text="The Circle • The Keeper remembers")
            try:
                await member.send(embed=dm_embed)
            except (discord.HTTPException, discord.Forbidden):
                pass

    # ═════════════════════════════════════════════════════════════════════════
    # 3. STREAK-AT-RISK NOTIFICATIONS  (every 30 min)
    # ═════════════════════════════════════════════════════════════════════════

    @tasks.loop(minutes=30)
    async def streak_at_risk_check(self):
        """At 10 PM UTC, warn users about to lose their streak (1 DM/day max)."""
        now = datetime.utcnow()
        current_hour = now.hour
        current_minute = now.minute

        # Only fire at 10 PM UTC (22:00) — single warning per day
        if not (current_hour == 22 and current_minute < 15):
            return

        # Reset daily tracker
        today_str = now.strftime("%Y-%m-%d")
        if self._streak_dm_date != today_str:
            self._streak_dm_sent_today.clear()
            self._streak_dm_date = today_str

        guild = self._get_guild()
        if not guild:
            return

        # Get users with streaks >= threshold (default 7)
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT user_id, current_streak FROM streaks WHERE current_streak >= ?",
                (STREAK_AT_RISK_MIN_STREAK,),
            )
            streak_users = [dict(row) for row in await cursor.fetchall()]

        for streak_data in streak_users:
            user_id = streak_data["user_id"]
            streak_length = streak_data["current_streak"]

            # Check daily DM limit
            if self._streak_dm_sent_today.get(user_id, 0) >= STREAK_AT_RISK_DMS_PER_DAY:
                continue

            # Check if they've messaged today
            msgs_today = await get_messages_today_count(user_id)
            if msgs_today > 0:
                continue  # Safe — already active today

            member = guild.get_member(user_id)
            if not member:
                continue

            # Check global DM coordinator before sending
            if not await global_can_dm(user_id, "loss_aversion"):
                continue

            embed = discord.Embed(
                title="🔥 STREAK AT RISK — FINAL WARNING",
                description=(
                    f"**{member.display_name}**, your **{streak_length}-day streak** "
                    f"dies at midnight UTC.\n\n"
                    f"That's **{streak_length} days** of dedication — gone.\n\n"
                    f"*One message. That's all it takes.*"
                ),
                color=EMBED_COLOR_ERROR,
            )
            embed.set_footer(text="The Circle • The Keeper is watching")

            try:
                await member.send(embed=embed)
                await global_record_dm(user_id, "loss_aversion")
                self._streak_dm_sent_today[user_id] = self._streak_dm_sent_today.get(user_id, 0) + 1
            except (discord.HTTPException, discord.Forbidden):
                pass

    @streak_at_risk_check.before_loop
    async def before_streak_check(self):
        await self.bot.wait_until_ready()

    # ═════════════════════════════════════════════════════════════════════════
    # 4. COMPETITIVE DISPLACEMENT ALERTS
    # ═════════════════════════════════════════════════════════════════════════

    async def check_displacement(
        self,
        climber_id: int,
        old_position: int,
        new_position: int,
    ):
        """
        Called externally when a user moves up the leaderboard.
        Alerts users who were displaced from the top positions.

        Parameters
        ----------
        climber_id : int
            The user who moved up.
        old_position : int
            The climber's previous leaderboard position (1-indexed).
        new_position : int
            The climber's new leaderboard position (1-indexed).
        """
        await self._ensure_ready()
        guild = self._get_guild()
        if not guild:
            return

        # Skip at small scale — too noisy
        if guild.member_count < DISPLACEMENT_MIN_MEMBERS:
            return

        # Only alert if the climber entered the top N
        if new_position > DISPLACEMENT_PROXIMITY:
            return

        top_users = await get_top_users(limit=DISPLACEMENT_PROXIMITY + 5)

        # Find users who got pushed down (those between new_position and old_position)
        for i, user_data in enumerate(top_users):
            position = i + 1  # 1-indexed
            displaced_id = user_data["user_id"]

            if displaced_id == climber_id:
                continue

            # Only alert users in the proximity zone who got bumped
            if position < new_position or position > DISPLACEMENT_PROXIMITY:
                continue

            # Check cooldown
            last_ts = await _get_last_displacement(displaced_id)
            if last_ts:
                last_dt = datetime.fromisoformat(last_ts)
                if (datetime.utcnow() - last_dt).total_seconds() < DISPLACEMENT_COOLDOWN_HOURS * 3600:
                    continue

            await _log_displacement(displaced_id, climber_id, position - 1, position)

            member = guild.get_member(displaced_id)
            climber_member = guild.get_member(climber_id)
            climber_name = climber_member.display_name if climber_member else "Someone"

            if member:
                embed = discord.Embed(
                    title="👀 YOU'VE BEEN OVERTAKEN",
                    description=(
                        f"**{climber_name}** just passed you on the leaderboard.\n\n"
                        f"You've dropped to **#{position}**. "
                        f"Are you going to let that stand?"
                    ),
                    color=EMBED_COLOR_WARNING,
                )
                embed.set_footer(text="The Circle • Reclaim your position")
                try:
                    await member.send(embed=embed)
                except (discord.HTTPException, discord.Forbidden):
                    pass

            # Post in #leaderboard
            leaderboard_ch = discord.utils.get(guild.text_channels, name="leaderboard")
            if leaderboard_ch:
                mention = member.mention if member else f"<@{displaced_id}>"
                climber_mention = climber_member.mention if climber_member else f"<@{climber_id}>"
                try:
                    await leaderboard_ch.send(
                        f"⚔️ **{climber_mention}** just overtook {mention} "
                        f"for **#{new_position}** on the leaderboard!",
                        delete_after=3600,
                    )
                except discord.HTTPException:
                    pass

    # ═════════════════════════════════════════════════════════════════════════
    # 5. FACTION RELEGATION  (weekly, Monday)
    # ═════════════════════════════════════════════════════════════════════════

    @tasks.loop(hours=168)  # Weekly
    async def faction_relegation(self):
        """Find last-place faction, lock their channel for 24h, announce shame."""
        now = datetime.utcnow()
        # Only run on Monday
        if now.weekday() != 0:
            return

        guild = self._get_guild()
        if not guild:
            return

        # Skip at small scale — punishing, not motivating
        if guild.member_count < FACTION_RELEGATION_MIN_MEMBERS:
            return

        # Get last week's faction scores
        last_week = (now - timedelta(days=7)).strftime("%Y-W%W")

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT team_name, total_score FROM faction_scores WHERE week = ? ORDER BY total_score ASC",
                (last_week,),
            )
            rows = [dict(row) for row in await cursor.fetchall()]

        if not rows:
            return

        last_place = rows[0]
        team_name = last_place["team_name"]
        team_score = last_place["total_score"]

        # Map faction names to channel names
        faction_channels = {
            "Inferno": "team-inferno",
            "Frost": "team-frost",
            "Venom": "team-venom",
            "Volt": "team-volt",
        }

        channel_name = faction_channels.get(team_name)
        if not channel_name:
            return

        team_channel = discord.utils.get(guild.text_channels, name=channel_name)
        faction_war_ch = discord.utils.get(guild.text_channels, name="faction-war")

        # Lock the losing team's channel (deny send messages for @everyone)
        if team_channel:
            overwrite = team_channel.overwrites_for(guild.default_role)
            overwrite.send_messages = False
            try:
                await team_channel.set_permissions(
                    guild.default_role,
                    overwrite=overwrite,
                    reason=f"Faction relegation — {team_name} finished last",
                )
                logger.info("Faction relegation: locked #%s for 24h", channel_name)
            except discord.HTTPException:
                pass

            # Post shame message in the locked channel
            shame_embed = discord.Embed(
                title="🔒 CHANNEL LOCKED — RELEGATION",
                description=(
                    f"**Team {team_name}** finished last this week with "
                    f"**{team_score:,.0f}** points.\n\n"
                    f"This channel is **read-only for 24 hours** as penance.\n\n"
                    f"*Come back stronger next week.*"
                ),
                color=EMBED_COLOR_ERROR,
            )
            shame_embed.set_footer(text="The Circle • The weak are silenced")
            try:
                await team_channel.send(embed=shame_embed)
            except discord.HTTPException:
                pass

        # Announce in #faction-war
        if faction_war_ch:
            announce_embed = discord.Embed(
                title="⚔️ FACTION RELEGATION",
                description=(
                    f"**Team {team_name}** finished in last place with "
                    f"**{team_score:,.0f}** points.\n\n"
                    f"Their channel has been **locked for 24 hours**. 💀\n\n"
                    f"Let this be a warning to all factions."
                ),
                color=EMBED_COLOR_ERROR,
            )
            announce_embed.set_footer(text="The Circle • Compete or be silenced")
            try:
                await faction_war_ch.send(embed=announce_embed)
            except discord.HTTPException:
                pass

        # Schedule unlock after 24 hours
        self.bot.loop.call_later(
            86400,  # 24 hours in seconds
            lambda: self.bot.loop.create_task(
                self._unlock_faction_channel(guild, team_channel)
            ),
        )

    async def _unlock_faction_channel(
        self, guild: discord.Guild, channel: discord.TextChannel | None
    ):
        """Re-enable sending in a faction channel after relegation ends."""
        if not channel:
            return
        overwrite = channel.overwrites_for(guild.default_role)
        overwrite.send_messages = None  # Reset to default
        try:
            await channel.set_permissions(
                guild.default_role,
                overwrite=overwrite,
                reason="Faction relegation period ended",
            )
            await channel.send("🔓 **Channel unlocked.** Your relegation is over. Don't finish last again.")
            logger.info("Faction relegation ended: unlocked #%s", channel.name)
        except discord.HTTPException:
            pass

    @faction_relegation.before_loop
    async def before_faction_relegation(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(LossAversion(bot))
