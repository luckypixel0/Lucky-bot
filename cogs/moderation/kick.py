import discord
from discord.ext import commands
from utils.Tools import *


class Kick(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF4444

    @commands.hybrid_command(
        name="kick",
        help="Kicks a member from the server.",
        usage="kick <member> [reason]",
        aliases=["kickmember"])
    @blacklist_check()
    @ignore_check()
    @top_check()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick_command(self, ctx, member: discord.Member, *, reason: str = None):
        reason = reason or "No reason provided"

        if member == ctx.author:
            return await ctx.send("🃏 You cannot kick yourself.")

        if member == self.bot.user:
            return await ctx.send("🃏 You cannot kick me.")

        if ctx.author.top_role <= member.top_role and ctx.guild.owner != ctx.author:
            return await ctx.send("🃏 You cannot kick a member with a higher or equal role than you.")

        if ctx.guild.me.top_role <= member.top_role:
            return await ctx.send("🃏 My role is not high enough to kick this member.")

        try:
            await member.send(f"🔱 You have been kicked from **{ctx.guild.name}**. Reason: {reason}")
        except (discord.Forbidden, discord.HTTPException):
            pass

        await member.kick(reason=f"Action by {ctx.author.name} | Reason: {reason}")

        embed = discord.Embed(
            description=f"🍀 **{member.mention} has been kicked.**\n**Reason:** {reason}",
            color=self.color
        )
        embed.set_author(name=f"Successfully Kicked {member.name}", icon_url=member.display_avatar.url)
        embed.set_footer(text=f"Lucky Bot • lucky.gg | Action by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Kick(bot))

# Lucky Bot — Rewritten
