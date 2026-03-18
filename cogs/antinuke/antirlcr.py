import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
import pytz


class AntiRoleCreate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.event_limits = {}
        self.cooldowns = {}

    def can_fetch_audit(self, guild_id, event_name, max_requests=5, interval=10, cooldown_duration=300):
        now = datetime.datetime.now()
        self.event_limits.setdefault(guild_id, {}).setdefault(event_name, []).append(now)
        timestamps = self.event_limits[guild_id][event_name]
        timestamps = [t for t in timestamps if (now - t).total_seconds() <= interval]
        self.event_limits[guild_id][event_name] = timestamps
        if guild_id in self.cooldowns and event_name in self.cooldowns[guild_id]:
            if (now - self.cooldowns[guild_id][event_name]).total_seconds() < cooldown_duration:
                return False
            del self.cooldowns[guild_id][event_name]
        if len(timestamps) > max_requests:
            self.cooldowns.setdefault(guild_id, {})[event_name] = now
            return False
        return True

    async def fetch_audit_logs(self, guild, action):
        if not guild.me.guild_permissions.ban_members:
            return None
        try:
            async for entry in guild.audit_logs(action=action, limit=1):
                now = datetime.datetime.now(pytz.utc)
                if (now - entry.created_at).total_seconds() * 1000 >= 3600000:
                    return None
                return entry
        except Exception:
            pass
        return None

    async def is_blacklisted_guild(self, guild_id):
        async with aiosqlite.connect('db/block.db') as db:
            cursor = await db.execute(
                "SELECT 1 FROM guild_blacklist WHERE guild_id = ?", (str(guild_id),)
            )
            return await cursor.fetchone() is not None

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        guild = role.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        async with aiosqlite.connect('db/anti.db') as db:
            async with db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?", (guild.id,)
            ) as cursor:
                row = await cursor.fetchone()
            if not row or not row[0]:
                return
        if not self.can_fetch_audit(guild.id, "role_create"):
            return
        log_entry = await self.fetch_audit_logs(guild, discord.AuditLogAction.role_create)
        if log_entry is None:
            return
        executor = log_entry.user
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        async with aiosqlite.connect('db/anti.db') as db:
            async with db.execute(
                "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
                (guild.id, executor.id),
            ) as cursor:
                if await cursor.fetchone():
                    return
            async with db.execute(
                "SELECT rlcr FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
                (guild.id, executor.id),
            ) as cursor:
                wl = await cursor.fetchone()
            if wl and wl[0]:
                return
        await self._ban_and_delete_role(guild, executor, role)
        await asyncio.sleep(3)

    async def _ban_and_delete_role(self, guild, executor, role, retries=3):
        while retries > 0:
            try:
                await guild.ban(
                    executor, reason="🔱 Lucky Antinuke | Role Create | Unwhitelisted User"
                )
                await role.delete(reason="🎪 Lucky Antinuke | Role created by unwhitelisted user")
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
    await bot.add_cog(AntiRoleCreate(bot))

# Lucky Bot — Rewritten
