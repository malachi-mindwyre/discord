"""
The Circle -- Bot Logger / Observability Cog
Comprehensive error logging, health summaries, and error-rate alerting.
Posts all errors, warnings, and info to #keeper-logs so issues are visible
without SSH-ing into the Pi.

Must be loaded FIRST in COG_EXTENSIONS so it catches errors from all cogs.
"""

from __future__ import annotations

import asyncio
import logging
import os
import traceback
import time
from collections import deque, Counter
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_ERROR,
    EMBED_COLOR_WARNING,
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_SUCCESS,
    GUILD_ID,
    LOGGER_CHANNEL,
    ERROR_SPIKE_THRESHOLD,
    ERROR_SPIKE_WINDOW,
    DAILY_SUMMARY_HOUR,
    LOG_BUFFER_FLUSH_INTERVAL,
    LOG_MAX_BUFFER_SIZE,
    LOG_HISTORY_MAX,
)
from database import DB_PATH

logger = logging.getLogger(__name__)


# ── Log levels ────────────────────────────────────────────────────────────

class LogLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


LEVEL_COLORS = {
    LogLevel.INFO: EMBED_COLOR_PRIMARY,      # Blue
    LogLevel.WARNING: EMBED_COLOR_WARNING,    # Yellow
    LogLevel.ERROR: EMBED_COLOR_ERROR,        # Red
}

LEVEL_EMOJI = {
    LogLevel.INFO: "\U0001f535",     # blue circle
    LogLevel.WARNING: "\U0001f7e1",  # yellow circle
    LogLevel.ERROR: "\U0001f534",    # red circle
}


# ── Log entry ─────────────────────────────────────────────────────────────

class LogEntry:
    __slots__ = ("level", "category", "title", "details", "timestamp")

    def __init__(self, level: LogLevel, category: str, title: str, details: str = ""):
        self.level = level
        self.category = category
        self.title = title
        self.details = details
        self.timestamp = datetime.now(timezone.utc)


# ── The cog ───────────────────────────────────────────────────────────────

