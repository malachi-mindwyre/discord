"""
The Circle — Database Layer
Async SQLite operations for users, messages, scores, ranks, and invites.
"""

from __future__ import annotations

import aiosqlite
from datetime import datetime, date, timedelta
from typing import Optional

DB_PATH = "circle.db"


async def init_db():
    """Create all tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                total_score REAL DEFAULT 0.0,
                current_rank INTEGER DEFAULT 1,
                joined_at TEXT NOT NULL,
                last_active TEXT NOT NULL,
                invite_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                word_count INTEGER DEFAULT 0,
                has_media INTEGER DEFAULT 0,
                is_reply INTEGER DEFAULT 0,
                has_mention INTEGER DEFAULT 0,
                points_earned REAL DEFAULT 0.0,
                parent_message_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS daily_scores (
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                points_today REAL DEFAULT 0.0,
                PRIMARY KEY (user_id, date),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS rank_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                old_rank INTEGER NOT NULL,
                new_rank INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS invites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inviter_id INTEGER NOT NULL,
                invitee_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                is_valid INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                FOREIGN KEY (inviter_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS streaks (
                user_id INTEGER PRIMARY KEY,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                last_streak_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                achievement_key TEXT NOT NULL,
                unlocked_at TEXT NOT NULL,
                UNIQUE(user_id, achievement_key),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS voice_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                left_at TEXT,
                minutes_earned REAL DEFAULT 0.0,
                points_earned REAL DEFAULT 0.0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS reactions_received (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_author_id INTEGER NOT NULL,
                reactor_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                points_earned REAL DEFAULT 0.0,
                FOREIGN KEY (message_author_id) REFERENCES users(user_id)
            );

            -- ─── Phase 2 Tables ──────────────────────────────────────────

            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER PRIMARY KEY,
                coins INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS shop_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_key TEXT NOT NULL,
                purchased_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS shop_rotating (
                item_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                cost INTEGER NOT NULL,
                description TEXT,
                available_until TEXT NOT NULL,
                stock_remaining INTEGER DEFAULT -1
            );

            CREATE TABLE IF NOT EXISTS confessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                number INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                reaction_count INTEGER DEFAULT 0,
                message_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS starboard (
                message_id INTEGER PRIMARY KEY,
                author_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                star_count INTEGER DEFAULT 0,
                starboard_message_id INTEGER,
                content TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS factions (
                user_id INTEGER PRIMARY KEY,
                team_name TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS faction_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_name TEXT NOT NULL,
                week TEXT NOT NULL,
                total_score REAL DEFAULT 0.0,
                UNIQUE(team_name, week)
            );

            CREATE TABLE IF NOT EXISTS buddies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mentor_id INTEGER NOT NULL,
                mentee_id INTEGER NOT NULL,
                assigned_at TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                mentee_msg_count INTEGER DEFAULT 0,
                FOREIGN KEY (mentor_id) REFERENCES users(user_id),
                FOREIGN KEY (mentee_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                bio TEXT DEFAULT '',
                accent_color TEXT DEFAULT '',
                banner_url TEXT DEFAULT '',
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS login_rewards (
                user_id INTEGER PRIMARY KEY,
                current_day INTEGER DEFAULT 0,
                last_claim_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS smart_dm_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                dm_type TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS trivia_scores (
                user_id INTEGER PRIMARY KEY,
                correct_count INTEGER DEFAULT 0,
                total_played INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS invite_reminders_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                template_index INTEGER NOT NULL,
                posted_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS monthly_invite_race (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                invite_count INTEGER DEFAULT 0,
                winner INTEGER DEFAULT 0,
                UNIQUE(user_id, month),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS server_milestones (
                milestone_key TEXT PRIMARY KEY,
                reached_at TEXT,
                rewarded INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS weekly_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_value INTEGER NOT NULL,
                current_value INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS rank_tease_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                teased_rank INTEGER NOT NULL,
                sent_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS stagnation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                nudged_at TEXT NOT NULL,
                rank_at_nudge INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS engagement_trigger_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger_type TEXT NOT NULL,
                channel_id INTEGER NOT NULL,
                posted_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS introductions (
                user_id INTEGER PRIMARY KEY,
                posted_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            -- ─── Phase 3 Tables (Ultimate Engagement Engine) ─────────

            -- Variable Rewards
            CREATE TABLE IF NOT EXISTS jackpot (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_pot REAL DEFAULT 50.0,
                last_winner_id INTEGER,
                last_won_at TEXT,
                total_wins INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS daily_spins (
                user_id INTEGER PRIMARY KEY,
                last_spin_date TEXT,
                total_spins INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS bonus_drops (
                user_id INTEGER PRIMARY KEY,
                multiplier REAL DEFAULT 1.0,
                expires_at TEXT
            );

            -- Loss Aversion
            CREATE TABLE IF NOT EXISTS demotion_watch (
                user_id INTEGER PRIMARY KEY,
                below_threshold_since TEXT,
                current_rank_at_watch INTEGER
            );

            CREATE TABLE IF NOT EXISTS streak_freezes (
                user_id INTEGER PRIMARY KEY,
                tokens_held INTEGER DEFAULT 0,
                tokens_used_total INTEGER DEFAULT 0,
                last_auto_used TEXT
            );

            CREATE TABLE IF NOT EXISTS displacement_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                overtaker_id INTEGER NOT NULL,
                old_position INTEGER,
                new_position INTEGER,
                timestamp TEXT NOT NULL
            );

            -- Onboarding v2
            CREATE TABLE IF NOT EXISTS onboarding_state (
                user_id INTEGER PRIMARY KEY,
                joined_at TEXT NOT NULL,
                stage TEXT NOT NULL DEFAULT 'joined',
                first_message_at TEXT,
                first_reply_at TEXT,
                intro_posted INTEGER DEFAULT 0,
                daily_claimed INTEGER DEFAULT 0,
                buddy_greeted INTEGER DEFAULT 0,
                voice_joined INTEGER DEFAULT 0,
                graduation_at TEXT,
                dm_log TEXT DEFAULT '[]'
            );

            -- Re-engagement
            CREATE TABLE IF NOT EXISTS reengagement_state (
                user_id INTEGER PRIMARY KEY,
                last_active TEXT NOT NULL,
                current_tier TEXT DEFAULT 'active',
                last_dm_sent TEXT,
                last_dm_tier TEXT,
                total_dms_sent INTEGER DEFAULT 0,
                opted_out INTEGER DEFAULT 0
            );

            -- Streaks v2
            CREATE TABLE IF NOT EXISTS streaks_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                streak_type TEXT NOT NULL,
                current_count INTEGER DEFAULT 0,
                longest_count INTEGER DEFAULT 0,
                last_activity_date TEXT,
                freeze_tokens INTEGER DEFAULT 0,
                frozen_today INTEGER DEFAULT 0,
                grace_period_used INTEGER DEFAULT 0,
                UNIQUE(user_id, streak_type)
            );

            CREATE TABLE IF NOT EXISTS paired_streaks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_a INTEGER NOT NULL,
                user_b INTEGER NOT NULL,
                current_count INTEGER DEFAULT 0,
                longest_count INTEGER DEFAULT 0,
                last_both_active TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(user_a, user_b)
            );

            -- Social Graph
            CREATE TABLE IF NOT EXISTS social_graph (
                user_a INTEGER NOT NULL,
                user_b INTEGER NOT NULL,
                interaction_count INTEGER DEFAULT 0,
                reply_count INTEGER DEFAULT 0,
                mention_count INTEGER DEFAULT 0,
                reaction_count INTEGER DEFAULT 0,
                voice_overlap_minutes REAL DEFAULT 0.0,
                last_interaction TEXT,
                friendship_score REAL DEFAULT 0.0,
                PRIMARY KEY (user_a, user_b)
            );

            -- Social streak cache (persists across restarts)
            CREATE TABLE IF NOT EXISTS social_streak_cache (
                user_id INTEGER NOT NULL,
                replied_to_id INTEGER NOT NULL,
                cache_date TEXT NOT NULL,
                PRIMARY KEY (user_id, replied_to_id, cache_date)
            );

            -- Coin transfers (trading)
            CREATE TABLE IF NOT EXISTS coin_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                tax INTEGER NOT NULL,
                transferred_at TEXT NOT NULL
            );

            -- Circles (Friend Groups)
            CREATE TABLE IF NOT EXISTS circles (
                circle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                creator_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                max_members INTEGER DEFAULT 8,
                description TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS circle_members (
                circle_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                role TEXT DEFAULT 'member',
                PRIMARY KEY (circle_id, user_id)
            );

            -- Content Engine
            CREATE TABLE IF NOT EXISTS content_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                content TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                used_at TEXT,
                engagement_score REAL DEFAULT 0.0,
                upvotes INTEGER DEFAULT 0,
                downvotes INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS debate_scores (
                user_id INTEGER PRIMARY KEY,
                debates_participated INTEGER DEFAULT 0,
                total_reactions INTEGER DEFAULT 0,
                mvp_count INTEGER DEFAULT 0,
                debate_score REAL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS trending_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                mention_count INTEGER DEFAULT 0,
                unique_users INTEGER DEFAULT 0,
                detected_at TEXT NOT NULL,
                window_start TEXT NOT NULL
            );

            -- Faction Warfare 2.0
            CREATE TABLE IF NOT EXISTS faction_wars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week TEXT NOT NULL,
                challenge_type TEXT NOT NULL,
                winning_team TEXT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                scores TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS faction_territories (
                channel_name TEXT NOT NULL,
                week TEXT NOT NULL,
                controlling_team TEXT,
                message_counts TEXT DEFAULT '{}',
                PRIMARY KEY (channel_name, week)
            );

            CREATE TABLE IF NOT EXISTS faction_treasury (
                team_name TEXT PRIMARY KEY,
                treasury INTEGER DEFAULT 0,
                total_contributed INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS faction_loyalty (
                user_id INTEGER PRIMARY KEY,
                team_name TEXT NOT NULL,
                loyalty_score REAL DEFAULT 0.0,
                days_in_faction INTEGER DEFAULT 0,
                treasury_donations INTEGER DEFAULT 0,
                wars_won INTEGER DEFAULT 0
            );

            -- Season Pass
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
                xp INTEGER DEFAULT 0,
                tier INTEGER DEFAULT 0,
                is_premium INTEGER DEFAULT 0,
                weekly_challenges_completed INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, season_id)
            );

            -- season_challenges and season_challenge_completions are created
            -- by cogs/season_pass.py with its own schema (includes frequency,
            -- target_key, target_value, active_date, expires_date columns).
            -- Do NOT create them here to avoid schema conflicts.

            CREATE TABLE IF NOT EXISTS season_rewards (
                season_id INTEGER NOT NULL,
                tier INTEGER NOT NULL,
                is_premium INTEGER DEFAULT 0,
                reward_type TEXT NOT NULL,
                reward_value TEXT NOT NULL,
                PRIMARY KEY (season_id, tier, is_premium)
            );

            -- Prestige
            CREATE TABLE IF NOT EXISTS prestige (
                user_id INTEGER PRIMARY KEY,
                prestige_level INTEGER DEFAULT 0,
                last_prestige_at TEXT,
                total_score_before_prestige REAL DEFAULT 0.0
            );

            -- Engagement Ladder
            CREATE TABLE IF NOT EXISTS user_engagement_tier (
                user_id INTEGER PRIMARY KEY,
                tier TEXT DEFAULT 'lurker',
                tier_since TEXT NOT NULL,
                messages_this_week INTEGER DEFAULT 0,
                replies_this_week INTEGER DEFAULT 0,
                voice_minutes_this_week REAL DEFAULT 0,
                invites_total INTEGER DEFAULT 0,
                consecutive_active_weeks INTEGER DEFAULT 0
            );

            -- Legacy / History
            CREATE TABLE IF NOT EXISTS legacy_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );

            -- Hidden Moderation
            CREATE TABLE IF NOT EXISTS mod_reputation (
                user_id INTEGER PRIMARY KEY,
                reputation REAL DEFAULT 100.0,
                warnings INTEGER DEFAULT 0,
                last_warning_at TEXT,
                muted_until TEXT
            );

            -- Combo Tracker
            CREATE TABLE IF NOT EXISTS combo_tracker (
                user_id INTEGER PRIMARY KEY,
                combo_count INTEGER DEFAULT 0,
                last_social_at TEXT
            );

            -- Channel Diversity Tracker
            CREATE TABLE IF NOT EXISTS channel_diversity (
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                channels TEXT DEFAULT '[]',
                PRIMARY KEY (user_id, date)
            );

            -- Kudos (Peer Recognition)
            CREATE TABLE IF NOT EXISTS kudos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                giver_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                reason TEXT,
                given_at TEXT NOT NULL
            );

            -- Rivals
            CREATE TABLE IF NOT EXISTS rivals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_a INTEGER NOT NULL,
                user_b INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                user_a_weekly_score REAL DEFAULT 0.0,
                user_b_weekly_score REAL DEFAULT 0.0,
                UNIQUE(user_a, user_b)
            );

            -- Time Capsules
            CREATE TABLE IF NOT EXISTS time_capsules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                reveal_at TEXT NOT NULL,
                revealed INTEGER DEFAULT 0
            );

            -- XP Boosts (active)
            CREATE TABLE IF NOT EXISTS active_boosts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                boost_type TEXT NOT NULL,
                multiplier REAL DEFAULT 2.0,
                expires_at TEXT NOT NULL
            );

            -- ─── Indexes ─────────────────────────────────────────────────

            CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
            CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id);
            CREATE INDEX IF NOT EXISTS idx_daily_scores_date ON daily_scores(date);
            CREATE INDEX IF NOT EXISTS idx_invites_inviter ON invites(inviter_id);
            CREATE INDEX IF NOT EXISTS idx_achievements_user ON achievements(user_id);
            CREATE INDEX IF NOT EXISTS idx_voice_user ON voice_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_reactions_author ON reactions_received(message_author_id);
            CREATE INDEX IF NOT EXISTS idx_confessions_number ON confessions(number);
            CREATE INDEX IF NOT EXISTS idx_starboard_author ON starboard(author_id);
            CREATE INDEX IF NOT EXISTS idx_factions_team ON factions(team_name);
            CREATE INDEX IF NOT EXISTS idx_buddies_mentee ON buddies(mentee_id);
            CREATE INDEX IF NOT EXISTS idx_smart_dm_user ON smart_dm_log(user_id);
            CREATE INDEX IF NOT EXISTS idx_engagement_trigger ON engagement_trigger_log(channel_id, posted_at);
            CREATE INDEX IF NOT EXISTS idx_social_graph_a ON social_graph(user_a);
            CREATE INDEX IF NOT EXISTS idx_social_graph_b ON social_graph(user_b);
            CREATE INDEX IF NOT EXISTS idx_streaks_v2_user ON streaks_v2(user_id);
            CREATE INDEX IF NOT EXISTS idx_paired_streaks ON paired_streaks(user_a, user_b);
            CREATE INDEX IF NOT EXISTS idx_legacy_user ON legacy_events(user_id);
            CREATE INDEX IF NOT EXISTS idx_kudos_receiver ON kudos(receiver_id);
            CREATE INDEX IF NOT EXISTS idx_season_progress ON season_progress(user_id);
            CREATE INDEX IF NOT EXISTS idx_active_boosts ON active_boosts(user_id, expires_at);
        """)

    # ── Schema Migrations (safe to run repeatedly) ──────────────────────────
    await _run_migrations()


