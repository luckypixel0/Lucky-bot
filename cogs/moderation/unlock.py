import discord
from discord.ext import commands


class Unlock(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF4444

    @commands.hybrid_command(
        name="unlock",
        help="Unlocks a channel to allow sending messages.",
        usage="unlock [channel]",
        aliases=["unlockchannel"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def unlock_command(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel

        if channel.permissions_for(ctx.guild.default_role).send_messages is True:
            embed = discord.Embed(
                description=f"🎴 **{channel.mention} is already unlocked.**",
                color=self.color
            )
            embed.set_author(name="Already Unlocked")
            embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        await channel.set_permissions(ctx.guild.default_role, send_messages=True)

        embed = discord.Embed(
            description=f"🍀 **{channel.mention} has been successfully unlocked.**",
            color=0x57F287
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_author(name=f"Successfully Unlocked {channel.name}")
        embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Unlock(bot))

# Lucky Bot — Rewritten
