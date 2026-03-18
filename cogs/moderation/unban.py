import discord
from discord.ext import commands
from utils.Tools import *


class Unban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF4444

    @commands.hybrid_command(
        name="unban",
        help="Unbans a user from the Server",
        usage="unban <member> [reason]",
        aliases=["forgive", "pardon"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, user: discord.User, *, reason=None):
        bans = [entry async for entry in ctx.guild.bans()]
        if not any(ban_entry.user.id == user.id for ban_entry in bans):
            embed = discord.Embed(description="🎴 **This user is not banned in this server.**", color=self.color)
            embed.set_author(name=f"{user.name} is Not Banned!", icon_url=user.display_avatar.url)
            embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        try:
            await user.send(f"🍀 You have been unbanned from **{ctx.guild.name}** by **{ctx.author}**. Reason: {reason or 'No reason provided'}")
            dm_status = "Yes"
        except (discord.Forbidden, discord.HTTPException):
            dm_status = "No"

        await ctx.guild.unban(user, reason=f"Unban requested by {ctx.author} | Reason: {reason or 'No reason provided'}")

        embed = discord.Embed(
            description=(
                f"🍀 **[{user}](https://discord.com/users/{user.id}) has been unbanned.**\n"
                f"**Reason:** {reason or 'No reason provided'}\n"
                f"**DM Sent:** {dm_status}"
            ),
            color=0x57F287
        )
        embed.set_author(name=f"Successfully Unbanned {user.name}", icon_url=user.display_avatar.url)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Unban(bot))

# Lucky Bot — Rewritten