async def _run_migrations():
    """Add new columns to existing tables. Each ALTER is wrapped in try/except
    so it's safe to run repeatedly (column already exists = no-op)."""
    migrations = [
        "ALTER TABLE messages ADD COLUMN parent_message_id INTEGER",
        "ALTER TABLE confessions ADD COLUMN message_id INTEGER",
        "ALTER TABLE metrics_daily ADD COLUMN onboarding_total INTEGER DEFAULT 0",
        "ALTER TABLE metrics_daily ADD COLUMN onboarding_messaged INTEGER DEFAULT 0",
        "ALTER TABLE metrics_daily ADD COLUMN onboarding_graduated INTEGER DEFAULT 0",
    ]
    async with aiosqlite.connect(DB_PATH) as db:
        for sql in migrations:
            try:
                await db.execute(sql)
            except Exception:
                pass  # Column already exists
        await db.commit()


# ─── User Operations ───────────────────────────────────────────────────────

async def get_or_create_user(user_id: int, username: str) -> dict:
    """Get existing user or create a new one. Returns user dict."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return dict(row)
        await db.execute(
            "INSERT INTO users (user_id, username, joined_at, last_active) VALUES (?, ?, ?, ?)",
            (user_id, username, now, now),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return dict(await cursor.fetchone())


async def update_user_score(user_id: int, points: float, new_rank: Optional[int] = None):
    """Add points to user's total score and update last_active. Optionally update rank."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        if new_rank is not None:
            await db.execute(
                "UPDATE users SET total_score = total_score + ?, last_active = ?, current_rank = ? WHERE user_id = ?",
                (points, now, new_rank, user_id),
            )
        else:
            await db.execute(
                "UPDATE users SET total_score = total_score + ?, last_active = ? WHERE user_id = ?",
                (points, now, user_id),
            )
        await db.commit()


