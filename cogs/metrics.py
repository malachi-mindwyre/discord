"""
The Circle — Metrics Cog
Retention analytics: DAU/MAU, D1/D7/D30 cohort retention, churn rate,
onboarding funnel tracking.
Runs daily at midnight UTC, stores snapshots in metrics_daily table.
"""

from __future__ import annotations

import logging
from datetime import datetime, date, timedelta, timezone

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    METRICS_ALERT_D7_THRESHOLD,
    METRICS_ALERT_DAU_MAU_THRESHOLD,
)
from database import DB_PATH

logger = logging.getLogger("circle.metrics")


# ─── Database Helpers ────────────────────────────────────────────────────────

async def _ensure_table():
    """Create metrics_daily table if it doesn't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS metrics_daily (
                date TEXT PRIMARY KEY,
                dau INTEGER DEFAULT 0,
                wau INTEGER DEFAULT 0,
                mau INTEGER DEFAULT 0,
                dau_mau_ratio REAL DEFAULT 0.0,
                messages_total INTEGER DEFAULT 0,
                new_users INTEGER DEFAULT 0,
                d1_retention REAL DEFAULT 0.0,
                d7_retention REAL DEFAULT 0.0,
                d30_retention REAL DEFAULT 0.0,
                churn_rate REAL DEFAULT 0.0,
                onboarding_total INTEGER DEFAULT 0,
                onboarding_messaged INTEGER DEFAULT 0,
                onboarding_graduated INTEGER DEFAULT 0
            )
        """)
        await db.commit()


async def _count_active_users(days: int) -> int:
    """Count distinct users who sent a message in the last N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM messages WHERE timestamp > ?",
            (cutoff,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def _count_messages_today() -> int:
    """Count total messages sent today."""
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM messages WHERE date(timestamp) = ?",
            (today,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def _count_new_users_today() -> int:
    """Count users who joined today."""
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE date(joined_at) = ?",
            (today,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def _compute_retention(days_ago: int) -> float:
    """Compute retention for the cohort that joined exactly N days ago.

    Returns the fraction (0.0-1.0) of users who joined N days ago
    AND sent at least 1 message today (or yesterday, for day-boundary tolerance).
    """
    target_date = (date.today() - timedelta(days=days_ago)).isoformat()
    check_start = (date.today() - timedelta(days=1)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        # Count users who joined on target_date
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE date(joined_at) = ?",
            (target_date,),
        )
        cohort_size = (await cursor.fetchone())[0]
        if cohort_size == 0:
            return 0.0

        # Count how many of those sent a message recently (last 2 days)
        cursor = await db.execute(
            """SELECT COUNT(DISTINCT u.user_id)
               FROM users u
               JOIN messages m ON u.user_id = m.user_id
               WHERE date(u.joined_at) = ?
               AND date(m.timestamp) >= ?""",
            (target_date, check_start),
        )
        retained = (await cursor.fetchone())[0]
        return retained / cohort_size


async def _compute_churn_rate() -> float:
    """Churn: users active last week but NOT active this week, as fraction of last week's active."""
    now = datetime.now(timezone.utc)
    this_week_start = (now - timedelta(days=7)).isoformat()
    last_week_start = (now - timedelta(days=14)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        # Active last week
        cursor = await db.execute(
            """SELECT COUNT(DISTINCT user_id) FROM messages
               WHERE timestamp > ? AND timestamp <= ?""",
            (last_week_start, this_week_start),
        )
        last_week_active = (await cursor.fetchone())[0]
        if last_week_active == 0:
            return 0.0

        # Of those, how many are NOT active this week
        cursor = await db.execute(
            """SELECT COUNT(DISTINCT m1.user_id)
               FROM messages m1
               WHERE m1.timestamp > ? AND m1.timestamp <= ?
               AND m1.user_id NOT IN (
                   SELECT DISTINCT user_id FROM messages WHERE timestamp > ?
               )""",
            (last_week_start, this_week_start, this_week_start),
        )
        churned = (await cursor.fetchone())[0]
        return churned / last_week_active


async def _compute_onboarding_funnel() -> dict:
    """Compute onboarding funnel metrics from the onboarding_state table."""
    result = {"total": 0, "welcomed": 0, "messaged": 0, "quest_done": 0, "graduated": 0}
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM onboarding_state")
            result["total"] = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM onboarding_state WHERE stage != 'joined'"
            )
            result["welcomed"] = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM onboarding_state WHERE first_message_at IS NOT NULL"
            )
            result["messaged"] = (await cursor.fetchone())[0]

            cursor = await db.execute(
                """SELECT COUNT(*) FROM onboarding_state
                   WHERE (intro_posted + CASE WHEN first_reply_at IS NOT NULL THEN 1 ELSE 0 END + daily_claimed) >= 2"""
            )
            result["quest_done"] = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM onboarding_state WHERE stage = 'graduated'"
            )
            result["graduated"] = (await cursor.fetchone())[0]
        except aiosqlite.OperationalError:
            # Table might not exist yet
            pass
    return result


