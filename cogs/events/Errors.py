import discord
import aiosqlite
from discord.ext import commands
from utils.config import serverLink
from core import Lucky, Cog, Context
from utils.Tools import getIgnore


class Errors(Cog):
    def __init__(self, client: Lucky):
        self.client = client

    @commands.Cog.listener()
    async def on_command_error(self, ctx: Context, error):
        if ctx.command is None:
            return

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, (commands.MissingRequiredArgument, commands.TooManyArguments, commands.BadArgument)):
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)
            return

        if isinstance(error, commands.CheckFailure):
            if not ctx.guild:
                return
            data = getIgnore(ctx.guild.id)
            ch = [str(c) for c in data.get("channel", [])]
            iuser = [str(u) for u in data.get("user", [])]
            cmd = data.get("commands", [])
            buser = [str(u) for u in data.get("bypassuser", [])]

            if str(ctx.author.id) in buser:
                return
            if str(ctx.channel.id) in ch:
                await ctx.reply(
                    f"🎠 {ctx.author.mention} This channel is ignored — try my commands elsewhere.",
                    delete_after=8,
                )
                return
            if str(ctx.author.id) in iuser:
                await ctx.reply(
                    f"🃏 {ctx.author.mention} You are ignored in this guild.",
                    delete_after=8,
                )
                return
            if ctx.command.name in cmd or any(a in cmd for a in ctx.command.aliases):
                await ctx.reply(
                    f"🃏 {ctx.author.mention} This command is ignored in this guild.",
                    delete_after=8,
                )
                return

        if isinstance(error, commands.NoPrivateMessage):
            embed = discord.Embed(
                color=0xFF4444,
                description="🃏 You can't use my commands in DMs.",
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.reply(embed=embed, delete_after=20)
            return

        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                color=0xFF4444,
                description=f"⏳ {ctx.author.mention} You're on cooldown. Try again in **{error.retry_after:.2f}s**.",
            )
            embed.set_author(name="Cooldown", icon_url=self.client.user.avatar.url)
            embed.set_footer(
                text=f"Lucky Bot • lucky.gg",
                icon_url=ctx.author.display_avatar.url,
            )
            await ctx.reply(embed=embed, delete_after=10)
            return

        if isinstance(error, commands.MaxConcurrencyReached):
            embed = discord.Embed(
                color=0xFF4444,
                description=f"🎲 {ctx.author.mention} This command is already running. Please wait for it to finish.",
            )
            embed.set_author(name="Command In Progress", icon_url=self.client.user.avatar.url)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.reply(embed=embed, delete_after=10)
            ctx.command.reset_cooldown(ctx)
            return

        if isinstance(error, commands.MissingPermissions):
            missing = [p.replace("_", " ").replace("guild", "server").title() for p in error.missing_permissions]
            fmt = ", ".join(missing[:-1]) + " and " + missing[-1] if len(missing) > 1 else missing[0]
            embed = discord.Embed(
                color=0xFF4444,
                description=f"🃏 You need **{fmt}** permission to use `{ctx.command.name}`.",
            )
            embed.set_author(name="Missing Permissions", icon_url=self.client.user.avatar.url)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.reply(embed=embed, delete_after=7)
            ctx.command.reset_cooldown(ctx)
            return

        if isinstance(error, commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            await ctx.reply(
                f"🃏 I need **{missing}** permission to run `{ctx.command.qualified_name}`.",
                delete_after=7,
            )
            return

        if isinstance(error, (discord.HTTPException, commands.CommandInvokeError)):
            return

# Lucky Bot — Rewritten
