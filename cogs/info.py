"""
The Circle — Info Channel Cog
Posts a series of clean, user-friendly guide embeds to #info via !postinfo command.
"""

import discord
from discord.ext import commands

from config import EMBED_COLOR_PRIMARY, EMBED_COLOR_ACCENT, CHANNEL_STRUCTURE
from ranks import ALL_RANKS, RANK_BY_TIER


class Info(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="postinfo")
    @commands.has_permissions(administrator=True)
    async def post_info(self, ctx: commands.Context):
        """Post all info guide embeds to #info. Admin only."""
        info_channel = discord.utils.get(ctx.guild.text_channels, name="info")
        if not info_channel:
            await ctx.send("⚠️ #info channel not found. Run `!setup` first.")
            return

        await ctx.send("⚫ Keeper is writing the sacred texts...")

        embeds = [
            self._build_welcome_embed(ctx.guild),
            self._build_scoring_embed(),
            self._build_streaks_embed(),
            self._build_ranks_overview_embed(),
            self._build_ranks_detail_embed(),
            self._build_channels_embed(ctx.guild),
            self._build_media_embed(),
            self._build_reactions_embed(),
            self._build_voice_embed(),
            self._build_achievements_embed(),
            self._build_invites_embed(),
            self._build_comeback_embed(),
            self._build_daily_prompts_embed(),
            # Phase 2 features
            self._build_economy_embed(),
            self._build_shop_embed(),
            self._build_daily_rewards_embed(),
            self._build_confessions_embed(),
            self._build_starboard_embed(),
            self._build_factions_embed(),
            self._build_profiles_embed(),
            self._build_events_embed(),
            self._build_buddy_embed(),
            self._build_commands_embed(),
        ]

        for embed in embeds:
            try:
                await info_channel.send(embed=embed)
            except discord.HTTPException as e:
                await ctx.send(f"⚠️ Failed to post embed: {e}")

        await ctx.send("⚫ The sacred texts have been written in #info.")

    def _build_welcome_embed(self, guild: discord.Guild) -> discord.Embed:
        embed = discord.Embed(
            title="⚫ WELCOME TO THE CIRCLE",
            description=(
                "This is your home now.\n\n"
                "The Circle is a social server built around **one idea:** "
                "the more you engage, the more you're rewarded.\n\n"
                "Every message you send, every reply, every tag, every meme — "
                "it all counts. You'll climb through **100 ranks**, unlock new colors, "
                "and compete on the leaderboard.\n\n"
                "**It's simple:**\n"
                "💬 Talk → Earn points\n"
                "📈 Earn points → Rank up\n"
                "🏆 Rank up → Flex on everyone\n\n"
                "Read below to learn exactly how it all works. 👇"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="The Circle • Keep scrolling for the full guide")
        return embed

    def _build_scoring_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🏆 HOW SCORING WORKS",
            description=(
                "Every message you send earns you points. "
                "But not all messages are equal.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.add_field(
            name="📝 BASIC POINTS",
            value=(
                "Every message = **1 point** base\n"
                "Longer messages earn more — **+0.2 pts per word**\n\n"
                "*Example: A 50-word message = 1 + 10 = **11 pts***"
            ),
            inline=False,
        )
        embed.add_field(
            name="📸 MEDIA BONUS",
            value=(
                "Post an image, video, GIF, or link?\n"
                "That's **+5 bonus points** on top of your text.\n\n"
                "*Share cool stuff = more points!*"
            ),
            inline=False,
        )
        embed.add_field(
            name="↩️ REPLY BOOST — 3x MULTIPLIER",
            value=(
                "When you **reply to someone's message**, "
                "your entire score for that message gets **tripled**.\n\n"
                "*This is HUGE. Conversations > monologues.*"
            ),
            inline=False,
        )
        embed.add_field(
            name="🏷️ TAG BOOST — 4x MULTIPLIER",
            value=(
                "When you **@mention someone**, "
                "your score gets **quadrupled**.\n\n"
                "*Tag people! Pull them into the conversation!*"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔥 MULTIPLIERS STACK",
            value=(
                "Reply + Tag + Media + Long message?\n"
                "The multipliers **stack on top of each other.**\n\n"
                "Example: 50-word reply with a pic + @tag\n"
                "→ (1 + 10 + 5) × 3 × 4 = **192 points** from one message!\n\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            ),
            inline=False,
        )
        embed.add_field(
            name="⏱️ LIMITS",
            value=(
                "• **15 second** cooldown between scored messages\n"
                "• **1,000 point** daily cap (resets at midnight)\n"
                "• Spamming the same message = no points\n\n"
                "*Quality over quantity — but quantity helps too 😏*"
            ),
            inline=False,
        )
        embed.set_footer(text="TL;DR — Reply to people, tag them, share media. That's how you win.")
        return embed

    def _build_streaks_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🔥 DAILY STREAKS",
            description=(
                "Log in and send a message **every day** to build your streak.\n"
                "The longer your streak, the bigger your score bonus.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**STREAK BONUSES:**\n"
                "🔥 **3 days** → +10% on all points\n"
                "🔥 **7 days** → +25% on all points\n"
                "🔥 **14 days** → +50% on all points\n"
                "🔥 **30 days** → +100% (DOUBLE points!)\n"
                "🔥 **60 days** → +150% on all points\n"
                "💀 **100 days** → +200% (TRIPLE points!)\n\n"
                "**Miss a day? Your streak resets to zero.**\n\n"
                "Use `!streak` to check your current streak.\n"
                "Use `!streaks` to see who has the longest streak."
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="The grind never stops. Neither should you.")
        return embed

    def _build_reactions_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="❤️ REACTION SCORING",
            description=(
                "When people **react to your message**, you earn points.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**How it works:**\n"
                "• Each unique reaction on your message = **+0.5 pts**\n"
                "• Max **100 reaction points** per day\n"
                "• You can't react to your own messages for points\n"
                "• Same person reacting twice to the same message only counts once\n\n"
                "**Why it matters:**\n"
                "This rewards posting **good content**, not just volume.\n"
                "If people react to your stuff, you're doing it right. 🎯"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="Post things people want to react to.")
        return embed

    def _build_voice_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎤 VOICE CHANNEL XP",
            description=(
                "Hanging out in voice channels earns points too.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**How it works:**\n"
                "• **+0.2 points per minute** in any voice channel\n"
                "• Max **8 hours** per session (capped to prevent abuse)\n"
                "• AFK channel doesn't count\n"
                "• Points are awarded when you **leave** the voice channel\n\n"
                "**Example:**\n"
                "1 hour in voice = **12 points**\n"
                "A whole evening (4 hours) = **48 points**\n\n"
                "Use `!voicetime` to check your total voice time.\n\n"
                "*Jump in a call. Hang out. Earn points just for being social.*"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="Voice counts. Literally.")
        return embed

    def _build_achievements_embed(self) -> discord.Embed:
        from config import ACHIEVEMENTS
        embed = discord.Embed(
            title="🏅 ACHIEVEMENTS",
            description=(
                f"There are **{len(ACHIEVEMENTS)} badges** to unlock.\n"
                "Achievements are one-time rewards for hitting milestones.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_PRIMARY,
        )

        # Group by category
        categories = {
            "💬 MESSAGING": ["first_message", "replies_50", "replies_500", "tags_50", "media_first", "media_50"],
            "🔥 STREAKS": ["streak_3", "streak_7", "streak_14", "streak_30", "streak_100"],
            "❤️ REACTIONS": ["reactions_100", "reactions_1000"],
            "🎤 VOICE": ["voice_60", "voice_600"],
            "📨 INVITES": ["invite_1", "invite_5", "invite_25"],
            "📈 SCORE": ["score_1000", "score_10000", "score_100000"],
            "🏷️ RANKS": ["rank_regular", "rank_certified", "rank_respected", "rank_veteran", "rank_og", "rank_elite", "rank_legend", "rank_icon", "rank_immortal"],
        }

        for cat_name, keys in categories.items():
            lines = []
            for key in keys:
                if key in ACHIEVEMENTS:
                    emoji, name, desc = ACHIEVEMENTS[key]
                    lines.append(f"{emoji} **{name}** — {desc}")
            if lines:
                embed.add_field(name=cat_name, value="\n".join(lines), inline=False)

        embed.add_field(
            name="",
            value="Use `!badges` to see which ones you've unlocked.",
            inline=False,
        )
        embed.set_footer(text="Collect them all. Flex on everyone.")
        return embed

    def _build_daily_prompts_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="💭 DAILY PROMPTS",
            description=(
                "Every day, Keeper posts a **discussion question** in #general.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**Why reply?**\n"
                "• It's an easy conversation starter\n"
                "• Replies get **3x points**\n"
                "• Tag someone in your reply for **4x**\n"
                "• Great way to keep your streak alive\n\n"
                "Topics range from hot takes to dating advice to gym talk.\n"
                "New question every day. Never run out of things to talk about."
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="Reply to the daily prompt. Easy points, good conversations.")
        return embed

    def _build_ranks_overview_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎨 THE 100 RANKS — OVERVIEW",
            description=(
                "There are **100 ranks** split into **10 tiers**.\n"
                "Each tier has **10 levels** (I → II → III → ... → X).\n\n"
                "Your **name color** changes automatically as you rank up.\n"
                "The color shifts gradually within each tier — so Rookie I is a dull gray,\n"
                "but by Rookie X it's a brighter gray approaching green.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_PRIMARY,
        )

        embed.add_field(
            name="⬜ ROOKIE I–X — Gray",
            value=(
                "**Starts at:** 0 pts\n"
                "**Tagline:** *\"You found the WiFi password.\"*\n"
                "You just got here. Everyone starts as Rookie I. The grind begins."
            ),
            inline=True,
        )
        embed.add_field(
            name="🟢 REGULAR I–X — Green",
            value=(
                "**Starts at:** ~180 pts\n"
                "**Tagline:** *\"Your screen time is concerning.\"*\n"
                "You're showing up consistently. People are starting to notice."
            ),
            inline=True,
        )
        embed.add_field(name="", value="", inline=False)  # Line break
        embed.add_field(
            name="🔵 CERTIFIED I–X — Blue",
            value=(
                "**Starts at:** ~680 pts\n"
                "**Tagline:** *\"Your mom would be worried.\"*\n"
                "You've proven you're not just passing through."
            ),
            inline=True,
        )
        embed.add_field(
            name="🟠 RESPECTED I–X — Orange",
            value=(
                "**Starts at:** ~2,000 pts\n"
                "**Tagline:** *\"Therapist: 'And the Discord?'\"*\n"
                "Real ones. This is where dedication shows."
            ),
            inline=True,
        )
        embed.add_field(name="", value="", inline=False)
        embed.add_field(
            name="🔴 VETERAN I–X — Red",
            value=(
                "**Starts at:** ~5,600 pts\n"
                "**Tagline:** *\"You've seen things.\"*\n"
                "You've been through it all. Respect."
            ),
            inline=True,
        )
        embed.add_field(
            name="🟣 OG I–X — Purple",
            value=(
                "**Starts at:** ~15,400 pts\n"
                "**Tagline:** *\"Touch grass? Never heard of it.\"*\n"
                "Day one energy. The Circle is your life now."
            ),
            inline=True,
        )
        embed.add_field(name="", value="", inline=False)
        embed.add_field(
            name="🩵 ELITE I–X — Teal",
            value=(
                "**Starts at:** ~41,700 pts\n"
                "**Tagline:** *\"Your keyboard fears you.\"*\n"
                "You're in the top tier. Few reach this."
            ),
            inline=True,
        )
        embed.add_field(
            name="🟡 LEGEND I–X — Gold",
            value=(
                "**Starts at:** ~112,000 pts\n"
                "**Tagline:** *\"Some say they never log off.\"*\n"
                "People talk about you. Your name means something."
            ),
            inline=True,
        )
        embed.add_field(name="", value="", inline=False)
        embed.add_field(
            name="🩷 ICON I–X — Hot Pink",
            value=(
                "**Starts at:** ~302,000 pts\n"
                "**Tagline:** *\"Are you okay? Genuinely.\"*\n"
                "You've transcended normal engagement. This is a lifestyle."
            ),
            inline=True,
        )
        embed.add_field(
            name="⚪ IMMORTAL I–X — White",
            value=(
                "**Starts at:** ~815,000 pts\n"
                "**Tagline:** *\"This IS your grass.\"*\n"
                "The final form. Rank 100 takes ~2,000,000 pts. Nothing left to prove."
            ),
            inline=True,
        )

        embed.set_footer(text="100 ranks. 10 colors. Your name tells your story.")
        return embed

    def _build_ranks_detail_embed(self) -> discord.Embed:
        from ranks import ALL_RANKS, RANK_BY_TIER
        from config import RANK_GROUPS as GROUPS

        embed = discord.Embed(
            title="📋 RANK THRESHOLDS — FULL BREAKDOWN",
            description=(
                "Here's **exactly** how many points you need for each rank.\n"
                "Points required grow exponentially — early ranks fly by, top ranks take real commitment.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_PRIMARY,
        )

        # Show each group's 10 sub-ranks with thresholds
        for group_idx, (group_name, _, _, tagline) in enumerate(GROUPS):
            lines = []
            for sub_idx in range(10):
                tier = group_idx * 10 + sub_idx + 1
                rank = RANK_BY_TIER[tier]
                lines.append(f"`{rank.name:15s}` — **{rank.threshold:>10,}** pts")

            embed.add_field(
                name=f"{['⬜','🟢','🔵','🟠','🔴','🟣','🩵','🟡','🩷','⚪'][group_idx]} {group_name.upper()} (Tiers {group_idx*10+1}–{group_idx*10+10})",
                value="\n".join(lines),
                inline=False,
            )

        embed.add_field(
            name="💡 KEY THINGS",
            value=(
                "• Your **name color** updates instantly when you rank up\n"
                "• Rank-ups are announced in **#rank-ups** with a big embed\n"
                "• A subtle message also appears in the channel where you ranked up\n"
                "• Use `!rank` anytime to see your progress bar to the next level\n"
                "• Streak bonuses make climbing **much** faster (up to 3x at 100-day streak)"
            ),
            inline=False,
        )
        embed.set_footer(text="The climb is long. The view from the top is worth it.")
        return embed

    def _build_channels_embed(self, guild: discord.Guild) -> discord.Embed:
        embed = discord.Embed(
            title="📍 CHANNEL GUIDE",
            description="Here's what each channel is for.\n\n━━━━━━━━━━━━━━━━━━━━━",
            color=EMBED_COLOR_PRIMARY,
        )

        emoji_map = {
            "general": ("💬", "The main hangout — talk about literally anything"),
            "memes": ("😂", "Funny stuff, memes, shitposts — you know the vibe"),
            "dating": ("💕", "Dating advice, stories, wins, and losses"),
            "politics": ("🗳️", "News, debates, and hot takes — keep it civil-ish"),
            "work": ("💼", "Career talk, side hustles, job hunting, grind culture"),
            "fitness": ("🏋️", "Gym talk, progress pics, routines, diet stuff"),
            "media-feed": ("📸", "Auto-collects ALL media posted anywhere — browse the best stuff in one place"),
            "leaderboard": ("🏆", "Live leaderboard — updates every hour — see who's on top"),
            "rank-ups": ("⚡", "Watch people level up in real time"),
            "bot-commands": ("🤖", "Talk to Keeper — use commands like !rank, !top, !stats"),
        }

        social = []
        serious = []
        auto = []

        for name, (emoji, desc) in emoji_map.items():
            ch = discord.utils.get(guild.text_channels, name=name)
            mention = ch.mention if ch else f"#{name}"
            line = f"{emoji} {mention} — {desc}"

            if name in ("general", "memes", "dating"):
                social.append(line)
            elif name in ("politics", "work", "fitness"):
                serious.append(line)
            else:
                auto.append(line)

        embed.add_field(name="💬 SOCIAL", value="\n".join(social), inline=False)
        embed.add_field(name="🏋️ SERIOUS", value="\n".join(serious), inline=False)
        embed.add_field(
            name="📊 AUTOMATED",
            value="\n".join(auto) + "\n\n*You earn points in the Social and Serious channels. Automated channels are read-only.*",
            inline=False,
        )
        embed.set_footer(text="Jump into any channel and start talking. That's it.")
        return embed

    def _build_media_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📸 THE MEDIA FEED",
            description=(
                "Any time someone posts media **anywhere** in the server, "
                "Keeper automatically copies it to #media-feed.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**What counts as media:**\n"
                "🖼️ Images (PNG, JPG, GIF, WebP)\n"
                "🎥 Videos (MP4, MOV, WebM)\n"
                "🔗 Links (YouTube, TikTok, Twitter/X, Reddit, Instagram, Twitch)\n"
                "📎 File attachments\n\n"
                "**Why it exists:**\n"
                "Scroll through #media-feed to see the best content "
                "from every channel in one place — like a highlight reel.\n\n"
                "*Nobody can post in #media-feed directly. Keeper curates it automatically.*"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="Post cool stuff in any channel and it shows up here automatically.")
        return embed

    def _build_invites_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📨 INVITING FRIENDS",
            description=(
                "Bring people to The Circle and earn **25 points per invite**.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**How it works:**\n"
                "1️⃣ Create an invite link (right-click the server name → Invite People)\n"
                "2️⃣ Send it to your friends\n"
                "3️⃣ When they join and stay **24 hours** + send **5 messages**, "
                "you get **25 points** automatically\n\n"
                "**Invite Leaderboard:**\n"
                "The top recruiters are featured on the leaderboard.\n"
                "Use `!invites` to see who's bringing in the most people.\n\n"
                "*The more people, the better the conversations, the more points for everyone.*"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="Grow The Circle. Everyone benefits.")
        return embed

    def _build_comeback_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🔄 BEEN AWAY?",
            description=(
                "Life happens. But The Circle remembers you.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**If you've been gone 7+ days:**\n"
                "⚡ Your first message back gets a **5x score bonus**\n"
                "📣 Keeper announces your return to the server\n\n"
                "**If you've been gone 14+ days:**\n"
                "📩 Keeper will DM you a friendly reminder\n\n"
                "**If you've been gone 30+ days:**\n"
                "📉 Your score starts to slowly decrease (**-2% per day**)\n"
                "This protects the leaderboard from being dominated by inactive accounts.\n\n"
                "*Come back before your rank slips. The Circle waits.*"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="Stay active. Stay relevant. Stay in The Circle.")
        return embed

    def _build_economy_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🪙 ECONOMY — CIRCLES",
            description=(
                "Alongside points, you earn **Circles** (🪙) — The Circle's virtual currency.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**How to earn Circles:**\n"
                "🪙 Every scored message = **+1 Circle**\n"
                "📅 Daily login rewards = **10-500 Circles**\n"
                "🏆 Achievements and milestones = bonus Circles\n"
                "🎁 Mystery box prizes\n\n"
                "**What to spend them on:**\n"
                "Use `!shop` to see the full store — custom colors, XP boosts, "
                "mystery boxes, profile upgrades, and limited-time exclusives.\n\n"
                "Use `!balance` to check your wallet."
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="Earn Circles. Spend wisely. Flex hard.")
        return embed

    def _build_shop_embed(self) -> discord.Embed:
        from config import SHOP_ITEMS, ECONOMY_CURRENCY_EMOJI
        embed = discord.Embed(
            title="🏪 THE SHOP",
            description=(
                "Spend your Circles on upgrades and goodies.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        lines = []
        for key, item in SHOP_ITEMS.items():
            lines.append(f"{item['emoji']} **{item['name']}** — {item['cost']} {ECONOMY_CURRENCY_EMOJI}\n   {item['desc']}")
        embed.add_field(name="📦 AVAILABLE ITEMS", value="\n\n".join(lines), inline=False)
        embed.add_field(
            name="🔄 ROTATING STOCK",
            value="Limited-time items appear weekly — exclusive roles, VIP access, and more. Check `!shop` regularly!",
            inline=False,
        )
        embed.set_footer(text="!shop to browse • !buy <item> to purchase")
        return embed

    def _build_daily_rewards_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📅 DAILY LOGIN REWARDS",
            description=(
                "Claim `!daily` every day for escalating rewards.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**How it works:**\n"
                "📅 Use `!daily` once per day to claim your reward\n"
                "📈 Rewards get bigger the longer your streak\n"
                "❌ **Miss a day?** Your login streak resets to Day 1\n\n"
                "**Reward milestones:**\n"
                "Day 1: 10 🪙\n"
                "Day 7: 75 🪙 + Mystery Box\n"
                "Day 14: 100 🪙 + Rare Color\n"
                "Day 30: 500 🪙 + Badge\n\n"
                "Use `!loginstreak` to check your progress."
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="Show up every day. The rewards are worth it.")
        return embed

    def _build_confessions_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🔮 ANONYMOUS CONFESSIONS",
            description=(
                "Got something to say? Say it anonymously.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**How to confess:**\n"
                "📩 DM Keeper: `!confess <your confession>`\n"
                "💬 Or use `!confess` in any channel (auto-deleted for privacy)\n\n"
                "**Rules:**\n"
                "• One confession every 6 hours\n"
                "• No slurs or harassment\n"
                "• Confessions posted in #confessions (read-only)\n"
                "• Discuss them in #confession-discussion\n\n"
                "Keeper will never reveal who said what... publicly. 👁️"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text="The Circle keeps your secrets.")
        return embed

    def _build_starboard_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="⭐ HALL OF FAME",
            description=(
                "Post something good enough and you'll be immortalized.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**How it works:**\n"
                "When a message gets enough reactions, Keeper automatically "
                "features it in **#hall-of-fame** with a special embed.\n\n"
                "**How many reactions?**\n"
                "• Under 50 members: **3 reactions**\n"
                "• 50-200 members: **5 reactions**\n"
                "• 200+ members: **10 reactions**\n\n"
                "React to messages you love. Help great content rise to the top. ⭐"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="Quality rises. The Hall of Fame remembers.")
        return embed

    def _build_factions_embed(self) -> discord.Embed:
        from config import FACTION_TEAMS, FACTION_UNLOCK_RANK
        embed = discord.Embed(
            title="⚔️ FACTIONS",
            description=(
                f"Reach **Rank {FACTION_UNLOCK_RANK}** (Respected I) and choose your allegiance.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        for name, info in FACTION_TEAMS.items():
            embed.add_field(
                name=f"{info['emoji']} {name}",
                value=f"*\"{info['motto']}\"*",
                inline=True,
            )
        embed.add_field(name="", value="", inline=False)
        embed.add_field(
            name="HOW IT WORKS",
            value=(
                "• **Permanent choice** — choose wisely\n"
                "• Each team has a **private channel**\n"
                "• Weekly **team competition** — all members' activity counts\n"
                "• **Winning team** gets 10% bonus points for the next week\n\n"
                "Use `!faction` to view standings or `!joinfaction <name>` to join."
            ),
            inline=False,
        )
        embed.set_footer(text="Choose your team. Fight for your team. Win together.")
        return embed

    def _build_profiles_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="👤 MEMBER PROFILES",
            description=(
                "Your profile is your identity in The Circle.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**View:** `!profile` or `!profile @user`\n\n"
                "Your profile shows your rank, score, coins, streak, badges, "
                "voice time, faction, bio, and more.\n\n"
                "**Customize:**\n"
                "✏️ `!setbio <text>` — Set your bio (free, 100 chars)\n"
                "🎨 `!setcolor #hex` — Custom accent color (100 🪙)\n"
                "🖼️ `!setbanner <url>` — Profile banner image (200 🪙)\n\n"
                "The more you invest in your profile, the harder it is to leave. 😏"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="!profile — Make it yours.")
        return embed

    def _build_events_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📅 WEEKLY EVENTS",
            description=(
                "Something happens **every day** in The Circle.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.add_field(
            name="THE WEEKLY CALENDAR",
            value=(
                "💪 **Monday** — Motivation Monday (fitness & work prompts)\n"
                "🧠 **Tuesday** — Trivia Tuesday (10 questions, first correct wins)\n"
                "🔮 **Wednesday** — Confession Wednesday (submit via DM)\n"
                "🔥 **Thursday** — Hot Take Thursday (spiciest opinions)\n"
                "😂 **Friday** — Meme Friday (best meme competition)\n"
                "🎤 **Saturday** — VC Saturday (voice channel hangouts)\n"
                "📊 **Sunday** — Weekly Recap (stats & highlights)"
            ),
            inline=False,
        )
        embed.add_field(
            name="🎯 WEEKLY COMMUNITY GOAL",
            value=(
                "Every week, The Circle sets a message target.\n"
                "If we hit it, **everyone** gets a reward.\n"
                "Use `!goal` to check progress."
            ),
            inline=False,
        )
        embed.set_footer(text="Never a dull day in The Circle.")
        return embed

    def _build_buddy_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🤝 BUDDY SYSTEM",
            description=(
                "New members get paired with an experienced guide.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**How it works:**\n"
                "🤝 When you join, Keeper assigns you a **buddy** (Certified+ rank)\n"
                "💬 Your buddy helps you get started\n"
                "🎯 Send **10 messages** in 48 hours → both of you earn **50 bonus pts**\n"
                "🏅 Buddies earn the **Mentor** badge for completing missions\n\n"
                "*A human connection in the first hour is the #1 predictor of whether someone stays.*"
            ),
            color=EMBED_COLOR_ACCENT,
        )
        embed.set_footer(text="Guide others. Earn together. Grow The Circle.")
        return embed

    def _build_commands_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🤖 ALL COMMANDS",
            description=(
                "Use these in any channel (or #bot-commands).\n\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.add_field(
            name="📊 STATS & RANKINGS",
            value=(
                "🏆 `!rank` — Your rank, score, and progress\n"
                "📊 `!top` — Top 10 leaderboard\n"
                "👤 `!profile [@user]` — Full profile view\n"
                "👀 `!stats @user` — Someone else's stats\n"
                "📨 `!invites` — Invite leaderboard"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔥 ENGAGEMENT",
            value=(
                "🔥 `!streak` — Your current daily streak\n"
                "🔥 `!streaks` — Streak leaderboard\n"
                "🎤 `!voicetime` — Your voice channel time\n"
                "🏅 `!badges` — Your achievement badges\n"
                "📅 `!daily` — Claim daily login reward\n"
                "📅 `!loginstreak` — Check login reward streak"
            ),
            inline=False,
        )
        embed.add_field(
            name="🪙 ECONOMY",
            value=(
                "💰 `!balance` — Check your Circles\n"
                "🏪 `!shop` — Browse the shop\n"
                "🛒 `!buy <item>` — Buy from the shop\n"
                "💎 `!richest` — Richest members"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚔️ FACTIONS & SOCIAL",
            value=(
                "⚔️ `!faction` — View faction standings\n"
                "⚔️ `!joinfaction <name>` — Join a faction\n"
                "🔮 `!confess <text>` — Anonymous confession\n"
                "📊 `!goal` — Weekly community goal\n"
                "✏️ `!setbio <text>` — Set profile bio\n"
                "🎨 `!setcolor #hex` — Set profile color (100🪙)\n"
                "🖼️ `!setbanner <url>` — Set profile banner (200🪙)"
            ),
            inline=False,
        )
        embed.add_field(
            name="❓ HELP",
            value="❓ `!help` — Quick command reference",
            inline=False,
        )
        embed.add_field(
            name="",
            value=(
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "**That's everything.**\n"
                "Now go talk, reply, tag, share, and climb. 🚀"
            ),
            inline=False,
        )
        embed.set_footer(text="The Circle • Your rank is your legacy")
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(Info(bot))
