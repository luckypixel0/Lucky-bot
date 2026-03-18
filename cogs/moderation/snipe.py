import discord
from discord.ext import commands
from datetime import datetime


class Snipe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sniped_messages = {}

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild:
            return
        self.sniped_messages[message.channel.id] = {
            "content": message.content,
            "author": message.author,
            "deleted_at": datetime.utcnow()
        }

    @commands.command(name="snipe", help="Shows the most recently deleted message in the channel.")
    @commands.has_permissions(manage_messages=True)
    async def snipe(self, ctx):
        if ctx.channel.id in self.sniped_messages:
            sniped_data = self.sniped_messages[ctx.channel.id]
            author = sniped_data["author"]
            content = sniped_data["content"] or "No text content found in the deleted message."
            deleted_at = sniped_data["deleted_at"]

            embed = discord.Embed(
                description=content,
                color=0xFF4444,
                timestamp=deleted_at
            )
            embed.set_author(name=f"Sniped message from {author.name}", icon_url=author.display_avatar.url)
            embed.set_footer(text="Lucky Bot • lucky.gg | Deleted at")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="🃏 There are no deleted messages to snipe in this channel.",
                color=0xFF4444
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Snipe(bot))

# Lucky Bot — Rewritten
