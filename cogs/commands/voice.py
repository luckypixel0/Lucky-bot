import discord
from discord.ext import commands
from discord.utils import get
import os
from utils.Tools import *
from typing import Optional, Union
from discord.ext.commands import Context
from utils import Paginator, DescriptionEmbedPaginator, FieldPagePaginator, TextPaginator
from utils import *


class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0x2F3136

    def _ok(self, description):
        e = discord.Embed(title="🍀 Success", description=description, color=0x57F287)
        e.set_footer(text="Lucky Bot • lucky.gg")
        return e

    def _err(self, description):
        e = discord.Embed(title="🃏 Error", description=description, color=0xFF4444)
        e.set_footer(text="Lucky Bot • lucky.gg")
        return e

    @commands.group(name="voice", invoke_without_command=True, aliases=['vc'])
    @blacklist_check()
    @ignore_check()
    async def vc(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @vc.command(name="kick", help="Removes a user from the voice channel.", usage="voice kick <member>")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _kick(self, ctx, *, member: discord.Member):
        if member.voice is None:
            return await ctx.reply(embed=self._err(f"{member} is not connected to any voice channel."))
        ch = member.voice.channel.mention
        await member.edit(voice_channel=None, reason=f"Disconnected by {ctx.author}")
        await ctx.reply(embed=self._ok(f"{member} has been disconnected from {ch}."))

    @vc.command(name="kickall", help="Disconnect all members from your voice channel.", usage="voice kickall")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _kickall(self, ctx):
        if ctx.author.voice is None:
            return await ctx.reply(embed=self._err("You are not connected to any voice channels."))
        count = 0
        ch = ctx.author.voice.channel.mention
        for member in ctx.author.voice.channel.members:
            await member.edit(voice_channel=None, reason=f"Disconnect All by {ctx.author}")
            count += 1
        await ctx.reply(embed=self._ok(f"Disconnected {count} members from {ch}."))

    @vc.command(name="mute", help="Mute a member in voice channel.", usage="voice mute <member>")
    @commands.has_guild_permissions(mute_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _mute(self, ctx, *, member: discord.Member = None):
        if member is None:
            return await ctx.reply(embed=self._err("You need to mention a member to mute."))
        if member.voice is None:
            return await ctx.reply(embed=self._err(f"{member} is not connected to any voice channels."))
        if member.voice.mute:
            return await ctx.reply(embed=self._err(f"{member} is already muted."))
        await member.edit(mute=True)
        await ctx.reply(embed=self._ok(f"{member} has been muted in {member.voice.channel.mention}."))

    @vc.command(name="unmute", help="Unmute a member in the voice channel.", usage="voice unmute <member>")
    @blacklist_check()
    @ignore_check()
    @commands.has_guild_permissions(mute_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def vcunmute(self, ctx, *, member: discord.Member):
        if member.voice is None:
            return await ctx.reply(embed=self._err(f"{member} is not connected to any voice channel."))
        if not member.voice.mute:
            return await ctx.reply(embed=self._err(f"{member} is already unmuted."))
        ch = member.voice.channel.mention
        await member.edit(mute=False, reason=f"Unmuted by {ctx.author}")
        await ctx.reply(embed=self._ok(f"{member} has been unmuted in {ch}."))

    @vc.command(name="muteall", help="Mute all members in a voice channel.", usage="voice muteall")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _muteall(self, ctx):
        if ctx.author.voice is None:
            return await ctx.reply(embed=self._err("You are not connected to any voice channel."))
        count = 0
        ch = ctx.author.voice.channel.mention
        for member in ctx.author.voice.channel.members:
            if not member.voice.mute:
                await member.edit(mute=True, reason=f"voice muteall by {ctx.author}")
                count += 1
        await ctx.reply(embed=self._ok(f"Muted {count} members in {ch}."))

    @vc.command(name="unmuteall", help="Unmute all members in a voice channel.", usage="voice unmuteall")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _unmuteall(self, ctx):
        if ctx.author.voice is None:
            return await ctx.reply(embed=self._err("You are not connected to any voice channel."))
        count = 0
        ch = ctx.author.voice.channel.mention
        for member in ctx.author.voice.channel.members:
            if member.voice.mute:
                await member.edit(mute=False, reason=f"Voice unmuteall by {ctx.author}")
                count += 1
        await ctx.reply(embed=self._ok(f"Unmuted {count} members in {ch}."))

    @vc.command(name="deafen", help="Deafen a user in a voice channel.", usage="voice deafen <member>")
    @blacklist_check()
    @ignore_check()
    @commands.has_guild_permissions(deafen_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _deafen(self, ctx, *, member: discord.Member):
        if member.voice is None:
            return await ctx.reply(embed=self._err(f"{member} is not connected to any voice channel."))
        if member.voice.deaf:
            return await ctx.reply(embed=self._err(f"{member} is already deafened."))
        ch = member.voice.channel.mention
        await member.edit(deafen=True, reason=f"Deafen by {ctx.author}")
        await ctx.reply(embed=self._ok(f"{member} has been deafened in {ch}."))

    @vc.command(name="undeafen", help="Undeafen a user in a voice channel.", usage="voice undeafen <member>")
    @blacklist_check()
    @ignore_check()
    @commands.has_guild_permissions(deafen_members=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _undeafen(self, ctx, *, member: discord.Member):
        if member.voice is None:
            return await ctx.reply(embed=self._err(f"{member} is not connected to any voice channel."))
        if not member.voice.deaf:
            return await ctx.reply(embed=self._err(f"{member} is already undeafened."))
        ch = member.voice.channel.mention
        await member.edit(deafen=False, reason=f"Undeafen by {ctx.author}")
        await ctx.reply(embed=self._ok(f"{member} has been undeafened in {ch}."))

    @vc.command(name="deafenall", help="Deafen all members in a voice channel.", usage="voice deafenall")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _deafenall(self, ctx):
        if ctx.author.voice is None:
            return await ctx.reply(embed=self._err("You are not connected to any voice channel."))
        count = 0
        ch = ctx.author.voice.channel.mention
        for member in ctx.author.voice.channel.members:
            if not member.voice.deaf:
                await member.edit(deafen=True, reason=f"voice deafenall by {ctx.author}")
                count += 1
        await ctx.reply(embed=self._ok(f"Deafened {count} members in {ch}."))

    @vc.command(name="undeafenall", help="Undeafen all members in a voice channel.", usage="voice undeafenall")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _undeafenall(self, ctx):
        if ctx.author.voice is None:
            return await ctx.reply(embed=self._err("You are not connected to any voice channel."))
        count = 0
        ch = ctx.author.voice.channel.mention
        for member in ctx.author.voice.channel.members:
            if member.voice.deaf:
                await member.edit(deafen=False, reason=f"Voice undeafenall by {ctx.author}")
                count += 1
        await ctx.reply(embed=self._ok(f"Undeafened {count} members in {ch}."))

    @vc.command(name="moveall", help="Move all members to specified voice channel.", usage="voice moveall <channel>")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _moveall(self, ctx, *, channel: discord.VoiceChannel):
        if ctx.author.voice is None:
            return await ctx.reply(embed=self._err("You are not connected to any voice channel."))
        try:
            ch = ctx.author.voice.channel.mention
            count = 0
            for member in ctx.author.voice.channel.members:
                await member.edit(voice_channel=channel, reason=f"voice moveall by {ctx.author}")
                count += 1
            await ctx.reply(embed=self._ok(f"{count} members moved from {ch} to {channel.mention}."))
        except Exception:
            await ctx.reply(embed=self._err("Invalid voice channel provided."))

    @vc.command(name="pullall", help="Move all members from ALL VCs to specified channel.", usage="voice pullall <channel>")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _pullall(self, ctx, *, channel: discord.VoiceChannel):
        if ctx.author.voice is None:
            return await ctx.reply(embed=self._err("You are not connected to any voice channel."))
        count = 0
        for vc in ctx.guild.voice_channels:
            for member in vc.members:
                if member != ctx.author:
                    try:
                        await member.edit(voice_channel=channel, reason=f"Pullall by {ctx.author}")
                        count += 1
                    except Exception:
                        pass
        await ctx.reply(embed=self._ok(f"Moved {count} members to {channel.mention}."))

    @vc.command(name="move", help="Move a member from one voice channel to another.", usage="voice move <member> <channel>")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _move(self, ctx, member: discord.Member, channel: discord.VoiceChannel):
        if member.voice is None:
            return await ctx.reply(embed=self._err(f"{member} is not connected to any voice channel."))
        if channel == member.voice.channel:
            return await ctx.reply(embed=self._err(f"{member} is already in {channel.mention}."))
        await member.edit(voice_channel=channel, reason=f"Moved by {ctx.author}")
        await ctx.reply(embed=self._ok(f"{member} has been moved to {channel.mention}."))

    @vc.command(name="pull", help="Pull a member from one voice channel to yours.", usage="voice pull <member>")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _pull(self, ctx, member: discord.Member):
        if ctx.author.voice is None:
            return await ctx.reply(embed=self._err("You are not connected to any voice channel."))
        if member.voice is None:
            return await ctx.reply(embed=self._err(f"{member} is not connected to any voice channel."))
        if member.voice.channel == ctx.author.voice.channel:
            return await ctx.reply(embed=self._err(f"{member} is already in your voice channel."))
        await member.edit(voice_channel=ctx.author.voice.channel, reason=f"Pulled by {ctx.author}")
        await ctx.reply(embed=self._ok(f"{member} has been pulled to your voice channel."))

    @vc.command(name="lock", help="Locks the voice channel.", usage="voice lock")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _lock(self, ctx):
        if ctx.author.voice is None:
            return await ctx.reply(embed=self._err("You are not connected to any voice channel."))
        ch = ctx.author.voice.channel.mention
        await ctx.author.voice.channel.set_permissions(ctx.guild.default_role, connect=False, reason=f"Locked by {ctx.author}")
        await ctx.reply(embed=self._ok(f"{ch} has been locked."))

    @vc.command(name="unlock", help="Unlocks the voice channel.", usage="voice unlock")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _unlock(self, ctx):
        if ctx.author.voice is None:
            return await ctx.reply(embed=self._err("You are not connected to any voice channel."))
        ch = ctx.author.voice.channel.mention
        await ctx.author.voice.channel.set_permissions(ctx.guild.default_role, connect=True, reason=f"Unlocked by {ctx.author}")
        await ctx.reply(embed=self._ok(f"{ch} has been unlocked."))

    @vc.command(name="private", help="Makes the voice channel private.", usage="voice private")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _private(self, ctx):
        if ctx.author.voice is None:
            return await ctx.reply(embed=self._err("You are not connected to any voice channel."))
        ch = ctx.author.voice.channel.mention
        await ctx.author.voice.channel.set_permissions(ctx.guild.default_role, connect=False, view_channel=False, reason=f"Made private by {ctx.author}")
        await ctx.reply(embed=self._ok(f"{ch} has been made private."))

    @vc.command(name="unprivate", help="Makes the voice channel public.", usage="voice unprivate")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _unprivate(self, ctx):
        if ctx.author.voice is None:
            return await ctx.reply(embed=self._err("You are not connected to any voice channel."))
        ch = ctx.author.voice.channel.mention
        await ctx.author.voice.channel.set_permissions(ctx.guild.default_role, connect=True, view_channel=True, reason=f"Made public by {ctx.author}")
        await ctx.reply(embed=self._ok(f"{ch} has been made public."))


async def setup(bot):
    await bot.add_cog(Voice(bot))

# Lucky Bot — Rewritten
