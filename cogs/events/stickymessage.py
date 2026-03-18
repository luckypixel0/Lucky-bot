import discord
import aiosqlite
import json
import asyncio
from discord.ext import commands


class StickyMessageListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.processing_channels: set = set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.channel.id in self.processing_channels:
            return

        async with aiosqlite.connect("db/stickymessages.db") as db:
            async with db.execute(
                """
                SELECT id, message_type, message_content, embed_data, last_message_id,
                       enabled, delay_seconds, auto_delete_after, ignore_bots,
                       ignore_commands, trigger_count, current_count
                FROM sticky_messages
                WHERE guild_id = ? AND channel_id = ? AND enabled = 1
                """,
                (message.guild.id, message.channel.id),
            ) as cursor:
                sticky = await cursor.fetchone()

        if not sticky:
            return

        (
            sticky_id, msg_type, msg_content, embed_data, last_msg_id,
            enabled, delay_seconds, auto_delete_after, ignore_bots,
            ignore_commands, trigger_count, current_count,
        ) = sticky

        if ignore_commands and message.content.startswith(await self._get_prefix(message)):
            return

        self.processing_channels.add(message.channel.id)
        try:
            new_count = current_count + 1
            if new_count >= trigger_count:
                await self._update_counter(message.guild.id, message.channel.id, 0)

                if last_msg_id:
                    try:
                        old = await message.channel.fetch_message(last_msg_id)
                        await old.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass

                await asyncio.sleep(delay_seconds)
                new_msg = await self._send_sticky(message.channel, msg_type, msg_content, embed_data)

                if new_msg:
                    async with aiosqlite.connect("db/stickymessages.db") as db:
                        await db.execute(
                            "UPDATE sticky_messages SET last_message_id = ? WHERE guild_id = ? AND channel_id = ?",
                            (new_msg.id, message.guild.id, message.channel.id),
                        )
                        await db.commit()
                    if auto_delete_after > 0:
                        asyncio.create_task(self._auto_delete(new_msg, auto_delete_after))
            else:
                await self._update_counter(message.guild.id, message.channel.id, new_count)
        except Exception:
            pass
        finally:
            self.processing_channels.discard(message.channel.id)

    async def _get_prefix(self, message: discord.Message) -> str:
        try:
            async with aiosqlite.connect("db/prefix.db") as db:
                async with db.execute(
                    "SELECT prefix FROM prefixes WHERE guild_id = ?", (message.guild.id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else ">"
        except Exception:
            return ">"

    async def _update_counter(self, guild_id: int, channel_id: int, count: int):
        async with aiosqlite.connect("db/stickymessages.db") as db:
            await db.execute(
                "UPDATE sticky_messages SET current_count = ? WHERE guild_id = ? AND channel_id = ?",
                (count, guild_id, channel_id),
            )
            await db.commit()

    async def _send_sticky(
        self, channel: discord.TextChannel, msg_type: str, msg_content: str, embed_data: str
    ):
        try:
            if msg_type == "plain" and msg_content:
                return await channel.send(content=msg_content)

            elif msg_type == "embed" and embed_data:
                data = json.loads(embed_data)
                embed = discord.Embed(color=0x2F3136)

                if data.get("title"):
                    embed.title = data["title"]
                if data.get("description"):
                    embed.description = data["description"]
                if data.get("color"):
                    try:
                        c = data["color"]
                        embed.color = discord.Color(int(c.lstrip("#"), 16)) if c.startswith("#") else embed.color
                    except Exception:
                        pass
                embed.set_footer(
                    text=data.get("footer", "Lucky Bot • lucky.gg")
                )
                embed.timestamp = discord.utils.utcnow()
                return await channel.send(embed=embed)

        except (discord.Forbidden, discord.HTTPException, json.JSONDecodeError):
            pass
        return None

    async def _auto_delete(self, message: discord.Message, delay: int):
        try:
            await asyncio.sleep(delay)
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        try:
            async with aiosqlite.connect("db/stickymessages.db") as db:
                await db.execute("DELETE FROM sticky_messages WHERE channel_id = ?", (channel.id,))
                await db.commit()
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        try:
            async with aiosqlite.connect("db/stickymessages.db") as db:
                await db.execute("DELETE FROM sticky_messages WHERE guild_id = ?", (guild.id,))
                await db.execute("DELETE FROM sticky_settings WHERE guild_id = ?", (guild.id,))
                await db.commit()
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(StickyMessageListener(bot))

# Lucky Bot — Rewritten
