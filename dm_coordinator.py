"""
The Circle — DM Coordinator
Prevents DM fatigue by coordinating sends across all cogs.
Rules: max 1 DM per 12 hours from any cog, max 3 DMs per 7 days total.
Users can opt out of all bot DMs via button or !dms off command.
"""

from __future__ import annotations

import aiosqlite
from datetime import datetime, timedelta

DB_PATH = "circle.db"


async def ensure_dm_table():
    """Create the dm_coordinator and dm_optout tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dm_coordinator (
                user_id INTEGER NOT NULL,
                cog_name TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                PRIMARY KEY (user_id, cog_name, sent_at)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dm_optout (
                user_id INTEGER PRIMARY KEY,
                opted_out_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def is_opted_out(user_id: int) -> bool:
    """Check if a user has opted out of bot DMs."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM dm_optout WHERE user_id = ?", (user_id,)
        )
        return await cursor.fetchone() is not None


async def set_dm_optout(user_id: int, opt_out: bool):
    """Set or clear DM opt-out for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        if opt_out:
            await db.execute(
                "INSERT OR REPLACE INTO dm_optout (user_id, opted_out_at) VALUES (?, ?)",
                (user_id, datetime.utcnow().isoformat()),
            )
        else:
            await db.execute("DELETE FROM dm_optout WHERE user_id = ?", (user_id,))
        await db.commit()


async def can_dm(user_id: int, cog_name: str, priority: bool = False) -> bool:
    """Check whether we're allowed to DM this user right now.

    Rules:
        - If user has opted out, always return False
        - Max 1 DM per 12 hours from ANY cog (skipped if priority=True)
        - Max 3 DMs per 7 days from ALL cogs combined (5 if priority=True)

    Priority mode is used by re-engagement to ensure critical anti-churn
    DMs aren't blocked by routine notifications.

    Also cleans up entries older than 30 days.
    """
    # Check opt-out first
    if await is_opted_out(user_id):
        return False

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


# ─── Persistent DM Opt-Out Button View ──────────────────────────────────────

import discord


class DMOptOutView(discord.ui.View):
    """Persistent view with a 'Stop Bot DMs' button attached to bot DMs."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Stop Bot DMs",
        style=discord.ButtonStyle.secondary,
        custom_id="dm_optout_toggle",
        emoji="🔕",
    )
    async def toggle_optout(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if await is_opted_out(user_id):
            await set_dm_optout(user_id, False)
            await interaction.response.send_message(
                "✅ **Bot DMs re-enabled.** You'll receive notifications again.\n"
                "Use `!dms off` or tap this button again to opt out.",
                ephemeral=True,
            )
        else:
            await set_dm_optout(user_id, True)
            await interaction.response.send_message(
                "🔕 **Bot DMs disabled.** You won't receive any more bot DMs.\n"
                "Use `!dms on` or tap this button again to re-enable.",
                ephemeral=True,
            )


def get_dm_optout_view() -> DMOptOutView:
    """Return a DMOptOutView instance to attach to bot DMs."""
    return DMOptOutView()
