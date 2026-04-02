"""
The Circle — Keeper Bot
Main entry point. Loads all cogs and initializes the database.
"""

import asyncio
import logging
import traceback

import discord
from discord.ext import commands, tasks

from config import DISCORD_TOKEN, BOT_PREFIX, GUILD_ID
from database import init_db

# ─── Logging Setup ─────────────────────────────────────────────────────
# Ensure all discord.py task errors get printed to stdout (visible in journalctl)
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Make task errors loud
logging.getLogger("discord.ext.tasks").setLevel(logging.ERROR)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)

COG_EXTENSIONS = [
    # ─── Phase 1 (Core) ──────────────────────────────────
    # "cogs.streaks",              # Superseded by streaks_v2
    "cogs.achievements",
    "cogs.scoring_handler",
    "cogs.leaderboard",
    "cogs.media_feed",
    "cogs.welcome",
    "cogs.invites",
    "cogs.comeback",
    "cogs.reactions",
    "cogs.voice_xp",
    "cogs.daily_prompts",
    "cogs.weekly_recap",
    "cogs.info",
    "setup_server",
    # ─── Phase 2 (Engagement) ────────────────────────────
    # "cogs.onboarding",             # Superseded by onboarding_v2
    "cogs.introductions",
    "cogs.confessions",
    "cogs.starboard",
    "cogs.invite_reminders",
    "cogs.growth_nudges",
    "cogs.engagement_triggers",
    "cogs.economy",
    "cogs.shop",
    "cogs.auto_events",
    "cogs.trivia",
    "cogs.server_goals",
    "cogs.profiles",
    "cogs.factions",
    # "cogs.smart_dm",             # Superseded by reengagement.py
    "cogs.buddy_system",
    "cogs.daily_rewards",
    # ─── Phase 3 (Ultimate Engagement Engine) ────────────
    "cogs.onboarding_v2",          # 7-day staged onboarding pipeline
    "cogs.streaks_v2",             # Multi-dimensional streaks + freezes + pairs
    "cogs.reengagement",           # Unified 8-tier re-engagement campaign
    "cogs.loss_aversion",          # Graduated decay, demotion, displacement
    "cogs.variable_rewards",       # Jackpot, surprise 2x, mystery drops
    "cogs.daily_wheel",            # Daily spin mechanic (!spin)
    "cogs.social_graph",           # Friendship tracking, rivals, icebreakers
    "cogs.circles",                # Friend group formation + competition
    "cogs.content_engine",         # UGC, Quick Fire, trending, dead zone
    "cogs.debates",                # Structured debates + thermostat
    "cogs.season_pass",            # Seasonal battle pass (8-week seasons)
    "cogs.prestige",               # Prestige system (endgame)
    "cogs.engagement_ladder",      # Lurker-to-evangelist pipeline
    "cogs.healthcheck",            # Self-test + !healthcheck command
    "cogs.oracle",                 # Evening prediction ritual
    "cogs.metrics",                # Retention analytics dashboard
    "cogs.mega_events",            # Monthly mega events (The Purge, Circle Games, etc.)
    "cogs.time_capsules",          # Time capsule system (!timecapsule, !capsules)
    "cogs.keeper_personality",     # Keeper ambient personality messages
]


@bot.event
async def on_ready():
    print(f"⚫ Keeper has awakened. Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"⚫ Watching over {len(bot.guilds)} guild(s)")

    # Set Keeper's status
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="The Circle"
    )
    await bot.change_presence(activity=activity)

    # Wait 15 seconds then check all background tasks
    await asyncio.sleep(15)
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
    }
    for cog_name, task_names in task_map.items():
        cog = bot.get_cog(cog_name)
        if not cog:
            print(f"  ⚠ Task check: cog {cog_name} not found")
            continue
        for task_name in task_names:
            task = getattr(cog, task_name, None)
            if task and hasattr(task, "is_running"):
                if task.is_running():
                    print(f"  ✓ Task {cog_name}.{task_name} running")
                else:
                    # Try to get the exception that killed it
                    exc = task.get_task().exception() if task.get_task() and task.get_task().done() else None
                    if exc:
                        print(f"  ✗ Task {cog_name}.{task_name} CRASHED: {exc}")
                        traceback.print_exception(type(exc), exc, exc.__traceback__)
                    else:
                        print(f"  ✗ Task {cog_name}.{task_name} not running (no exception captured)")
            else:
                print(f"  ⚠ Task {cog_name}.{task_name} attribute not found")


async def main():
    # Initialize database
    await init_db()
    print("⚫ Database initialized.")

    # Load all cogs
    for ext in COG_EXTENSIONS:
        try:
            await bot.load_extension(ext)
            print(f"  ✓ Loaded {ext}")
        except Exception as e:
            print(f"  ✗ Failed to load {ext}: {e}")

    # Start the bot
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
