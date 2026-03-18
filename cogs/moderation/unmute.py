import discord
from discord.ext import commands
from utils.Tools import *


class Unmute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF4444

    @commands.hybrid_command(
        name="unmute",
        help="Unmutes a user from the Server",
        usage="unmute <member>",
        aliases=["untimeout"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def unmute(self, ctx, user: discord.Member):
        if not user.timed_out_until or user.timed_out_until <= discord.utils.utcnow():
            embed = discord.Embed(description="🎴 **This user is not muted in this server.**", color=self.color)
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            embed.set_author(name=f"{user.name} is Not Muted!", icon_url=user.display_avatar.url)
            embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        try:
            await user.edit(timed_out_until=None)

            try:
                await user.send(f"🍀 You have been unmuted in **{ctx.guild.name}**.")
                dm_status = "Yes"
            except (discord.Forbidden, discord.HTTPException):
                dm_status = "No"

        except discord.Forbidden:
            error = discord.Embed(color=self.color, description="🃏 I can't unmute a user with higher permissions!")
            error.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            error.set_author(name="Error Unmuting User")
            return await ctx.send(embed=error)

        embed = discord.Embed(
            description=f"🍀 **[{user}](https://discord.com/users/{user.id}) has been unmuted.**\n**DM Sent:** {dm_status}",
            color=0x57F287
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_author(name=f"Successfully Unmuted {user.name}", icon_url=user.display_avatar.url)
        embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Unmute(bot))

# Lucky Bot — Rewritten
