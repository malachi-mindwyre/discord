"""
The Circle — Shop Cog
Shop UI, purchasing permanent and rotating items, mystery boxes.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    ECONOMY_CURRENCY_NAME,
    ECONOMY_CURRENCY_EMOJI,
    SHOP_ITEMS,
    MYSTERY_BOX_LOOT_TABLE,
    ROTATING_SHOP_POOL,
    ROTATING_SHOP_ITEMS_PER_DAY,
)
from database import DB_PATH

logger = logging.getLogger("circle.shop")


class Shop(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.rotate_shop_items.start()
        logger.info("✓ Shop cog loaded — rotating shop task started")

    def cog_unload(self):
        self.rotate_shop_items.cancel()

    # ── Rotating Shop Task ───────────────────────────────────────────────

    @tasks.loop(hours=24)
    async def rotate_shop_items(self):
        """Rotate limited-time shop items daily."""
        now = datetime.now(timezone.utc)

        async with aiosqlite.connect(DB_PATH) as db:
            # Remove expired items
            await db.execute(
                "DELETE FROM shop_rotating WHERE available_until <= ?",
                (now.isoformat(),),
            )

            # Count current active items
            cursor = await db.execute(
                "SELECT COUNT(*) FROM shop_rotating WHERE available_until > ?",
                (now.isoformat(),),
            )
            active_count = (await cursor.fetchone())[0]

            # Add new items if needed
            items_to_add = max(0, ROTATING_SHOP_ITEMS_PER_DAY - active_count)
            if items_to_add > 0:
                # Get keys of currently active items
                cursor = await db.execute(
                    "SELECT item_key FROM shop_rotating WHERE available_until > ?",
                    (now.isoformat(),),
                )
                active_keys = {row[0] for row in await cursor.fetchall()}

                # Pick new items not already active
                available = [i for i in ROTATING_SHOP_POOL if i["key"] not in active_keys]
                random.shuffle(available)
                chosen = available[:items_to_add]

                for item in chosen:
                    expires = now + timedelta(hours=item["duration_hours"])
                    await db.execute(
                        """INSERT OR REPLACE INTO shop_rotating
                           (item_key, name, cost, description, available_until, stock_remaining)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (item["key"], item["name"], item["cost"],
                         item["desc"], expires.isoformat(), item["stock"]),
                    )
                    logger.info("Rotating shop: added %s (expires %s)", item["name"], expires.isoformat())

            await db.commit()

    @rotate_shop_items.before_loop
    async def before_rotate(self):
        await self.bot.wait_until_ready()

    @commands.command(name="shop")
    async def shop_cmd(self, ctx: commands.Context):
        """Display the shop."""
        # Get user balance
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT coins FROM economy WHERE user_id = ?", (ctx.author.id,)
            )
            row = await cursor.fetchone()
            balance = row[0] if row else 0

        embed = discord.Embed(
            title=f"🏪 THE CIRCLE SHOP",
            description=(
                f"Your balance: **{balance:,}** {ECONOMY_CURRENCY_EMOJI}\n\n"
                f"Use `!buy <item>` to purchase.\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_PRIMARY,
        )

        # Permanent items
        lines = []
        for key, item in SHOP_ITEMS.items():
            lines.append(f"{item['emoji']} **{item['name']}** — {item['cost']} {ECONOMY_CURRENCY_EMOJI}\n   {item['desc']}")

        embed.add_field(
            name="📦 PERMANENT STOCK",
            value="\n\n".join(lines),
            inline=False,
        )

        # Show rotating items if any
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT item_key, name, cost, description, available_until, stock_remaining FROM shop_rotating WHERE available_until > ?",
                (datetime.utcnow().isoformat(),),
            )
            rotating = await cursor.fetchall()

        if rotating:
            rot_lines = []
            for item in rotating:
                stock = f"({item[5]} left)" if item[5] > 0 else "(unlimited)"
                rot_lines.append(f"🔄 **{item[1]}** — {item[2]} {ECONOMY_CURRENCY_EMOJI} {stock}\n   {item[3]}")
            embed.add_field(
                name="🔄 LIMITED TIME",
                value="\n\n".join(rot_lines),
                inline=False,
            )

        embed.set_footer(text=f"Earn {ECONOMY_CURRENCY_NAME} by chatting, streaks, and daily rewards")
        await ctx.send(embed=embed)

    @commands.command(name="buy")
    async def buy_cmd(self, ctx: commands.Context, *, item_name: str = None):
        """Buy an item from the shop."""
        if not item_name:
            await ctx.send(f"⚫ Usage: `!buy <item name>`\nUse `!shop` to see available items.")
            return

        # Match item by name (case-insensitive partial match)
        item_name_lower = item_name.lower()
        matched_key = None
        matched_item = None
        for key, item in SHOP_ITEMS.items():
            if item_name_lower in item["name"].lower() or item_name_lower == key:
                matched_key = key
                matched_item = item
                break

        if not matched_item:
            await ctx.send(f"⚫ Item not found. Use `!shop` to see available items.")
            return

        cost = matched_item["cost"]

        # Check balance and spend
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT coins FROM economy WHERE user_id = ?", (ctx.author.id,)
            )
            row = await cursor.fetchone()
            balance = row[0] if row else 0

            if balance < cost:
                await ctx.send(
                    f"⚫ Not enough {ECONOMY_CURRENCY_NAME}. "
                    f"You have **{balance:,}** {ECONOMY_CURRENCY_EMOJI}, need **{cost:,}** {ECONOMY_CURRENCY_EMOJI}."
                )
                return

            # Deduct coins
            await db.execute(
                "UPDATE economy SET coins = coins - ?, total_spent = total_spent + ? WHERE user_id = ?",
                (cost, cost, ctx.author.id),
            )
            # Log purchase
            await db.execute(
                "INSERT INTO shop_purchases (user_id, item_key, purchased_at) VALUES (?, ?, ?)",
                (ctx.author.id, matched_key, datetime.utcnow().isoformat()),
            )
            await db.commit()

        # Handle special items
        result_text = f"You purchased **{matched_item['name']}**!"

        if matched_key == "mystery_box":
            result_text = await self._open_mystery_box(ctx.author.id)
        elif matched_key == "xp_boost":
            result_text += "\n⚡ **2x XP active for 1 hour!** (tracked in scoring)"

        embed = discord.Embed(
            title=f"{matched_item['emoji']} PURCHASE COMPLETE",
            description=(
                f"{result_text}\n\n"
                f"💰 Spent: **{cost}** {ECONOMY_CURRENCY_EMOJI}\n"
                f"💰 Remaining: **{balance - cost:,}** {ECONOMY_CURRENCY_EMOJI}"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        await ctx.send(embed=embed)

    async def _open_mystery_box(self, user_id: int) -> str:
        """Open a mystery box with the redesigned loot table."""
        # Weighted random from config loot table
        items = MYSTERY_BOX_LOOT_TABLE
        weights = [item["weight"] for item in items]
        prize = random.choices(items, weights=weights, k=1)[0]

        result_parts = [f"🎁 **MYSTERY BOX OPENED!**\nYou got: **{prize['name']}**"]

        # Handle different prize types
        if prize["type"] == "coins" and prize["coins"] > 0:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """INSERT INTO economy (user_id, coins, total_earned)
                       VALUES (?, ?, ?)
                       ON CONFLICT(user_id) DO UPDATE SET
                       coins = coins + ?, total_earned = total_earned + ?""",
                    (user_id, prize["coins"], prize["coins"], prize["coins"], prize["coins"]),
                )
                await db.commit()
            result_parts.append(f"💰 +{prize['coins']} {ECONOMY_CURRENCY_EMOJI}")

        elif prize["type"] == "xp_boost_30":
            now = datetime.utcnow()
            expires = now.replace(minute=now.minute + 30) if now.minute < 30 else now.replace(hour=now.hour + 1, minute=now.minute - 30)
            from datetime import timedelta
            expires = now + timedelta(minutes=30)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO active_boosts (user_id, boost_type, multiplier, expires_at) VALUES (?, 'xp', 2.0, ?)",
                    (user_id, expires.isoformat()),
                )
                await db.commit()
            result_parts.append("⚡ 2x XP active for 30 minutes!")

        elif prize["type"] == "xp_boost_60":
            from datetime import timedelta
            expires = datetime.utcnow() + timedelta(hours=1)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO active_boosts (user_id, boost_type, multiplier, expires_at) VALUES (?, 'xp', 2.0, ?)",
                    (user_id, expires.isoformat()),
                )
                await db.commit()
            result_parts.append("⚡ 2x XP active for 1 hour!")

        elif prize["type"] == "streak_freeze":
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """INSERT INTO streak_freezes (user_id, tokens_held)
                       VALUES (?, 1)
                       ON CONFLICT(user_id) DO UPDATE SET
                       tokens_held = MIN(tokens_held + 1, 3)""",
                    (user_id,),
                )
                await db.commit()
            result_parts.append("🧊 Streak Freeze token added! Saves your streak if you miss a day.")

        elif prize["type"] == "rank_shield":
            result_parts.append("🛡️ Rank Shield active for 24 hours! Your rank can't drop.")

        elif prize["type"] == "nothing":
            result_parts.append("Better luck next time... 💀")

        return "\n".join(result_parts)


async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))