# ─── The Cog ────────────────────────────────────────────────────────────────

class Metrics(commands.Cog):
    """Retention analytics dashboard. Runs daily, stores snapshots."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await _ensure_table()
        self.daily_snapshot.start()
        logger.info("✓ Metrics cog loaded — daily snapshot started")

    def cog_unload(self):
        self.daily_snapshot.cancel()

    # ── Background Task ──────────────────────────────────────────────────

    @tasks.loop(hours=24)
    async def daily_snapshot(self):
        """Compute and store daily metrics."""
        try:
            today = date.today().isoformat()

            dau = await _count_active_users(1)
            wau = await _count_active_users(7)
            mau = await _count_active_users(30)
            dau_mau = dau / mau if mau > 0 else 0.0
            messages = await _count_messages_today()
            new_users = await _count_new_users_today()
            d1 = await _compute_retention(1)
            d7 = await _compute_retention(7)
            d30 = await _compute_retention(30)
            churn = await _compute_churn_rate()
            funnel = await _compute_onboarding_funnel()

            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """INSERT INTO metrics_daily
                       (date, dau, wau, mau, dau_mau_ratio, messages_total,
                        new_users, d1_retention, d7_retention, d30_retention, churn_rate,
                        onboarding_total, onboarding_messaged, onboarding_graduated)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(date) DO UPDATE SET
                           dau = excluded.dau, wau = excluded.wau, mau = excluded.mau,
                           dau_mau_ratio = excluded.dau_mau_ratio,
                           messages_total = excluded.messages_total,
                           new_users = excluded.new_users,
                           d1_retention = excluded.d1_retention,
                           d7_retention = excluded.d7_retention,
                           d30_retention = excluded.d30_retention,
                           churn_rate = excluded.churn_rate,
                           onboarding_total = excluded.onboarding_total,
                           onboarding_messaged = excluded.onboarding_messaged,
                           onboarding_graduated = excluded.onboarding_graduated
                    """,
                    (today, dau, wau, mau, dau_mau, messages, new_users,
                     d1, d7, d30, churn,
                     funnel["total"], funnel["messaged"], funnel["graduated"]),
                )
                await db.commit()

            logger.info(
                "Metrics snapshot: DAU=%d WAU=%d MAU=%d DAU/MAU=%.2f D1=%.0f%% D7=%.0f%% D30=%.0f%% Funnel=%d/%d/%d",
                dau, wau, mau, dau_mau, d1 * 100, d7 * 100, d30 * 100,
                funnel["total"], funnel["messaged"], funnel["graduated"],
            )

            # ── Automated alerts when metrics drop below thresholds ──
            alerts = []
            if mau > 0 and d7 < METRICS_ALERT_D7_THRESHOLD:
                alerts.append(f"📉 **D7 Retention** dropped to **{d7*100:.0f}%** (threshold: {METRICS_ALERT_D7_THRESHOLD*100:.0f}%)")
            if mau > 0 and dau_mau < METRICS_ALERT_DAU_MAU_THRESHOLD:
                alerts.append(f"📉 **DAU/MAU** dropped to **{dau_mau:.2f}** (threshold: {METRICS_ALERT_DAU_MAU_THRESHOLD:.2f})")

            if alerts:
                for guild in self.bot.guilds:
                    alert_channel = None
                    for ch in guild.text_channels:
                        if "admin" in ch.name or "mod" in ch.name:
                            alert_channel = ch
                            break
                    if not alert_channel and guild.text_channels:
                        alert_channel = guild.text_channels[0]
                    if alert_channel:
                        embed = discord.Embed(
                            title="⚠️ METRICS ALERT",
                            description="\n".join(alerts),
                            color=0xFF0000,
                        )
                        embed.set_footer(text=f"Snapshot: {today} • Run !metrics for details")
                        try:
                            await alert_channel.send(embed=embed)
                        except discord.HTTPException:
                            pass
                logger.warning("Metrics alerts triggered: %s", "; ".join(alerts))

        except Exception:
            logger.exception("Failed to compute daily metrics")

    @daily_snapshot.before_loop
    async def before_snapshot(self):
        await self.bot.wait_until_ready()

    # ── Admin Command ────────────────────────────────────────────────────

    @commands.command(name="metrics")
    @commands.is_owner()
    async def metrics_cmd(self, ctx: commands.Context):
        """Show retention metrics for the last 7 days."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM metrics_daily ORDER BY date DESC LIMIT 7"
            )
            cols = [d[0] for d in cursor.description]
            rows = [dict(zip(cols, r)) for r in await cursor.fetchall()]

        if not rows:
            # Run a live snapshot if no data exists
            await self.daily_snapshot()
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT * FROM metrics_daily ORDER BY date DESC LIMIT 7"
                )
                cols = [d[0] for d in cursor.description]
                rows = [dict(zip(cols, r)) for r in await cursor.fetchall()]

        if not rows:
            await ctx.send("No metrics data yet. Check back after midnight UTC.")
            return

        latest = rows[0]
        prev = rows[1] if len(rows) > 1 else None

        def trend(current: float, previous: float | None) -> str:
            if previous is None:
                return ""
            if current > previous:
                return " ↑"
            if current < previous:
                return " ↓"
            return " →"

        dau = latest["dau"]
        mau = latest["mau"]
        ratio = latest["dau_mau_ratio"]
        d1 = latest["d1_retention"] * 100
        d7 = latest["d7_retention"] * 100
        d30 = latest["d30_retention"] * 100
        churn = latest["churn_rate"] * 100

        # Build 7-day sparkline for DAU
        dau_history = [r["dau"] for r in reversed(rows)]
        max_dau = max(dau_history) if dau_history else 1
        bars = "".join("▓" if d > max_dau * 0.5 else "░" for d in dau_history)

        # Onboarding funnel (live)
        funnel = await _compute_onboarding_funnel()
        funnel_text = (
            f"📥 {funnel['total']} joined → "
            f"👋 {funnel['welcomed']} welcomed → "
            f"💬 {funnel['messaged']} messaged → "
            f"🎯 {funnel['quest_done']} quests → "
            f"🏅 {funnel['graduated']} graduated"
        )

        embed = discord.Embed(
            title="📊 THE CIRCLE — RETENTION DASHBOARD",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 **{latest['date']}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👥 **DAU:** {dau}{trend(dau, prev['dau'] if prev else None)}\n"
                f"📅 **WAU:** {latest['wau']}\n"
                f"📆 **MAU:** {mau}\n"
                f"📈 **DAU/MAU:** {ratio:.2f}{trend(ratio, prev['dau_mau_ratio'] if prev else None)} "
                f"{'🟢' if ratio >= 0.4 else '🟡' if ratio >= 0.25 else '🔴'}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔄 **RETENTION**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"D1: **{d1:.0f}%**{trend(d1, prev['d1_retention'] * 100 if prev else None)} "
                f"{'🟢' if d1 >= 70 else '🟡' if d1 >= 40 else '🔴'} (target: >70%)\n"
                f"D7: **{d7:.0f}%**{trend(d7, prev['d7_retention'] * 100 if prev else None)} "
                f"{'🟢' if d7 >= 50 else '🟡' if d7 >= 25 else '🔴'} (target: >50%)\n"
                f"D30: **{d30:.0f}%**{trend(d30, prev['d30_retention'] * 100 if prev else None)} "
                f"{'🟢' if d30 >= 30 else '🟡' if d30 >= 15 else '🔴'} (target: >30%)\n\n"
                f"📉 **Churn:** {churn:.0f}%{trend(-churn, -(prev['churn_rate'] * 100) if prev else None)}\n"
                f"🆕 **New users:** {latest['new_users']}\n"
                f"💬 **Messages:** {latest['messages_total']}\n\n"
                f"**7-day DAU:** `{bars}` ({' → '.join(str(d) for d in dau_history)})\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎓 **ONBOARDING FUNNEL**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{funnel_text}"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="The Circle • Keeper sees all")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Metrics(bot))