async def set_user_score(user_id: int, score: float, rank: int):
    """Set a user's score and rank directly (admin use)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET total_score = ?, current_rank = ? WHERE user_id = ?",
            (score, rank, user_id),
        )
        await db.commit()


async def get_user(user_id: int) -> Optional[dict]:
    """Get a user by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_top_users(limit: int = 25) -> list[dict]:
    """Get top users by score."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users ORDER BY total_score DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in await cursor.fetchall()]


async def get_inactive_users(days: int) -> list[dict]:
    """Get users who haven't been active for N+ days."""

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE last_active < ? AND total_score > 0",
            (cutoff,),
        )
        return [dict(row) for row in await cursor.fetchall()]


async def apply_score_decay(user_id: int, decay_rate: float):
    """Reduce a user's score by a percentage."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET total_score = total_score * (1.0 - ?) WHERE user_id = ?",
            (decay_rate, user_id),
        )
        await db.commit()


async def reset_user(user_id: int):
    """Reset a user's score and rank to defaults."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET total_score = 0.0, current_rank = 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


# ─── Message Logging ───────────────────────────────────────────────────────

async def log_message(user_id: int, channel_id: int, word_count: int,
                      has_media: bool, is_reply: bool, has_mention: bool,
                      points_earned: float, parent_message_id: int | None = None):
    """Log a scored message."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO messages
               (user_id, channel_id, timestamp, word_count, has_media, is_reply, has_mention, points_earned, parent_message_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, channel_id, now, word_count, int(has_media), int(is_reply), int(has_mention), points_earned, parent_message_id),
        )
        await db.commit()


async def get_recent_message_text(user_id: int, seconds: int) -> list[str]:
    """Get message timestamps within the last N seconds (for spam/duplicate detection).
    Returns list of timestamps as strings."""

    cutoff = (datetime.utcnow() - timedelta(seconds=seconds)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT timestamp FROM messages WHERE user_id = ? AND timestamp > ? ORDER BY timestamp DESC",
            (user_id, cutoff),
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


# ─── Daily Score Tracking ──────────────────────────────────────────────────

async def get_daily_points(user_id: int) -> float:
    """Get how many points a user has earned today."""
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT points_today FROM daily_scores WHERE user_id = ? AND date = ?",
            (user_id, today),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0.0


async def add_daily_points(user_id: int, points: float):
    """Add to today's point total."""
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO daily_scores (user_id, date, points_today)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, date) DO UPDATE SET points_today = points_today + ?""",
            (user_id, today, points, points),
        )
        await db.commit()


async def get_today_top_user() -> Optional[dict]:
    """Get the most active user today."""
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT u.*, ds.points_today FROM daily_scores ds
               JOIN users u ON u.user_id = ds.user_id
               WHERE ds.date = ? ORDER BY ds.points_today DESC LIMIT 1""",
            (today,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ─── Rank History ──────────────────────────────────────────────────────────

async def log_rank_change(user_id: int, old_rank: int, new_rank: int):
    """Log a rank change."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO rank_history (user_id, old_rank, new_rank, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, old_rank, new_rank, now),
        )
        await db.commit()


# ─── Invite Tracking ──────────────────────────────────────────────────────

async def log_invite(inviter_id: int, invitee_id: int):
    """Log a new invite (not yet validated)."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO invites (inviter_id, invitee_id, joined_at) VALUES (?, ?, ?)",
            (inviter_id, invitee_id, now),
        )
        await db.commit()


