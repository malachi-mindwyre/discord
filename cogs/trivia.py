"""
The Circle — Trivia Cog
Auto trivia game for Trivia Tuesday + on-demand !trivia command.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import (
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_ACCENT,
    AUTO_EVENT_HOUR,
    TRIVIA_POINTS_CORRECT,
    TRIVIA_QUESTIONS_PER_ROUND,
    TRIVIA_ANSWER_SECONDS,
    TRIVIA_QUESTIONS,
)
from database import DB_PATH, update_user_score


class Trivia(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._active_game: bool = False
        self.tuesday_trivia.start()

    def cog_unload(self):
        self.tuesday_trivia.cancel()

    @tasks.loop(hours=1)
    async def tuesday_trivia(self):
        """Auto-start trivia on Tuesdays."""
        now = datetime.utcnow()
        if now.weekday() != 1 or now.hour != AUTO_EVENT_HOUR:
            return

        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name="general")
            if channel:
                await self._run_trivia(channel, TRIVIA_QUESTIONS_PER_ROUND)

    @tuesday_trivia.before_loop
    async def before_trivia(self):
        await self.bot.wait_until_ready()

    @commands.command(name="trivia")
    @commands.has_permissions(administrator=True)
    async def trivia_cmd(self, ctx: commands.Context, count: int = 5):
        """Start a trivia round. Admin only. Usage: !trivia [count]"""
        count = min(max(count, 1), len(TRIVIA_QUESTIONS))
        await self._run_trivia(ctx.channel, count)

    async def _run_trivia(self, channel: discord.TextChannel, question_count: int):
        """Run a trivia game in a channel."""
        if self._active_game:
            try:
                await channel.send("⚫ A trivia game is already in progress!")
            except discord.HTTPException:
                pass
            return

        self._active_game = True
        questions = random.sample(TRIVIA_QUESTIONS, min(question_count, len(TRIVIA_QUESTIONS)))

        embed = discord.Embed(
            title="🧠 TRIVIA TIME",
            description=(
                f"**{len(questions)} questions** incoming!\n"
                f"First to type the correct answer wins **{TRIVIA_POINTS_CORRECT} pts** per question.\n"
                f"You have **{TRIVIA_ANSWER_SECONDS} seconds** per question.\n\n"
                f"Starting in 5 seconds..."
            ),
            color=EMBED_COLOR_ACCENT,
        )
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            self._active_game = False
            return

        await asyncio.sleep(5)

        scoreboard: dict[int, int] = {}  # user_id -> correct_count

        for i, q in enumerate(questions, 1):
            # Post question
            options_text = "\n".join(f"  **{chr(65+j)}.** {opt}" for j, opt in enumerate(q["options"]))
            q_embed = discord.Embed(
                title=f"❓ Question {i}/{len(questions)}",
                description=f"{q['q']}\n\n{options_text}",
                color=EMBED_COLOR_PRIMARY,
            )
            q_embed.set_footer(text=f"{TRIVIA_ANSWER_SECONDS}s to answer • Type the answer or letter")

            try:
                await channel.send(embed=q_embed)
            except discord.HTTPException:
                continue

            # Wait for correct answer
            correct = q["a"].lower()
            # Also accept letter answers
            correct_idx = q["options"].index(q["a"])
            correct_letter = chr(65 + correct_idx).lower()

            def check(m: discord.Message) -> bool:
                if m.channel.id != channel.id or m.author.bot:
                    return False
                answer = m.content.strip().lower()
                return answer == correct or answer == correct_letter

            try:
                winner_msg = await self.bot.wait_for("message", check=check, timeout=TRIVIA_ANSWER_SECONDS)
                winner = winner_msg.author

                # Award points
                scoreboard[winner.id] = scoreboard.get(winner.id, 0) + 1
                await update_user_score(winner.id, TRIVIA_POINTS_CORRECT)

                # Update trivia scores table
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        """INSERT INTO trivia_scores (user_id, correct_count, total_played)
                           VALUES (?, 1, 1)
                           ON CONFLICT(user_id) DO UPDATE SET
                           correct_count = correct_count + 1, total_played = total_played + 1""",
                        (winner.id,),
                    )
                    await db.commit()

                try:
                    await channel.send(
                        f"✅ **{winner.display_name}** got it! The answer was **{q['a']}**. "
                        f"(+{TRIVIA_POINTS_CORRECT} pts)"
                    )
                except discord.HTTPException:
                    pass

            except asyncio.TimeoutError:
                try:
                    await channel.send(f"⏰ Time's up! The answer was **{q['a']}**.")
                except discord.HTTPException:
                    pass

            # Brief pause between questions
            if i < len(questions):
                await asyncio.sleep(3)

        # Final scoreboard
        if scoreboard:
            sorted_scores = sorted(scoreboard.items(), key=lambda x: x[1], reverse=True)
            lines = []
            for rank, (uid, count) in enumerate(sorted_scores, 1):
                member = channel.guild.get_member(uid)
                name = member.display_name if member else f"User {uid}"
                lines.append(f"**#{rank}** {name} — {count} correct ({count * TRIVIA_POINTS_CORRECT} pts)")

            result_embed = discord.Embed(
                title="🏆 TRIVIA RESULTS",
                description="\n".join(lines),
                color=EMBED_COLOR_ACCENT,
            )
            try:
                await channel.send(embed=result_embed)
            except discord.HTTPException:
                pass
        else:
            try:
                await channel.send("⚫ No correct answers this round. The Circle is disappointed.")
            except discord.HTTPException:
                pass

        self._active_game = False


async def setup(bot: commands.Bot):
    await bot.add_cog(Trivia(bot))
