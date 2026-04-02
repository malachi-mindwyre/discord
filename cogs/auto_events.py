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
        "name": "💪 MOTIVATION MONDAY",
        "channels": ["fitness", "work"],
        "prompts": [
            "What's your #1 goal this week? Drop it below and hold yourself accountable. 💪",
            "Monday motivation: What's one thing you're grateful for right now?",
            "New week, new grind. What are you working on? Share your goals. 🎯",
            "Quote that keeps you going? Drop it. Motivate someone else today.",
            "What's the hardest thing you overcame last week? Flex on it. 💪",
        ],
    },
    1: {  # Tuesday
        "name": "🧠 TRIVIA TUESDAY",
        "channels": ["general"],
        "prompts": None,  # Handled by trivia.py
        "announcement": "🧠 **TRIVIA TUESDAY** is starting! Head to #general for 10 trivia questions. First correct answer wins!",
    },
    2: {  # Wednesday
        "name": "🔮 CONFESSION WEDNESDAY",
        "channels": ["general"],
        "prompts": [
            "🔮 It's **Confession Wednesday**. Got something on your mind? DM Keeper with `!confess <your confession>` and let it out. 100% anonymous.",
            "🔮 **Confession Wednesday** is here. The Circle listens without judgment. DM `!confess` to Keeper.",
            "🔮 What's your deepest confession? DM Keeper: `!confess <text>`. Nobody will know. The Circle keeps your secrets.",
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
        "name": "😂 MEME FRIDAY",
        "channels": ["memes"],
        "prompts": [
            "😂 **MEME FRIDAY** — Post your best meme. Most reactions wins bragging rights. 🏆",
            "😂 It's **Meme Friday**! Drop the funniest meme you've got. Winner = most reactions.",
            "😂 **MEME COMPETITION** — Best meme posted today gets crowned. Go. 🏆",
        ],
    },
    5: {  # Saturday
        "name": "🎤 VC SATURDAY",
        "channels": ["general"],
        "prompts": [
            "🎤 **VC SATURDAY** — Voice channels are open. Pull up. Talk to real humans for once.",
            "🎤 It's **VC Saturday**. Jump in a voice channel. You earn points just for hanging out.",
            "🎤 **VC Saturday** is live. Get in voice. Earn points. Make friends. Simple.",
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
