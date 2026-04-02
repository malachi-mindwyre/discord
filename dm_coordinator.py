"""
The Circle — DM Coordinator
Prevents DM fatigue by coordinating sends across all cogs.
Rules: max 1 DM per 12 hours from any cog, max 3 DMs per 7 days total.
"""

from __future__ import annotations

import aiosqlite
from datetime import datetime, timedelta

DB_PATH = "circle.db"


async def ensure_dm_table():
    """Create the dm_coordinator table if it doesn't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dm_coordinator (
                user_id INTEGER NOT NULL,
                cog_name TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                PRIMARY KEY (user_id, cog_name, sent_at)
            )
        """)
        await db.commit()


async def can_dm(user_id: int, cog_name: str, priority: bool = False) -> bool:
    """Check whether we're allowed to DM this user right now.

    Rules:
        - Max 1 DM per 12 hours from ANY cog (skipped if priority=True)
        - Max 3 DMs per 7 days from ALL cogs combined (5 if priority=True)

    Priority mode is used by re-engagement to ensure critical anti-churn
    DMs aren't blocked by routine notifications.

    Also cleans up entries older than 30 days.
    """
    now = datetime.utcnow()
    cutoff_30d = (now - timedelta(days=30)).isoformat()
    cutoff_12h = (now - timedelta(hours=12)).isoformat()
    cutoff_7d = (now - timedelta(days=7)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        # Clean up old entries
        await db.execute(
            "DELETE FROM dm_coordinator WHERE sent_at < ?",
            (cutoff_30d,)
        )
        await db.commit()

        # Check: any DM to this user in the last 12 hours? (skipped for priority)
        if not priority:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM dm_coordinator WHERE user_id = ? AND sent_at > ?",
                (user_id, cutoff_12h)
            )
            row = await cursor.fetchone()
            if row[0] >= 1:
                return False

        # Check: DMs in the last 7 days? (3 max normal, 5 max priority)
        max_weekly = 5 if priority else 3
        cursor = await db.execute(
            "SELECT COUNT(*) FROM dm_coordinator WHERE user_id = ? AND sent_at > ?",
            (user_id, cutoff_7d)
        )
        row = await cursor.fetchone()
        if row[0] >= max_weekly:
            return False

    return True


async def record_dm(user_id: int, cog_name: str):
    """Log that a DM was sent to a user from a specific cog."""
    now = datetime.utcnow().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO dm_coordinator (user_id, cog_name, sent_at) VALUES (?, ?, ?)",
            (user_id, cog_name, now)
        )
        await db.commit()
