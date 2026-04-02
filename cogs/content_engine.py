"""
The Circle — Content Engine Cog
Quick Fire rounds, dead zone detection, user-generated content submissions, and trending topics.
Keeper keeps The Circle alive — even when the members won't.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EXCLUDED_CHANNELS,
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    GUILD_ID,
    QUICK_FIRE_PROMPTS,
    QUICK_FIRE_PER_DAY,
    QUICK_FIRE_MIN_GAP_HOURS,
    QUICK_FIRE_FIRST_N_BONUS,
    QUICK_FIRE_BONUS_POINTS,
    DEAD_ZONE_MINUTES,
    TRENDING_WINDOW_HOURS,
    TRENDING_MIN_MENTIONS,
    TRENDING_MIN_USERS,
    UGC_SUBMIT_COST,
    UGC_USED_REWARD_COINS,
    UGC_AUTO_APPROVE_THRESHOLD,
)
from database import (
    DB_PATH,
    add_coins,
    spend_coins,
    update_user_score,
    add_daily_points,
)

log = logging.getLogger(__name__)

# ─── Stop Words ───────────────────────────────────────────────────────────────
STOP_WORDS: Set[str] = {
    "the", "is", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "but", "it", "its", "i", "me", "my", "you", "your", "we", "our", "they",
    "them", "their", "he", "she", "his", "her", "this", "that", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "can", "may", "might", "shall", "not", "no",
    "so", "if", "then", "than", "too", "very", "just", "about", "up", "out",
    "with", "from", "by", "as", "are", "am", "all", "any", "some", "what",
    "when", "where", "who", "how", "which", "there", "here", "more", "most",
    "also", "only", "now", "new", "one", "two", "like", "get", "got", "go",
    "going", "make", "know", "think", "right", "well", "way", "even", "back",
    "come", "thing", "want", "see", "look", "time", "day", "good", "people",
    "take", "say", "said", "really", "yeah", "yes", "no", "oh", "ok", "okay",
    "lol", "lmao", "haha", "im", "dont", "doesnt", "didnt", "cant", "wont",
    "thats", "whats", "its", "ive", "youre", "theyre", "were", "hes", "shes",
}

# Minimum word length to count for trending
TRENDING_MIN_WORD_LEN = 4


# ─── Database Helpers ─────────────────────────────────────────────────────────

async def _init_content_tables():
    """Create content engine tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS content_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                content TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                reviewed_by INTEGER,
                reviewed_at TEXT,
                times_used INTEGER DEFAULT 0,
                user_approval_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS trending_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                mention_count INTEGER NOT NULL,
                unique_users INTEGER NOT NULL,
                detected_at TEXT NOT NULL,
                posted INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS quick_fire_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER,
                posted_at TEXT NOT NULL,
                reply_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS quick_fire_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fire_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                replied_at TEXT NOT NULL,
                bonus_awarded INTEGER DEFAULT 0,
                FOREIGN KEY (fire_id) REFERENCES quick_fire_log(id)
            );
        """)
        await db.commit()


async def _get_most_active_channel(guild_id: int, hours: int = 2) -> Optional[int]:
    """Return the channel_id with the most messages in the last N hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT channel_id, COUNT(*) as cnt
            FROM messages
            WHERE timestamp > ?
            GROUP BY channel_id
            ORDER BY cnt DESC
            LIMIT 1
            """,
            (cutoff,),
        )
        row = await cursor.fetchone()
        return row["channel_id"] if row else None


async def _get_last_message_time() -> Optional[datetime]:
    """Return the timestamp of the most recent message in any non-excluded channel."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT timestamp FROM messages ORDER BY id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if row and row[0]:
            try:
                return datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                return None
    return None


async def _get_recent_words(hours: int) -> List[Tuple[str, int]]:
    """Fetch all message content from the last N hours (via word_count > 0 rows).
    Returns list of (word, user_id) pairs for frequency analysis.
    Note: We query the messages table which doesn't store content directly.
    Instead we'll use the trending approach of tracking in-memory from on_message.
    """
    # This is a placeholder — actual word tracking happens in memory via on_message
    return []


