"""
The Circle — Unified Re-Engagement Pipeline (8 Tiers)
Replaces smart_dm.py with an escalating 8-tier outreach system.
Day 1 streak warning (server), Day 2-60 DMs with personalized data.
Background task runs every 6 hours. Rate-limited: max 1 DM per 5 days per user.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import EMBED_COLOR_PRIMARY, EMBED_COLOR_ACCENT, GUILD_ID
from database import DB_PATH, get_inactive_users, get_user, get_streak, get_onboarding_state
from dm_coordinator import can_dm as global_can_dm, record_dm as global_record_dm, ensure_dm_table as ensure_dm_coordinator_table
from ranks import get_rank_for_score, get_next_rank, RANK_BY_TIER

logger = logging.getLogger("circle.reengagement")

# ─── Tier Definitions ───────────────────────────────────────────────────────
# Each tier: (day_threshold, tier_id, is_dm)
TIERS = [
    (1, "day1_streak_warning", False),   # Server-side (#general)
    (2, "day2_streak_lost", True),
    (3, "day3_fomo", True),
    (5, "day5_rank_fomo", True),
    (7, "day7_comeback_window", True),
    (14, "day14_decay_warning", True),
    (30, "day30_nostalgia", True),
    (60, "day60_final", True),
]

# Map day thresholds for quick lookup
TIER_DAY_MAP = {day: (tier_id, is_dm) for day, tier_id, is_dm in TIERS}

DM_RATE_LIMIT_DAYS = 5  # Max 1 DM per 5 days per user


# ─── Database Operations ────────────────────────────────────────────────────

async def _ensure_table():
    """Create the reengagement_state table if it doesn't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reengagement_state (
                user_id INTEGER PRIMARY KEY,
                last_active TEXT,
                current_tier TEXT DEFAULT '',
                last_dm_sent TEXT,
                last_dm_tier TEXT DEFAULT '',
                total_dms_sent INTEGER DEFAULT 0,
                opted_out INTEGER DEFAULT 0
            )
        """)
        await db.commit()


async def _get_state(user_id: int) -> Optional[dict]:
    """Get re-engagement state for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reengagement_state WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def _upsert_state(
    user_id: int,
    current_tier: str = "",
    last_dm_sent: str | None = None,
    last_dm_tier: str = "",
    total_dms_sent: int = 0,
    opted_out: int = 0,
):
    """Insert or update re-engagement state."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO reengagement_state
               (user_id, last_active, current_tier, last_dm_sent, last_dm_tier, total_dms_sent, opted_out)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   current_tier = excluded.current_tier,
                   last_dm_sent = COALESCE(excluded.last_dm_sent, last_dm_sent),
                   last_dm_tier = CASE WHEN excluded.last_dm_tier != '' THEN excluded.last_dm_tier ELSE last_dm_tier END,
                   total_dms_sent = total_dms_sent + excluded.total_dms_sent,
                   opted_out = excluded.opted_out
            """,
            (user_id, now, current_tier, last_dm_sent, last_dm_tier, total_dms_sent, opted_out),
        )
        await db.commit()


async def _can_dm(user_id: int) -> bool:
    """Check if we can DM this user (rate limit: 1 DM per 5 days)."""
    state = await _get_state(user_id)
    if not state:
        return True
    if state["opted_out"]:
        return False
    if not state["last_dm_sent"]:
        return True
    last_sent = datetime.fromisoformat(state["last_dm_sent"])
    return (datetime.utcnow() - last_sent).days >= DM_RATE_LIMIT_DAYS


