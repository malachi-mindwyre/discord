"""
The Circle — Health Check Cog
Automated self-testing and system health monitoring.
Runs checks on all systems and reports status via !healthcheck command.
Also runs a background check every 6 hours and logs results.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, date, timedelta
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_SUCCESS,
    EMBED_COLOR_ERROR,
    EMBED_COLOR_WARNING,
    EMBED_COLOR_PRIMARY,
    EXCLUDED_CHANNELS,
    CHANNEL_STRUCTURE,
    STREAK_BONUS_MULTIPLIER_V2,
    WHEEL_SEGMENTS,
    FACTION_TEAMS,
)
from database import DB_PATH


class HealthCheck(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_report: Optional[dict] = None

    @commands.Cog.listener()
    async def on_ready(self):
        """Start background tasks (guard against double-start on reconnect)."""
        if not self.periodic_check.is_running():
            self.periodic_check.start()

    def cog_unload(self):
        self.periodic_check.cancel()

    @tasks.loop(hours=6)
    async def periodic_check(self):
        """Run health check every 6 hours and log results."""
        await self.bot.wait_until_ready()
        try:
            report = await self._run_all_checks()
            self._last_report = report
            failed = [c for c in report["checks"] if c["status"] == "FAIL"]
            if failed:
                print(f"⚠️ Health check: {len(failed)} issues found")
                for f in failed:
                    print(f"  ✗ {f['name']}: {f['detail']}")
            else:
                print(f"✓ Health check: all {len(report['checks'])} checks passed")
        except Exception as e:
            print(f"✗ Health check failed to run: {e}")

    @commands.command(name="healthcheck", aliases=["hc", "health"])
    @commands.has_permissions(administrator=True)
    async def healthcheck_cmd(self, ctx: commands.Context):
        """Run a comprehensive health check on all bot systems. Admin only."""
        msg = await ctx.send("⚫ **Running health check...**")

        report = await self._run_all_checks()
        self._last_report = report

        # Build embed
        passed = [c for c in report["checks"] if c["status"] == "PASS"]
        warned = [c for c in report["checks"] if c["status"] == "WARN"]
        failed = [c for c in report["checks"] if c["status"] == "FAIL"]

        if failed:
            color = EMBED_COLOR_ERROR
            title = f"🔴 HEALTH CHECK — {len(failed)} ISSUE(S)"
        elif warned:
            color = EMBED_COLOR_WARNING
            title = f"🟡 HEALTH CHECK — {len(warned)} WARNING(S)"
        else:
            color = EMBED_COLOR_SUCCESS
            title = "🟢 HEALTH CHECK — ALL SYSTEMS OPERATIONAL"

        embed = discord.Embed(
            title=title,
            description=f"Ran **{len(report['checks'])}** checks in **{report['duration_ms']:.0f}ms**",
            color=color,
            timestamp=datetime.utcnow(),
        )

        # Failed checks
        if failed:
            fail_text = "\n".join(f"✗ **{c['name']}**: {c['detail']}" for c in failed[:10])
            embed.add_field(name="🔴 Failed", value=fail_text, inline=False)

        # Warnings
        if warned:
            warn_text = "\n".join(f"⚠️ **{c['name']}**: {c['detail']}" for c in warned[:10])
            embed.add_field(name="🟡 Warnings", value=warn_text, inline=False)

        # Passed (summarized)
        if passed:
            # Group by category
            pass_names = ", ".join(c["name"] for c in passed)
            if len(pass_names) > 1000:
                pass_names = pass_names[:997] + "..."
            embed.add_field(name=f"🟢 Passed ({len(passed)})", value=pass_names, inline=False)

        # System stats
        embed.add_field(
            name="📊 System Stats",
            value=(
                f"Cogs loaded: **{len(self.bot.cogs)}**\n"
                f"Commands registered: **{len(list(self.bot.walk_commands()))}**\n"
                f"Guilds: **{len(self.bot.guilds)}**\n"
                f"Latency: **{self.bot.latency*1000:.0f}ms**"
            ),
            inline=False,
        )

        await msg.edit(content=None, embed=embed)

    async def _run_all_checks(self) -> dict:
        """Run all health checks and return a report dict."""
        start = time.monotonic()
        checks = []

        # 1. Database connectivity
        checks.append(await self._check_database())

        # 2. All expected tables exist
        checks.extend(await self._check_tables())

        # 3. All expected cogs are loaded
        checks.extend(self._check_cogs())

        # 4. Channel structure
        checks.extend(await self._check_channels())

        # 5. Background tasks running
        checks.extend(self._check_background_tasks())

        # 6. Scoring engine imports
        checks.append(self._check_scoring_engine())

        # 7. Config integrity
        checks.append(self._check_config())

        # 8. Database data health
        checks.extend(await self._check_data_health())

        # 9. Bot permissions
        checks.extend(await self._check_permissions())

        duration = (time.monotonic() - start) * 1000
        return {"checks": checks, "duration_ms": duration, "timestamp": datetime.utcnow().isoformat()}

    async def _check_database(self) -> dict:
        """Check database connectivity."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM users")
                count = (await cursor.fetchone())[0]
            return {"name": "Database", "status": "PASS", "detail": f"Connected, {count} users"}
        except Exception as e:
            return {"name": "Database", "status": "FAIL", "detail": str(e)}

    async def _check_tables(self) -> list[dict]:
        """Check all expected tables exist."""
        expected_tables = [
            # Phase 1
            "users", "messages", "daily_scores", "rank_history", "invites",
            "streaks", "achievements", "voice_sessions", "reactions_received",
            # Phase 2
            "economy", "shop_purchases", "confessions", "starboard", "factions",
            "faction_scores", "buddies", "profiles", "login_rewards", "smart_dm_log",
            "trivia_scores", "server_milestones", "weekly_goals",
            # Phase 3
            "jackpot", "daily_spins", "demotion_watch", "streak_freezes",
            "onboarding_state", "reengagement_state", "streaks_v2", "paired_streaks",
            "social_graph", "circles", "circle_members", "content_submissions",
            "debate_scores", "trending_topics", "faction_wars", "faction_territories",
            "faction_treasury", "faction_loyalty", "seasons", "season_progress",
            "prestige", "user_engagement_tier", "legacy_events", "mod_reputation",
            "combo_tracker", "channel_diversity", "kudos", "rivals", "active_boosts",
            # Phase 4 (audit fixes)
            "metrics_daily", "connection_quests", "oracle_log",
        ]

        results = []
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing = {row[0] for row in await cursor.fetchall()}

            missing = [t for t in expected_tables if t not in existing]
            if missing:
                results.append({
                    "name": "DB Tables",
                    "status": "FAIL",
                    "detail": f"Missing: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}"
                })
            else:
                results.append({
                    "name": "DB Tables",
                    "status": "PASS",
                    "detail": f"All {len(expected_tables)} tables present"
                })
        except Exception as e:
            results.append({"name": "DB Tables", "status": "FAIL", "detail": str(e)})

        return results

    def _check_cogs(self) -> list[dict]:
        """Check all expected cogs are loaded."""
        # Use actual class names from each cog file
        expected_cogs = [
            # Phase 1
            "Streaks", "AchievementChecker", "ScoringHandler", "Leaderboard",
            "MediaFeed", "Welcome", "InviteTracker", "Comeback", "ReactionScoring",
            "VoiceXP", "DailyPrompts", "WeeklyRecap", "Info", "SetupServer",
            # Phase 2
            "Onboarding", "Introductions", "Confessions", "Starboard",
            "InviteReminders", "GrowthNudges", "EngagementTriggers", "Economy",
            "Shop", "AutoEvents", "Trivia", "ServerGoals", "Profiles",
            "Factions", "BuddySystem", "DailyRewards",
            # Phase 3
            "OnboardingV2", "StreaksV2", "Reengagement", "LossAversion",
            "VariableRewards", "DailyWheel", "SocialGraph", "Circles",
            "ContentEngine", "Debates", "SeasonPass", "Prestige",
            "EngagementLadder", "HealthCheck", "Oracle", "Metrics",
        ]

        loaded_cogs = set(self.bot.cogs.keys())
        results = []

        missing_cogs = [c for c in expected_cogs if c not in loaded_cogs]
        # Some cogs may have slightly different class names — check case-insensitively
        loaded_lower = {c.lower() for c in loaded_cogs}
        truly_missing = [c for c in missing_cogs if c.lower() not in loaded_lower]

        if truly_missing:
            results.append({
                "name": "Cogs",
                "status": "WARN",
                "detail": f"Not found: {', '.join(truly_missing[:5])}"
            })
        else:
            results.append({
                "name": "Cogs",
                "status": "PASS",
                "detail": f"{len(loaded_cogs)} cogs loaded"
            })

        return results

    async def _check_channels(self) -> list[dict]:
        """Check expected channels exist in the guild."""
        results = []
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return [{"name": "Channels", "status": "FAIL", "detail": "No guild found"}]

        expected_channels = set()
        for cat_channels in CHANNEL_STRUCTURE.values():
            expected_channels.update(cat_channels.keys())

        existing = {c.name for c in guild.text_channels}
        missing = expected_channels - existing
        if missing:
            results.append({
                "name": "Channels",
                "status": "WARN",
                "detail": f"Missing: {', '.join(sorted(missing)[:5])}"
            })
        else:
            results.append({
                "name": "Channels",
                "status": "PASS",
                "detail": f"All {len(expected_channels)} channels present"
            })

        # Check for duplicate categories
        from collections import Counter
        cat_names = [c.name for c in guild.categories]
        dupes = {name: count for name, count in Counter(cat_names).items() if count > 1}
        if dupes:
            dupe_str = ", ".join(f"{name} (x{count})" for name, count in dupes.items())
            results.append({
                "name": "Categories",
                "status": "WARN",
                "detail": f"Duplicates: {dupe_str}"
            })
        else:
            results.append({
                "name": "Categories",
                "status": "PASS",
                "detail": f"{len(guild.categories)} categories, no duplicates"
            })

        return results

    def _check_background_tasks(self) -> list[dict]:
        """Check that key background tasks are running."""
        results = []
        task_checks = {
            "LossAversion": ["daily_decay_and_demotion", "streak_at_risk_check"],
            "ContentEngine": ["quick_fire_scheduler", "dead_zone_detector", "trending_scanner"],
            "Reengagement": ["reengagement_loop"],
            # Note: VariableRewards uses create_task instead of tasks.loop for surprise 2x
            # so we check for the scheduler coroutine existence instead
            "VariableRewards": [],  # _surprise_2x_scheduler runs via create_task, not tasks.loop
            "SocialGraph": ["friendship_decay", "icebreaker_matchmaking", "best_friend_detection"],
            "SeasonPass": ["check_season_loop"],
            "EngagementLadder": ["weekly_recalculate"],
        }

        for cog_name, task_names in task_checks.items():
            cog = self.bot.get_cog(cog_name)
            if not cog:
                results.append({
                    "name": f"Tasks/{cog_name}",
                    "status": "WARN",
                    "detail": f"Cog not loaded"
                })
                continue

            for task_name in task_names:
                task = getattr(cog, task_name, None)
                if task and hasattr(task, "is_running"):
                    if task.is_running():
                        results.append({
                            "name": f"Task/{task_name}",
                            "status": "PASS",
                            "detail": "Running"
                        })
                    else:
                        results.append({
                            "name": f"Task/{task_name}",
                            "status": "WARN",
                            "detail": "Not running"
                        })

        return results

    def _check_scoring_engine(self) -> dict:
        """Check scoring engine imports and basic function."""
        try:
            from scoring import calculate_score, MessageContext, extract_quality_signals

            # Test a basic score calculation
            ctx = MessageContext(
                word_count=10,
                has_media=False,
                is_reply=True,
                has_mention=False,
                daily_points_so_far=0,
                message_content="test message with some words",
                unique_word_count=5,
                streak_multiplier=1.0,
                user_rank_tier=1,
                current_hour_utc=12,
            )
            result = calculate_score(ctx)
            if result.points > 0:
                return {"name": "Scoring Engine", "status": "PASS", "detail": f"Test score: {result.points:.1f} pts"}
            else:
                return {"name": "Scoring Engine", "status": "FAIL", "detail": "Calculated 0 points for valid message"}
        except Exception as e:
            return {"name": "Scoring Engine", "status": "FAIL", "detail": str(e)}

    def _check_config(self) -> dict:
        """Check config integrity."""
        try:
            from config import (
                SCORE_BASE_MESSAGE, SCORE_REPLY_MULTIPLIER, TIME_MULTIPLIERS,
                DIMINISHING_RETURNS_TIERS, CATCHUP_TIERS, DAILY_CAP_TIERS,
                WHEEL_SEGMENTS, MYSTERY_BOX_LOOT_TABLE, QUICK_FIRE_PROMPTS,
                FACTION_TEAMS, STREAK_TYPES, PRESTIGE_REWARDS, SEASON_FREE_REWARDS,
            )

            issues = []
            if len(TIME_MULTIPLIERS) != 24:
                issues.append(f"TIME_MULTIPLIERS has {len(TIME_MULTIPLIERS)} entries, expected 24")
            if len(WHEEL_SEGMENTS) < 5:
                issues.append(f"WHEEL_SEGMENTS only has {len(WHEEL_SEGMENTS)} segments")
            if len(QUICK_FIRE_PROMPTS) < 10:
                issues.append(f"QUICK_FIRE_PROMPTS only has {len(QUICK_FIRE_PROMPTS)} prompts")
            if len(FACTION_TEAMS) != 4:
                issues.append(f"FACTION_TEAMS has {len(FACTION_TEAMS)} teams, expected 4")

            if issues:
                return {"name": "Config", "status": "WARN", "detail": "; ".join(issues)}
            return {"name": "Config", "status": "PASS", "detail": "All config constants valid"}
        except Exception as e:
            return {"name": "Config", "status": "FAIL", "detail": str(e)}

    async def _check_data_health(self) -> list[dict]:
        """Check database data for anomalies."""
        results = []
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # Check for negative scores
                cursor = await db.execute("SELECT COUNT(*) FROM users WHERE total_score < 0")
                neg_scores = (await cursor.fetchone())[0]
                if neg_scores > 0:
                    results.append({"name": "Negative Scores", "status": "WARN", "detail": f"{neg_scores} users with negative scores"})

                # Check jackpot pot
                cursor = await db.execute("SELECT current_pot FROM jackpot WHERE id = 1")
                row = await cursor.fetchone()
                if row:
                    results.append({"name": "Jackpot", "status": "PASS", "detail": f"Pot: {row[0]:.0f} Circles"})
                else:
                    results.append({"name": "Jackpot", "status": "PASS", "detail": "Not yet initialized (normal)"})

                # Check active season
                cursor = await db.execute("SELECT season_number, name FROM seasons WHERE is_active = 1")
                row = await cursor.fetchone()
                if row:
                    results.append({"name": "Season", "status": "PASS", "detail": f"Season {row[0]}: {row[1]}"})
                else:
                    results.append({"name": "Season", "status": "WARN", "detail": "No active season"})

                # User count
                cursor = await db.execute("SELECT COUNT(*) FROM users")
                user_count = (await cursor.fetchone())[0]
                results.append({"name": "Users", "status": "PASS", "detail": f"{user_count} registered users"})

                # Messages today
                today = date.today().isoformat()
                cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE timestamp >= ?", (today,))
                msgs_today = (await cursor.fetchone())[0]
                results.append({"name": "Activity", "status": "PASS", "detail": f"{msgs_today} messages today"})

        except Exception as e:
            results.append({"name": "Data Health", "status": "FAIL", "detail": str(e)})

        return results

    async def _check_permissions(self) -> list[dict]:
        """Check bot has required permissions in the guild."""
        results = []
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return [{"name": "Permissions", "status": "FAIL", "detail": "No guild"}]

        me = guild.me
        perms = me.guild_permissions

        required = {
            "manage_roles": perms.manage_roles,
            "manage_channels": perms.manage_channels,
            "send_messages": perms.send_messages,
            "embed_links": perms.embed_links,
            "read_message_history": perms.read_message_history,
            "add_reactions": perms.add_reactions,
            "manage_messages": perms.manage_messages,
        }

        missing = [name for name, has in required.items() if not has]
        if missing:
            results.append({
                "name": "Permissions",
                "status": "FAIL",
                "detail": f"Missing: {', '.join(missing)}"
            })
        else:
            results.append({
                "name": "Permissions",
                "status": "PASS",
                "detail": "All required permissions granted"
            })

        return results


async def setup(bot: commands.Bot):
    await bot.add_cog(HealthCheck(bot))
