import discord
from discord.ext import commands


class Hide(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF4444

    @commands.hybrid_command(
        name="hide",
        help="Hides a channel from the default role (@everyone).",
        usage="hide [channel]",
        aliases=["hidechannel"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def hide_command(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel

        if not channel.permissions_for(ctx.guild.default_role).read_messages:
            embed = discord.Embed(
                description=f"🎴 **{channel.mention} is already hidden.**",
                color=self.color
            )
            embed.set_author(name="Already Hidden", icon_url=ctx.author.display_avatar.url)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        await channel.set_permissions(ctx.guild.default_role, read_messages=False)

        embed = discord.Embed(
            description=f"🍀 **{channel.mention} has been successfully hidden.**",
            color=self.color
        )
        embed.set_author(name="Channel Hidden", icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Lucky Bot • lucky.gg | Action by {ctx.author.name}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Hide(bot))

# Lucky Bot — Rewritten
