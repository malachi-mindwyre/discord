"""
The Circle — Media Feed Cog
Scrapes all scored channels for media content and mirrors it to #media-feed.
"""

import re

import discord
from discord.ext import commands

from config import EXCLUDED_CHANNELS, EMBED_COLOR_PRIMARY

# URL patterns that count as media embeds
MEDIA_URL_PATTERNS = [
    re.compile(r"https?://(?:www\.)?youtube\.com/watch\S+", re.IGNORECASE),
    re.compile(r"https?://youtu\.be/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?twitter\.com/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?x\.com/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?tiktok\.com/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:vm\.)?tiktok\.com/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?reddit\.com/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?instagram\.com/\S+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?twitch\.tv/\S+", re.IGNORECASE),
    re.compile(r"https?://\S+\.(?:gif|png|jpg|jpeg|webp|mp4|mov|webm)", re.IGNORECASE),
    re.compile(r"https?://tenor\.com/\S+", re.IGNORECASE),
    re.compile(r"https?://giphy\.com/\S+", re.IGNORECASE),
    re.compile(r"https?://imgur\.com/\S+", re.IGNORECASE),
    re.compile(r"https?://streamable\.com/\S+", re.IGNORECASE),
    re.compile(r"https?://medal\.tv/\S+", re.IGNORECASE),
]


class MediaFeed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Dedup: track recently mirrored message IDs to prevent double posts
        self._recent_mirrors: set[int] = set()
        self._recent_mirrors_limit = 100

    def _has_media(self, message: discord.Message) -> bool:
        """Check if a message contains any media content."""
        # Direct attachments (images, videos, files)
        if message.attachments:
            return True

        # Discord auto-embeds (YouTube, Twitter, etc.)
        if message.embeds:
            for embed in message.embeds:
                if embed.type in ("image", "video", "gifv", "rich", "article"):
                    return True

        # URL patterns in message text
        if message.content:
            for pattern in MEDIA_URL_PATTERNS:
                if pattern.search(message.content):
                    return True

        return False

    def _extract_media_urls(self, message: discord.Message) -> list[str]:
        """Extract all media URLs from a message."""
        urls = []

        # Attachment URLs
        for att in message.attachments:
            urls.append(att.url)

        # URLs from message content
        if message.content:
            for pattern in MEDIA_URL_PATTERNS:
                urls.extend(pattern.findall(message.content))

        return urls

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots, DMs, media-feed itself, and excluded channels
        if message.author.bot or not message.guild:
            return
        if message.channel.name in EXCLUDED_CHANNELS:
            return
        if message.channel.name == "media-feed":
            return

        if not self._has_media(message):
            return

        # Dedup: skip if we already mirrored this message
        if message.id in self._recent_mirrors:
            return
        self._recent_mirrors.add(message.id)
        if len(self._recent_mirrors) > self._recent_mirrors_limit:
            # Remove oldest entries
            excess = len(self._recent_mirrors) - self._recent_mirrors_limit
            for _ in range(excess):
                self._recent_mirrors.pop()

        # Find the media-feed channel
        feed_channel = discord.utils.get(message.guild.text_channels, name="media-feed")
        if not feed_channel:
            return

        # Build the mirror embed
        embed = discord.Embed(
            description=message.content[:200] if message.content else "",
            color=EMBED_COLOR_PRIMARY,
            timestamp=message.created_at,
        )
        embed.set_author(
            name=f"{message.author.display_name} in #{message.channel.name}",
            icon_url=message.author.display_avatar.url,
        )

        # Add image if there's an attachment
        image_set = False
        for att in message.attachments:
            if att.content_type and att.content_type.startswith("image/"):
                if not image_set:
                    embed.set_image(url=att.url)
                    image_set = True
                else:
                    embed.add_field(name="📎", value=f"[Image]({att.url})", inline=True)
            elif att.content_type and att.content_type.startswith("video/"):
                embed.add_field(name="🎥", value=f"[Video]({att.url})", inline=True)
            else:
                embed.add_field(name="📄", value=f"[{att.filename}]({att.url})", inline=True)

        # If no image from attachments, try embeds
        if not image_set and message.embeds:
            for msg_embed in message.embeds:
                if msg_embed.thumbnail and msg_embed.thumbnail.url:
                    embed.set_image(url=msg_embed.thumbnail.url)
                    image_set = True
                    break
                elif msg_embed.image and msg_embed.image.url:
                    embed.set_image(url=msg_embed.image.url)
                    image_set = True
                    break

        # Add link to original message
        embed.add_field(
            name="",
            value=f"[↗️ Jump to message]({message.jump_url})",
            inline=False,
        )

        try:
            await feed_channel.send(embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(MediaFeed(bot))
