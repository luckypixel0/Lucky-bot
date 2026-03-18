import discord
from discord.ext import commands
import aiosqlite
import asyncio
from datetime import timedelta
import re


class AntiLink(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.link_pattern = re.compile(r"https?://\S+")
        self.invite_pattern = re.compile(
            r"(https?://)?(www\.)?(discord\.(gg|io|me|li)|discordapp\.com/invite|discord\.com/invite)/\S+"
        )
        self.gif_pattern = re.compile(
            r"(\.gif$|^https://(tenor\.com|giphy\.com/gifs|cdn\.discordapp\.com|media\.discordapp\.net))"
        )
        self.spotify_pattern = re.compile(r"^https://open\.spotify\.com/track/\S+")

    async def _automod_enabled(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            cur = await db.execute("SELECT enabled FROM automod WHERE guild_id = ?", (guild_id,))
            row = await cur.fetchone()
            return row is not None and row[0] == 1

    async def _feature_enabled(self, guild_id):
        async with aiosqlite.connect("db/automod.db") as db:
            cur = await db.execute(
                "SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = 'Anti link'",
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
                "SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = 'Anti link'",
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
        embed = discord.Embed(title="🧩 Lucky Automod — Anti Link", color=0xFF4444)
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

        if not self.link_pattern.search(message.content):
            return
        # Allow invites, GIFs, and Spotify links
        if (
            self.invite_pattern.search(message.content)
            or self.gif_pattern.search(message.content)
            or self.spotify_pattern.search(message.content)
        ):
            return

        punishment = await self._punishment(guild.id)
        action_taken = None
        reason = "Posted a link"
        try:
            if punishment == "Mute":
                await user.edit(
                    timed_out_until=discord.utils.utcnow() + timedelta(minutes=7), reason=reason
                )
                action_taken = "Muted for 7 minutes"
            elif punishment == "Kick":
                await user.kick(reason=reason)
                action_taken = "Kicked"
            elif punishment == "Ban":
                await user.ban(reason=reason)
                action_taken = "Banned"
            await message.delete()
            embed = discord.Embed(
                description=f"🍀 {user.mention} has been **{action_taken}** for **Posting a Link**.",
                color=0xFF4444,
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await channel.send(embed=embed, delete_after=30)
            await self._log(guild, user, channel, action_taken, reason)
        except (discord.Forbidden, discord.HTTPException, Exception):
            pass


async def setup(bot):
    await bot.add_cog(AntiLink(bot))

# Lucky Bot — Rewritten
