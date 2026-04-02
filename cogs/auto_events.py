"""
The Circle — Auto Events Calendar Cog
Full weekly event schedule — Motivation Monday through Weekly Recap Sunday.
"""

from __future__ import annotations

import random
from datetime import datetime

import discord
from discord.ext import commands, tasks

from config import EMBED_COLOR_PRIMARY, EMBED_COLOR_ACCENT, AUTO_EVENT_HOUR


# Weekly event definitions
WEEKLY_EVENTS = {
    0: {  # Monday
        "name": "😂 MEME MONDAY",
        "channels": ["memes", "general"],
        "prompts": [
            "😂 **MEME MONDAY** — New week, new memes. Post your best. Most reactions wins bragging rights. 🏆",
            "😂 It's **Meme Monday**! Start the week right. Drop the funniest meme you've got.",
            "😂 **MEME MONDAY** — Cure the Monday blues with memes. Best one gets crowned. 🏆",
            "😂 **Meme Monday** is here. Post memes. Get reactions. Earn points. Simple.",
            "😂 Your mission: post a meme that makes at least 3 people react. Go. 🏆",
        ],
    },
    1: {  # Tuesday
        "name": "🧠 TRIVIA TUESDAY",
        "channels": ["general"],
        "prompts": None,  # Handled by trivia.py
        "announcement": "🧠 **TRIVIA TUESDAY** is starting! Head to #general for 10 trivia questions. First correct answer wins!",
    },
    2: {  # Wednesday
        "name": "🧠 WISDOM WEDNESDAY",
        "channels": ["general", "work"],
        "prompts": [
            "🧠 **WISDOM WEDNESDAY** — Best life advice you've ever received? Share it below.",
            "🧠 **Wisdom Wednesday** — What's something you wish you knew 5 years ago?",
            "🧠 What's the most useful skill you've taught yourself? Drop your wisdom. 🧠",
            "🧠 **Wisdom Wednesday** — Give advice to your younger self in one sentence.",
            "🧠 **Real talk:** What's a hard lesson you learned this year? Share it so others don't have to learn it the hard way.",
        ],
    },
    3: {  # Thursday
        "name": "🔥 HOT TAKE THURSDAY",
        "channels": ["general", "politics"],
        "prompts": [
            "🔥 **HOT TAKE THURSDAY** — Drop your most controversial opinion. No holding back.",
            "🔥 **Hot Take:** What's something everyone agrees on that you think is WRONG?",
            "🔥 **Unpopular opinion time.** Say something that would get you cancelled. Go.",
            "🔥 **Hot Take Thursday** — What's overhyped right now? Be honest.",
            "🔥 **Spicy take:** What's a popular thing you genuinely don't understand?",
        ],
    },
    4: {  # Friday
        "name": "💪 FLEX FRIDAY",
        "channels": ["general"],
        "prompts": [
            "💪 **FLEX FRIDAY** — What's your biggest W this week? Brag about it. You earned it.",
            "💪 **Flex Friday** — Show off your achievements. Rank ups, streaks, badges, real life wins. Flex.",
            "💪 It's **Flex Friday**! Check `!profile` and flex your stats. Who's got the highest streak?",
            "💪 **FLEX FRIDAY** — Drop your `!rank` screenshot. Let's see who's been grinding.",
            "💪 What did you accomplish this week? In-server or IRL — this is your moment. 💪",
        ],
    },
    5: {  # Saturday
        "name": "🎉 SOCIAL SATURDAY",
        "channels": ["general"],
        "prompts": [
            "🎉 **SOCIAL SATURDAY** — Tag someone you haven't talked to this week. Start a conversation. 3x reply points!",
            "🎉 It's **Social Saturday**! Jump in voice, tag a friend, or reply to someone new. Social points are boosted.",
            "🎉 **SOCIAL SATURDAY** — The Circle rewards connections. Reply to 3 different people today for a social streak bonus.",
            "🎉 **Social Saturday** — Who's your `!bestfriend`? Tag them. If you don't have one yet, make one today.",
            "🎉 **Social Saturday** is live. Voice channels + reply bonuses. Get in there. 🎤",
        ],
    },
    # Sunday (6) handled by weekly_recap.py
}


class AutoEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.event_loop.start()

    def cog_unload(self):
        self.event_loop.cancel()

    @tasks.loop(hours=1)
    async def event_loop(self):
        """Post the daily event at the scheduled hour."""
        now = datetime.utcnow()
        if now.hour != AUTO_EVENT_HOUR:
            return

        weekday = now.weekday()
        event = WEEKLY_EVENTS.get(weekday)
        if not event:
            return  # Sunday or no event

        for guild in self.bot.guilds:
            # Post announcement if it has one (like Trivia Tuesday)
            if event.get("announcement"):
                general = discord.utils.get(guild.text_channels, name="general")
                if general:
                    try:
                        await general.send(event["announcement"])
                    except discord.HTTPException:
                        pass

            # Post prompts in designated channels
            if event["prompts"]:
                prompt = random.choice(event["prompts"])
                for ch_name in event["channels"]:
                    channel = discord.utils.get(guild.text_channels, name=ch_name)
                    if channel:
                        embed = discord.Embed(
                            title=event["name"],
                            description=prompt,
                            color=EMBED_COLOR_ACCENT,
                        )
                        embed.set_footer(text="The Circle • Reply for 3x points")
                        try:
                            await channel.send(embed=embed)
                        except discord.HTTPException:
                            pass

    @event_loop.before_loop
    async def before_event(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoEvents(bot))
