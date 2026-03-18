import discord
import asyncio
import logging
import aiosqlite
from discord.ext import commands
from core import Lucky, Cog

DATABASE_PATH = "db/autorole.db"
logger = logging.getLogger(__name__)


class Autorole2(Cog):
    def __init__(self, bot: Lucky):
        self.bot = bot

    async def get_autorole(self, guild_id: int) -> dict:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT bots, humans FROM autorole WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return {"bots": [], "humans": []}
                bots_raw, humans_raw = row
                bots = [
                    int(r) for r in bots_raw.strip("[]").replace(" ", "").split(",") if r
                ]
                humans = [
                    int(r) for r in humans_raw.strip("[]").replace(" ", "").split(",") if r
                ]
                return {"bots": bots, "humans": humans}

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        data = await self.get_autorole(member.guild.id)
        roles_to_add = data["bots"] if member.bot else data["humans"]

        for role_id in roles_to_add:
            role = member.guild.get_role(role_id)
            if not role:
                continue
            try:
                await member.add_roles(role, reason="Lucky Autorole")
            except discord.Forbidden:
                logger.warning(f"[Lucky] Missing permissions to add autorole in {member.guild.name}")
            except discord.HTTPException as e:
                if e.status == 429:
                    retry = float(e.response.headers.get("Retry-After", 1))
                    await asyncio.sleep(retry)
                    try:
                        await member.add_roles(role, reason="Lucky Autorole (retry)")
                    except Exception:
                        pass
            except discord.errors.RateLimited as e:
                await asyncio.sleep(e.retry_after)
                try:
                    await member.add_roles(role, reason="Lucky Autorole (retry)")
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"[Lucky] Autorole unexpected error: {e}")

# Lucky Bot — Rewritten
