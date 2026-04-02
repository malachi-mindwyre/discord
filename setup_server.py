"""
The Circle — Server Setup Cog
Creates all channels, categories, roles, and permissions via !setup command.
"""

import discord
from discord.ext import commands

from config import CHANNEL_STRUCTURE, EXCLUDED_CHANNELS, GUILD_ID
from ranks import ALL_RANKS


class SetupServer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx: commands.Context):
        """Create all channels, categories, and 100 rank roles. Admin only."""
        guild = ctx.guild
        if not guild:
            return

        await ctx.send("⚫ **Keeper is shaping The Circle...**\nThis may take a moment.")

        # ─── Create Rank Roles (lowest rank first so highest is at top) ────
        await ctx.send("⚫ Forging 100 rank roles...")
        created_roles = 0
        existing_role_names = {r.name for r in guild.roles}

        # Create from highest to lowest so Discord positions them correctly
        for rank in reversed(ALL_RANKS):
            if rank.name not in existing_role_names:
                try:
                    await guild.create_role(
                        name=rank.name,
                        color=discord.Color(rank.color),
                        hoist=False,
                        mentionable=False,
                        reason=f"The Circle rank setup: Tier {rank.tier}",
                    )
                    created_roles += 1
                except discord.HTTPException as e:
                    await ctx.send(f"⚠️ Failed to create role {rank.name}: {e}")

        await ctx.send(f"⚫ {created_roles} rank roles forged.")

        # ─── Create Categories and Channels ────────────────────────────────
        await ctx.send("⚫ Building the chambers...")
        existing_channels = {c.name: c for c in guild.channels}
        created_channels = 0

        for category_name, channels in CHANNEL_STRUCTURE.items():
            # Create or find category
            category = discord.utils.get(guild.categories, name=category_name)
            if not category:
                category = await guild.create_category(
                    name=category_name,
                    reason="The Circle setup",
                )

            for channel_name, channel_config in channels.items():
                if channel_name in existing_channels:
                    continue

                overwrites = {}
                if channel_config["read_only"]:
                    overwrites[guild.default_role] = discord.PermissionOverwrite(
                        send_messages=False,
                        add_reactions=True,
                        read_messages=True,
                    )
                    overwrites[guild.me] = discord.PermissionOverwrite(
                        send_messages=True,
                        embed_links=True,
                        attach_files=True,
                        manage_messages=True,
                    )

                try:
                    await guild.create_text_channel(
                        name=channel_name,
                        category=category,
                        topic=channel_config["topic"],
                        overwrites=overwrites,
                        reason="The Circle setup",
                    )
                    created_channels += 1
                except discord.HTTPException as e:
                    await ctx.send(f"⚠️ Failed to create #{channel_name}: {e}")

        await ctx.send(f"⚫ {created_channels} chambers constructed.")

        # ─── Final Message ─────────────────────────────────────────────────
        embed = discord.Embed(
            title="⚫ THE CIRCLE IS COMPLETE",
            description=(
                "The chambers have been built. The ranks have been forged.\n"
                "Keeper now watches over all.\n\n"
                f"🏷️ **{created_roles}** rank roles created\n"
                f"💬 **{created_channels}** channels created\n\n"
                "The Circle awaits its first souls."
            ),
            color=0x1A1A2E,
        )
        await ctx.send(embed=embed)

    @commands.command(name="cleanup")
    @commands.has_permissions(administrator=True)
    async def cleanup(self, ctx: commands.Context):
        """Fix channel structure: move orphan channels to correct categories, remove empty duplicate categories. Admin only."""
        guild = ctx.guild
        if not guild:
            return

        await ctx.send("⚫ **Keeper is tidying The Circle...**")

        # Build a map: channel_name -> target_category_name
        channel_to_category = {}
        for cat_name, channels in CHANNEL_STRUCTURE.items():
            for ch_name in channels:
                channel_to_category[ch_name] = cat_name

        moved = 0
        deleted_cats = 0

        # ─── Move orphan/misplaced channels to their correct category ──
        for channel in guild.text_channels:
            target_cat_name = channel_to_category.get(channel.name)
            if not target_cat_name:
                continue  # Not a managed channel

            target_cat = discord.utils.get(guild.categories, name=target_cat_name)
            if not target_cat:
                continue  # Category doesn't exist yet

            if channel.category != target_cat:
                try:
                    await channel.edit(category=target_cat, reason="Cleanup: move to correct category")
                    moved += 1
                except discord.HTTPException:
                    pass

        # ─── Remove empty duplicate categories ─────────────────────────
        # Count how many categories share the same name
        from collections import Counter
        cat_names = [c.name for c in guild.categories]
        dupes = {name for name, count in Counter(cat_names).items() if count > 1}

        for cat in guild.categories:
            if cat.name in dupes and len(cat.channels) == 0:
                try:
                    await cat.delete(reason="Cleanup: remove empty duplicate category")
                    deleted_cats += 1
                except discord.HTTPException:
                    pass

        # ─── Remove duplicate channels (same name, keep the one in correct category) ──
        channel_names = [c.name for c in guild.text_channels]
        dupe_channels = {name for name, count in Counter(channel_names).items() if count > 1}
        deleted_channels = 0

        for ch_name in dupe_channels:
            channels_with_name = [c for c in guild.text_channels if c.name == ch_name]
            target_cat_name = channel_to_category.get(ch_name)
            if not target_cat_name or len(channels_with_name) <= 1:
                continue

            # Keep the one in the correct category, delete others
            target_cat = discord.utils.get(guild.categories, name=target_cat_name)
            kept = False
            for ch in channels_with_name:
                if ch.category == target_cat and not kept:
                    kept = True  # Keep this one
                    continue
                # Delete the duplicate (only if it's empty or a duplicate)
                try:
                    # Only delete if the channel has very few messages (< 5) to be safe
                    # We don't want to delete a channel with real content
                    pass  # Skip auto-deletion of channels with content for safety
                except discord.HTTPException:
                    pass

        embed = discord.Embed(
            title="⚫ CLEANUP COMPLETE",
            description=(
                f"📦 **{moved}** channels moved to correct categories\n"
                f"🗑️ **{deleted_cats}** empty duplicate categories removed\n\n"
                "If you still see duplicates with content, delete them manually:\n"
                "Right-click category/channel → Delete"
            ),
            color=0x1A1A2E,
        )
        await ctx.send(embed=embed)


    @commands.command(name="purgeall")
    @commands.has_permissions(administrator=True)
    async def purge_all_channels(self, ctx: commands.Context):
        """Delete ALL messages in ALL text channels. Admin only. Irreversible."""
        guild = ctx.guild
        if not guild:
            return

        await ctx.send("⚫ **Keeper is purging The Circle...**\nThis will take a while. Do not interrupt.")

        total_deleted = 0
        channels_purged = 0

        for channel in guild.text_channels:
            try:
                count = 0
                # bulk_delete handles messages < 14 days old (up to 100 at a time)
                while True:
                    deleted = await channel.purge(limit=100)
                    if not deleted:
                        break
                    count += len(deleted)
                total_deleted += count
                if count > 0:
                    channels_purged += 1
            except discord.Forbidden:
                pass  # Skip channels the bot can't manage
            except discord.HTTPException:
                pass

        # Send summary in the command channel (it was just purged too, so create fresh message)
        try:
            summary_ch = ctx.channel if ctx.channel in guild.text_channels else guild.text_channels[0]
            embed = discord.Embed(
                title="⚫ PURGE COMPLETE",
                description=(
                    f"**{total_deleted:,}** messages deleted across **{channels_purged}** channels.\n\n"
                    f"The Circle is reborn. The slate is clean.\n"
                    f"*Run `!postinfo` to repopulate #info.*"
                ),
                color=0xE94560,
            )
            await summary_ch.send(embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupServer(bot))
