"""
The Circle — Keeper Bot
Main entry point. Loads all cogs and initializes the database.
"""

import asyncio
import discord
from discord.ext import commands

from config import DISCORD_TOKEN, BOT_PREFIX, GUILD_ID
from database import init_db

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)

COG_EXTENSIONS = [
    # ─── Phase 1 (Core) ──────────────────────────────────
    "cogs.streaks",
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
    "cogs.onboarding",
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
    "cogs.smart_dm",
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
