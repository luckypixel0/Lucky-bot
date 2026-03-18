import discord
from discord.ext import commands
from datetime import timedelta
import re
from utils.Tools import *


class Mute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF4444

    def parse_time(self, time_str):
        time_pattern = r"(\d+)([mhd])"
        match = re.match(time_pattern, time_str)
        if match:
            time_value = int(match.group(1))
            time_unit = match.group(2)
            if time_unit == "m" and 0 < time_value <= 60:
                return timedelta(minutes=time_value), f"{time_value} minutes"
            elif time_unit == "h" and 0 < time_value <= 24:
                return timedelta(hours=time_value), f"{time_value} hours"
            elif time_unit == "d" and 0 < time_value <= 28:
                return timedelta(days=time_value), f"{time_value} days"
        return None, None

    @commands.hybrid_command(
        name="mute",
        help="Mutes a user with optional time and reason",
        usage="mute <member> [time] [reason]",
        aliases=["timeout", "stfu"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def mute(self, ctx, user: discord.Member, time: str = None, *, reason=None):

        if user.is_timed_out():
            embed = discord.Embed(description="🎴 **This user is already muted in this server.**", color=self.color)
            embed.set_author(name=f"{user.name} is Already Muted!", icon_url=user.display_avatar.url)
            embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        if user == ctx.guild.owner:
            embed = discord.Embed(color=self.color, description="🃏 You can't timeout the Server Owner!")
            embed.set_author(name="Error Timing Out User")
            embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        if ctx.author != ctx.guild.owner and user.top_role >= ctx.author.top_role:
            embed = discord.Embed(color=self.color, description="🃏 You can't timeout users with a higher or equal role than yours!")
            embed.set_author(name="Error Timing Out User")
            embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        if user.top_role >= ctx.guild.me.top_role:
            embed = discord.Embed(color=self.color, description="🃏 I can't timeout users with a higher or equal role than mine.")
            embed.set_author(name="Error Timing Out User")
            embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        time_delta, duration_text = self.parse_time(time) if time else (timedelta(hours=24), "24 hours")

        if not time_delta:
            embed = discord.Embed(color=self.color, description="🃏 Invalid time format! Use `<number><m/h/d>` — m: minutes (max 60), h: hours (max 24), d: days (max 28).")
            embed.set_author(name="Error Timing Out User")
            embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        try:
            await user.send(f"🎴 You have been muted in **{ctx.guild.name}** by **{ctx.author}** for {duration_text}. Reason: {reason or 'None'}")
            dm_status = "Yes"
        except (discord.Forbidden, discord.HTTPException):
            dm_status = "No"

        await user.edit(timed_out_until=discord.utils.utcnow() + time_delta,
                        reason=f"Muted by {ctx.author} for {duration_text}. Reason: {reason or 'None'}")

        embed = discord.Embed(
            description=(
                f"🍀 **[{user}](https://discord.com/users/{user.id}) has been muted for {duration_text}.**\n"
                f"**Reason:** {reason or 'No reason provided'}\n"
                f"**DM Sent:** {dm_status}"
            ),
            color=self.color
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_author(name=f"Successfully Muted {user.name}", icon_url=user.display_avatar.url)
        embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        await ctx.send(embed=embed)

    @mute.error
    async def mute_error(self, ctx, error):
        if isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(title="🃏 Access Denied", description="I don't have permission to mute members.", color=self.color)
            await ctx.send(embed=embed)
        elif isinstance(error, discord.Forbidden):
            embed = discord.Embed(title="🃏 Missing Permissions", description="I can't mute this user — they may have higher privileges.", color=self.color)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="🃏 Unexpected Error", description=str(error), color=self.color)
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Mute(bot))

# Lucky Bot — Rewritten
