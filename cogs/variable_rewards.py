"""
The Circle — Variable Rewards Cog (Dopamine Engine)
Progressive jackpot, surprise 2x XP windows, and server-wide mystery drops.
Drives engagement through unpredictable, high-impact reward moments.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_ACCENT,
    EMBED_COLOR_WARNING,
    JACKPOT_CONTRIBUTION_PER_MESSAGE,
    JACKPOT_TRIGGER_CHANCE,
    JACKPOT_MIN_POT,
    JACKPOT_SEED,
    SURPRISE_2X_MIN_INTERVAL_HOURS,
    SURPRISE_2X_MAX_INTERVAL_HOURS,
    SURPRISE_2X_DURATION_MIN,
    SURPRISE_2X_DURATION_MAX,
    GUILD_ID,
)
from database import get_jackpot_pot, award_jackpot, update_jackpot_pot, add_coins

logger = logging.getLogger("circle.variable_rewards")

# ─── Mystery Drop Config ────────────────────────────────────────────────────
MYSTERY_DROP_INTERVAL = 100          # Every N server-wide scored messages
MYSTERY_DROP_MIN_COINS = 25
MYSTERY_DROP_MAX_COINS = 500
MYSTERY_DROP_STREAK_FREEZE_CHANCE = 0.15  # 15% chance of streak freeze instead of coins


class VariableRewards(commands.Cog):
    """Dopamine engine: jackpot, surprise 2x windows, mystery drops."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # ── Jackpot state ──
        # Pot is persisted in DB; contributions happen via check_jackpot()

        # ── Surprise 2x state ──
        self._double_xp_active: bool = False
        self._double_xp_until: datetime | None = None

        # ── Mystery drop counter ──
        self._global_scored_counter: int = 0

    @commands.Cog.listener()
    async def on_ready(self):
        """Start background tasks (guard against double-start on reconnect)."""
        if not self._surprise_2x_loop.is_running():
            self._surprise_2x_loop.start()

    def cog_unload(self):
        self._surprise_2x_loop.cancel()

    # ─── Properties ──────────────────────────────────────────────────────────

    @property
    def is_double_xp(self) -> bool:
        """Check if a surprise 2x XP window is currently active.
        Other cogs (e.g. scoring_handler) can read this."""
        if not self._double_xp_active:
            return False
        if self._double_xp_until and datetime.utcnow() > self._double_xp_until:
            self._double_xp_active = False
            self._double_xp_until = None
            return False
        return True

    # ─── Helper: find #general ───────────────────────────────────────────────

    def _get_general_channel(self) -> discord.TextChannel | None:
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return None
        return discord.utils.get(guild.text_channels, name="general")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  1. PROGRESSIVE JACKPOT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def check_jackpot(self, user_id: int, channel: discord.TextChannel):
        """Called by scoring_handler on every scored message.
        Contributes to the pot and rolls for a jackpot win."""
        # Contribute to the pot
        await update_jackpot_pot(JACKPOT_CONTRIBUTION_PER_MESSAGE)

        # Roll the dice
        if random.random() >= JACKPOT_TRIGGER_CHANCE:
            return  # No win this time

        # Check minimum pot threshold
        pot = await get_jackpot_pot()
        if pot < JACKPOT_MIN_POT:
            return

        # ── JACKPOT WIN ──
        won_amount = await award_jackpot(user_id)

        logger.info(
            "JACKPOT WON — user=%s amount=%.0f channel=%s",
            user_id, won_amount, channel.name,
        )

        # Build fanfare embed
        member = channel.guild.get_member(user_id)
        display = member.mention if member else f"<@{user_id}>"

        embed = discord.Embed(
            title="🎰  JACKPOT  🎰",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏆 {display} **HIT THE JACKPOT!**\n\n"
                f"💰 **{int(won_amount):,} Circles** 🪙\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"The Circle giveth... to the chosen.\n"
                f"The pot resets to **{JACKPOT_SEED} 🪙** — it grows with every message."
            ),
            color=EMBED_COLOR_WARNING,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="Every message feeds the pot. Will you be next?")

        # Post in #general for server-wide visibility
        general = self._get_general_channel()
        target = general or channel
        try:
            await target.send(embed=embed)
        except discord.HTTPException:
            pass

        # Also announce in the channel where it happened, if different
        if general and channel.id != general.id:
            try:
                await channel.send(
                    f"🎰 **JACKPOT!** {display} just won **{int(won_amount):,} 🪙** — "
                    f"check #general!",
                    delete_after=30,
                )
            except discord.HTTPException:
                pass

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  2. SURPRISE DOUBLE XP WINDOWS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @tasks.loop(minutes=1)
    async def _surprise_2x_loop(self):
        """Master loop that handles scheduling and running surprise 2x windows.
        Picks a random interval, sleeps, then activates a window."""
        pass  # Actual logic is in before_loop + after_loop pattern below

    @_surprise_2x_loop.before_loop
    async def _before_surprise_2x(self):
        await self.bot.wait_until_ready()
        # Run the actual scheduling loop forever
        self._surprise_2x_loop.cancel()  # Cancel the dummy 1-min loop
        self.bot.loop.create_task(self._surprise_2x_scheduler())

    async def _surprise_2x_scheduler(self):
        """Long-running task that schedules surprise 2x windows at random intervals."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                # Random wait between windows
                wait_hours = random.uniform(
                    SURPRISE_2X_MIN_INTERVAL_HOURS,
                    SURPRISE_2X_MAX_INTERVAL_HOURS,
                )
                wait_seconds = wait_hours * 3600
                logger.info(
                    "Next surprise 2x window in %.1f hours (%.0f seconds)",
                    wait_hours, wait_seconds,
                )
                await asyncio.sleep(wait_seconds)

                # Activate the window
                duration_minutes = random.randint(
                    SURPRISE_2X_DURATION_MIN,
                    SURPRISE_2X_DURATION_MAX,
                )
                await self._activate_double_xp(duration_minutes)

                # Wait for the window to finish before scheduling the next one
                await asyncio.sleep(duration_minutes * 60)
                self._double_xp_active = False
                self._double_xp_until = None
                logger.info("Surprise 2x window ended.")

            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("Error in surprise 2x scheduler")
                await asyncio.sleep(300)  # Back off on error

    async def _activate_double_xp(self, duration_minutes: int):
        """Turn on the 2x flag and announce it."""
        self._double_xp_active = True
        self._double_xp_until = datetime.utcnow() + timedelta(minutes=duration_minutes)

        logger.info("SURPRISE 2x XP ACTIVATED for %d minutes", duration_minutes)

        general = self._get_general_channel()
        if not general:
            return

        embed = discord.Embed(
            title="⚡  DOUBLE XP — ACTIVATED  ⚡",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔥 **ALL POINTS ARE DOUBLED** for the next "
                f"**{duration_minutes} minutes!**\n\n"
                f"⏰ Ends <t:{int(self._double_xp_until.timestamp())}:R>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"The Circle pulses with energy... seize this moment.\n"
                f"Every message, every reply, every reaction — **2x.**"
            ),
            color=EMBED_COLOR_ACCENT,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="Surprise windows are random. You never know when the next one hits.")

        try:
            await general.send(embed=embed)
        except discord.HTTPException:
            pass

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  3. MYSTERY DROP (every 100 server-wide scored messages)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def on_scored_message(self, user_id: int, channel: discord.TextChannel):
        """Called by scoring_handler after every scored message.
        Handles jackpot contribution AND mystery drop counter."""
        # Jackpot check
        await self.check_jackpot(user_id, channel)

        # Mystery drop counter
        self._global_scored_counter += 1
        if self._global_scored_counter >= MYSTERY_DROP_INTERVAL:
            self._global_scored_counter = 0
            await self._trigger_mystery_drop(user_id, channel)

    async def _trigger_mystery_drop(self, user_id: int, channel: discord.TextChannel):
        """Award a random mystery drop to the user who sent the Nth message."""
        member = channel.guild.get_member(user_id)
        display = member.mention if member else f"<@{user_id}>"

        # Decide reward type
        if random.random() < MYSTERY_DROP_STREAK_FREEZE_CHANCE:
            # Streak freeze token
            reward_desc = "🧊 **Streak Freeze Token**"
            reward_detail = "Your streak is protected for one missed day."
            try:
                async with aiosqlite.connect("circle.db") as db:
                    await db.execute(
                        """INSERT INTO streak_freezes (user_id, tokens_held)
                           VALUES (?, 1)
                           ON CONFLICT(user_id)
                           DO UPDATE SET tokens_held = tokens_held + 1""",
                        (user_id,),
                    )
                    await db.commit()
            except Exception:
                logger.exception("Failed to award streak freeze token to %s", user_id)
                return
        else:
            # Random Circles
            amount = random.randint(MYSTERY_DROP_MIN_COINS, MYSTERY_DROP_MAX_COINS)
            # Weight toward lower amounts (use triangular distribution)
            amount = int(random.triangular(
                MYSTERY_DROP_MIN_COINS, MYSTERY_DROP_MAX_COINS,
                MYSTERY_DROP_MIN_COINS,  # mode = low end
            ))
            reward_desc = f"💰 **{amount:,} Circles** 🪙"
            reward_detail = "Spend them in the shop... or save for something bigger."
            try:
                await add_coins(user_id, amount)
            except Exception:
                logger.exception("Failed to award mystery drop coins to %s", user_id)
                return

        logger.info("MYSTERY DROP — user=%s reward=%s", user_id, reward_desc)

        embed = discord.Embed(
            title="🎁  MYSTERY DROP  🎁",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 {display} triggered a **Mystery Drop!**\n\n"
                f"{reward_desc}\n"
                f"_{reward_detail}_\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Every **{MYSTERY_DROP_INTERVAL}** messages, "
                f"The Circle rewards the chosen one."
            ),
            color=EMBED_COLOR_ACCENT,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="Keep talking. The next drop could be yours.")

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(VariableRewards(bot))
