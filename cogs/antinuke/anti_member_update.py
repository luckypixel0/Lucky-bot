import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
import pytz


class AntiMemberUpdate(commands.Cog):
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

    async def fetch_audit_logs(self, guild, action, target_id):
        if not guild.me.guild_permissions.ban_members:
            return None
        try:
            async for entry in guild.audit_logs(action=action, limit=1):
                if entry.target.id == target_id:
                    now = datetime.datetime.now(pytz.utc)
                    if (now - entry.created_at).total_seconds() * 1000 < 3600000:
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

    # Dangerous permissions that should trigger antinuke
    DANGEROUS_PERMS = (
        "ban_members",
        "administrator",
        "manage_guild",
        "manage_channels",
        "manage_roles",
        "mention_everyone",
        "manage_webhooks",
    )

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        guild = before.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        async with aiosqlite.connect('db/anti.db') as db:
            async with db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?", (guild.id,)
            ) as cursor:
                row = await cursor.fetchone()
            if not row or not row[0]:
                return
        if not self.can_fetch_audit(guild.id, "member_update"):
            return
        log_entry = await self.fetch_audit_logs(
            guild, discord.AuditLogAction.member_role_update, after.id
        )
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
                "SELECT memup FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
                (guild.id, executor.id),
            ) as cursor:
                wl = await cursor.fetchone()
            if wl and wl[0]:
                return

        # Find the newly added role
        try:
            new_role = next(r for r in after.roles if r not in before.roles)
        except StopIteration:
            return

        # Only act if the role carries dangerous permissions
        if any(getattr(new_role.permissions, perm, False) for perm in self.DANGEROUS_PERMS):
            await self._revert_and_ban(after, executor, new_role)
            await asyncio.sleep(3)

    async def _revert_and_ban(self, member, executor, new_role, retries=3):
        reason = "🔱 Lucky Antinuke | Dangerous Role Assigned | Unwhitelisted User"
        while retries > 0:
            try:
                await member.remove_roles(new_role, reason=reason)
                await member.guild.ban(executor, reason=reason)
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
    await bot.add_cog(AntiMemberUpdate(bot))

# Lucky Bot — Rewritten
