import discord
from discord.ext import commands


class Unhide(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF4444

    @commands.hybrid_command(
        name="unhide",
        help="Unhides a channel for the default role (@everyone).",
        usage="unhide [channel]",
        aliases=["unhidechannel"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unhide_command(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel

        if channel.permissions_for(ctx.guild.default_role).read_messages:
            embed = discord.Embed(
                description=f"🎴 **{channel.mention} is already visible.**",
                color=self.color
            )
            embed.set_author(name="Already Visible", icon_url=ctx.author.display_avatar.url)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        await channel.set_permissions(ctx.guild.default_role, read_messages=True)

        embed = discord.Embed(
            description=f"🍀 **{channel.mention} has been successfully unhidden.**",
            color=0x57F287
        )
        embed.set_author(name="Channel Unhidden", icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Lucky Bot • lucky.gg | Action by {ctx.author.name}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Unhide(bot))

# Lucky Bot — Rewritten
