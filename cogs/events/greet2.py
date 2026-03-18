import discord
import aiosqlite
import json
import re
import asyncio
from discord.ext import commands


class greet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.join_queue: dict = {}
        self.processing: set = set()

    async def safe_format(self, text: str, placeholders: dict) -> str:
        lower_ph = {k.lower(): v for k, v in placeholders.items()}

        def replace_var(match):
            key = match.group(1).lower()
            return str(lower_ph.get(key, f"{{{key}}}"))

        return re.sub(r"\{(\w+)\}", replace_var, text or "")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        gid = member.guild.id
        self.join_queue.setdefault(gid, []).append(member)
        if gid not in self.processing:
            self.processing.add(gid)
            await self._process_queue(member.guild)

    async def _process_queue(self, guild: discord.Guild):
        while self.join_queue.get(guild.id):
            member = self.join_queue[guild.id].pop(0)
            async with aiosqlite.connect("db/welcome.db") as db:
                async with db.execute(
                    "SELECT welcome_type, welcome_message, channel_id, embed_data, auto_delete_duration "
                    "FROM welcome WHERE guild_id = ?",
                    (guild.id,),
                ) as cursor:
                    row = await cursor.fetchone()

            if not row:
                continue

            welcome_type, welcome_message, channel_id, embed_data, auto_delete = row
            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue

            placeholders = {
                "user": member.mention,
                "user_avatar": member.avatar.url if member.avatar else member.default_avatar.url,
                "user_name": member.name,
                "user_id": str(member.id),
                "user_nick": member.display_name,
                "user_joindate": member.joined_at.strftime("%a, %b %d, %Y") if member.joined_at else "Unknown",
                "user_createdate": member.created_at.strftime("%a, %b %d, %Y"),
                "server_name": guild.name,
                "server_id": str(guild.id),
                "server_membercount": str(guild.member_count),
                "server_icon": guild.icon.url if guild.icon else "",
                "timestamp": discord.utils.format_dt(discord.utils.utcnow()),
            }

            try:
                sent = None
                if welcome_type == "simple" and welcome_message:
                    content = await self.safe_format(welcome_message, placeholders)
                    sent = await channel.send(content=content)

                elif welcome_type == "embed" and embed_data:
                    info = json.loads(embed_data)
                    color_raw = info.get("color", None)
                    color = 0x2F3136
                    if isinstance(color_raw, str) and color_raw.startswith("#"):
                        color = int(color_raw.lstrip("#"), 16)
                    elif isinstance(color_raw, int):
                        color = color_raw

                    content = await self.safe_format(info.get("message", ""), placeholders) or None
                    embed = discord.Embed(
                        title=await self.safe_format(info.get("title", ""), placeholders),
                        description=await self.safe_format(info.get("description", ""), placeholders),
                        color=color,
                    )
                    embed.timestamp = discord.utils.utcnow()

                    if info.get("footer_text"):
                        embed.set_footer(
                            text=await self.safe_format(info["footer_text"], placeholders),
                            icon_url=await self.safe_format(info.get("footer_icon", ""), placeholders),
                        )
                    else:
                        embed.set_footer(text="Lucky Bot • lucky.gg")

                    if info.get("author_name"):
                        embed.set_author(
                            name=await self.safe_format(info["author_name"], placeholders),
                            icon_url=await self.safe_format(info.get("author_icon", ""), placeholders),
                        )
                    if info.get("thumbnail"):
                        embed.set_thumbnail(url=await self.safe_format(info["thumbnail"], placeholders))
                    if info.get("image"):
                        embed.set_image(url=await self.safe_format(info["image"], placeholders))

                    sent = await channel.send(content=content, embed=embed)

                if sent and auto_delete:
                    await sent.delete(delay=auto_delete)

            except discord.Forbidden:
                continue
            except discord.HTTPException as e:
                if e.code == 50035 or e.status == 429:
                    await asyncio.sleep(1)
                    self.join_queue.setdefault(guild.id, []).append(member)
                    continue

            await asyncio.sleep(2)

        self.processing.discard(guild.id)

# Lucky Bot — Rewritten
