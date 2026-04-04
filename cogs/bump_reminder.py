"""
Bump Reminder — Automated reminders for Disboard, Top.gg, and Discord.me.

Tracks cooldowns, pings @Bumper role when it's time, detects Disboard success,
and rewards bumpers with Circles + streak bonuses.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    GUILD_ID,
    BUMP_CHANNEL,
    BUMP_ROLE_NAME,
    BUMP_REWARD_COINS,
    BUMP_STREAK_BONUS,
    DISBOARD_COOLDOWN,
    TOPGG_COOLDOWN,
    DISCORDME_COOLDOWN,
    DISBOARD_BOT_ID,
    TOPGG_VOTE_URL,
    DISCORDME_BUMP_URL,
)
from database import DB_PATH, add_coins

logger = logging.getLogger("circle.bump_reminder")

PLATFORMS = {
    "disboard": {
        "name": "Disboard",
        "emoji": "🟢",
        "cooldown": DISBOARD_COOLDOWN,
        "action": f"Type `!d bump` in this channel",
    },
    "topgg": {
        "name": "Top.gg",
        "emoji": "🔴",
        "cooldown": TOPGG_COOLDOWN,
        "action": f"[Vote here]({TOPGG_VOTE_URL})",
    },
    "discordme": {
        "name": "Discord.me",
        "emoji": "🔵",
        "cooldown": DISCORDME_COOLDOWN,
        "action": f"[Bump here]({DISCORDME_BUMP_URL})",
    },
}


# ─── DB Helpers ────────────────────────────────────────────────────────

async def _ensure_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bump_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                bumped_at TEXT NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_bump_log_platform ON bump_log(platform, bumped_at)"
        )
        await db.commit()


async def _log_bump(user_id: int, platform: str):
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bump_log (user_id, platform, bumped_at) VALUES (?, ?, ?)",
            (user_id, platform, now),
        )
        await db.commit()


async def _get_last_bump(platform: str) -> tuple[int | None, datetime | None]:
    """Return (user_id, bumped_at) of the most recent bump for a platform."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, bumped_at FROM bump_log WHERE platform = ? ORDER BY bumped_at DESC LIMIT 1",
            (platform,),
        )
        row = await cursor.fetchone()
        if not row:
            return None, None
        return row[0], datetime.fromisoformat(row[1]).replace(tzinfo=timezone.utc)


async def _get_bump_leaderboard(days: int = 30) -> list[tuple[int, int]]:
    """Return [(user_id, bump_count)] for the last N days, sorted desc."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT user_id, COUNT(*) as cnt FROM bump_log
               WHERE bumped_at > ? GROUP BY user_id ORDER BY cnt DESC LIMIT 10""",
            (cutoff,),
        )
        return await cursor.fetchall()


async def _get_user_bump_streak(user_id: int) -> int:
    """Count consecutive days the user has bumped (any platform)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT DISTINCT date(bumped_at) as d FROM bump_log
               WHERE user_id = ? ORDER BY d DESC""",
            (user_id,),
        )
        rows = await cursor.fetchall()

    if not rows:
        return 0

    streak = 0
    today = datetime.now(timezone.utc).date()
    for row in rows:
        expected = today - timedelta(days=streak)
        bump_date = datetime.fromisoformat(row[0]).date()
        if bump_date == expected:
            streak += 1
        else:
            break
    return streak


# ─── Confirm Button View ──────────────────────────────────────────────

