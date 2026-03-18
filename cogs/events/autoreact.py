import discord
import asyncio
import aiosqlite
import re
from discord.ext import commands


class AutoReactListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = "db/autoreact.db"
        self.rate_limited_users: set = set()

    async def _get_triggers(self, guild_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT trigger, emojis FROM autoreact WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                return await cursor.fetchall()

    async def _rate_limit_user(self, user_id: int):
        self.rate_limited_users.add(user_id)
        await asyncio.sleep(5)
        self.rate_limited_users.discard(user_id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.author.id in self.rate_limited_users:
            return

        triggers = await self._get_triggers(message.guild.id)
        if not triggers:
            return

        content = message.content.strip().lower()
        for trigger, emojis in triggers:
            if content != trigger:
                continue
            for emoji_str in emojis.split():
                try:
                    if re.match(r"<a?:\w+:\d+>", emoji_str):
                        emoji_obj = discord.PartialEmoji.from_str(emoji_str)
                    else:
                        emoji_obj = emoji_str
                    await message.add_reaction(emoji_obj)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    continue

            asyncio.create_task(self._rate_limit_user(message.author.id))
            break

# Lucky Bot — Rewritten
