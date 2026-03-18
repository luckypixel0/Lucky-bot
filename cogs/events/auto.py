import discord
from discord.utils import *
from core import Lucky, Cog
from utils.Tools import *
from utils.config import BotName, serverLink
from discord.ext import commands
from discord.ui import Button, View


class Autorole(Cog):
    def __init__(self, bot: Lucky):
        self.bot = bot

    @commands.Cog.listener(name="on_guild_join")
    async def send_msg_to_adder(self, guild: discord.Guild):
        async for entry in guild.audit_logs(limit=3):
            if entry.action == discord.AuditLogAction.bot_add:
                data = await getConfig(guild.id)
                prefix = data.get("prefix", ">")

                embed = discord.Embed(
                    description=(
                        f"🍀 **Thanks for adding Lucky!**\n\n"
                        f"🔮 My default prefix is `{prefix}`\n"
                        f"🔮 Use `{prefix}help` to see all commands\n"
                        f"🔮 For support visit **[lucky.gg]({serverLink})**"
                    ),
                    color=0x57F287,
                )
                embed.set_thumbnail(
                    url=entry.user.avatar.url if entry.user.avatar else entry.user.default_avatar.url
                )
                embed.set_author(name=guild.name, icon_url=guild.me.display_avatar.url)
                embed.set_footer(text="Lucky Bot • lucky.gg")

                support_btn = Button(label="Support", style=discord.ButtonStyle.link, url=serverLink)
                view = View()
                view.add_item(support_btn)

                if guild.icon:
                    embed.set_author(name=guild.name, icon_url=guild.icon.url)

                try:
                    await entry.user.send(embed=embed, view=view)
                except Exception as e:
                    print(f"[Lucky] Could not DM guild adder: {e}")

# Lucky Bot — Rewritten