class BotLogger(commands.Cog):
    """Observability cog -- catches all errors and posts to #keeper-logs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # In-memory buffer flushed periodically to Discord
        self._buffer: list[LogEntry] = []
        self._buffer_lock = asyncio.Lock()

        # Rolling error history for !logs / !errors
        self._error_history: deque[LogEntry] = deque(maxlen=LOG_HISTORY_MAX)

        # Error rate tracking for spike detection
        self._error_timestamps: deque[float] = deque()

        # Stats counters (reset daily)
        self._stats: Counter = Counter()  # category -> count
        self._stats_reset: datetime = datetime.now(timezone.utc)

        # Startup time
        self._start_time: Optional[datetime] = None

        # Cached channel reference
        self._log_channel: Optional[discord.TextChannel] = None

        # Track cog load results (populated by bot.py)
        self.cog_load_results: list[tuple[str, bool, str]] = []

    # ── Lifecycle ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self):
        self._start_time = datetime.now(timezone.utc)
        self._log_channel = None  # refresh on reconnect

        if not self._flush_loop.is_running():
            self._flush_loop.start()
        if not self._daily_summary.is_running():
            self._daily_summary.start()
        if not self._spike_check.is_running():
            self._spike_check.start()

        # Post cog load summary if we have results
        if self.cog_load_results:
            await self._post_cog_load_summary()

    def cog_unload(self):
        self._flush_loop.cancel()
        self._daily_summary.cancel()
        self._spike_check.cancel()

    # ── Channel resolution ────────────────────────────────────────────────

    async def _get_channel(self) -> Optional[discord.TextChannel]:
        if self._log_channel and self._log_channel.guild:
            return self._log_channel
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return None
        self._log_channel = discord.utils.get(guild.text_channels, name=LOGGER_CHANNEL)
        return self._log_channel

    # ── Public logging API ────────────────────────────────────────────────

    async def log(self, level: LogLevel, category: str, title: str, details: str = ""):
        """Queue a log entry for posting to #keeper-logs."""
        entry = LogEntry(level, category, title, details)

        if level == LogLevel.ERROR:
            self._error_history.append(entry)
            self._error_timestamps.append(time.monotonic())
            self._stats[category] += 1

        async with self._buffer_lock:
            self._buffer.append(entry)
            if len(self._buffer) >= LOG_MAX_BUFFER_SIZE:
                await self._flush()

    async def log_error(self, category: str, title: str, details: str = ""):
        await self.log(LogLevel.ERROR, category, title, details)

    async def log_warning(self, category: str, title: str, details: str = ""):
        await self.log(LogLevel.WARNING, category, title, details)

    async def log_info(self, category: str, title: str, details: str = ""):
        await self.log(LogLevel.INFO, category, title, details)

    # ── Buffer flush ──────────────────────────────────────────────────────

    @tasks.loop(seconds=LOG_BUFFER_FLUSH_INTERVAL)
    async def _flush_loop(self):
        await self.bot.wait_until_ready()
        async with self._buffer_lock:
            if self._buffer:
                await self._flush()

    async def _flush(self):
        """Send buffered entries to #keeper-logs. Called under lock."""
        if not self._buffer:
            return

        channel = await self._get_channel()
        if not channel:
            # Fallback: print to stdout so journalctl still has them
            for entry in self._buffer:
                print(f"[BotLogger] {entry.level.value} [{entry.category}] {entry.title}")
                if entry.details:
                    print(f"  {entry.details[:500]}")
            self._buffer.clear()
            return

        # Group entries into embeds (max ~4000 chars per embed, Discord limit)
        # If many entries, batch into multiple embeds
        entries = list(self._buffer)
        self._buffer.clear()

        # If a single entry, send a clean individual embed
        if len(entries) == 1:
            entry = entries[0]
            embed = self._entry_to_embed(entry)
            try:
                await channel.send(embed=embed)
            except Exception:
                print(f"[BotLogger] Failed to post to #{LOGGER_CHANNEL}: {traceback.format_exc()}")
            return

        # Multiple entries: batch into a single embed
        embed = discord.Embed(
            title=f"Log Batch ({len(entries)} entries)",
            color=LEVEL_COLORS.get(
                max(entries, key=lambda e: list(LogLevel).index(e.level)).level,
                EMBED_COLOR_PRIMARY,
            ),
            timestamp=datetime.now(timezone.utc),
        )

        description_parts = []
        for entry in entries:
            emoji = LEVEL_EMOJI[entry.level]
            ts = int(entry.timestamp.timestamp())
            line = f"{emoji} **[{entry.category}]** {entry.title}"
            if entry.details:
                short = entry.details[:200].replace("```", "")
                line += f"\n```\n{short}\n```"
            description_parts.append(line)

        # Discord embed description limit is 4096
        full_desc = "\n".join(description_parts)
        if len(full_desc) > 4000:
            full_desc = full_desc[:3997] + "..."
        embed.description = full_desc

        try:
            await channel.send(embed=embed)
        except Exception:
            print(f"[BotLogger] Failed to post batch to #{LOGGER_CHANNEL}: {traceback.format_exc()}")

    def _entry_to_embed(self, entry: LogEntry) -> discord.Embed:
        embed = discord.Embed(
            title=f"{LEVEL_EMOJI[entry.level]} {entry.title}",
            color=LEVEL_COLORS[entry.level],
            timestamp=entry.timestamp,
        )
        embed.set_footer(text=f"{entry.level.value} | {entry.category}")

        if entry.details:
            # Truncate to embed field limit
            details = entry.details[:4000]
            if len(details) > 1024:
                # Use description for long details
                embed.description = f"```\n{details[:3900]}\n```"
            else:
                embed.add_field(name="Details", value=f"```\n{details}\n```", inline=False)
        return embed

    # ── Global command error handler ──────────────────────────────────────

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Catch ALL command exceptions."""
        # Unwrap CommandInvokeError to get the real exception
        original = getattr(error, "original", error)

        # ── User-facing errors: send clean message to user ────────────
        if isinstance(error, commands.CommandNotFound):
            return  # Silently ignore unknown commands

        if isinstance(error, commands.MissingRequiredArgument):
            try:
                await ctx.send(f"Missing argument: `{error.param.name}`. Check `!help` for usage.")
            except discord.HTTPException:
                pass
            return

        if isinstance(error, commands.BadArgument):
            try:
                await ctx.send(f"Invalid argument. Check `!help` for usage.")
            except discord.HTTPException:
                pass
            return

        if isinstance(error, (commands.NotOwner, commands.MissingPermissions)):
            try:
                await ctx.send("You don't have permission to use this command.")
            except discord.HTTPException:
                pass
            return

        if isinstance(error, commands.CommandOnCooldown):
            try:
                await ctx.send(f"Cooldown -- try again in {error.retry_after:.0f}s.")
            except discord.HTTPException:
                pass
            return

        if isinstance(error, commands.CheckFailure):
            return  # Generic check failure, silently ignore

        # ── Internal errors: notify user + full details to #keeper-logs ──
        try:
            await ctx.send("Something went wrong. The error has been logged.")
        except discord.HTTPException:
            pass

        # Build traceback
        tb = "".join(traceback.format_exception(type(original), original, original.__traceback__))

        details = (
            f"Command: !{ctx.command}\n"
            f"User: {ctx.author} ({ctx.author.id})\n"
            f"Channel: #{ctx.channel}\n"
            f"Message: {ctx.message.content[:200]}\n"
            f"{'─' * 40}\n"
            f"{tb[-1500:]}"
        )

        await self.log_error("command", f"!{ctx.command} failed", details)

    # ── Event listener error handler ──────────────────────────────────────

    @commands.Cog.listener()
    async def on_error(self, event: str, *args, **kwargs):
        """Catch exceptions in event listeners (on_message, on_member_join, etc.)."""
        tb = traceback.format_exc()

        # Try to extract useful context from args
        context_parts = []
        for arg in args:
            if isinstance(arg, discord.Message):
                context_parts.append(f"Message by {arg.author} in #{arg.channel}: {arg.content[:100]}")
            elif isinstance(arg, discord.Member):
                context_parts.append(f"Member: {arg} ({arg.id})")
            elif isinstance(arg, discord.RawReactionActionEvent):
                context_parts.append(f"Reaction event: message_id={arg.message_id}")
        context = "\n".join(context_parts) if context_parts else "No context available"

        details = f"Event: {event}\nContext: {context}\n{'─' * 40}\n{tb[-1500:]}"
        await self.log_error("event", f"Event '{event}' error", details)

    # ── Background task crash monitor ─────────────────────────────────────

    async def check_tasks(self):
        """Check all background tasks for crashes. Called periodically."""
        task_map = {
            "LossAversion": ["daily_decay_and_demotion", "streak_at_risk_check"],
            "ContentEngine": ["quick_fire_scheduler", "dead_zone_detector", "trending_scanner"],
            "Reengagement": ["reengagement_loop"],
            "VariableRewards": ["_surprise_2x_loop"],
            "SocialGraph": ["friendship_decay", "icebreaker_matchmaking", "best_friend_detection"],
            "SeasonPass": ["check_season_loop", "check_challenges_loop"],
            "EngagementLadder": ["weekly_recalculate"],
            "MegaEvents": ["event_loop"],
            "TimeCapsules": ["reveal_loop"],
            "HealthCheck": ["periodic_check"],
            "KeeperPersonality": ["ambient_message_loop"],
            "DailyPrompts": ["post_daily_prompt"],
            "Leaderboard": ["update_leaderboard"],
            "Oracle": ["evening_prediction"],
            "Metrics": ["daily_snapshot"],
        }

        for cog_name, task_names in task_map.items():
            cog = self.bot.get_cog(cog_name)
            if not cog:
                continue
            for task_name in task_names:
                task_obj = getattr(cog, task_name, None)
                if not task_obj or not hasattr(task_obj, "is_running"):
                    continue
                if task_obj.is_running():
                    continue
                # Task is NOT running -- check why
                internal_task = task_obj.get_task()
                if internal_task and internal_task.done():
                    exc = internal_task.exception()
                    if exc:
                        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                        await self.log_error(
                            "task",
                            f"Task {cog_name}.{task_name} CRASHED",
                            f"Cog: {cog_name}\nTask: {task_name}\n{'─' * 40}\n{tb[-1500:]}",
                        )
                        # Try to restart
                        try:
                            task_obj.restart()
                            await self.log_info(
                                "task",
                                f"Task {cog_name}.{task_name} restarted",
                            )
                        except Exception as restart_err:
                            await self.log_error(
                                "task",
                                f"Failed to restart {cog_name}.{task_name}",
                                str(restart_err),
                            )
                    else:
                        await self.log_warning(
                            "task",
                            f"Task {cog_name}.{task_name} stopped (no exception)",
                        )

    # ── Cog load summary ──────────────────────────────────────────────────

    async def _post_cog_load_summary(self):
        """Post startup summary of cog loading."""
        results = self.cog_load_results
        total = len(results)
        loaded = sum(1 for _, ok, _ in results if ok)
        failed = [(name, err) for name, ok, err in results if not ok]

        if not failed:
            await self.log_info(
                "startup",
                f"All {total} cogs loaded successfully",
            )
            return

        details_parts = []
        for name, err in failed:
            details_parts.append(f"FAILED: {name}\n  {err}")

        await self.log_error(
            "startup",
            f"{loaded}/{total} cogs loaded. {len(failed)} FAILED.",
            "\n".join(details_parts)[:1500],
        )

    # ── Error spike detection ─────────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _spike_check(self):
        await self.bot.wait_until_ready()

        now = time.monotonic()
        cutoff = now - ERROR_SPIKE_WINDOW

        # Prune old timestamps
        while self._error_timestamps and self._error_timestamps[0] < cutoff:
            self._error_timestamps.popleft()

        count = len(self._error_timestamps)
        if count >= ERROR_SPIKE_THRESHOLD:
            # Find most common error category
            recent = [e for e in self._error_history if e.timestamp > datetime.now(timezone.utc) - timedelta(seconds=ERROR_SPIKE_WINDOW)]
            cats = Counter(e.category for e in recent)
            top_cat = cats.most_common(1)[0] if cats else ("unknown", 0)

            channel = await self._get_channel()
            if channel:
                embed = discord.Embed(
                    title="\U0001f6a8 ERROR SPIKE DETECTED",
                    description=(
                        f"**{count} errors** in the last {ERROR_SPIKE_WINDOW // 60} minutes!\n\n"
                        f"Most common: **{top_cat[0]}** ({top_cat[1]} occurrences)"
                    ),
                    color=0xFF0000,
                    timestamp=datetime.now(timezone.utc),
                )
                try:
                    await channel.send(embed=embed)
                except Exception:
                    print(f"[BotLogger] Failed to post spike alert")

            # Clear timestamps so we don't re-alert immediately
            self._error_timestamps.clear()

    # ── Background task health check (every 5 min) ────────────────────────

    @tasks.loop(minutes=5)
    async def _flush_loop_task_check(self):
        """Piggyback on flush loop to also check tasks periodically."""
        pass  # check_tasks is called from daily summary and spike check

    # ── Daily health summary ──────────────────────────────────────────────

    @tasks.loop(hours=1)
    async def _daily_summary(self):
        await self.bot.wait_until_ready()

        now = datetime.now(timezone.utc)
        if now.hour != DAILY_SUMMARY_HOUR:
            return

        # Also check background tasks
        await self.check_tasks()

        channel = await self._get_channel()
        if not channel:
            return

        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return

        # ── Uptime ──
        uptime_str = "Unknown"
        if self._start_time:
            delta = now - self._start_time
            days = delta.days
            hours = delta.seconds // 3600
            mins = (delta.seconds % 3600) // 60
            uptime_str = f"{days}d {hours}h {mins}m"

        # ── Error stats ──
        total_errors = sum(self._stats.values())
        error_breakdown = ""
        if self._stats:
            top5 = self._stats.most_common(5)
            error_breakdown = "\n".join(f"  {cat}: {cnt}" for cat, cnt in top5)
        else:
            error_breakdown = "  None!"

        # ── Cog status ──
        cog_count = len(self.bot.cogs)

        # ── Task status ──
        task_map = {
            "LossAversion": ["daily_decay_and_demotion", "streak_at_risk_check"],
            "ContentEngine": ["quick_fire_scheduler", "dead_zone_detector", "trending_scanner"],
            "Reengagement": ["reengagement_loop"],
            "VariableRewards": ["_surprise_2x_loop"],
            "SocialGraph": ["friendship_decay", "icebreaker_matchmaking", "best_friend_detection"],
            "SeasonPass": ["check_season_loop", "check_challenges_loop"],
            "EngagementLadder": ["weekly_recalculate"],
            "MegaEvents": ["event_loop"],
            "TimeCapsules": ["reveal_loop"],
            "HealthCheck": ["periodic_check"],
        }
        running_tasks = 0
        stopped_tasks = 0
        stopped_names = []
        for cog_name, task_names in task_map.items():
            cog_obj = self.bot.get_cog(cog_name)
            if not cog_obj:
                continue
            for tn in task_names:
                t = getattr(cog_obj, tn, None)
                if t and hasattr(t, "is_running"):
                    if t.is_running():
                        running_tasks += 1
                    else:
                        stopped_tasks += 1
                        stopped_names.append(f"{cog_name}.{tn}")

        task_status = f"{running_tasks} running"
        if stopped_tasks:
            task_status += f", **{stopped_tasks} STOPPED**: {', '.join(stopped_names[:5])}"

        # ── DB health ──
        db_info = "N/A"
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                row = await db.execute_fetchall("SELECT COUNT(*) FROM users")
                user_count = row[0][0] if row else 0

                row2 = await db.execute_fetchall(
                    "SELECT COUNT(*) FROM messages WHERE date = ?",
                    (now.strftime("%Y-%m-%d"),),
                )
                msgs_today = row2[0][0] if row2 else 0

                row3 = await db.execute_fetchall(
                    "SELECT COUNT(*) FROM users WHERE score < 0",
                )
                negative = row3[0][0] if row3 else 0

                db_info = f"{user_count} users, {msgs_today} msgs today"
                if negative > 0:
                    db_info += f", **{negative} negative scores**"
        except Exception as e:
            db_info = f"Error: {e}"

        # ── Memory usage ──
        mem_info = "N/A"
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            mem_mb = usage.ru_maxrss / (1024 * 1024)  # macOS returns bytes
            # On Linux, ru_maxrss is in KB
            if mem_mb < 1:
                mem_mb = usage.ru_maxrss / 1024
            mem_info = f"{mem_mb:.1f} MB peak RSS"
        except Exception:
            pass

        # ── Build embed ──
        embed = discord.Embed(
            title="\U0001f4ca DAILY HEALTH SUMMARY",
            color=EMBED_COLOR_SUCCESS if total_errors == 0 else EMBED_COLOR_WARNING,
            timestamp=now,
        )
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="Cogs Loaded", value=str(cog_count), inline=True)
        embed.add_field(name="Memory", value=mem_info, inline=True)
        embed.add_field(name="Background Tasks", value=task_status, inline=False)
        embed.add_field(
            name=f"Errors (last 24h): {total_errors}",
            value=f"```\n{error_breakdown}\n```",
            inline=False,
        )
        embed.add_field(name="Database", value=db_info, inline=False)

        try:
            await channel.send(embed=embed)
        except Exception:
            print(f"[BotLogger] Failed to post daily summary: {traceback.format_exc()}")

        # Reset daily stats
        self._stats.clear()
        self._stats_reset = now

    # ── Admin commands ────────────────────────────────────────────────────

    @commands.command(name="logs")
    @commands.is_owner()
    async def logs_cmd(self, ctx: commands.Context, count: int = 10):
        """Show the last N error entries. Owner only."""
        count = min(count, 50)
        entries = list(self._error_history)[-count:]

        if not entries:
            await ctx.send("No errors recorded since last restart.")
            return

        embed = discord.Embed(
            title=f"Last {len(entries)} Errors",
            color=EMBED_COLOR_ERROR,
            timestamp=datetime.now(timezone.utc),
        )

        desc_parts = []
        for e in entries:
            ts = int(e.timestamp.timestamp())
            line = f"<t:{ts}:T> **[{e.category}]** {e.title[:80]}"
            desc_parts.append(line)

        embed.description = "\n".join(desc_parts)[:4000]
        await ctx.send(embed=embed)

    @commands.command(name="errors")
    @commands.is_owner()
    async def errors_cmd(self, ctx: commands.Context):
        """Show error frequency by category in the last 24h. Owner only."""
        if not self._stats:
            await ctx.send("No errors in the current tracking period.")
            return

        embed = discord.Embed(
            title="Error Frequency (Current Period)",
            color=EMBED_COLOR_ERROR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Since {self._stats_reset.strftime('%Y-%m-%d %H:%M UTC')}")

        lines = []
        total = 0
        for cat, cnt in self._stats.most_common(20):
            lines.append(f"`{cat:20s}` {cnt}")
            total += cnt

        lines.insert(0, f"**Total: {total}**\n")
        embed.description = "\n".join(lines)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(BotLogger(bot))
