"""
The Circle — Season Pass Cog
8-week seasonal battle pass with 50 tiers, weekly/daily challenges,
free and premium reward tracks, and end-of-season ceremonies.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, date, timedelta, timezone
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    EMBED_COLOR_SUCCESS,
    ECONOMY_CURRENCY_EMOJI,
    ECONOMY_CURRENCY_NAME,
)
from database import DB_PATH, add_coins, spend_coins

logger = logging.getLogger("circle.season_pass")

# ─── Season Config ────────────────────────────────────────────────────────────
SEASON_LENGTH_WEEKS = 8
SEASON_PASS_TIERS = 50
SEASON_PASS_PREMIUM_COST = 5000
SEASON_EARLY_BIRD_HOURS = 48
SEASON_EARLY_BIRD_MULT = 2.0
OFF_SEASON_DAYS = 7

# XP required per tier (exponential curve).  Tier 1 = 0 XP, tier 50 ≈ 50k total.
# Each tier costs slightly more than the last.
_TIER_XP: list[int] = []
for _t in range(SEASON_PASS_TIERS):
    if _t == 0:
        _TIER_XP.append(0)
    else:
        _TIER_XP.append(int(100 * (1.08 ** _t)))

TIER_CUMULATIVE_XP: list[int] = []
_running = 0
for _x in _TIER_XP:
    _running += _x
    TIER_CUMULATIVE_XP.append(_running)

# Free rewards every 5 tiers: {tier: description}
SEASON_FREE_REWARDS: dict[int, dict] = {
    5:  {"coins": 200,  "label": f"200 {ECONOMY_CURRENCY_EMOJI}"},
    10: {"coins": 400,  "label": f"400 {ECONOMY_CURRENCY_EMOJI}"},
    15: {"coins": 600,  "label": f"600 {ECONOMY_CURRENCY_EMOJI}"},
    20: {"coins": 1000, "label": f"1,000 {ECONOMY_CURRENCY_EMOJI}"},
    25: {"coins": 1500, "label": f"1,500 {ECONOMY_CURRENCY_EMOJI} + Badge: Halfway There"},
    30: {"coins": 2000, "label": f"2,000 {ECONOMY_CURRENCY_EMOJI}"},
    35: {"coins": 2500, "label": f"2,500 {ECONOMY_CURRENCY_EMOJI}"},
    40: {"coins": 3000, "label": f"3,000 {ECONOMY_CURRENCY_EMOJI}"},
    45: {"coins": 4000, "label": f"4,000 {ECONOMY_CURRENCY_EMOJI}"},
    50: {"coins": 5000, "label": f"5,000 {ECONOMY_CURRENCY_EMOJI} + Badge: Season Champion"},
}

# Premium bonus rewards (on top of free rewards at same tiers, plus extras)
SEASON_PREMIUM_REWARDS: dict[int, dict] = {
    5:  {"coins": 300,  "label": f"300 {ECONOMY_CURRENCY_EMOJI} bonus"},
    10: {"coins": 500,  "label": f"500 {ECONOMY_CURRENCY_EMOJI} bonus"},
    15: {"coins": 700,  "label": f"700 {ECONOMY_CURRENCY_EMOJI} bonus"},
    20: {"coins": 1000, "label": f"1,000 {ECONOMY_CURRENCY_EMOJI} bonus"},
    25: {"coins": 1500, "label": f"1,500 {ECONOMY_CURRENCY_EMOJI} bonus + exclusive color role"},
    30: {"coins": 2000, "label": f"2,000 {ECONOMY_CURRENCY_EMOJI} bonus"},
    35: {"coins": 2500, "label": f"2,500 {ECONOMY_CURRENCY_EMOJI} bonus"},
    40: {"coins": 3000, "label": f"3,000 {ECONOMY_CURRENCY_EMOJI} bonus"},
    45: {"coins": 4000, "label": f"4,000 {ECONOMY_CURRENCY_EMOJI} bonus"},
    50: {"coins": 7000, "label": f"7,000 {ECONOMY_CURRENCY_EMOJI} bonus + Season Master badge"},
}

# ─── Challenge Templates ──────────────────────────────────────────────────────
WEEKLY_CHALLENGE_POOL = [
    # (type, description_template, target, xp_reward)
    ("social",      "Reply to {target} different people",     20,  1000),
    ("social",      "Reply to {target} messages",             30,  1200),
    ("social",      "Mention {target} different users",       15,   800),
    ("creative",    "Post {target} media items",              10,  1000),
    ("creative",    "Post in {target} different channels",     5,   500),
    ("creative",    "Post {target} messages with links",       8,   700),
    ("engagement",  "Maintain a {target}-day streak",          7,  1500),
    ("engagement",  "Earn {target}+ points in a single day", 200,   800),
    ("engagement",  "Spend {target} minutes in voice",        60,   900),
    ("community",   "React to {target} messages",            100,   800),
    ("community",   "Earn {target} reactions on your posts",  30,  1200),
    ("community",   "Send messages on {target} different days", 5,   600),
]

DAILY_CHALLENGE_POOL = [
    # (description, target_key, target_value, xp_reward)
    ("Send {target} messages",              "messages",   10,  200),
    ("Send {target} messages",              "messages",   20,  300),
    ("Reply to {target} people",            "replies",     5,  200),
    ("Reply to {target} people",            "replies",    10,  300),
    ("Spend {target} minutes in voice",     "voice_min",  15,  200),
    ("Spend {target} minutes in voice",     "voice_min",  30,  300),
    ("Post {target} media/meme",            "media",       1,  100),
    ("Post {target} media items",           "media",       3,  200),
    ("React to {target} messages",          "reactions",  10,  150),
    ("React to {target} messages",          "reactions",  25,  250),
    ("Send a message in {target} channels", "channels",    3,  150),
]


class SeasonPass(commands.Cog):
    """Seasonal battle pass with tiers, challenges, and rewards."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await self._ensure_tables()
        self.check_season_loop.start()
        self.check_challenges_loop.start()
        logger.info("✓ SeasonPass cog loaded")

    async def cog_unload(self):
        self.check_season_loop.cancel()
        self.check_challenges_loop.cancel()

    # ─── DB Setup ─────────────────────────────────────────────────────────────

    async def _ensure_tables(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS seasons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    season_number INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    off_season_until TEXT
                );

                CREATE TABLE IF NOT EXISTS season_progress (
                    user_id INTEGER NOT NULL,
                    season_id INTEGER NOT NULL,
                    season_xp INTEGER DEFAULT 0,
                    current_tier INTEGER DEFAULT 0,
                    is_premium INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, season_id)
                );

                CREATE TABLE IF NOT EXISTS season_challenges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    season_id INTEGER NOT NULL,
                    challenge_type TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    description TEXT NOT NULL,
                    target_key TEXT NOT NULL,
                    target_value INTEGER NOT NULL,
                    xp_reward INTEGER NOT NULL,
                    week_number INTEGER,
                    active_date TEXT NOT NULL,
                    expires_date TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS season_challenge_completions (
                    user_id INTEGER NOT NULL,
                    challenge_id INTEGER NOT NULL,
                    progress INTEGER DEFAULT 0,
                    completed INTEGER DEFAULT 0,
                    completed_at TEXT,
                    PRIMARY KEY (user_id, challenge_id)
                );

                CREATE TABLE IF NOT EXISTS season_rewards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    season_id INTEGER NOT NULL,
                    tier INTEGER NOT NULL,
                    reward_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    claimed_at TEXT NOT NULL
                );
            """)
            await db.commit()

    # ─── Background Tasks ─────────────────────────────────────────────────────

    @tasks.loop(hours=24)
    async def check_season_loop(self):
        """Check if the current season has ended, start a new one if needed."""
        try:
            await self._check_season_lifecycle()
        except Exception as e:
            logger.error(f"Season lifecycle check failed: {e}")

    @check_season_loop.before_loop
    async def before_check_season(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=1)
    async def check_challenges_loop(self):
        """Generate daily/weekly challenges if needed."""
        try:
            season = await self._get_active_season()
            if not season:
                return
            await self._ensure_daily_challenge(season["id"])
            await self._ensure_weekly_challenges(season["id"])
        except Exception as e:
            logger.error(f"Challenge generation check failed: {e}")

    @check_challenges_loop.before_loop
    async def before_check_challenges(self):
        await self.bot.wait_until_ready()

    # ─── Season Lifecycle ─────────────────────────────────────────────────────

    async def _check_season_lifecycle(self):
        now = datetime.now(timezone.utc)
        season = await self._get_active_season()

        if season:
            end_date = datetime.fromisoformat(season["end_date"]).replace(tzinfo=timezone.utc)
            if now >= end_date:
                await self._end_season(season)
                return
        else:
            # Check if off-season is over
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT * FROM seasons ORDER BY id DESC LIMIT 1"
                )
                cols = [d[0] for d in cursor.description]
                row = await cursor.fetchone()

            if row:
                last = dict(zip(cols, row))
                off_until = last.get("off_season_until")
                if off_until:
                    off_date = datetime.fromisoformat(off_until).replace(tzinfo=timezone.utc)
                    if now < off_date:
                        return  # Still in off-season
                # Off-season over (or no off-season set) — start new season
                await self._start_new_season(last["season_number"] + 1)
            else:
                # No seasons exist at all — start the first one
                await self._start_new_season(1)

    async def _start_new_season(self, season_number: int):
        now = datetime.now(timezone.utc)
        end = now + timedelta(weeks=SEASON_LENGTH_WEEKS)

        season_names = [
            "The Awakening", "Crimson Tide", "Void Eclipse",
            "Neon Surge", "Shadow Reign", "Ember Fall",
            "Frostbite", "Phantom Drift", "Iron Bloom",
            "Obsidian Dawn",
        ]
        name = season_names[(season_number - 1) % len(season_names)]

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO seasons (season_number, name, start_date, end_date, is_active)
                   VALUES (?, ?, ?, ?, 1)""",
                (season_number, name, now.isoformat(), end.isoformat()),
            )
            await db.commit()

        logger.info(f"Season {season_number} '{name}' started — ends {end.date()}")

        # Announce in rank-ups channel
        for guild in self.bot.guilds:
            ch = discord.utils.get(guild.text_channels, name="rank-ups")
            if ch:
                embed = discord.Embed(
                    title="⚡ A NEW SEASON BEGINS ⚡",
                    description=(
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"**Season {season_number}: {name}**\n\n"
                        f"The Circle turns once more. {SEASON_PASS_TIERS} tiers of glory await.\n\n"
                        f"🆓 Free track — rewards every 5 tiers\n"
                        f"👑 Premium pass — {SEASON_PASS_PREMIUM_COST:,} {ECONOMY_CURRENCY_EMOJI} for double rewards\n"
                        f"🔥 **Early bird: 2x Season XP for the first 48 hours!**\n\n"
                        f"Use `!season` to track your progress.\n"
                        f"Use `!challenges` to see your missions.\n"
                        f"━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=EMBED_COLOR_ACCENT,
                )
                embed.set_footer(text=f"Ends {end.strftime('%B %d, %Y')}")
                try:
                    await ch.send(embed=embed)
                except discord.Forbidden:
                    pass

    async def _end_season(self, season: dict):
        """End the current season — award prizes, post recap, enter off-season."""
        season_id = season["id"]
        off_until = datetime.now(timezone.utc) + timedelta(days=OFF_SEASON_DAYS)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE seasons SET is_active = 0, off_season_until = ? WHERE id = ?",
                (off_until.isoformat(), season_id),
            )
            await db.commit()

            # Get top participants
            cursor = await db.execute(
                """SELECT user_id, season_xp, current_tier, is_premium
                   FROM season_progress
                   WHERE season_id = ?
                   ORDER BY season_xp DESC""",
                (season_id,),
            )
            rows = await cursor.fetchall()

        if not rows:
            logger.info(f"Season {season['season_number']} ended with no participants")
            return

        # Award top 3
        top_prizes = [(5000, "🥇"), (3000, "🥈"), (1000, "🥉")]
        top_lines = []
        for i, (prize_coins, medal) in enumerate(top_prizes):
            if i < len(rows):
                uid = rows[i][0]
                await add_coins(uid, prize_coins)
                member_name = f"<@{uid}>"
                top_lines.append(f"{medal} {member_name} — Tier {rows[i][2]} | {rows[i][1]:,} XP → +{prize_coins:,} {ECONOMY_CURRENCY_EMOJI}")

        # Top 25% get veteran badge note
        top_quarter = max(1, len(rows) // 4)
        veteran_count = top_quarter

        # Build recap embed
        total_participants = len(rows)
        total_xp = sum(r[1] for r in rows)
        premium_count = sum(1 for r in rows if r[3])

        for guild in self.bot.guilds:
            ch = discord.utils.get(guild.text_channels, name="rank-ups")
            if ch:
                embed = discord.Embed(
                    title=f"🏁 SEASON {season['season_number']} COMPLETE 🏁",
                    description=(
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"**{season['name']}** has come to an end.\n\n"
                        f"**Top Finishers:**\n"
                        + "\n".join(top_lines) + "\n\n"
                        f"📊 **Stats:**\n"
                        f"• Participants: **{total_participants}**\n"
                        f"• Premium holders: **{premium_count}**\n"
                        f"• Total Season XP earned: **{total_xp:,}**\n"
                        f"• Top 25% ({veteran_count} members) earned Season Veteran status\n\n"
                        f"⏳ Off-season: **{OFF_SEASON_DAYS} days** — next season begins soon.\n"
                        f"━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=EMBED_COLOR_SUCCESS,
                )
                try:
                    await ch.send(embed=embed)
                except discord.Forbidden:
                    pass

        logger.info(
            f"Season {season['season_number']} ended. "
            f"{total_participants} participants, {total_xp:,} total XP."
        )

    # ─── Season Helpers ───────────────────────────────────────────────────────

    async def _get_active_season(self) -> Optional[dict]:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM seasons WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
            )
            cols = [d[0] for d in cursor.description]
            row = await cursor.fetchone()
            return dict(zip(cols, row)) if row else None

    async def _get_progress(self, user_id: int, season_id: int) -> dict:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT season_xp, current_tier, is_premium FROM season_progress WHERE user_id = ? AND season_id = ?",
                (user_id, season_id),
            )
            row = await cursor.fetchone()
            if row:
                return {"season_xp": row[0], "current_tier": row[1], "is_premium": bool(row[2])}
            return {"season_xp": 0, "current_tier": 0, "is_premium": False}

    def _tier_for_xp(self, xp: int) -> int:
        """Return the tier (0-based index into TIER_CUMULATIVE_XP) for a given XP total."""
        tier = 0
        for i, threshold in enumerate(TIER_CUMULATIVE_XP):
            if xp >= threshold:
                tier = i
            else:
                break
        return tier

    def _xp_for_next_tier(self, current_tier: int) -> tuple[int, int]:
        """Return (xp_needed_for_next_tier, xp_at_current_tier)."""
        if current_tier >= SEASON_PASS_TIERS - 1:
            return (TIER_CUMULATIVE_XP[-1], TIER_CUMULATIVE_XP[-1])
        return (TIER_CUMULATIVE_XP[current_tier + 1], TIER_CUMULATIVE_XP[current_tier])

    def _progress_bar(self, current: int, total: int, length: int = 20) -> str:
        if total <= 0:
            return "▓" * length
        ratio = min(current / total, 1.0)
        filled = int(ratio * length)
        return "▓" * filled + "░" * (length - filled)

    # ─── Season XP API ────────────────────────────────────────────────────────

    async def add_season_xp(self, user_id: int, amount: int):
        """Add Season XP to a user. Checks for tier-ups and awards rewards."""
        season = await self._get_active_season()
        if not season:
            return
        season_id = season["id"]

        # Early bird multiplier
        start = datetime.fromisoformat(season["start_date"]).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if (now - start).total_seconds() < SEASON_EARLY_BIRD_HOURS * 3600:
            amount = int(amount * SEASON_EARLY_BIRD_MULT)

        async with aiosqlite.connect(DB_PATH) as db:
            # Upsert progress
            await db.execute(
                """INSERT INTO season_progress (user_id, season_id, season_xp, current_tier)
                   VALUES (?, ?, ?, 0)
                   ON CONFLICT(user_id, season_id) DO UPDATE SET
                   season_xp = season_xp + ?""",
                (user_id, season_id, amount, amount),
            )
            await db.commit()

            cursor = await db.execute(
                "SELECT season_xp, current_tier, is_premium FROM season_progress WHERE user_id = ? AND season_id = ?",
                (user_id, season_id),
            )
            row = await cursor.fetchone()

        if not row:
            return

        total_xp, old_tier, is_premium = row[0], row[1], bool(row[2])
        new_tier = self._tier_for_xp(total_xp)

        if new_tier > old_tier:
            # Update tier
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE season_progress SET current_tier = ? WHERE user_id = ? AND season_id = ?",
                    (new_tier, user_id, season_id),
                )
                await db.commit()

            # Check for rewards at each tier crossed
            for tier in range(old_tier + 1, new_tier + 1):
                tier_display = tier + 1  # 0-indexed internally, 1-indexed for display
                await self._award_tier_rewards(user_id, season_id, tier_display, is_premium)

    async def _award_tier_rewards(self, user_id: int, season_id: int, tier: int, is_premium: bool):
        """Award free (and premium if applicable) rewards for reaching a tier."""
        now = datetime.now(timezone.utc).isoformat()

        # Free rewards
        if tier in SEASON_FREE_REWARDS:
            reward = SEASON_FREE_REWARDS[tier]
            if reward["coins"] > 0:
                await add_coins(user_id, reward["coins"])
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO season_rewards (user_id, season_id, tier, reward_type, description, claimed_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, season_id, tier, "free", reward["label"], now),
                )
                await db.commit()

        # Premium rewards
        if is_premium and tier in SEASON_PREMIUM_REWARDS:
            reward = SEASON_PREMIUM_REWARDS[tier]
            if reward["coins"] > 0:
                await add_coins(user_id, reward["coins"])
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO season_rewards (user_id, season_id, tier, reward_type, description, claimed_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, season_id, tier, "premium", reward["label"], now),
                )
                await db.commit()

        # Notify in rank-ups channel
        for guild in self.bot.guilds:
            ch = discord.utils.get(guild.text_channels, name="rank-ups")
            if ch:
                label = f"Season Tier {tier}"
                try:
                    await ch.send(
                        f"⚡ <@{user_id}> reached **{label}**! "
                        + (f"{'👑 Premium rewards claimed!' if is_premium and tier in SEASON_PREMIUM_REWARDS else ''}"
                           if tier in SEASON_FREE_REWARDS else "The grind continues...")
                    )
                except discord.Forbidden:
                    pass

    # ─── Challenge Generation ─────────────────────────────────────────────────

    async def _ensure_daily_challenge(self, season_id: int):
        """Generate today's daily challenge if one doesn't exist."""
        today = date.today().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id FROM season_challenges WHERE season_id = ? AND frequency = 'daily' AND active_date = ?",
                (season_id, today),
            )
            if await cursor.fetchone():
                return  # Already exists

            template = random.choice(DAILY_CHALLENGE_POOL)
            desc, target_key, target_val, xp = template
            description = desc.format(target=target_val)
            tomorrow = (date.today() + timedelta(days=1)).isoformat()

            await db.execute(
                """INSERT INTO season_challenges
                   (season_id, challenge_type, frequency, description, target_key, target_value, xp_reward, active_date, expires_date)
                   VALUES (?, 'daily', 'daily', ?, ?, ?, ?, ?, ?)""",
                (season_id, description, target_key, target_val, xp, today, tomorrow),
            )
            await db.commit()
            logger.info(f"Generated daily challenge: {description}")

    async def _ensure_weekly_challenges(self, season_id: int):
        """Generate this week's 3 weekly challenges if they don't exist (Monday)."""
        today = date.today()
        # Monday of this week
        monday = today - timedelta(days=today.weekday())
        monday_str = monday.isoformat()
        next_monday = (monday + timedelta(days=7)).isoformat()

        # Calculate week number within the season
        season = await self._get_active_season()
        if not season:
            return
        start = datetime.fromisoformat(season["start_date"]).replace(tzinfo=timezone.utc).date()
        week_number = max(1, ((today - start).days // 7) + 1)

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM season_challenges WHERE season_id = ? AND frequency = 'weekly' AND week_number = ?",
                (season_id, week_number),
            )
            count = (await cursor.fetchone())[0]
            if count >= 3:
                return  # Already generated

            # Pick 3 from different types
            types_used: set[str] = set()
            chosen: list[tuple] = []
            pool = list(WEEKLY_CHALLENGE_POOL)
            random.shuffle(pool)

            for template in pool:
                ctype, desc_tmpl, target, xp = template
                if ctype not in types_used and len(chosen) < 3:
                    types_used.add(ctype)
                    chosen.append(template)
            # If we couldn't get 3 unique types, fill remaining
            for template in pool:
                if len(chosen) >= 3:
                    break
                if template not in chosen:
                    chosen.append(template)

            for ctype, desc_tmpl, target, xp in chosen[:3]:
                description = desc_tmpl.format(target=target)
                await db.execute(
                    """INSERT INTO season_challenges
                       (season_id, challenge_type, frequency, description, target_key, target_value,
                        xp_reward, week_number, active_date, expires_date)
                       VALUES (?, ?, 'weekly', ?, ?, ?, ?, ?, ?, ?)""",
                    (season_id, ctype, description, ctype, target, xp, week_number, monday_str, next_monday),
                )

            await db.commit()
            logger.info(f"Generated {len(chosen[:3])} weekly challenges for week {week_number}")

    # ─── Commands ─────────────────────────────────────────────────────────────

    @commands.command(name="season")
    async def season_cmd(self, ctx: commands.Context, action: Optional[str] = None):
        """Show season info or buy premium pass."""
        if action and action.lower() == "buy":
            await self._buy_premium(ctx)
            return

        season = await self._get_active_season()
        if not season:
            # Check off-season
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute("SELECT * FROM seasons ORDER BY id DESC LIMIT 1")
                cols = [d[0] for d in cursor.description]
                row = await cursor.fetchone()
            if row:
                last = dict(zip(cols, row))
                off_until = last.get("off_season_until", "")
                embed = discord.Embed(
                    title="⏳ OFF-SEASON",
                    description=(
                        f"Season {last['season_number']} has ended.\n"
                        f"Next season begins: **{off_until[:10] if off_until else 'Soon'}**\n\n"
                        f"Rest up. The Circle waits for no one."
                    ),
                    color=EMBED_COLOR_PRIMARY,
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("⚫ No seasons have been run yet. The Circle is patient.")
            return

        progress = await self._get_progress(ctx.author.id, season["id"])
        tier = progress["current_tier"]
        xp = progress["season_xp"]
        is_premium = progress["is_premium"]

        # Calculate progress to next tier
        tier_display = tier + 1  # 1-indexed
        if tier < SEASON_PASS_TIERS - 1:
            xp_next, xp_current = self._xp_for_next_tier(tier)
            xp_in_tier = xp - xp_current
            xp_needed = xp_next - xp_current
            bar = self._progress_bar(xp_in_tier, xp_needed)
            progress_text = f"{bar}\n`{xp_in_tier:,} / {xp_needed:,} XP` to Tier {tier_display + 1}"
        else:
            bar = self._progress_bar(1, 1)
            progress_text = f"{bar}\n**MAX TIER REACHED** — {xp:,} XP total"

        # Time remaining
        end = datetime.fromisoformat(season["end_date"]).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days_left = max(0, (end - now).days)
        weeks_left = days_left // 7
        remaining_days = days_left % 7

        # Early bird check
        start = datetime.fromisoformat(season["start_date"]).replace(tzinfo=timezone.utc)
        is_early = (now - start).total_seconds() < SEASON_EARLY_BIRD_HOURS * 3600
        early_text = "\n🔥 **EARLY BIRD ACTIVE — 2x Season XP!**" if is_early else ""

        # Next free reward
        next_reward = ""
        for t in sorted(SEASON_FREE_REWARDS.keys()):
            if t > tier_display:
                next_reward = f"\n🎁 Next free reward: **Tier {t}** — {SEASON_FREE_REWARDS[t]['label']}"
                break

        pass_type = "👑 PREMIUM" if is_premium else "🆓 FREE"

        embed = discord.Embed(
            title=f"⚡ SEASON {season['season_number']}: {season['name'].upper()} ⚡",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"**Your Pass:** {pass_type}\n"
                f"**Tier:** {tier_display} / {SEASON_PASS_TIERS}\n"
                f"**Season XP:** {xp:,}\n\n"
                f"{progress_text}"
                f"{early_text}"
                f"{next_reward}\n\n"
                f"⏰ **{weeks_left}w {remaining_days}d** remaining\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_ACCENT,
        )

        if not is_premium:
            embed.set_footer(text=f"!season buy — Upgrade to Premium for {SEASON_PASS_PREMIUM_COST:,} {ECONOMY_CURRENCY_NAME}")

        # Show active challenges summary
        challenges = await self._get_user_challenges(ctx.author.id, season["id"])
        if challenges:
            ch_lines = []
            for ch in challenges[:5]:
                status = "✅" if ch["completed"] else f"({ch['progress']}/{ch['target_value']})"
                ch_lines.append(f"{status} {ch['description']} — {ch['xp_reward']} XP")
            embed.add_field(
                name="🎯 Active Challenges",
                value="\n".join(ch_lines) + "\n\nUse `!challenges` for full details.",
                inline=False,
            )

        await ctx.send(embed=embed)

    async def _buy_premium(self, ctx: commands.Context):
        """Purchase premium season pass."""
        season = await self._get_active_season()
        if not season:
            await ctx.send("⚫ No active season. Wait for the next one.")
            return

        progress = await self._get_progress(ctx.author.id, season["id"])
        if progress["is_premium"]:
            await ctx.send("👑 You already have the premium pass this season.")
            return

        success = await spend_coins(ctx.author.id, SEASON_PASS_PREMIUM_COST)
        if not success:
            await ctx.send(
                f"⚫ Not enough {ECONOMY_CURRENCY_NAME}. "
                f"Premium pass costs **{SEASON_PASS_PREMIUM_COST:,}** {ECONOMY_CURRENCY_EMOJI}."
            )
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO season_progress (user_id, season_id, is_premium)
                   VALUES (?, ?, 1)
                   ON CONFLICT(user_id, season_id) DO UPDATE SET is_premium = 1""",
                (ctx.author.id, season["id"]),
            )
            await db.commit()

        # Retroactively award any premium rewards for tiers already passed
        tier_display = progress["current_tier"] + 1
        for t in sorted(SEASON_PREMIUM_REWARDS.keys()):
            if t <= tier_display:
                reward = SEASON_PREMIUM_REWARDS[t]
                if reward["coins"] > 0:
                    await add_coins(ctx.author.id, reward["coins"])

        embed = discord.Embed(
            title="👑 PREMIUM PASS ACTIVATED",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"The Circle recognizes your commitment.\n\n"
                f"All premium rewards unlocked retroactively up to Tier {tier_display}.\n"
                f"Double rewards await on the path ahead.\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_SUCCESS,
        )
        await ctx.send(embed=embed)

    @commands.command(name="challenges")
    async def challenges_cmd(self, ctx: commands.Context):
        """Show weekly and daily challenges with completion status."""
        season = await self._get_active_season()
        if not season:
            await ctx.send("⚫ No active season. The Circle rests.")
            return

        challenges = await self._get_user_challenges(ctx.author.id, season["id"])

        daily = [c for c in challenges if c["frequency"] == "daily"]
        weekly = [c for c in challenges if c["frequency"] == "weekly"]

        embed = discord.Embed(
            title="🎯 SEASON CHALLENGES",
            color=EMBED_COLOR_PRIMARY,
        )

        # Daily
        if daily:
            lines = []
            for c in daily:
                if c["completed"]:
                    lines.append(f"✅ ~~{c['description']}~~ — **{c['xp_reward']} XP** ✓")
                else:
                    pct = min(100, int((c["progress"] / max(1, c["target_value"])) * 100))
                    bar = self._progress_bar(c["progress"], c["target_value"], length=10)
                    lines.append(f"🔸 {c['description']} — **{c['xp_reward']} XP**\n  {bar} {pct}% ({c['progress']}/{c['target_value']})")
            embed.add_field(name="📅 Daily Challenge", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="📅 Daily Challenge", value="*Generating...*", inline=False)

        # Weekly
        if weekly:
            lines = []
            for c in weekly:
                if c["completed"]:
                    lines.append(f"✅ ~~{c['description']}~~ — **{c['xp_reward']} XP** ✓")
                else:
                    pct = min(100, int((c["progress"] / max(1, c["target_value"])) * 100))
                    bar = self._progress_bar(c["progress"], c["target_value"], length=10)
                    lines.append(f"🔹 {c['description']} — **{c['xp_reward']} XP**\n  {bar} {pct}% ({c['progress']}/{c['target_value']})")
            embed.add_field(name="📆 Weekly Challenges", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="📆 Weekly Challenges", value="*Generating...*", inline=False)

        embed.set_footer(text="Challenges auto-track — no claiming needed!")
        await ctx.send(embed=embed)

    # ─── Challenge Tracking ───────────────────────────────────────────────────

    async def _get_user_challenges(self, user_id: int, season_id: int) -> list[dict]:
        """Get all active challenges with user progress."""
        today = date.today().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT sc.id, sc.challenge_type, sc.frequency, sc.description,
                          sc.target_key, sc.target_value, sc.xp_reward,
                          COALESCE(scc.progress, 0) AS progress,
                          COALESCE(scc.completed, 0) AS completed
                   FROM season_challenges sc
                   LEFT JOIN season_challenge_completions scc
                        ON sc.id = scc.challenge_id AND scc.user_id = ?
                   WHERE sc.season_id = ? AND sc.expires_date > ?
                   ORDER BY sc.frequency DESC, sc.id""",
                (user_id, season_id, today),
            )
            cols = [d[0] for d in cursor.description]
            rows = await cursor.fetchall()
            return [dict(zip(cols, r)) for r in rows]

    async def update_challenge_progress(self, user_id: int, target_key: str, increment: int = 1):
        """Update progress on active challenges matching the target key.
        Called from scoring_handler and other cogs.
        """
        season = await self._get_active_season()
        if not season:
            return

        today = date.today().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            # Find matching active challenges
            cursor = await db.execute(
                """SELECT id, target_value, xp_reward FROM season_challenges
                   WHERE season_id = ? AND target_key = ? AND expires_date > ?""",
                (season["id"], target_key, today),
            )
            challenges = await cursor.fetchall()

            for challenge_id, target_value, xp_reward in challenges:
                # Upsert progress
                await db.execute(
                    """INSERT INTO season_challenge_completions (user_id, challenge_id, progress)
                       VALUES (?, ?, ?)
                       ON CONFLICT(user_id, challenge_id) DO UPDATE SET
                       progress = progress + ?
                       WHERE completed = 0""",
                    (user_id, challenge_id, increment, increment),
                )

                # Check completion
                cursor2 = await db.execute(
                    "SELECT progress, completed FROM season_challenge_completions WHERE user_id = ? AND challenge_id = ?",
                    (user_id, challenge_id),
                )
                row = await cursor2.fetchone()
                if row and row[0] >= target_value and not row[1]:
                    await db.execute(
                        "UPDATE season_challenge_completions SET completed = 1, completed_at = ? WHERE user_id = ? AND challenge_id = ?",
                        (datetime.now(timezone.utc).isoformat(), user_id, challenge_id),
                    )
                    # Award XP for challenge completion
                    await db.commit()
                    await self.add_season_xp(user_id, xp_reward)
                    return  # add_season_xp handles its own commit

            await db.commit()

    # ─── Listener: Score → Season XP (1:1) ────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Pass-through: season XP is granted via add_season_xp called from
        scoring_handler. This listener tracks challenge progress for messages."""
        if message.author.bot:
            return
        if not message.guild:
            return

        user_id = message.author.id

        # Track message-related challenge progress
        await self.update_challenge_progress(user_id, "messages", 1)

        if message.attachments or any(e.type in ("image", "gifv", "video") for e in message.embeds):
            await self.update_challenge_progress(user_id, "media", 1)

        if message.reference and message.reference.message_id:
            await self.update_challenge_progress(user_id, "replies", 1)

        await self.update_challenge_progress(user_id, "channels", 0)
        # Channel tracking is tricky — we handle it by counting distinct channels today
        await self._update_channel_diversity(user_id, message.channel.id)

    async def _update_channel_diversity(self, user_id: int, channel_id: int):
        """Track unique channels a user posts in today for challenge progress."""
        season = await self._get_active_season()
        if not season:
            return

        today = date.today().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            # Count distinct channels the user has messaged in today
            # We use the messages table for this
            cursor = await db.execute(
                """SELECT COUNT(DISTINCT channel_id) FROM messages
                   WHERE user_id = ? AND date(timestamp) = ?""",
                (user_id, today),
            )
            row = await cursor.fetchone()
            channel_count = row[0] if row else 0

            # Update any 'channels' challenges to reflect actual count
            cursor2 = await db.execute(
                """SELECT sc.id FROM season_challenges sc
                   WHERE sc.season_id = ? AND sc.target_key = 'channels' AND sc.expires_date > ?""",
                (season["id"], today),
            )
            for (challenge_id,) in await cursor2.fetchall():
                await db.execute(
                    """INSERT INTO season_challenge_completions (user_id, challenge_id, progress)
                       VALUES (?, ?, ?)
                       ON CONFLICT(user_id, challenge_id) DO UPDATE SET
                       progress = ?
                       WHERE completed = 0""",
                    (user_id, challenge_id, channel_count, channel_count),
                )

                # Check completion
                cursor3 = await db.execute(
                    """SELECT scc.progress, scc.completed, sc.target_value, sc.xp_reward
                       FROM season_challenge_completions scc
                       JOIN season_challenges sc ON sc.id = scc.challenge_id
                       WHERE scc.user_id = ? AND scc.challenge_id = ?""",
                    (user_id, challenge_id),
                )
                r = await cursor3.fetchone()
                if r and r[0] >= r[2] and not r[1]:
                    await db.execute(
                        "UPDATE season_challenge_completions SET completed = 1, completed_at = ? WHERE user_id = ? AND challenge_id = ?",
                        (datetime.now(timezone.utc).isoformat(), user_id, challenge_id),
                    )
                    await db.commit()
                    await self.add_season_xp(user_id, r[3])
                    return

            await db.commit()


async def setup(bot: commands.Bot):
    await bot.add_cog(SeasonPass(bot))