async def validate_invite(invitee_id: int):
    """Mark an invite as valid and increment the inviter's count."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT inviter_id FROM invites WHERE invitee_id = ? AND is_valid = 0",
            (invitee_id,),
        )
        row = await cursor.fetchone()
        if row:
            inviter_id = row[0]
            await db.execute(
                "UPDATE invites SET is_valid = 1 WHERE invitee_id = ?",
                (invitee_id,),
            )
            await db.execute(
                "UPDATE users SET invite_count = invite_count + 1 WHERE user_id = ?",
                (inviter_id,),
            )
            await db.commit()
            return inviter_id
        return None


async def increment_invitee_messages(invitee_id: int) -> int:
    """Increment message count for an invitee tracking. Returns new count."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE invites SET message_count = message_count + 1 WHERE invitee_id = ? AND is_valid = 0",
            (invitee_id,),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT message_count FROM invites WHERE invitee_id = ? AND is_valid = 0",
            (invitee_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_top_inviters(limit: int = 10) -> list[dict]:
    """Get top users by invite count."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE invite_count > 0 ORDER BY invite_count DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in await cursor.fetchall()]


# ─── Streaks ───────────────────────────────────────────────────────────────

async def get_streak(user_id: int) -> dict:
    """Get a user's streak data."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM streaks WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return {"user_id": user_id, "current_streak": 0, "longest_streak": 0, "last_streak_date": None}


async def update_streak(user_id: int) -> dict:
    """Update a user's streak. Returns updated streak info with 'streak_changed' flag."""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM streaks WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()

        if not row:
            # First ever message
            await db.execute(
                "INSERT INTO streaks (user_id, current_streak, longest_streak, last_streak_date) VALUES (?, 1, 1, ?)",
                (user_id, today),
            )
            await db.commit()
            return {"current_streak": 1, "longest_streak": 1, "streak_changed": True, "is_new": True}

        streak_data = dict(row)
        last_date = streak_data["last_streak_date"]

        if last_date == today:
            # Already logged today
            return {**streak_data, "streak_changed": False, "is_new": False}

        if last_date == yesterday:
            # Continuing streak
            new_streak = streak_data["current_streak"] + 1
            new_longest = max(new_streak, streak_data["longest_streak"])
            await db.execute(
                "UPDATE streaks SET current_streak = ?, longest_streak = ?, last_streak_date = ? WHERE user_id = ?",
                (new_streak, new_longest, today, user_id),
            )
            await db.commit()
            return {"current_streak": new_streak, "longest_streak": new_longest, "streak_changed": True, "is_new": False}
        else:
            # Streak broken — reset to 1
            await db.execute(
                "UPDATE streaks SET current_streak = 1, last_streak_date = ? WHERE user_id = ?",
                (today, user_id),
            )
            await db.commit()
            return {"current_streak": 1, "longest_streak": streak_data["longest_streak"], "streak_changed": True, "is_new": False}


async def get_top_streaks(limit: int = 10) -> list[dict]:
    """Get users with highest current streaks."""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT s.*, u.username FROM streaks s
               JOIN users u ON u.user_id = s.user_id
               WHERE s.last_streak_date IN (?, ?) AND s.current_streak > 0
               ORDER BY s.current_streak DESC LIMIT ?""",
            (today, yesterday, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]


# ─── Achievements ──────────────────────────────────────────────────────────

async def unlock_achievement(user_id: int, achievement_key: str) -> bool:
    """Unlock an achievement. Returns True if newly unlocked, False if already had it."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO achievements (user_id, achievement_key, unlocked_at) VALUES (?, ?, ?)",
                (user_id, achievement_key, now),
            )
            await db.commit()
            return True
        except Exception:
            return False


