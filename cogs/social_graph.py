"""
The Circle — Social Graph Cog
Tracks social interactions between users, calculates friendship scores,
detects best friends, runs icebreaker matchmaking, and supports rivalries.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import EXCLUDED_CHANNELS, BEST_FRIEND_MIN_SCORE
from database import (
    DB_PATH,
    add_coins,
    get_or_create_user,
    get_top_friends,
    spend_coins,
    update_social_interaction,
    update_user_score,
)

logger = logging.getLogger(__name__)

# ─── Config Constants ──────────────────────────────────────────────────────
FRIENDSHIP_DECAY_WEEKLY = 0.05
FRIENDSHIP_MIN_CONNECTIONS = 3
ICEBREAKER_CHECK_HOURS = 12
ICEBREAKER_REPLY_GOAL = 3
ICEBREAKER_REWARD_POINTS = 25
ICEBREAKER_REWARD_COINS = 10
RIVAL_COST = 50
RIVAL_DURATION_WEEKS = 4
RIVAL_WINNER_COINS = 25
RIVAL_CHECK_DAY = 0  # Monday
EMBED_COLOR_PRIMARY = 0x1A1A2E
EMBED_COLOR_ACCENT = 0xE94560

# ─── Roman numeral helper ──────────────────────────────────────────────────
_ROMAN = ["I", "II", "III", "IV", "V"]


def _friendship_bar(score: float, max_score: float = 100.0) -> str:
    """Return a visual bar representing friendship strength."""
    filled = int(min(score / max(max_score, 1), 1.0) * 10)
    return "█" * filled + "░" * (10 - filled)


def _rank_friendship(score: float) -> str:
    """Return a label for a friendship score."""
    if score >= 100:
        return "Soulbound 💀"
    if score >= 50:
        return "Bonded 🔗"
    if score >= 25:
        return "Close 🤝"
    if score >= 10:
        return "Familiar 👋"
    return "Acquaintance 👤"


async def _ensure_quest_table():
    """Create connection_quests table if it doesn't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS connection_quests (
                user_a INTEGER NOT NULL,
                user_b INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                a_replies INTEGER DEFAULT 0,
                b_replies INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                PRIMARY KEY (user_a, user_b)
            )
        """)
        await db.commit()


class SocialGraph(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track announced best-friend pairs so we don't repeat
        self._announced_bf: set[tuple[int, int]] = set()

    @commands.Cog.listener()
    async def on_ready(self):
        """Start background tasks (guard against double-start on reconnect)."""
        await _ensure_quest_table()
        await _ensure_bf_announce_table()
        if not self.friendship_decay.is_running():
            self.friendship_decay.start()
        if not self.icebreaker_matchmaking.is_running():
            self.icebreaker_matchmaking.start()
        if not self.best_friend_detection.is_running():
            self.best_friend_detection.start()
        if not self.weekly_rivalry_check.is_running():
            self.weekly_rivalry_check.start()

    def cog_unload(self):
        self.friendship_decay.cancel()
        self.icebreaker_matchmaking.cancel()
        self.best_friend_detection.cancel()
        self.weekly_rivalry_check.cancel()

    # ═══════════════════════════════════════════════════════════════════════
    # LISTENERS — Interaction Tracking
    # ═══════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track reply and mention interactions in the social graph."""
        if message.author.bot or not message.guild:
            return
        if message.channel.name in EXCLUDED_CHANNELS:
            return

        user_id = message.author.id

        # ─── Reply tracking ───────────────────────────────────────────
        if message.reference and message.reference.message_id:
            try:
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
                if ref_msg.author and not ref_msg.author.bot and ref_msg.author.id != user_id:
                    await update_social_interaction(user_id, ref_msg.author.id, "reply")
                    # Check icebreaker quest progress
                    await self._check_quest_progress(user_id, ref_msg.author.id)
            except (discord.NotFound, discord.HTTPException):
                pass

        # ─── Mention tracking ─────────────────────────────────────────
        for mentioned in message.mentions:
            if not mentioned.bot and mentioned.id != user_id:
                await update_social_interaction(user_id, mentioned.id, "mention")

        # ─── Rivalry score tracking ───────────────────────────────────
        await self._update_rival_score(user_id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Track reaction interactions in the social graph."""
        if payload.member and payload.member.bot:
            return
        if not payload.guild_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = guild.get_channel(payload.channel_id)
        if not channel or channel.name in EXCLUDED_CHANNELS:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.HTTPException):
            return

        if message.author.bot or payload.user_id == message.author.id:
            return

        await update_social_interaction(payload.user_id, message.author.id, "reaction")

    # ═══════════════════════════════════════════════════════════════════════
    # BACKGROUND TASKS
    # ═══════════════════════════════════════════════════════════════════════

    @tasks.loop(hours=168)  # Weekly (7 * 24)
    async def friendship_decay(self):
        """Reduce friendship scores for pairs with no interaction in the past week."""
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """UPDATE social_graph
                       SET friendship_score = friendship_score * ?
                       WHERE last_interaction < ? AND friendship_score > 0.1""",
                    (1.0 - FRIENDSHIP_DECAY_WEEKLY, cutoff),
                )
                # Clean up near-zero scores
                await db.execute(
                    "UPDATE social_graph SET friendship_score = 0 WHERE friendship_score <= 0.1"
                )
                await db.commit()
            logger.info("Social graph: weekly friendship decay applied (%.0f%% reduction)", FRIENDSHIP_DECAY_WEEKLY * 100)
        except Exception as e:
            logger.error("Social graph: friendship decay failed — %s", e)

    @friendship_decay.before_loop
    async def before_friendship_decay(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=ICEBREAKER_CHECK_HOURS)
    async def icebreaker_matchmaking(self):
        """Find new members with few connections and match them with active members."""
        try:
            await self._run_icebreaker_matchmaking()
        except Exception as e:
            logger.error("Social graph: icebreaker matchmaking failed — %s", e)

    @icebreaker_matchmaking.before_loop
    async def before_icebreaker(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=6)
    async def best_friend_detection(self):
        """Check for mutual #1 friendships and announce them."""
        try:
            await self._run_best_friend_detection()
        except Exception as e:
            logger.error("Social graph: best friend detection failed — %s", e)

    @best_friend_detection.before_loop
    async def before_best_friend(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=24)
    async def weekly_rivalry_check(self):
        """On Monday, compare rival weekly scores, award winners, reset scores."""
        if datetime.utcnow().weekday() != RIVAL_CHECK_DAY:
            return
        try:
            await self._run_weekly_rivalry_check()
        except Exception as e:
            logger.error("Social graph: weekly rivalry check failed — %s", e)

    @weekly_rivalry_check.before_loop
    async def before_rivalry_check(self):
        await self.bot.wait_until_ready()

    # ═══════════════════════════════════════════════════════════════════════
    # COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    @commands.command(name="friends")
    async def friends_cmd(self, ctx: commands.Context):
        """Show your top 5 connections with friendship scores."""
        user_id = ctx.author.id
        friends = await get_top_friends(user_id, limit=5)

        if not friends:
            embed = discord.Embed(
                title="👥 SOCIAL CONNECTIONS",
                description=(
                    "The Circle sees no bonds yet.\n\n"
                    "Start replying, mentioning, and reacting to others — "
                    "the threads will form on their own."
                ),
                color=EMBED_COLOR_PRIMARY,
            )
            await ctx.send(embed=embed)
            return

        lines = []
        for i, f in enumerate(friends, 1):
            # Determine who the friend is (the other user in the pair)
            friend_id = f["user_b"] if f["user_a"] == user_id else f["user_a"]
            score = f["friendship_score"]
            guild = ctx.guild
            member = guild.get_member(friend_id) if guild else None
            name = member.display_name if member else f"User {friend_id}"
            medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i - 1]
            bar = _friendship_bar(score)
            label = _rank_friendship(score)
            lines.append(f"{medal} **{name}**\n╰ {bar} `{score:.1f}` — {label}")

        embed = discord.Embed(
            title="👥 YOUR INNER CIRCLE",
            description="━━━━━━━━━━━━━━━━━━━━━\n" + "\n\n".join(lines) + "\n━━━━━━━━━━━━━━━━━━━━━",
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="Friendship scores grow from replies, mentions, and reactions.")
        await ctx.send(embed=embed)

    @commands.command(name="bestfriend", aliases=["bf"])
    async def bestfriend_cmd(self, ctx: commands.Context):
        """Show your #1 connection. If mutual, announce Best Friends status."""
        user_id = ctx.author.id
        friends = await get_top_friends(user_id, limit=1)

        if not friends:
            embed = discord.Embed(
                title="💔 NO BONDS DETECTED",
                description="The Circle has not yet woven your thread to another soul.\nInteract more — and the bond will form.",
                color=EMBED_COLOR_PRIMARY,
            )
            await ctx.send(embed=embed)
            return

        top = friends[0]
        friend_id = top["user_b"] if top["user_a"] == user_id else top["user_a"]
        score = top["friendship_score"]
        guild = ctx.guild
        member = guild.get_member(friend_id) if guild else None
        name = member.display_name if member else f"User {friend_id}"

        # Check if mutual
        their_friends = await get_top_friends(friend_id, limit=1)
        mutual = False
        if their_friends:
            their_top_id = their_friends[0]["user_b"] if their_friends[0]["user_a"] == friend_id else their_friends[0]["user_a"]
            if their_top_id == user_id:
                mutual = True

        if mutual:
            embed = discord.Embed(
                title="🔗 BEST FRIENDS — MUTUAL BOND",
                description=(
                    f"**{ctx.author.display_name}** ⟷ **{name}**\n\n"
                    f"Friendship Score: `{score:.1f}`\n"
                    f"{_friendship_bar(score)}\n\n"
                    "✨ *The Circle recognizes this bond as mutual.*\n"
                    "*Your threads are intertwined.*"
                ),
                color=EMBED_COLOR_ACCENT,
            )
        else:
            embed = discord.Embed(
                title="👤 YOUR STRONGEST BOND",
                description=(
                    f"🥇 **{name}**\n\n"
                    f"Friendship Score: `{score:.1f}`\n"
                    f"{_friendship_bar(score)}\n"
                    f"Status: {_rank_friendship(score)}\n\n"
                    "*The bond is strong from your side...\nbut is it mutual?*"
                ),
                color=EMBED_COLOR_PRIMARY,
            )

        await ctx.send(embed=embed)

    @commands.command(name="rival")
    async def rival_cmd(self, ctx: commands.Context, target: discord.Member | None = None):
        """Declare a 4-week rivalry with another member. Costs 50 Circles."""
        if target is None:
            embed = discord.Embed(
                title="⚔️ RIVALRY",
                description=(
                    "**Usage:** `!rival @user`\n\n"
                    f"Costs **{RIVAL_COST}** 🪙 to declare.\n"
                    f"Lasts **{RIVAL_DURATION_WEEKS} weeks**. Weekly score comparison.\n"
                    f"Winner earns **{RIVAL_WINNER_COINS}** 🪙 per week.\n\n"
                    "*Choose your enemy wisely...*"
                ),
                color=EMBED_COLOR_PRIMARY,
            )
            await ctx.send(embed=embed)
            return

        if target.bot:
            await ctx.send("⚠️ You cannot rival a bot. They feel nothing.")
            return
        if target.id == ctx.author.id:
            await ctx.send("⚠️ You cannot rival yourself... though that would explain a lot.")
            return

        user_id = ctx.author.id
        target_id = target.id

        # Check for existing rivalry
        a, b = min(user_id, target_id), max(user_id, target_id)
        now = datetime.utcnow()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM rivals WHERE user_a = ? AND user_b = ? AND expires_at > ?",
                (a, b, now.isoformat()),
            )
            existing = await cursor.fetchone()

        if existing:
            await ctx.send("⚠️ A rivalry already exists between you two. Settle the current one first.")
            return

        # Spend coins
        success = await spend_coins(user_id, RIVAL_COST)
        if not success:
            await ctx.send(f"⚠️ You need **{RIVAL_COST}** 🪙 to declare a rivalry. Earn more Circles first.")
            return

        # Create rivalry
        expires = now + timedelta(weeks=RIVAL_DURATION_WEEKS)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO rivals (user_a, user_b, started_at, expires_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_a, user_b) DO UPDATE SET
                       started_at = ?, expires_at = ?,
                       user_a_weekly_score = 0, user_b_weekly_score = 0""",
                (a, b, now.isoformat(), expires.isoformat(), now.isoformat(), expires.isoformat()),
            )
            await db.commit()

        embed = discord.Embed(
            title="⚔️ RIVALRY DECLARED",
            description=(
                f"**{ctx.author.display_name}** vs **{target.display_name}**\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Cost: {RIVAL_COST} 🪙\n"
                f"⏱️ Duration: {RIVAL_DURATION_WEEKS} weeks\n"
                f"🏆 Weekly winner: {RIVAL_WINNER_COINS} 🪙\n"
                f"📅 Expires: <t:{int(expires.timestamp())}:R>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                "*The Circle watches with great interest...*"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        await ctx.send(embed=embed)
        logger.info("Rivalry declared: %s vs %s (expires %s)", user_id, target_id, expires.isoformat())

    # ═══════════════════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    async def _check_quest_progress(self, replier_id: int, replied_to_id: int):
        """Check if a reply counts toward an active icebreaker quest (DB-persisted)."""
        key_a = min(replier_id, replied_to_id)
        key_b = max(replier_id, replied_to_id)

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM connection_quests WHERE user_a = ? AND user_b = ? AND completed = 0",
                (key_a, key_b),
            )
            quest = await cursor.fetchone()
            if not quest:
                return
            quest = dict(quest)

            # Check 24h expiry
            started = datetime.fromisoformat(quest["started_at"])
            if datetime.utcnow() > started + timedelta(hours=24):
                await db.execute(
                    "DELETE FROM connection_quests WHERE user_a = ? AND user_b = ?",
                    (key_a, key_b),
                )
                await db.commit()
                return

            # Increment the replier's count
            if replier_id == key_a:
                await db.execute(
                    "UPDATE connection_quests SET a_replies = a_replies + 1 WHERE user_a = ? AND user_b = ?",
                    (key_a, key_b),
                )
            else:
                await db.execute(
                    "UPDATE connection_quests SET b_replies = b_replies + 1 WHERE user_a = ? AND user_b = ?",
                    (key_a, key_b),
                )
            await db.commit()

            # Re-read to check completion
            cursor = await db.execute(
                "SELECT a_replies, b_replies FROM connection_quests WHERE user_a = ? AND user_b = ?",
                (key_a, key_b),
            )
            row = await cursor.fetchone()
            if not row:
                return

        a_replies, b_replies = row[0], row[1]
        if a_replies >= ICEBREAKER_REPLY_GOAL and b_replies >= ICEBREAKER_REPLY_GOAL:
            # Mark complete
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE connection_quests SET completed = 1 WHERE user_a = ? AND user_b = ?",
                    (key_a, key_b),
                )
                await db.commit()

            # Reward both users
            for uid in (key_a, key_b):
                await update_user_score(uid, ICEBREAKER_REWARD_POINTS)
                await add_coins(uid, ICEBREAKER_REWARD_COINS)

            # Announce completion
            for guild in self.bot.guilds:
                general = discord.utils.get(guild.text_channels, name="general")
                if general:
                    member_a = guild.get_member(key_a)
                    member_b = guild.get_member(key_b)
                    name_a = member_a.display_name if member_a else f"User {key_a}"
                    name_b = member_b.display_name if member_b else f"User {key_b}"
                    embed = discord.Embed(
                        title="🤝 CONNECTION QUEST COMPLETE",
                        description=(
                            f"**{name_a}** and **{name_b}** have forged a new bond!\n\n"
                            f"Both earned **{ICEBREAKER_REWARD_POINTS}** pts + **{ICEBREAKER_REWARD_COINS}** 🪙\n\n"
                            "*The Circle grows stronger with every connection.*"
                        ),
                        color=EMBED_COLOR_ACCENT,
                    )
                    try:
                        await general.send(embed=embed)
                    except discord.HTTPException:
                        pass
                    break

    async def _run_icebreaker_matchmaking(self):
        """Find new members with few connections and pair them with active members."""
        # Clean up expired quests older than 24h
        cutoff_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM connection_quests WHERE completed = 0 AND started_at < ?",
                (cutoff_24h,),
            )
            await db.commit()

        for guild in self.bot.guilds:
            cutoff = datetime.utcnow() - timedelta(days=7)

            # Find new members who joined within the last 7 days
            new_members = [
                m for m in guild.members
                if not m.bot and m.joined_at and m.joined_at.replace(tzinfo=None) > cutoff
            ]

            for new_member in new_members:
                # Check if they already have enough connections
                friends = await get_top_friends(new_member.id, limit=FRIENDSHIP_MIN_CONNECTIONS)
                strong_friends = [f for f in friends if f["friendship_score"] > 5]
                if len(strong_friends) >= FRIENDSHIP_MIN_CONNECTIONS:
                    continue

                # Don't give them a quest if one is already active (check DB)
                async with aiosqlite.connect(DB_PATH) as db:
                    cursor = await db.execute(
                        """SELECT COUNT(*) FROM connection_quests
                           WHERE (user_a = ? OR user_b = ?) AND completed = 0""",
                        (new_member.id, new_member.id),
                    )
                    active_count = (await cursor.fetchone())[0]
                if active_count > 0:
                    continue

                # Find an active member to pair with (not a bot, not the same person, active recently)
                active_cutoff = datetime.utcnow() - timedelta(days=3)
                candidates = []
                async with aiosqlite.connect(DB_PATH) as db:
                    db.row_factory = aiosqlite.Row
                    cursor = await db.execute(
                        """SELECT user_id FROM users
                           WHERE last_active > ? AND user_id != ?
                           ORDER BY total_score DESC LIMIT 20""",
                        (active_cutoff.isoformat(), new_member.id),
                    )
                    rows = await cursor.fetchall()
                    candidates = [row["user_id"] for row in rows]

                if not candidates:
                    continue

                # Pick a random active member
                match_id = random.choice(candidates)
                match_member = guild.get_member(match_id)
                if not match_member:
                    continue

                # Create the quest (persisted to DB)
                key_a = min(new_member.id, match_id)
                key_b = max(new_member.id, match_id)
                now_iso = datetime.utcnow().isoformat()
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        """INSERT OR IGNORE INTO connection_quests (user_a, user_b, started_at)
                           VALUES (?, ?, ?)""",
                        (key_a, key_b, now_iso),
                    )
                    await db.commit()

                # DM both users
                quest_desc = (
                    f"🤝 **CONNECTION QUEST**\n\n"
                    f"The Circle pairs you with **{{partner}}**.\n\n"
                    f"**Goal:** Reply to each other **{ICEBREAKER_REPLY_GOAL}** times in the next 24 hours.\n"
                    f"**Reward:** {ICEBREAKER_REWARD_POINTS} pts + {ICEBREAKER_REWARD_COINS} 🪙 each\n\n"
                    f"*The Circle watches... will you answer the call?*"
                )

                for user, partner in [(new_member, match_member), (match_member, new_member)]:
                    try:
                        embed = discord.Embed(
                            title="⚡ NEW CONNECTION QUEST",
                            description=quest_desc.format(partner=partner.display_name),
                            color=EMBED_COLOR_ACCENT,
                        )
                        await user.send(embed=embed)
                    except discord.HTTPException:
                        pass

                logger.info(
                    "Icebreaker quest created: %s (%s) <-> %s (%s)",
                    new_member.display_name, new_member.id,
                    match_member.display_name, match_id,
                )

    async def _run_best_friend_detection(self):
        """Check for mutual #1 friendships and announce new ones."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            # Get all users who have at least one friendship
            cursor = await db.execute(
                """SELECT DISTINCT user_a AS uid FROM social_graph WHERE friendship_score > 0
                   UNION
                   SELECT DISTINCT user_b AS uid FROM social_graph WHERE friendship_score > 0"""
            )
            all_users = [row["uid"] for row in await cursor.fetchall()]

        # For each user, find their #1 friend
        top_map: dict[int, int] = {}
        for uid in all_users:
            friends = await get_top_friends(uid, limit=1)
            if friends:
                f = friends[0]
                friend_id = f["user_b"] if f["user_a"] == uid else f["user_a"]
                top_map[uid] = friend_id

        # Find mutual pairs
        for uid, friend_id in top_map.items():
            if top_map.get(friend_id) == uid:
                pair = (min(uid, friend_id), max(uid, friend_id))

                # Check DB to see if we already announced this pair recently
                async with aiosqlite.connect(DB_PATH) as db:
                    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
                    cursor = await db.execute(
                        "SELECT 1 FROM best_friend_announcements WHERE user_a = ? AND user_b = ? AND announced_at > ?",
                        (pair[0], pair[1], cutoff),
                    )
                    if await cursor.fetchone():
                        continue

                # Check minimum score threshold
                uid_friends = await get_top_friends(uid, limit=1)
                if not uid_friends or uid_friends[0]["friendship_score"] < BEST_FRIEND_MIN_SCORE:
                    continue

                # Persist announcement to DB
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        """INSERT OR REPLACE INTO best_friend_announcements (user_a, user_b, announced_at)
                           VALUES (?, ?, ?)""",
                        (pair[0], pair[1], datetime.utcnow().isoformat()),
                    )
                    await db.commit()

                # Announce in #general
                for guild in self.bot.guilds:
                    general = discord.utils.get(guild.text_channels, name="general")
                    if not general:
                        continue
                    member_a = guild.get_member(pair[0])
                    member_b = guild.get_member(pair[1])
                    if not member_a or not member_b:
                        continue

                    embed = discord.Embed(
                        title="🔗 BEST FRIENDS DETECTED",
                        description=(
                            f"**{member_a.display_name}** ⟷ **{member_b.display_name}**\n\n"
                            "They are each other's strongest connection.\n"
                            "The Circle recognizes this mutual bond.\n\n"
                            "*Some threads are stronger than others...*"
                        ),
                        color=EMBED_COLOR_ACCENT,
                    )
                    try:
                        await general.send(embed=embed)
                    except discord.HTTPException:
                        pass
                    break

                logger.info("Best friend pair announced: %s <-> %s", pair[0], pair[1])


    async def _update_rival_score(self, user_id: int):
        """Increment weekly score for any active rivalry involving this user."""
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            # Check if user is user_a in any active rivalry
            await db.execute(
                """UPDATE rivals SET user_a_weekly_score = user_a_weekly_score + 1
                   WHERE user_a = ? AND expires_at > ?""",
                (user_id, now),
            )
            # Check if user is user_b in any active rivalry
            await db.execute(
                """UPDATE rivals SET user_b_weekly_score = user_b_weekly_score + 1
                   WHERE user_b = ? AND expires_at > ?""",
                (user_id, now),
            )
            await db.commit()

    async def _run_weekly_rivalry_check(self):
        """Compare rival weekly scores, award winners, reset for next week."""
        now = datetime.utcnow()
        guild = self.bot.guilds[0] if self.bot.guilds else None
        general = discord.utils.get(guild.text_channels, name="general") if guild else None

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM rivals WHERE expires_at > ?",
                (now.isoformat(),),
            )
            rivals = [dict(r) for r in await cursor.fetchall()]

        for rival in rivals:
            a_score = rival.get("user_a_weekly_score", 0)
            b_score = rival.get("user_b_weekly_score", 0)
            user_a = rival["user_a"]
            user_b = rival["user_b"]

            winner_id = None
            loser_id = None
            if a_score > b_score:
                winner_id, loser_id = user_a, user_b
            elif b_score > a_score:
                winner_id, loser_id = user_b, user_a
            # Tie = no winner

            if winner_id:
                await add_coins(winner_id, RIVAL_WINNER_COINS)

            # Reset weekly scores
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE rivals SET user_a_weekly_score = 0, user_b_weekly_score = 0 WHERE user_a = ? AND user_b = ?",
                    (user_a, user_b),
                )
                await db.commit()

            # Announce
            if general and guild and winner_id:
                w_member = guild.get_member(winner_id)
                l_member = guild.get_member(loser_id)
                w_name = w_member.display_name if w_member else f"User {winner_id}"
                l_name = l_member.display_name if l_member else f"User {loser_id}"
                try:
                    await general.send(
                        f"⚔️ **RIVALRY UPDATE** — **{w_name}** beat **{l_name}** this week "
                        f"({a_score if winner_id == user_a else b_score} vs "
                        f"{b_score if winner_id == user_a else a_score}) "
                        f"and earned **{RIVAL_WINNER_COINS}** 🪙!",
                        delete_after=3600,
                    )
                except discord.HTTPException:
                    pass

        # Clean up expired rivalries
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM rivals WHERE expires_at <= ?", (now.isoformat(),))
            await db.commit()

        logger.info("Weekly rivalry check complete: %d active rivalries processed", len(rivals))


async def _ensure_bf_announce_table():
    """Create best_friend_announcements table for persisting announced pairs."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS best_friend_announcements (
                user_a INTEGER NOT NULL,
                user_b INTEGER NOT NULL,
                announced_at TEXT NOT NULL,
                PRIMARY KEY (user_a, user_b)
            )
        """)
        await db.commit()


async def setup(bot: commands.Bot):
    await bot.add_cog(SocialGraph(bot))
    logger.info("✓ SocialGraph cog loaded")
