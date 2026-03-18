import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
from datetime import timedelta


class AntiEveryone(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.event_limits = {}

    def can_act(self, guild_id, event_name, max_requests=5, interval=10):
        now = datetime.datetime.now()
        self.event_limits.setdefault(guild_id, {}).setdefault(event_name, []).append(now)
        timestamps = self.event_limits[guild_id][event_name]
        timestamps = [t for t in timestamps if (now - t).total_seconds() <= interval]
        self.event_limits[guild_id][event_name] = timestamps
        return len(timestamps) <= max_requests

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or not message.mention_everyone:
            return
        guild = message.guild
        async with aiosqlite.connect('db/anti.db') as db:
            async with db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?", (guild.id,)
            ) as cursor:
                row = await cursor.fetchone()
            if not row or not row[0]:
                return
            if message.author.id in {guild.owner_id, self.bot.user.id}:
                return
            async with db.execute(
                "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
                (guild.id, message.author.id),
            ) as cursor:
                if await cursor.fetchone():
                    return
            async with db.execute(
                "SELECT meneve FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
                (guild.id, message.author.id),
            ) as cursor:
                wl = await cursor.fetchone()
            if wl and wl[0]:
                return
            if not self.can_act(guild.id, "mention_everyone"):
                return
            try:
                await self._timeout_user(message.author)
                await self._delete_everyone_messages(message.channel)
            except Exception:
                pass

    async def _timeout_user(self, member, retries=3):
        duration = 60 * 60  # 1 hour
        while retries > 0:
            try:
                await member.edit(
                    timed_out_until=discord.utils.utcnow() + timedelta(seconds=duration),
                    reason="🔱 Lucky Antinuke | @everyone Mention | Unwhitelisted User",
                )
                return
            except discord.Forbidden:
                return
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        await asyncio.sleep(float(retry_after))
                        retries -= 1
                else:
                    return
            except discord.errors.RateLimited as e:
                await asyncio.sleep(e.retry_after)
                retries -= 1
            except Exception:
                return

    async def _delete_everyone_messages(self, channel, retries=3):
        while retries > 0:
            try:
                async for msg in channel.history(limit=100):
                    if msg.mention_everyone:
                        await msg.delete()
                        await asyncio.sleep(3)
                return
            except discord.Forbidden:
                return
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        await asyncio.sleep(float(retry_after))
                        retries -= 1
                else:
                    return
            except discord.errors.RateLimited as e:
                await asyncio.sleep(e.retry_after)
                retries -= 1
            except Exception:
                return


async def setup(bot):
    await bot.add_cog(AntiEveryone(bot))

# Lucky Bot — Rewritten