async def _get_user_top_channel(user_id: int) -> Optional[int]:
    """Get the channel where the user is most active."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT channel_id, COUNT(*) as msg_count
               FROM messages WHERE user_id = ?
               GROUP BY channel_id ORDER BY msg_count DESC LIMIT 1""",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def _get_best_friend(user_id: int) -> Optional[int]:
    """Get the user's top friend from social_graph."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM social_graph
               WHERE (user_a = ? OR user_b = ?) AND friendship_score > 0
               ORDER BY friendship_score DESC LIMIT 1""",
            (user_id, user_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        row = dict(row)
        return row["user_b"] if row["user_a"] == user_id else row["user_a"]


async def _get_recent_rankups(days: int = 7) -> int:
    """Count how many users ranked up in the last N days."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM rank_history WHERE timestamp > ?", (cutoff,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def _get_achievements_count(user_id: int) -> int:
    """Count badges a user has earned."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM achievements WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


# ─── Embed Builders ─────────────────────────────────────────────────────────

def _keeper_embed(title: str, description: str, *, accent: bool = False) -> discord.Embed:
    """Build a standard Keeper-themed embed."""
    color = EMBED_COLOR_ACCENT if accent else EMBED_COLOR_PRIMARY
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="The Circle \u2022 Keeper watches all")
    return embed


# ─── The Cog ────────────────────────────────────────────────────────────────