async def _log_quick_fire(prompt: str, channel_id: int, message_id: int) -> int:
    """Log a Quick Fire round and return its ID."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO quick_fire_log (prompt, channel_id, message_id, posted_at) VALUES (?, ?, ?, ?)",
            (prompt, channel_id, message_id, now),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def _log_quick_fire_reply(fire_id: int, user_id: int, bonus: bool) -> int:
    """Log a reply to a Quick Fire. Returns the reply position (1-based)."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        # Count existing replies
        cursor = await db.execute(
            "SELECT COUNT(*) FROM quick_fire_replies WHERE fire_id = ?",
            (fire_id,),
        )
        row = await cursor.fetchone()
        position = (row[0] if row else 0) + 1

        await db.execute(
            "INSERT INTO quick_fire_replies (fire_id, user_id, replied_at, bonus_awarded) VALUES (?, ?, ?, ?)",
            (fire_id, user_id, now, 1 if bonus else 0),
        )
        # Update reply count
        await db.execute(
            "UPDATE quick_fire_log SET reply_count = ? WHERE id = ?",
            (position, fire_id),
        )
        await db.commit()
        return position


async def _get_user_approval_count(user_id: int) -> int:
    """How many of this user's submissions have been approved."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM content_submissions WHERE user_id = ? AND status = 'approved'",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def _create_submission(user_id: int, content_type: str, content: str, auto_approved: bool = False) -> int:
    """Create a content submission. Returns submission ID."""
    now = datetime.now(timezone.utc).isoformat()
    approval_count = await _get_user_approval_count(user_id)
    status = "approved" if auto_approved else "pending"

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO content_submissions
               (user_id, content_type, content, submitted_at, status, user_approval_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, content_type, content, now, status, approval_count),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def _update_submission_status(sub_id: int, status: str, reviewer_id: int) -> Optional[dict]:
    """Approve or reject a submission. Returns submission info or None."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM content_submissions WHERE id = ?", (sub_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None

        await db.execute(
            "UPDATE content_submissions SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?",
            (status, reviewer_id, now, sub_id),
        )
        await db.commit()
        return dict(row)


async def _log_trending(word: str, count: int, unique_users: int):
    """Log a detected trending topic."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO trending_topics (word, mention_count, unique_users, detected_at, posted) VALUES (?, ?, ?, ?, 1)",
            (word, count, unique_users, now),
        )
        await db.commit()


async def _was_trending_recently(word: str, hours: int = 24) -> bool:
    """Check if a word was already flagged as trending in the last N hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM trending_topics WHERE word = ? AND detected_at > ?",
            (word, cutoff),
        )
        row = await cursor.fetchone()
        return (row[0] if row else 0) > 0


# ─── Cog ──────────────────────────────────────────────────────────────────────

