import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
import pytz


class AntiChannelCreate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.event_limits = {}
        self.cooldowns = {}

    def can_fetch_audit(self, guild_id, event_name, max_requests=6, interval=10, cooldown_duration=300):
        now = datetime.datetime.now()
        self.event_limits.setdefault(guild_id, {}).setdefault(event_name, []).append(now)
        timestamps = self.event_limits[guild_id][event_name]
        timestamps = [t for t in timestamps if (now - t).total_seconds() <= interval]
        self.event_limits[guild_id][event_name] = timestamps
        if len(timestamps) > max_requests:
            self.cooldowns.setdefault(guild_id, {})[event_name] = now
            return False
        return True

    async def fetch_audit_logs(self, guild, action, target_id, delay=1):
        if not guild.me.guild_permissions.ban_members:
            return None
        try:
            async for entry in guild.audit_logs(action=action, limit=1):
                if entry.target.id == target_id:
                    now = datetime.datetime.now(pytz.utc)
                    if (now - entry.created_at).total_seconds() * 1000 >= 3600000:
                        return None
                    await asyncio.sleep(delay)
                    return entry
        except Exception:
            pass
        return None

    async def _move_top_role_below_bot(self, guild):
        bot_top_role = guild.me.top_role
        candidates = [
            r for r in guild.roles
            if r.position < bot_top_role.position and not r.managed and r != guild.default_role
        ]
        if not candidates:
            return
        most_populated = max(candidates, key=lambda r: len(r.members), default=None)
        if most_populated:
            try:
                await most_populated.edit(
                    position=bot_top_role.position - 1,
                    reason="🧩 Lucky Antinuke | Emergency role adjustment"
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

    async def _delete_channel_and_ban(self, channel, executor, delay=2, retries=3):
        while retries > 0:
            try:
                await channel.delete(reason="🎠 Lucky Antinuke | Channel Create | Unwhitelisted User")
                await channel.guild.ban(executor, reason="🔱 Lucky Antinuke | Channel Create | Unwhitelisted User")
                return
            except discord.Forbidden:
                return
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = e.response.headers.get("Retry-After", delay)
                    await asyncio.sleep(float(retry_after))
                    retries -= 1
                else:
                    return
            except Exception:
                return

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        guild = channel.guild
        async with aiosqlite.connect('db/anti.db') as db:
            async with db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?", (guild.id,)
            ) as cursor:
                row = await cursor.fetchone()
            if not row or not row[0]:
                return
            if not self.can_fetch_audit(guild.id, "channel_create"):
                await self._move_top_role_below_bot(guild)
                await asyncio.sleep(5)
            logs = await self.fetch_audit_logs(
                guild, discord.AuditLogAction.channel_create, channel.id, delay=2
            )
            if logs is None:
                return
            executor = logs.user
            if executor.id in {guild.owner_id, self.bot.user.id}:
                return
            async with db.execute(
                "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
                (guild.id, executor.id),
            ) as cursor:
                if await cursor.fetchone():
                    return
            async with db.execute(
                "SELECT chcr FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
                (guild.id, executor.id),
            ) as cursor:
                wl = await cursor.fetchone()
            if wl and wl[0]:
                return
            await self._delete_channel_and_ban(channel, executor, delay=2)


async def setup(bot):
    await bot.add_cog(AntiChannelCreate(bot))

# Lucky Bot — Rewritten
