import discord
from discord.ext import commands
import aiosqlite
import re
from datetime import timedelta
import asyncio


class AntiEmojiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji_threshold = 5
        self.emoji_pattern = re.compile(
            r"<a?:[a-zA-Z0-9_]+:[0-9]+>|"
            r"[\U0001F600-\U0001F64F]|[\U0001F300-\U0001F5FF]|"
            r"[\U0001F680-\U0001F6FF]|[\U0001F700-\U0001F77F]|"
            r"[\U0001F780-\U0001F7FF]|[\U0001F800-\U0001F8FF]|"
            r"[\U0001F900-\U0001F9FF]|[\U0001FA00-\U0001FAFF]|"
            r"[\U00002700-\U000027BF]|[\U0001F1E6-\U0001F1FF]|"
            r"[\U0001F004-\U0001F0CF]|[\U0001F9B0-\U0001F9FF]"
        )

    # ── DB helpers ────────────────────────────────────────────────────────────

    async def _automod_enabled(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            cur = await db.execute("SELECT enabled FROM automod WHERE guild_id = ?", (guild_id,))
            row = await cur.fetchone()
            return row is not None and row[0] == 1

    async def _feature_enabled(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            cur = await db.execute(
                "SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = 'Anti emoji spam'",
                (guild_id,),
            )
            return await cur.fetchone() is not None

    async def _ignored_channels(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            cur = await db.execute(
                "SELECT id FROM automod_ignored WHERE guild_id = ? AND type = 'channel'", (guild_id,)
            )
            return [r[0] for r in await cur.fetchall()]

    async def _ignored_roles(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            cur = await db.execute(
                "SELECT id FROM automod_ignored WHERE guild_id = ? AND type = 'role'", (guild_id,)
            )
            return [r[0] for r in await cur.fetchall()]

    async def _punishment(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            cur = await db.execute(
                "SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = 'Anti emoji spam'",
                (guild_id,),
            )
            row = await cur.fetchone()
            return row[0] if row else None

    async def _log(self, guild, user, channel, action, reason):
        async with aiosqlite.connect("db/automod.db") as db:
            cur = await db.execute(
                "SELECT log_channel FROM automod_logging WHERE guild_id = ?", (guild.id,)
            )
            row = await cur.fetchone()
        if not row or not row[0]:
            return
        log_ch = guild.get_channel(row[0])
        if not log_ch:
            return
        embed = discord.Embed(title="🧩 Lucky Automod — Anti Emoji Spam", color=0xFF4444)
        embed.add_field(name="🎭 User", value=user.mention, inline=True)
        embed.add_field(name="⚜️ Action", value=action, inline=True)
        embed.add_field(name="🎠 Channel", value=channel.mention, inline=True)
        embed.add_field(name="📜 Reason", value=reason, inline=False)
        embed.set_footer(text=f"Lucky Bot • lucky.gg | User ID: {user.id}")
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        try:
            await log_ch.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ── Listener ──────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return
        guild, user, channel = message.guild, message.author, message.channel
        if not await self._automod_enabled(guild.id) or not await self._feature_enabled(guild.id):
            return
        if user.id in {guild.owner_id, self.bot.user.id}:
            return
        if channel.id in await self._ignored_channels(guild.id):
            return
        if any(r.id in await self._ignored_roles(guild.id) for r in user.roles):
            return

        emoji_count = len(self.emoji_pattern.findall(message.content))
        if emoji_count <= self.emoji_threshold:
            return

        punishment = await self._punishment(guild.id)
        action_taken = None
        reason = f"Emoji Spam ({emoji_count} emojis)"
        try:
            if punishment == "Mute":
                await user.edit(
                    timed_out_until=discord.utils.utcnow() + timedelta(minutes=1), reason=reason
                )
                action_taken = "Muted for 1 minute"
            elif punishment == "Kick":
                await user.kick(reason=reason)
                action_taken = "Kicked"
            elif punishment == "Ban":
                await user.ban(reason=reason)
                action_taken = "Banned"
            await message.delete()
            embed = discord.Embed(
                description=f"🍀 {user.mention} has been **{action_taken}** for **Emoji Spam**.",
                color=0xFF4444,
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await channel.send(embed=embed, delete_after=30)
            await self._log(guild, user, channel, action_taken, reason)
        except (discord.Forbidden, discord.HTTPException, Exception):
            pass


async def setup(bot):
    await bot.add_cog(AntiEmojiSpam(bot))

# Lucky Bot — Rewritten