async def get_user_achievements(user_id: int) -> list[str]:
    """Get all achievement keys a user has unlocked."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT achievement_key FROM achievements WHERE user_id = ?",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def count_user_achievements(user_id: int) -> int:
    """Count how many achievements a user has."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM achievements WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


# ─── Voice Sessions ───────────────────────────────────────────────────────

async def start_voice_session(user_id: int, channel_id: int):
    """Log when a user joins a voice channel."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO voice_sessions (user_id, channel_id, joined_at) VALUES (?, ?, ?)",
            (user_id, channel_id, now),
        )
        await db.commit()


async def end_voice_session(user_id: int, points_per_minute: float) -> Optional[float]:
    """End a voice session. Returns points earned, or None if no open session."""
    now = datetime.utcnow()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, joined_at FROM voice_sessions WHERE user_id = ? AND left_at IS NULL ORDER BY joined_at DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        session_id, joined_at_str = row
        joined_at = datetime.fromisoformat(joined_at_str)
        minutes = (now - joined_at).total_seconds() / 60.0
        # Cap at 8 hours per session to prevent abuse
        minutes = min(minutes, 480)
        points = minutes * points_per_minute

        await db.execute(
            "UPDATE voice_sessions SET left_at = ?, minutes_earned = ?, points_earned = ? WHERE id = ?",
            (now.isoformat(), minutes, points, session_id),
        )
        await db.commit()
        return points


async def get_user_voice_minutes(user_id: int) -> float:
    """Get total voice minutes for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(SUM(minutes_earned), 0) FROM voice_sessions WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0.0