class ContentEngine(commands.Cog):
    """Quick Fire rounds, dead zone detection, UGC submissions, and trending topics."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Quick Fire state
        self._fire_times_today: List[datetime] = []
        self._used_prompt_indices: List[int] = []
        self._active_fires: Dict[int, int] = {}  # message_id -> fire_id

        # Trending word tracker: word -> {user_ids}
        self._word_tracker: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self._word_window_start: datetime = datetime.now(timezone.utc)

    @commands.Cog.listener()
    async def on_ready(self):
        """Start background tasks (guard against double-start on reconnect)."""
        # Restore active Quick Fires from DB (survive restart)
        await self._restore_active_fires()

        if not self.quick_fire_scheduler.is_running():
            self.quick_fire_scheduler.start()
        if not self.dead_zone_detector.is_running():
            self.dead_zone_detector.start()
        if not self.trending_scanner.is_running():
            self.trending_scanner.start()

    async def _restore_active_fires(self):
        """Repopulate _active_fires from DB for fires started within the last 2 hours."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT id, message_id FROM quick_fire_log WHERE posted_at > ? AND message_id IS NOT NULL",
                    (cutoff,),
                )
                rows = await cursor.fetchall()
                for row in rows:
                    if row["message_id"]:
                        self._active_fires[row["message_id"]] = row["id"]
            if self._active_fires:
                log.info("Restored %d active Quick Fire(s) from DB", len(self._active_fires))
        except Exception as e:
            log.debug("Could not restore active fires: %s", e)

    def cog_unload(self):
        self.quick_fire_scheduler.cancel()
        self.dead_zone_detector.cancel()
        self.trending_scanner.cancel()

    # ─── Quick Fire ───────────────────────────────────────────────────────

    def _pick_prompt(self) -> str:
        """Pick a Quick Fire prompt, avoiding recent repeats."""
        available = [
            i for i in range(len(QUICK_FIRE_PROMPTS))
            if i not in self._used_prompt_indices
        ]
        if not available:
            self._used_prompt_indices.clear()
            available = list(range(len(QUICK_FIRE_PROMPTS)))

        idx = random.choice(available)
        self._used_prompt_indices.append(idx)
        if len(self._used_prompt_indices) > len(QUICK_FIRE_PROMPTS) // 2:
            self._used_prompt_indices = self._used_prompt_indices[-(len(QUICK_FIRE_PROMPTS) // 2):]
        return QUICK_FIRE_PROMPTS[idx]

    def _get_effective_fires_per_day(self) -> int:
        """Scale Quick Fire frequency based on member count."""
        guild = self.bot.get_guild(GUILD_ID)
        member_count = guild.member_count if guild else 50
        if member_count < 25:
            return 1
        if member_count < 100:
            return 2
        return QUICK_FIRE_PER_DAY

    def _can_fire_now(self) -> bool:
        """Check if we can fire (respect daily limit and min gap)."""
        now = datetime.now(timezone.utc)

        # Reset daily counters at midnight UTC
        if self._fire_times_today and self._fire_times_today[0].date() < now.date():
            self._fire_times_today.clear()

        max_fires = self._get_effective_fires_per_day()
        if len(self._fire_times_today) >= max_fires:
            return False

        if self._fire_times_today:
            last = self._fire_times_today[-1]
            gap = timedelta(hours=QUICK_FIRE_MIN_GAP_HOURS)
            if now - last < gap:
                return False

        return True

    async def _post_quick_fire(self, channel: discord.TextChannel, prompt: Optional[str] = None) -> Optional[int]:
        """Post a Quick Fire round to the given channel. Returns the fire_id."""
        if prompt is None:
            prompt = self._pick_prompt()

        embed = discord.Embed(
            title="⚡ QUICK FIRE",
            description=(
                f"**{prompt}**\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏆 First **{QUICK_FIRE_FIRST_N_BONUS}** replies earn **{QUICK_FIRE_BONUS_POINTS} bonus points**!\n"
                "*The Circle demands your speed.*"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="The Circle • Quick Fire")

        try:
            msg = await channel.send(embed=embed)
        except discord.HTTPException:
            log.warning("ContentEngine: Failed to post Quick Fire in #%s", channel.name)
            return None

        fire_id = await _log_quick_fire(prompt, channel.id, msg.id)
        self._active_fires[msg.id] = fire_id
        self._fire_times_today.append(datetime.now(timezone.utc))

        log.info("ContentEngine: Quick Fire #%d posted in #%s", fire_id, channel.name)
        return fire_id

    @tasks.loop(minutes=30)
    async def quick_fire_scheduler(self):
        """Schedule Quick Fire rounds at random times, ~3x per day."""
        if not self._can_fire_now():
            return

        # Random chance each 30-min window — spread across the day
        # With 3 fires and 48 windows, fire ~6% of the time per window
        # But weighted toward active hours (14:00-03:00 UTC)
        now = datetime.now(timezone.utc)
        hour = now.hour

        # Higher chance during peak hours
        if 14 <= hour or hour < 3:
            fire_chance = 0.12
        elif 6 <= hour < 14:
            fire_chance = 0.04
        else:
            fire_chance = 0.08

        if random.random() > fire_chance:
            return

        # Find most active channel
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return

        # Always post Quick Fire in #general — it's a server-wide engagement mechanic
        channel = discord.utils.get(guild.text_channels, name="general")
        if channel:
            await self._post_quick_fire(channel)

    @quick_fire_scheduler.before_loop
    async def before_quick_fire(self):
        await self.bot.wait_until_ready()
        await _init_content_tables()

    # ─── Quick Fire Reply Detection ───────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track Quick Fire replies and words for trending."""
        if message.author.bot or not message.guild:
            return

        # --- Quick Fire reply tracking ---
        if message.reference and message.reference.message_id in self._active_fires:
            fire_id = self._active_fires[message.reference.message_id]
            # Check if user already replied to this fire
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM quick_fire_replies WHERE fire_id = ? AND user_id = ?",
                    (fire_id, message.author.id),
                )
                row = await cursor.fetchone()
                if row and row[0] > 0:
                    # Already replied — no double bonus
                    pass
                else:
                    position = await _log_quick_fire_reply(fire_id, message.author.id, bonus=True)
                    if position <= QUICK_FIRE_FIRST_N_BONUS:
                        # Award bonus points
                        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        await update_user_score(message.author.id, QUICK_FIRE_BONUS_POINTS)
                        await add_daily_points(message.author.id, QUICK_FIRE_BONUS_POINTS)

                        try:
                            await message.add_reaction("⚡")
                        except discord.HTTPException:
                            pass

                        if position == 1:
                            try:
                                await message.channel.send(
                                    f"⚡ **FIRST!** {message.author.mention} claims the fastest response. "
                                    f"+{QUICK_FIRE_BONUS_POINTS} pts.",
                                    delete_after=15,
                                )
                            except discord.HTTPException:
                                pass
                    else:
                        # Still log the reply, just no bonus
                        pass

                    # Clean up after enough replies (keep active for a while)
                    if position >= QUICK_FIRE_FIRST_N_BONUS + 5:
                        self._active_fires.pop(message.reference.message_id, None)

        # --- Trending word tracking ---
        if message.channel.name not in EXCLUDED_CHANNELS:
            self._track_words(message)

    def _track_words(self, message: discord.Message):
        """Extract words from a message and add to the trending tracker."""
        # Reset window if expired
        now = datetime.now(timezone.utc)
        window = timedelta(hours=TRENDING_WINDOW_HOURS)
        if now - self._word_window_start > window:
            self._word_tracker.clear()
            self._word_window_start = now

        # Extract words (alpha only, lowercase, min length)
        text = message.content.lower()
        words = re.findall(r"[a-z']+", text)

        for word in words:
            if len(word) < TRENDING_MIN_WORD_LEN:
                continue
            if word in STOP_WORDS:
                continue
            self._word_tracker[word][message.author.id] += 1

    # ─── Dead Zone Detection ──────────────────────────────────────────────

    @tasks.loop(minutes=15)
    async def dead_zone_detector(self):
        """If the server is silent for too long during peak hours, drop content.
        Quiet mode: at < 15 members, only trigger if 2+ users were active recently."""
        now = datetime.now(timezone.utc)
        hour = now.hour

        # Only during peak hours: 14:00–03:59 UTC
        if 4 <= hour < 14:
            return

        last_msg_time = await _get_last_message_time()
        if last_msg_time is None:
            return

        silence_minutes = (now - last_msg_time).total_seconds() / 60.0
        if silence_minutes < DEAD_ZONE_MINUTES:
            return

        # Can we still fire today?
        if not self._can_fire_now():
            return

        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return

        # Quiet mode: at small scale, only break silence if someone is around
        if guild.member_count and guild.member_count < 15:
            recent_cutoff = (now - timedelta(hours=4)).isoformat()
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT COUNT(DISTINCT user_id) FROM messages WHERE timestamp > ?",
                    (recent_cutoff,),
                )
                recent_users = (await cursor.fetchone())[0]
            if recent_users < 2:
                return  # Nobody around to respond — don't shout into the void

        # Post in #general
        channel = discord.utils.get(guild.text_channels, name="general")
        if not channel:
            return

        # 50/50: Quick Fire or a "Throwback" message
        if random.random() < 0.5:
            await self._post_quick_fire(channel)
        else:
            await self._post_throwback(channel)

        log.info(
            "ContentEngine: Dead zone detected (%d min silence). Dropped content in #%s",
            int(silence_minutes),
            channel.name,
        )

    async def _post_throwback(self, channel: discord.TextChannel):
        """Post a throwback/conversation starter when the server is dead."""
        throwbacks = [
            "👀 The Circle has gone quiet... **Too quiet.** What's everyone up to right now?",
            "🔮 Keeper has been watching. The silence is deafening. **Someone say something interesting.**",
            "💀 Is The Circle... dead? Prove me wrong. Drop your hottest take below.",
            "⚡ **Activity check!** React with 🔥 if you're lurking right now.",
            "🎯 **Random question from the void:** What's the last thing that made you genuinely laugh?",
            "👑 The silence tells Keeper all it needs to know. Who's brave enough to break it?",
            "🌙 The Circle never truly sleeps. **What's keeping you up?**",
            "📡 Keeper senses life out there. **Drop a message. Any message. The Circle needs you.**",
        ]
        text = random.choice(throwbacks)

        embed = discord.Embed(
            title="🔮 THE CIRCLE STIRS",
            description=f"{text}\n\n━━━━━━━━━━━━━━━━━━━━━",
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="The Circle • Keeper is always watching")

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    @dead_zone_detector.before_loop
    async def before_dead_zone(self):
        await self.bot.wait_until_ready()

    # ─── Trending Topics ──────────────────────────────────────────────────

    @tasks.loop(hours=2)
    async def trending_scanner(self):
        """Analyze word frequency and post trending topics."""
        if not self._word_tracker:
            return

        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return

        channel = discord.utils.get(guild.text_channels, name="general")
        if not channel:
            return

        trending_found: List[Tuple[str, int, int]] = []  # (word, count, user_count)

        # Scale trending thresholds for small servers
        member_count = guild.member_count if guild else 50
        if member_count < 50:
            min_mentions = max(3, int(TRENDING_MIN_MENTIONS * member_count / 200))
            min_users = max(2, int(TRENDING_MIN_USERS * member_count / 200))
        else:
            min_mentions = TRENDING_MIN_MENTIONS
            min_users = TRENDING_MIN_USERS

        for word, user_counts in self._word_tracker.items():
            total_count = sum(user_counts.values())
            unique_users = len(user_counts)

            if total_count >= min_mentions and unique_users >= min_users:
                trending_found.append((word, total_count, unique_users))

        if not trending_found:
            return

        # Sort by total mentions, pick the top one that hasn't trended recently
        trending_found.sort(key=lambda x: x[1], reverse=True)

        for word, count, users in trending_found:
            if await _was_trending_recently(word, hours=24):
                continue

            await _log_trending(word, count, users)

            embed = discord.Embed(
                title="📈 TRENDING IN THE CIRCLE",
                description=(
                    f"**\"{word}\"** is on fire right now.\n\n"
                    f"📊 **{count}** mentions by **{users}** members\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "*The Circle has spoken. Join the conversation.*"
                ),
                color=EMBED_COLOR_ACCENT,
            )
            embed.set_footer(text="The Circle • Trending Topics")

            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

            log.info("ContentEngine: Trending topic '%s' (%d mentions, %d users)", word, count, users)
            break  # Only post one trending topic per cycle

        # Reset tracker after scan
        self._word_tracker.clear()
        self._word_window_start = datetime.now(timezone.utc)

    @trending_scanner.before_loop
    async def before_trending(self):
        await self.bot.wait_until_ready()

    # ─── User-Generated Content Submissions ───────────────────────────────

    @commands.group(name="submit", invoke_without_command=True)
    async def submit_group(self, ctx: commands.Context):
        """Submit user-generated content to The Circle."""
        embed = discord.Embed(
            title="📝 CONTENT SUBMISSIONS",
            description=(
                "Submit content for The Circle to use. Costs **"
                f"{UGC_SUBMIT_COST} 🪙** per submission.\n\n"
                "**Available types:**\n"
                "• `!submit prompt <text>` — Daily prompt\n"
                "• `!submit hottake <text>` — Hot Take Thursday topic\n"
                "• `!submit trivia <question>|<answer>|<wrong1>|<wrong2>|<wrong3>`\n\n"
                f"After **{UGC_AUTO_APPROVE_THRESHOLD}** approved submissions, "
                "your content is auto-approved.\n"
                f"When your content is used, you earn **{UGC_USED_REWARD_COINS} 🪙**."
                "\n━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="The Circle • Your voice matters")
        await ctx.send(embed=embed)

    @submit_group.command(name="prompt")
    async def submit_prompt(self, ctx: commands.Context, *, text: str):
        """Submit a daily prompt."""
        await self._handle_submission(ctx, "prompt", text)

    @submit_group.command(name="hottake")
    async def submit_hottake(self, ctx: commands.Context, *, text: str):
        """Submit a Hot Take Thursday topic."""
        await self._handle_submission(ctx, "hottake", text)

    @submit_group.command(name="trivia")
    async def submit_trivia(self, ctx: commands.Context, *, text: str):
        """Submit a trivia question. Format: question|answer|wrong1|wrong2|wrong3"""
        parts = [p.strip() for p in text.split("|")]
        if len(parts) != 5:
            await ctx.send(
                "❌ Invalid format. Use: `!submit trivia <question>|<answer>|<wrong1>|<wrong2>|<wrong3>`"
            )
            return
        await self._handle_submission(ctx, "trivia", text)

    async def _handle_submission(self, ctx: commands.Context, content_type: str, content: str):
        """Process a content submission: charge coins, check auto-approve, store."""
        # Rate limit: max 3 submissions per 24 hours per user
        cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM content_submissions WHERE user_id = ? AND submitted_at > ?",
                (ctx.author.id, cutoff_24h),
            )
            recent_count = (await cursor.fetchone())[0]
        if recent_count >= 3:
            await ctx.send("❌ You've hit the daily submission limit (3/day). Try again tomorrow.")
            return

        # Check and spend coins
        success = await spend_coins(ctx.author.id, UGC_SUBMIT_COST)
        if not success:
            await ctx.send(
                f"❌ Not enough Circles. You need **{UGC_SUBMIT_COST} 🪙** to submit content. "
                "Keep chatting to earn more!"
            )
            return

        # Check auto-approve eligibility
        prev_approvals = await _get_user_approval_count(ctx.author.id)
        auto_approved = prev_approvals >= UGC_AUTO_APPROVE_THRESHOLD

        sub_id = await _create_submission(ctx.author.id, content_type, content, auto_approved)

        if auto_approved:
            embed = discord.Embed(
                title="✅ SUBMISSION AUTO-APPROVED",
                description=(
                    f"**#{sub_id}** — Your `{content_type}` submission has been accepted.\n\n"
                    f"*\"{content[:100]}{'...' if len(content) > 100 else ''}\"*\n\n"
                    f"You've earned trust in The Circle. ({prev_approvals} prior approvals)\n"
                    f"You'll earn **{UGC_USED_REWARD_COINS} 🪙** when it's used."
                ),
                color=0x2ECC71,
            )
        else:
            embed = discord.Embed(
                title="📝 SUBMISSION RECEIVED",
                description=(
                    f"**#{sub_id}** — Your `{content_type}` is pending review.\n\n"
                    f"*\"{content[:100]}{'...' if len(content) > 100 else ''}\"*\n\n"
                    f"Cost: **{UGC_SUBMIT_COST} 🪙** | "
                    f"You'll earn **{UGC_USED_REWARD_COINS} 🪙** if approved and used.\n"
                    f"Get {UGC_AUTO_APPROVE_THRESHOLD} approvals for auto-trust "
                    f"({prev_approvals}/{UGC_AUTO_APPROVE_THRESHOLD} so far)."
                ),
                color=EMBED_COLOR_PRIMARY,
            )
        embed.set_footer(text="The Circle • Content Submissions")
        await ctx.send(embed=embed)

        log.info(
            "ContentEngine: Submission #%d (%s) from %s [auto=%s]",
            sub_id, content_type, ctx.author, auto_approved,
        )

    # ─── Admin: Approve / Reject ──────────────────────────────────────────

    @commands.command(name="approve")
    @commands.has_permissions(manage_messages=True)
    async def approve_submission(self, ctx: commands.Context, sub_id: int):
        """Approve a user-generated content submission."""
        result = await _update_submission_status(sub_id, "approved", ctx.author.id)
        if not result:
            await ctx.send(f"❌ Submission #{sub_id} not found.")
            return

        embed = discord.Embed(
            title="✅ SUBMISSION APPROVED",
            description=(
                f"**#{sub_id}** (`{result['content_type']}`) has been approved.\n\n"
                f"*\"{result['content'][:100]}{'...' if len(result['content']) > 100 else ''}\"*\n\n"
                f"Submitted by <@{result['user_id']}>"
            ),
            color=0x2ECC71,
        )
        embed.set_footer(text=f"Approved by {ctx.author}")
        await ctx.send(embed=embed)

    @commands.command(name="reject")
    @commands.has_permissions(manage_messages=True)
    async def reject_submission(self, ctx: commands.Context, sub_id: int):
        """Reject a user-generated content submission and refund coins."""
        result = await _update_submission_status(sub_id, "rejected", ctx.author.id)
        if not result:
            await ctx.send(f"❌ Submission #{sub_id} not found.")
            return

        # Refund the submission cost
        await add_coins(result["user_id"], UGC_SUBMIT_COST)

        embed = discord.Embed(
            title="❌ SUBMISSION REJECTED",
            description=(
                f"**#{sub_id}** (`{result['content_type']}`) has been rejected.\n\n"
                f"*\"{result['content'][:100]}{'...' if len(result['content']) > 100 else ''}\"*\n\n"
                f"**{UGC_SUBMIT_COST} 🪙** refunded to <@{result['user_id']}>."
            ),
            color=0xE74C3C,
        )
        embed.set_footer(text=f"Rejected by {ctx.author}")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ContentEngine(bot))
