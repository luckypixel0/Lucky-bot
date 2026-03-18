import os
import discord
import logging
from discord.ext import commands
from discord.ui import View, Button
from core import Lucky, Cog
from utils.config import serverLink

logging.basicConfig(
    level=logging.INFO,
    format="\x1b[38;5;82m[\x1b[0m%(asctime)s\x1b[38;5;82m]\x1b[0m → %(message)s",
    datefmt="%H:%M:%S",
)

LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))


class Guild(Cog):
    def __init__(self, client: Lucky):
        self.client = client

    @commands.Cog.listener(name="on_guild_join")
    async def on_guild_add(self, guild: discord.Guild):
        try:
            # Internal log embed
            log_ch = self.client.get_channel(LOG_CHANNEL_ID)
            if log_ch:
                invites = []
                try:
                    invites = [inv for inv in await guild.invites() if inv.max_age == 0 and inv.max_uses == 0]
                except Exception:
                    pass

                total_channels = len(set(self.client.get_all_channels()))
                embed = discord.Embed(title=f"🏛️ {guild.name}", color=0x57F287)
                embed.set_author(name="Guild Joined")
                embed.set_footer(text=f"Lucky Bot • lucky.gg — Added to {guild.name}")

                embed.add_field(
                    name="__About__",
                    value=(
                        f"**Name:** {guild.name}\n"
                        f"**ID:** `{guild.id}`\n"
                        f"**Owner:** {guild.owner} (`{guild.owner_id}`)\n"
                        f"**Created:** {guild.created_at.strftime('%b %d, %Y')}\n"
                        f"**Members:** {len(guild.members)}"
                    ),
                    inline=False,
                )
                embed.add_field(
                    name="__Members__",
                    value=(
                        f"🎭 Total: {len(guild.members)}\n"
                        f"👤 Humans: {len([m for m in guild.members if not m.bot])}\n"
                        f"🤖 Bots: {len([m for m in guild.members if m.bot])}"
                    ),
                    inline=False,
                )
                embed.add_field(
                    name="__Channels__",
                    value=(
                        f"📂 Categories: {len(guild.categories)}\n"
                        f"💬 Text: {len(guild.text_channels)}\n"
                        f"🔊 Voice: {len(guild.voice_channels)}\n"
                        f"🧵 Threads: {len(guild.threads)}"
                    ),
                    inline=False,
                )
                embed.add_field(
                    name="__Bot Stats__",
                    value=(
                        f"🏛️ Servers: `{len(self.client.guilds)}`\n"
                        f"🎭 Users: `{len(self.client.users)}`\n"
                        f"🎠 Channels: `{total_channels}`"
                    ),
                    inline=False,
                )
                if guild.icon:
                    embed.set_thumbnail(url=guild.icon.url)
                embed.timestamp = discord.utils.utcnow()

                await log_ch.send(invites[0].url if invites else "No pre-made invite found", embed=embed)

            # Welcome message in guild
            if not guild.chunked:
                await guild.chunk()

            data = self.client.get_guild(guild.id)
            prefix = ">"

            welcome_embed = discord.Embed(
                description=(
                    f"🔮 My prefix for this server is `{prefix}`\n"
                    f"🔮 Use `{prefix}help` to explore all commands\n"
                    f"🔮 Need help? Visit our **[Support Server]({serverLink})**"
                ),
                color=0x57F287,
            )
            welcome_embed.set_author(name="🍀 Thanks for adding Lucky!", icon_url=guild.me.display_avatar.url)
            welcome_embed.set_footer(text="Lucky Bot • lucky.gg")
            if guild.icon:
                welcome_embed.set_thumbnail(url=guild.icon.url)

            support_btn = Button(label="Support", style=discord.ButtonStyle.link, url=serverLink)
            view = View()
            view.add_item(support_btn)

            channel = discord.utils.get(guild.text_channels, name="general")
            if not channel:
                writable = [c for c in guild.text_channels if c.permissions_for(guild.me).send_messages]
                channel = writable[0] if writable else None

            if channel:
                await channel.send(embed=welcome_embed, view=view)

        except Exception as e:
            logging.error(f"[Lucky] on_guild_join error: {e}")

    @commands.Cog.listener(name="on_guild_remove")
    async def on_guild_remove(self, guild: discord.Guild):
        try:
            log_ch = self.client.get_channel(LOG_CHANNEL_ID)
            if not log_ch:
                return

            total_channels = len(set(self.client.get_all_channels()))
            embed = discord.Embed(title=f"🏛️ {guild.name}", color=0xFF4444)
            embed.set_author(name="Guild Removed")
            embed.set_footer(text=f"Lucky Bot • lucky.gg — Removed from {guild.name}")

            embed.add_field(
                name="__About__",
                value=(
                    f"**Name:** {guild.name}\n"
                    f"**ID:** `{guild.id}`\n"
                    f"**Owner:** {guild.owner} (`{guild.owner_id}`)\n"
                    f"**Members:** {len(guild.members)}"
                ),
                inline=False,
            )
            embed.add_field(
                name="__Members__",
                value=(
                    f"Total: {len(guild.members)}\n"
                    f"Humans: {len([m for m in guild.members if not m.bot])}\n"
                    f"Bots: {len([m for m in guild.members if m.bot])}"
                ),
                inline=False,
            )
            embed.add_field(
                name="__Bot Stats__",
                value=(
                    f"Servers: `{len(self.client.guilds)}`\n"
                    f"Users: `{len(self.client.users)}`\n"
                    f"Channels: `{total_channels}`"
                ),
                inline=False,
            )
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            embed.timestamp = discord.utils.utcnow()

            await log_ch.send(embed=embed)

        except Exception as e:
            logging.error(f"[Lucky] on_guild_remove error: {e}")

# Lucky Bot — Rewritten