# ─── Reactions ─────────────────────────────────────────────────────────────

async def log_reaction(message_author_id: int, reactor_id: int, message_id: int,
                       channel_id: int, points: float):
    """Log a reaction received and its points."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        # Check if this reactor already reacted to this message
        cursor = await db.execute(
            "SELECT id FROM reactions_received WHERE reactor_id = ? AND message_id = ?",
            (reactor_id, message_id),
        )
        if await cursor.fetchone():
            return False  # Already counted
        await db.execute(
            """INSERT INTO reactions_received
               (message_author_id, reactor_id, message_id, channel_id, timestamp, points_earned)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (message_author_id, reactor_id, message_id, channel_id, now, points),
        )
        await db.commit()
        return True


async def get_user_total_reactions(user_id: int) -> int:
    """Get total reactions received by a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM reactions_received WHERE message_author_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


# ─── Weekly Stats ──────────────────────────────────────────────────────────

async def get_weekly_stats() -> dict:
    """Get stats for the past 7 days for the weekly recap."""

    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Top poster this week
        cursor = await db.execute(
            """SELECT u.username, u.user_id, SUM(m.points_earned) as week_points, COUNT(*) as msg_count
               FROM messages m JOIN users u ON u.user_id = m.user_id
               WHERE m.timestamp > ? GROUP BY m.user_id ORDER BY week_points DESC LIMIT 1""",
            (week_ago,),
        )
        top_poster = await cursor.fetchone()

        # Most replied-to (most replies received)
        cursor = await db.execute(
            """SELECT u.username, u.user_id, COUNT(*) as reply_count
               FROM messages m JOIN users u ON u.user_id = m.user_id
               WHERE m.timestamp > ? AND m.is_reply = 1
               GROUP BY m.user_id ORDER BY reply_count DESC LIMIT 1""",
            (week_ago,),
        )
        most_social = await cursor.fetchone()

        # Biggest rank-up (most tiers gained)
        cursor = await db.execute(
            """SELECT u.username, u.user_id, MAX(rh.new_rank) - MIN(rh.old_rank) as tiers_gained
               FROM rank_history rh JOIN users u ON u.user_id = rh.user_id
               WHERE rh.timestamp > ? GROUP BY rh.user_id ORDER BY tiers_gained DESC LIMIT 1""",
            (week_ago,),
        )
        biggest_climber = await cursor.fetchone()

        # Total messages this week
        cursor = await db.execute(
            "SELECT COUNT(*) FROM messages WHERE timestamp > ?", (week_ago,),
        )
        total_messages = (await cursor.fetchone())[0]

        # Total active users this week
        cursor = await db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM messages WHERE timestamp > ?", (week_ago,),
        )
        active_users = (await cursor.fetchone())[0]

        # Total reactions this week
        cursor = await db.execute(
            "SELECT COUNT(*) FROM reactions_received WHERE timestamp > ?", (week_ago,),
        )
        total_reactions = (await cursor.fetchone())[0]

        return {
            "top_poster": dict(top_poster) if top_poster else None,
            "most_social": dict(most_social) if most_social else None,
            "biggest_climber": dict(biggest_climber) if biggest_climber else None,
            "total_messages": total_messages,
            "active_users": active_users,
            "total_reactions": total_reactions,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 3 — New Helper Functions for Scoring Engine v2
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def get_messages_today_count(user_id: int) -> int:
    """Get how many messages a user has sent today."""
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM messages WHERE user_id = ? AND timestamp >= ?",
            (user_id, today),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_unique_channels_today(user_id: int) -> int:
    """Get how many unique channels a user has posted in today."""
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(DISTINCT channel_id) FROM messages WHERE user_id = ? AND timestamp >= ?",
            (user_id, today),
        )
        row = await cursor.fetchone()
        return max(1, row[0] if row else 1)


async def get_user_faction(user_id: int) -> Optional[str]:
    """Get a user's faction team name, or None if not in a faction."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT team_name FROM factions WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_winning_faction() -> Optional[str]:
    """Get the currently winning faction for this week."""
    from datetime import datetime
    # Current ISO week
    now = datetime.utcnow()
    week = now.strftime("%Y-W%W")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT team_name FROM faction_scores WHERE week = ? ORDER BY total_score DESC LIMIT 1",
            (week,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_prestige_level(user_id: int) -> int:
    """Get a user's prestige level."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT prestige_level FROM prestige WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_combo_state(user_id: int) -> Optional[dict]:
    """Get a user's current combo state."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM combo_tracker WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_combo_state(user_id: int, combo_count: int, last_social_at: str):
    """Update a user's combo state."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO combo_tracker (user_id, combo_count, last_social_at)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET combo_count = ?, last_social_at = ?""",
            (user_id, combo_count, last_social_at, combo_count, last_social_at),
        )
        await db.commit()


