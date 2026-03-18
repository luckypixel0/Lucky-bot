import discord
from discord.ext import commands
from discord import ui
from utils.Tools import *


class Ban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF4444

    @commands.hybrid_command(
        name="ban",
        help="Bans a user from the Server",
        usage="ban <member> [reason]",
        aliases=["hackban"])
    @blacklist_check()
    @ignore_check()
    @top_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.User, *, reason=None):

        member = ctx.guild.get_member(user.id)
        if not member:
            try:
                user = await self.bot.fetch_user(user.id)
            except discord.NotFound:
                embed = discord.Embed(
                    description=f"🃏 **User Not Found** — No user with ID `{user.id}` exists.",
                    color=self.color
                )
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

        bans = [entry async for entry in ctx.guild.bans()]
        if any(ban_entry.user.id == user.id for ban_entry in bans):
            embed = discord.Embed(
                description=f"🎴 **{user.name} is Already Banned!**\nThis user is already banned in this server.\n*Requested by {ctx.author}*",
                color=self.color
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        if member == ctx.guild.owner:
            embed = discord.Embed(
                description=f"🃏 I can't ban the Server Owner!\n*Requested by {ctx.author}*",
                color=self.color
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        if isinstance(member, discord.Member) and member.top_role >= ctx.guild.me.top_role:
            embed = discord.Embed(
                description=f"🃏 I can't ban a user with a higher or equal role!\n*Requested by {ctx.author}*",
                color=self.color
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        if isinstance(member, discord.Member):
            if ctx.author != ctx.guild.owner:
                if member.top_role >= ctx.author.top_role:
                    embed = discord.Embed(
                        description=f"🃏 You can't ban a user with a higher or equal role!\n*Requested by {ctx.author}*",
                        color=self.color
                    )
                    embed.set_footer(text="Lucky Bot • lucky.gg")
                    return await ctx.send(embed=embed)

        try:
            await user.send(f"🔱 You have been banned from **{ctx.guild.name}** by **{ctx.author}**. Reason: {reason or 'No reason provided'}")
            dm_status = "Yes"
        except (discord.Forbidden, discord.HTTPException):
            dm_status = "No"

        await ctx.guild.ban(user, reason=f"Ban requested by {ctx.author} | Reason: {reason or 'No reason provided'}")

        embed = discord.Embed(
            description=(
                f"🍀 **[{user}](https://discord.com/users/{user.id}) has been banned.**\n"
                f"**Reason:** {reason or 'No reason provided'}\n"
                f"**DM Sent:** {dm_status}\n"
                f"**Moderator:** {ctx.author.mention}"
            ),
            color=self.color
        )
        embed.set_author(name=f"Successfully Banned {user.name}", icon_url=user.display_avatar.url)
        embed.set_footer(text=f"Lucky Bot • lucky.gg | {discord.utils.format_dt(discord.utils.utcnow(), 'R')}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Ban(bot))

# Lucky Bot — Rewritten