class BumpConfirmView(discord.ui.View):
    """Button for users to confirm they bumped on Top.gg or Discord.me."""

    def __init__(self, platform: str, cog: BumpReminder):
        super().__init__(timeout=None)
        self.platform = platform
        self.cog = cog
        self._confirmed_users: set[int] = set()

    @discord.ui.button(
        label="I bumped it!",
        style=discord.ButtonStyle.green,
        emoji="✅",
        custom_id="bump_confirm",
    )
    async def confirm_bump(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in self._confirmed_users:
            await interaction.response.send_message(
                "You already confirmed this bump!", ephemeral=True
            )
            return

        self._confirmed_users.add(user_id)
        await self.cog._reward_bumper(user_id, self.platform)

        await interaction.response.send_message(
            f"🪙 Thanks for bumping **{PLATFORMS[self.platform]['name']}**! "
            f"You earned **{BUMP_REWARD_COINS} Circles**!",
            ephemeral=True,
        )


# ─── Cog ──────────────────────────────────────────────────────────────

class BumpReminder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track when we last sent a reminder per platform (avoid spam on restart)
        self._last_reminder: dict[str, datetime] = {}

    async def cog_load(self):
        await _ensure_table()
        self.check_bumps.start()
        logger.info("✓ BumpReminder loaded")

    def cog_unload(self):
        self.check_bumps.cancel()

    # ─── Background Task: Check Cooldowns ─────────────────────────────

    @tasks.loop(minutes=2)
    async def check_bumps(self):
        """Check each platform's cooldown and post a reminder when ready."""
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return

        channel = discord.utils.get(guild.text_channels, name=BUMP_CHANNEL)
        if not channel:
            return

        bump_role = discord.utils.get(guild.roles, name=BUMP_ROLE_NAME)
        now = datetime.now(timezone.utc)

        for platform_key, info in PLATFORMS.items():
            _, last_bump_time = await _get_last_bump(platform_key)
            cooldown = info["cooldown"]

            # Check if cooldown has expired
            if last_bump_time and (now - last_bump_time).total_seconds() < cooldown:
                continue  # Still on cooldown

            # Don't spam reminders — wait at least half the cooldown before re-reminding
            last_reminded = self._last_reminder.get(platform_key)
            if last_reminded and (now - last_reminded).total_seconds() < cooldown / 2:
                continue

            # Time to bump!
            self._last_reminder[platform_key] = now
            await self._send_reminder(channel, platform_key, info, bump_role)

    @check_bumps.before_loop
    async def before_check_bumps(self):
        await self.bot.wait_until_ready()

    # ─── Send Reminder ────────────────────────────────────────────────

    async def _send_reminder(
        self,
        channel: discord.TextChannel,
        platform_key: str,
        info: dict,
        bump_role: discord.Role | None,
    ):
        cooldown_str = self._format_cooldown(info["cooldown"])
        role_mention = bump_role.mention if bump_role else "**@Bumper**"

        embed = discord.Embed(
            title=f"{info['emoji']} TIME TO BUMP — {info['name'].upper()}",
            description=(
                f"The Circle needs your help growing!\n\n"
                f"**How:** {info['action']}\n"
                f"**Reward:** 🪙 {BUMP_REWARD_COINS} Circles + streak bonus\n"
                f"**Cooldown:** {cooldown_str}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="The Circle grows through your loyalty • Keeper watches all")

        # For Disboard, just remind — we detect the bump automatically
        if platform_key == "disboard":
            await channel.send(
                content=f"🔔 {role_mention} — Disboard bump is ready!",
                embed=embed,
            )
        else:
            # For Top.gg and Discord.me, add a confirm button
            view = BumpConfirmView(platform_key, self)
            await channel.send(
                content=f"🔔 {role_mention} — {info['name']} bump is ready!",
                embed=embed,
                view=view,
            )

    # ─── Detect Disboard Bump Success ─────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Detect Disboard bot's success response after !d bump."""
        if not message.author.bot:
            return
        if message.author.id != DISBOARD_BOT_ID:
            return
        if not message.embeds:
            return

        # Disboard's success embed contains "Bump done!" in the description
        embed = message.embeds[0]
        desc = (embed.description or "").lower()
        if "bump done" not in desc:
            return

        # Find who bumped — check recent messages for !d bump
        bumper_id = None
        async for msg in message.channel.history(limit=10, before=message):
            if not msg.author.bot and msg.content.strip().lower() in ("!d bump", "!d bump "):
                bumper_id = msg.author.id
                break

        if bumper_id:
            await self._reward_bumper(bumper_id, "disboard")

            guild = self.bot.get_guild(GUILD_ID)
            member = guild.get_member(bumper_id) if guild else None
            name = member.display_name if member else f"User {bumper_id}"

            await message.channel.send(
                f"🪙 **{name}** bumped Disboard! +**{BUMP_REWARD_COINS} Circles** earned.",
                delete_after=30,
            )

    # ─── Reward Logic ─────────────────────────────────────────────────

    async def _reward_bumper(self, user_id: int, platform: str):
        """Log the bump, award coins + streak bonus."""
        await _log_bump(user_id, platform)

        streak = await _get_user_bump_streak(user_id)
        bonus = min(streak * BUMP_STREAK_BONUS, 50)  # Cap streak bonus at 50
        total = BUMP_REWARD_COINS + bonus

        await add_coins(user_id, total)
        logger.info(f"Bump reward: user={user_id} platform={platform} coins={total} streak={streak}")

    # ─── Commands ─────────────────────────────────────────────────────

    @commands.command(name="bumps", aliases=["bumpboard", "bumpleaderboard"])
    async def bump_leaderboard(self, ctx: commands.Context):
        """View the bump leaderboard for the last 30 days."""
        rows = await _get_bump_leaderboard(30)
        if not rows:
            await ctx.send("No bumps recorded yet! Be the first to bump.")
            return

        guild = self.bot.get_guild(GUILD_ID)
        lines = []
        for i, (user_id, count) in enumerate(rows, 1):
            medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"**{i}.**"
            member = guild.get_member(user_id) if guild else None
            name = member.display_name if member else f"User {user_id}"
            lines.append(f"{medal} {name} — **{count}** bumps")

        embed = discord.Embed(
            title="📊 BUMP LEADERBOARD (30 Days)",
            description="\n".join(lines),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="Bump Disboard, Top.gg, and Discord.me to climb!")
        await ctx.send(embed=embed)

    @commands.command(name="bumpstatus", aliases=["bs"])
    async def bump_status(self, ctx: commands.Context):
        """Check cooldown status for all listing platforms."""
        now = datetime.now(timezone.utc)
        lines = []

        for platform_key, info in PLATFORMS.items():
            _, last_bump_time = await _get_last_bump(platform_key)
            cooldown = info["cooldown"]

            if not last_bump_time:
                status = "⚡ **READY NOW**"
            else:
                elapsed = (now - last_bump_time).total_seconds()
                remaining = cooldown - elapsed
                if remaining <= 0:
                    status = "⚡ **READY NOW**"
                else:
                    mins = int(remaining // 60)
                    hrs = mins // 60
                    mins = mins % 60
                    status = f"⏳ Ready in **{hrs}h {mins}m**"

            lines.append(f"{info['emoji']} **{info['name']}** — {status}")

        embed = discord.Embed(
            title="🔔 BUMP STATUS",
            description="\n\n".join(lines),
            color=EMBED_COLOR_PRIMARY,
        )

        # Show user's personal bump streak
        streak = await _get_user_bump_streak(ctx.author.id)
        if streak > 0:
            embed.add_field(
                name="🔥 Your Bump Streak",
                value=f"**{streak}** day{'s' if streak != 1 else ''} (+{min(streak * BUMP_STREAK_BONUS, 50)} bonus Circles)",
                inline=False,
            )

        embed.set_footer(text="The Circle grows through your loyalty")
        await ctx.send(embed=embed)

    @commands.command(name="forcebump")
    @commands.is_owner()
    async def force_bump(self, ctx: commands.Context):
        """Manually trigger bump reminders for all platforms. Owner only."""
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return

        channel = discord.utils.get(guild.text_channels, name=BUMP_CHANNEL)
        if not channel:
            await ctx.send("Bump channel not found.")
            return

        bump_role = discord.utils.get(guild.roles, name=BUMP_ROLE_NAME)
        for platform_key, info in PLATFORMS.items():
            await self._send_reminder(channel, platform_key, info, bump_role)

        await ctx.send("✅ Bump reminders sent for all platforms.")

    # ─── Helper ───────────────────────────────────────────────────────

    @staticmethod
    def _format_cooldown(seconds: int) -> str:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        if hours and mins:
            return f"{hours}h {mins}m"
        if hours:
            return f"{hours}h"
        return f"{mins}m"


async def setup(bot: commands.Bot):
    await bot.add_cog(BumpReminder(bot))