async def add_coins(user_id: int, amount: int):
    """Add coins to a user's economy balance."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO economy (user_id, coins, total_earned)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET coins = coins + ?, total_earned = total_earned + ?""",
            (user_id, amount, amount, amount, amount),
        )
        await db.commit()


async def spend_coins(user_id: int, amount: int) -> bool:
    """Spend coins. Returns True if user had enough, False otherwise."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT coins FROM economy WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        current = row[0] if row else 0
        if current < amount:
            return False
        await db.execute(
            "UPDATE economy SET coins = coins - ?, total_spent = total_spent + ? WHERE user_id = ?",
            (amount, amount, user_id),
        )
        await db.commit()
        return True


async def get_coins(user_id: int) -> int:
    """Get a user's coin balance."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT coins FROM economy WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def update_jackpot_pot(amount: float):
    """Add to the progressive jackpot pot."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO jackpot (id, current_pot) VALUES (1, ?)
               ON CONFLICT(id) DO UPDATE SET current_pot = current_pot + ?""",
            (50.0 + amount, amount),
        )
        await db.commit()


async def get_jackpot_pot() -> float:
    """Get the current jackpot pot amount."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT current_pot FROM jackpot WHERE id = 1")
        row = await cursor.fetchone()
        return row[0] if row else 50.0


async def award_jackpot(user_id: int) -> float:
    """Award the jackpot to a user. Returns the amount won."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT current_pot FROM jackpot WHERE id = 1")
        row = await cursor.fetchone()
        pot = row[0] if row else 50.0

        now = datetime.utcnow().isoformat()
        await db.execute(
            """UPDATE jackpot SET current_pot = 50.0, last_winner_id = ?, last_won_at = ?,
               total_wins = total_wins + 1 WHERE id = 1""",
            (user_id, now),
        )
        await db.commit()

    # Add coins to winner
    await add_coins(user_id, int(pot))
    return pot


async def get_reply_chain_depth(message_id: int, channel_id: int) -> int:
    """Estimate reply chain depth by counting replies in a thread.
    Returns 0 if the message is not a reply to another message in our DB."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Count how many messages in this channel are replies (rough approximation)
        # A more accurate approach would track parent_message_id in the messages table
        # For now, return a reasonable estimate based on recent reply activity
        cursor = await db.execute(
            """SELECT COUNT(*) FROM messages
               WHERE channel_id = ? AND is_reply = 1
               AND timestamp >= datetime('now', '-1 hour')""",
            (channel_id,),
        )
        row = await cursor.fetchone()
        count = row[0] if row else 0
        # Estimate depth as capped reply count in the last hour
        return min(count, 5)


async def is_first_reply_to_message(parent_message_id: int) -> bool:
    """Check if this is the first reply to a given message.
    Returns True if no other scored message has this parent_message_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM messages WHERE parent_message_id = ?",
            (parent_message_id,),
        )
        row = await cursor.fetchone()
        return (row[0] if row else 0) == 0


async def get_all_users() -> list[dict]:
    """Get all users."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users ORDER BY total_score DESC")
        return [dict(row) for row in await cursor.fetchall()]


# ─── UGC Content Pipeline ────────────────────────────────────────────────

async def get_approved_ugc_prompt() -> dict | None:
    """Get a random approved UGC prompt, preferring least-used ones."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM content_submissions
               WHERE content_type = 'prompt' AND status = 'approved'
               ORDER BY times_used ASC, RANDOM()
               LIMIT 1"""
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def mark_ugc_prompt_used(sub_id: int):
    """Increment times_used for a UGC submission."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE content_submissions SET times_used = times_used + 1 WHERE id = ?",
            (sub_id,),
        )
        await db.commit()