class Reengagement(commands.Cog):
    """8-tier re-engagement pipeline. Runs every 6 hours."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Start background tasks (guard against double-start on reconnect)."""
        if not self.reengagement_loop.is_running():
            self.reengagement_loop.start()

    def cog_unload(self):
        self.reengagement_loop.cancel()

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(GUILD_ID)

    def _get_general(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        for ch in guild.text_channels:
            if ch.name == "general":
                return ch
        return None

    def _get_applicable_tier(self, days_inactive: int) -> Optional[tuple[int, str, bool]]:
        """Return the highest-matching tier for a given inactivity duration."""
        matched = None
        for day, tier_id, is_dm in TIERS:
            if days_inactive >= day:
                matched = (day, tier_id, is_dm)
        return matched

    # ── Tier Message Generators ──────────────────────────────────────────

    async def _build_day1(self, member: discord.Member, streak: int) -> Optional[discord.Embed]:
        """Day 1: Server-side streak warning. Only fires if streak >= 3."""
        if streak < 3:
            return None
        embed = _keeper_embed(
            "\u26a0\ufe0f STREAK AT RISK",
            (
                f"**{member.mention}**'s **{streak}-day streak** is at risk.\n\n"
                f"Tag them before midnight or The Circle forgets.\n"
                f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
            ),
            accent=True,
        )
        return embed

    async def _build_day2(self, member: discord.Member, streak: int) -> discord.Embed:
        """Day 2: Streak lost warning DM."""
        return _keeper_embed(
            "\ud83d\udea8 YOUR STREAK IS DYING",
            (
                f"You missed yesterday. Your **{streak}-day streak** is gone "
                f"unless you come back **TODAY**.\n\n"
                f"One message. That's all it takes.\n"
                f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
            ),
            accent=True,
        )

    async def _build_day3(
        self, member: discord.Member, guild: discord.Guild
    ) -> discord.Embed:
        """Day 3: FOMO — top channel + friend activity."""
        top_channel_id = await _get_user_top_channel(member.id)
        friend_id = await _get_best_friend(member.id)

        channel_text = "your favourite channels"
        if top_channel_id:
            ch = guild.get_channel(top_channel_id)
            if ch:
                channel_text = f"**#{ch.name}**"

        friend_text = "People"
        if friend_id:
            friend_member = guild.get_member(friend_id)
            if friend_member:
                friend_text = f"**{friend_member.display_name}**"

        return _keeper_embed(
            "\ud83d\udd25 YOU'RE MISSING OUT",
            (
                f"{channel_text} is going off right now. {friend_text} posted.\n\n"
                f"\u26a1 **3x comeback bonus** is waiting for you. Every message "
                f"counts 3x. Don't waste it.\n"
                f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
            ),
            accent=True,
        )

    async def _build_day5(self, member: discord.Member, user_data: dict) -> discord.Embed:
        """Day 5: Rank FOMO — people ranking up without them."""
        rankups = await _get_recent_rankups(7)
        next_rank = get_next_rank(user_data["current_rank"])
        current_score = user_data["total_score"]

        next_info = ""
        if next_rank:
            pts_needed = next_rank.min_score - current_score
            next_info = f"**{next_rank.name}** is only **{max(0, pts_needed):,.0f} pts** away."

        return _keeper_embed(
            "\ud83d\udcc8 THEY'RE PASSING YOU",
            (
                f"**{rankups}** people ranked up since you left.\n\n"
                f"{next_info}\n"
                f"The Circle doesn't wait.\n"
                f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
            ),
        )

    async def _build_day7(self, member: discord.Member) -> discord.Embed:
        """Day 7: 3x comeback window announcement."""
        return _keeper_embed(
            "\u26a1 3x COMEBACK WINDOW ACTIVE",
            (
                "Every single message you send = **3x points**.\n\n"
                "Return before Day 30 and this becomes **5x**. After Day 60, it drops to **3x** permanently.\n\n"
                "The Circle rewards those who return. Don't let it slip.\n"
                "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
            ),
            accent=True,
        )

    async def _build_day14(self, member: discord.Member, user_data: dict) -> discord.Embed:
        """Day 14: Pre-decay warning — decay starts at Day 30."""
        current_score = user_data["total_score"]

        return _keeper_embed(
            "\ud83d\udcc9 DECAY IS COMING",
            (
                f"Your score is **{current_score:,.0f}** — for now.\n\n"
                f"At Day 30, score decay begins. **0.5% per day**, accelerating to **5% per day** the longer you're gone.\n\n"
                f"\u26a1 **3x comeback bonus** is still active. Return now before it gets worse.\n"
                f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
            ),
            accent=True,
        )

    async def _build_day30(self, member: discord.Member, user_data: dict) -> discord.Embed:
        """Day 30: Nostalgia — their legacy in The Circle. Peak 5x window."""
        streak_data = await get_streak(member.id)
        badges = await _get_achievements_count(member.id)
        rank_info = RANK_BY_TIER.get(user_data["current_rank"])
        rank_name = rank_info.name if rank_info else f"Tier {user_data['current_rank']}"

        return _keeper_embed(
            "\ud83d\udd2e THE CIRCLE REMEMBERS YOU",
            (
                f"**Your legacy:**\n"
                f"\ud83d\udd25 Longest streak: **{streak_data['longest_streak']} days**\n"
                f"\ud83c\udfc5 Badges earned: **{badges}**\n"
                f"\ud83d\udc51 Rank reached: **{rank_name}**\n"
                f"\ud83d\udcca Score: **{user_data['total_score']:,.0f}** (decaying daily)\n\n"
                f"Right now you have the **peak 5x comeback bonus**. After Day 60, it drops to **3x** permanently.\n\n"
                f"Keeper doesn't forget. But Keeper stops asking.\n"
                f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
            ),
        )

    async def _build_day60(self, member: discord.Member) -> discord.Embed:
        """Day 60: Final message. After this, opted_out = 1."""
        return _keeper_embed(
            "\u26ab FINAL TRANSMISSION",
            (
                "This is the last time Keeper reaches out.\n\n"
                "If you return, you'll still get a **3x bonus**.\n"
                "But The Circle moves on. New faces. New legends.\n\n"
                "Your seat stays empty unless you fill it.\n\n"
                "*\u2014 Keeper*\n"
                "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
            ),
        )

    # ── Main Loop ────────────────────────────────────────────────────────

    @tasks.loop(hours=6)
    async def reengagement_loop(self):
        """Process all inactive users through the 8-tier pipeline."""
        await _ensure_table()

        guild = self._get_guild()
        if not guild:
            logger.warning("Reengagement: guild not found")
            return

        general = self._get_general(guild)

        # Query ALL users from the users table and compute inactivity
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE total_score > 0"
            )
            all_users = [dict(row) for row in await cursor.fetchall()]

        now = datetime.utcnow()

        for user_data in all_users:
            user_id = user_data["user_id"]

            # Calculate days inactive
            try:
                last_active = datetime.fromisoformat(user_data["last_active"])
            except (ValueError, TypeError):
                continue
            days_inactive = (now - last_active).days

            if days_inactive < 1:
                continue

            # Skip users still in onboarding pipeline
            ob_state = await get_onboarding_state(user_id)
            if ob_state and ob_state.get("stage") != "graduated":
                continue

            # Check opt-out
            state = await _get_state(user_id)
            if state and state["opted_out"]:
                continue

            # Determine which tier applies
            tier_match = self._get_applicable_tier(days_inactive)
            if not tier_match:
                continue

            day, tier_id, is_dm = tier_match

            # Skip if we already processed this tier for this user
            if state and state["current_tier"] == tier_id:
                continue

            member = guild.get_member(user_id)
            if not member:
                continue

            # ── Tier 1 (Day 1): Server message ──────────────────────────
            if tier_id == "day1_streak_warning":
                streak_data = await get_streak(user_id)
                streak = streak_data.get("current_streak", 0)
                embed = await self._build_day1(member, streak)
                if embed and general:
                    try:
                        await general.send(embed=embed)
                    except discord.HTTPException:
                        pass
                # Update state (no DM rate limit for server messages)
                await _upsert_state(user_id, current_tier=tier_id)
                continue

            # ── DM Tiers (Day 2+) ───────────────────────────────────────
            if not await _can_dm(user_id):
                continue
            # Also check global DM coordinator (cross-cog rate limiting)
            if not await global_can_dm(user_id, "reengagement", priority=True):
                continue

            embed: Optional[discord.Embed] = None

            if tier_id == "day2_streak_lost":
                streak_data = await get_streak(user_id)
                streak = streak_data.get("current_streak", 0)
                embed = await self._build_day2(member, max(streak, 1))

            elif tier_id == "day3_fomo":
                embed = await self._build_day3(member, guild)

            elif tier_id == "day5_rank_fomo":
                embed = await self._build_day5(member, user_data)

            elif tier_id == "day7_comeback_window":
                embed = await self._build_day7(member)

            elif tier_id == "day14_decay_warning":
                embed = await self._build_day14(member, user_data)

            elif tier_id == "day30_nostalgia":
                embed = await self._build_day30(member, user_data)

            elif tier_id == "day60_final":
                embed = await self._build_day60(member)

            if embed is None:
                continue

            # Send the DM
            dm_sent = False
            try:
                await member.send(embed=embed)
                await global_record_dm(user_id, "reengagement")
                dm_sent = True
                logger.info(
                    "Reengagement DM sent: user=%s tier=%s days_inactive=%d",
                    user_id, tier_id, days_inactive,
                )
            except (discord.HTTPException, discord.Forbidden):
                logger.debug(
                    "Reengagement DM failed (blocked/disabled): user=%s tier=%s",
                    user_id, tier_id,
                )

            # Always advance tier (even if DM failed) to prevent stuck pipeline
            now_iso = datetime.utcnow().isoformat()
            opted = 1 if tier_id == "day60_final" else 0
            await _upsert_state(
                user_id,
                current_tier=tier_id,
                last_dm_sent=now_iso if dm_sent else None,
                last_dm_tier=tier_id,
                total_dms_sent=1 if dm_sent else 0,
                opted_out=opted,
            )

    @reengagement_loop.before_loop
    async def before_reengagement_loop(self):
        await self.bot.wait_until_ready()

    # ── Listener: Reset state when user comes back ───────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """When a user sends a message, clear their re-engagement state."""
        if message.author.bot:
            return

        state = await _get_state(message.author.id)
        if state and state["current_tier"]:
            # User came back — reset their tier so pipeline restarts fresh
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """UPDATE reengagement_state
                       SET current_tier = '', opted_out = 0
                       WHERE user_id = ?""",
                    (message.author.id,),
                )
                await db.commit()


async def setup(bot: commands.Bot):
    await _ensure_table()
    await ensure_dm_coordinator_table()
    await bot.add_cog(Reengagement(bot))
