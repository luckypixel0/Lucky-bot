import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
import pytz


class AntiPrune(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_audit_logs(self, guild, action):
        try:
            async for entry in guild.audit_logs(action=action, limit=1):
                now = datetime.datetime.now(pytz.utc)
                if (now - entry.created_at).total_seconds() * 1000 >= 3600000:
                    return None
                return entry
        except Exception:
            pass
        return None

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        async with aiosqlite.connect('db/anti.db') as db:
            async with db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?", (guild.id,)
            ) as cursor:
                row = await cursor.fetchone()
            if not row or not row[0]:
                return
            log_entry = await self.fetch_audit_logs(guild, discord.AuditLogAction.member_prune)
            if log_entry is None:
                return
            executor = log_entry.user
            if executor.id in {guild.owner_id, self.bot.user.id}:
                return
            async with db.execute(
                "SELECT prune FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
                (guild.id, executor.id),
            ) as cursor:
                wl = await cursor.fetchone()
            if wl and wl[0]:
                return
            async with db.execute(
                "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
                (guild.id, executor.id),
            ) as cursor:
                if await cursor.fetchone():
                    return
            await self._ban_executor(guild, executor)

    async def _ban_executor(self, guild, executor, retries=3):
        while retries > 0:
            try:
                await guild.ban(
                    executor, reason="🔱 Lucky Antinuke | Member Prune | Unwhitelisted User"
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


async def setup(bot):
    await bot.add_cog(AntiPrune(bot))

# Lucky Bot — Rewritten