# ─── Weekly Recap Helpers ────────────────────────────────────────────────

async def get_weekly_voice_minutes() -> float:
    """Get total voice minutes earned in the last 7 days."""
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(SUM(minutes_earned), 0) FROM voice_sessions WHERE joined_at > ?",
            (cutoff,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0.0


async def get_weekly_best_friend_pair() -> tuple | None:
    """Get the pair with the highest friendship score growth this week."""
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT user_a, user_b, friendship_score
               FROM social_graph
               WHERE last_interaction > ? AND friendship_score > 0
               ORDER BY friendship_score DESC
               LIMIT 1"""
        )
        row = await cursor.fetchone()
        if row:
            return (row["user_a"], row["user_b"], row["friendship_score"])
        return None


async def get_weekly_achievements_count() -> int:
    """Count badges unlocked in the last 7 days."""
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM achievements WHERE unlocked_at > ?",
            (cutoff,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_weekly_faction_standings() -> list[dict]:
    """Get faction scores for the current week."""
    week_key = datetime.utcnow().strftime("%Y-W%W")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT team_name, total_score FROM faction_scores WHERE week = ? ORDER BY total_score DESC",
            (week_key,),
        )
        return [dict(row) for row in await cursor.fetchall()]


# ─── Social Graph Operations ─────────────────────────────────────────────

async def update_social_interaction(user_a: int, user_b: int, interaction_type: str):
    """Update the social graph when two users interact."""
    # Ensure consistent ordering (lower ID first)
    a, b = min(user_a, user_b), max(user_a, user_b)
    now = datetime.utcnow().isoformat()

    col_map = {
        "reply": "reply_count",
        "mention": "mention_count",
        "reaction": "reaction_count",
    }
    col = col_map.get(interaction_type, "interaction_count")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"""INSERT INTO social_graph (user_a, user_b, {col}, interaction_count, last_interaction)
                VALUES (?, ?, 1, 1, ?)
                ON CONFLICT(user_a, user_b) DO UPDATE SET
                    {col} = {col} + 1,
                    interaction_count = interaction_count + 1,
                    last_interaction = ?,
                    friendship_score = (reply_count * 3) + (mention_count * 2) + (reaction_count * 1) + (voice_overlap_minutes * 0.5)""",
            (a, b, now, now),
        )
        await db.commit()


async def update_voice_co_presence(user_a: int, user_b: int, minutes: float):
    """Update voice co-presence minutes in the social graph."""
    a, b = min(user_a, user_b), max(user_a, user_b)
    now = datetime.utcnow().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO social_graph (user_a, user_b, voice_overlap_minutes, interaction_count, last_interaction)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(user_a, user_b) DO UPDATE SET
                    voice_overlap_minutes = voice_overlap_minutes + ?,
                    interaction_count = interaction_count + 1,
                    last_interaction = ?,
                    friendship_score = (reply_count * 3) + (mention_count * 2) + (reaction_count * 1) + (voice_overlap_minutes * 0.5)""",
            (a, b, minutes, now, minutes, now),
        )
        await db.commit()


async def get_top_friends(user_id: int, limit: int = 5) -> list[dict]:
    """Get a user's top friends by friendship score."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM social_graph
               WHERE (user_a = ? OR user_b = ?) AND friendship_score > 0
               ORDER BY friendship_score DESC LIMIT ?""",
            (user_id, user_id, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]


# ─── Onboarding State ────────────────────────────────────────────────────

async def get_onboarding_state(user_id: int) -> Optional[dict]:
    """Get a user's onboarding state."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM onboarding_state WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_onboarding_state(user_id: int):
    """Create onboarding state for a new user."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO onboarding_state (user_id, joined_at, stage)
               VALUES (?, ?, 'joined')""",
            (user_id, now),
        )
        await db.commit()


async def update_onboarding_stage(user_id: int, stage: str, **kwargs):
    """Update onboarding stage and optional fields."""
    async with aiosqlite.connect(DB_PATH) as db:
        sets = ["stage = ?"]
        vals = [stage]
        for key, val in kwargs.items():
            sets.append(f"{key} = ?")
            vals.append(val)
        vals.append(user_id)
        await db.execute(
            f"UPDATE onboarding_state SET {', '.join(sets)} WHERE user_id = ?",
            vals,
        )
        await db.commit()


# ─── Active Boosts ────────────────────────────────────────────────────────

async def get_active_boost(user_id: int) -> float | None:
    """Return the highest active XP boost multiplier for a user, or None."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT multiplier FROM active_boosts
               WHERE user_id = ? AND boost_type IN ('xp', 'xp_2x')
               AND expires_at > ?
               ORDER BY multiplier DESC LIMIT 1""",
            (user_id, now),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def cleanup_expired_boosts():
    """Delete all expired boost rows."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM active_boosts WHERE expires_at <= ?", (now,)
        )
        await db.commit()
