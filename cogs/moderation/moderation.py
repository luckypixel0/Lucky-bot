import discord
import asyncio
import re
from typing import Union, Optional
from collections import Counter
from utils.Tools import *
from core import Cog, Lucky, Context
from discord.ext import commands
from discord.ui import Button, View
from discord.utils import utcnow
import aiohttp


time_regex = re.compile(r"(?:(\d{1,5})(h|s|m|d))+?")
time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400}


def convert(argument):
    args = argument.lower()
    matches = re.findall(time_regex, args)
    time = 0
    for key, value in matches:
        try:
            time += time_dict[value] * float(key)
        except KeyError:
            raise commands.BadArgument(f"{value} is an invalid time key! h|m|s|d are valid arguments")
        except ValueError:
            raise commands.BadArgument(f"{key} is not a number!")
    return round(time)


async def do_removal(ctx, limit, predicate, *, before=None, after=None):
    if limit > 2000:
        return await ctx.send(f"🃏 Too many messages to search given ({limit}/2000)")

    if before is None:
        before = ctx.message
    else:
        before = discord.Object(id=before)

    if after is not None:
        after = discord.Object(id=after)

    try:
        deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
    except discord.Forbidden:
        return await ctx.send("🃏 I do not have permissions to delete messages.")
    except discord.HTTPException as e:
        return await ctx.send(f"🃏 Error: {e} (try a smaller search?)")

    spammers = Counter(m.author.display_name for m in deleted)
    deleted = len(deleted)
    messages = [f'🍀 {deleted} message{"" if deleted == 1 else "s"} removed.']
    if deleted:
        messages.append("")
        spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
        messages.extend(f"**{name}**: {count}" for name, count in spammers)

    to_send = "\n".join(messages)
    if len(to_send) > 2000:
        await ctx.send(f"🍀 Successfully removed {deleted} messages.", delete_after=7)
    else:
        await ctx.send(to_send, delete_after=7)


class Moderation(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF4444

    def convert_time(self, time):
        pos = ["s", "m", "h", "d"]
        time_dict = {"s": 1, "m": 60, "h": 3600, "d": 3600 * 24}
        unit = time[-1]
        if unit not in pos:
            return -1
        try:
            val = int(time[:-1])
        except Exception:
            return -2
        return val * time_dict[unit]

    def _footer(self, ctx):
        return {"text": f"Lucky Bot • lucky.gg | Requested by {ctx.author}",
                "icon_url": ctx.author.display_avatar.url}

    @commands.command()
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def enlarge(self, ctx, emoji: Union[discord.Emoji, discord.PartialEmoji, str]):
        url = emoji.url
        await ctx.send(url)

    @commands.hybrid_command(name="unlockall", help="Unlocks all channels in the Guild.", usage="unlockall")
    @blacklist_check()
    @ignore_check()
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def unlockall(self, ctx):
        if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
            button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji="🍀")
            button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji="🃏")

            async def button_callback(interaction: discord.Interaction):
                a = 0
                if interaction.user == ctx.author:
                    if interaction.guild.me.guild_permissions.manage_roles:
                        embed1 = discord.Embed(color=self.color, description=f"⏳ Unlocking all channels in **{ctx.guild.name}**...")
                        await interaction.response.edit_message(embed=embed1, view=None)
                        for channel in interaction.guild.channels:
                            try:
                                await channel.set_permissions(ctx.guild.default_role,
                                    overwrite=discord.PermissionOverwrite(send_messages=True, read_messages=True),
                                    reason=f"Unlockall executed by {ctx.author}")
                                a += 1
                            except Exception:
                                pass
                        await interaction.channel.send(content=f"🍀 Successfully unlocked {a} channel(s).")
                    else:
                        await interaction.response.edit_message(
                            content="🃏 I'm missing `Manage Roles` permission.", embed=None, view=None)
                else:
                    await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

            async def button1_callback(interaction: discord.Interaction):
                if interaction.user == ctx.author:
                    embed2 = discord.Embed(color=self.color, description="❌ Cancelled — no channels were unlocked.")
                    await interaction.response.edit_message(embed=embed2, view=None)
                else:
                    await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

            embed = discord.Embed(color=self.color, description=f"⏳ Unlock all channels in **{ctx.guild.name}**?")
            embed.set_footer(**self._footer(ctx))
            view = View()
            button.callback = button_callback
            button1.callback = button1_callback
            view.add_item(button)
            view.add_item(button1)
            await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)
        else:
            embed5 = discord.Embed(title="🃏 Access Denied", description="Your role must be above my top role.", color=self.color)
            embed5.set_footer(**self._footer(ctx))
            await ctx.send(embed=embed5)

    @commands.hybrid_command(name="lockall", help="Locks all channels in the Guild.", usage="lockall")
    @blacklist_check()
    @ignore_check()
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def lockall(self, ctx):
        if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
            button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji="🍀")
            button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji="🃏")

            async def button_callback(interaction: discord.Interaction):
                a = 0
                if interaction.user == ctx.author:
                    if interaction.guild.me.guild_permissions.manage_roles:
                        embed1 = discord.Embed(color=self.color, description=f"⏳ Locking all channels in **{ctx.guild.name}**...")
                        await interaction.response.edit_message(embed=embed1, view=None)
                        for channel in interaction.guild.channels:
                            try:
                                await channel.set_permissions(ctx.guild.default_role,
                                    overwrite=discord.PermissionOverwrite(send_messages=False, read_messages=True),
                                    reason=f"Lockall executed by {ctx.author}")
                                a += 1
                            except Exception:
                                pass
                        await interaction.channel.send(content=f"🍀 Successfully locked {a} channel(s).")
                    else:
                        await interaction.response.edit_message(
                            content="🃏 I'm missing `Manage Roles` permission.", embed=None, view=None)
                else:
                    await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

            async def button1_callback(interaction: discord.Interaction):
                if interaction.user == ctx.author:
                    embed2 = discord.Embed(color=self.color, description="❌ Cancelled — no channels were locked.")
                    await interaction.response.edit_message(embed=embed2, view=None)
                else:
                    await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

            embed = discord.Embed(color=self.color, description=f"⏳ Lock all channels in **{ctx.guild.name}**?")
            embed.set_footer(**self._footer(ctx))
            view = View()
            button.callback = button_callback
            button1.callback = button1_callback
            view.add_item(button)
            view.add_item(button1)
            await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)
        else:
            denied = discord.Embed(title="🃏 Access Denied", description="Your role must be above my top role.", color=self.color)
            denied.set_footer(**self._footer(ctx))
            await ctx.send(embed=denied)

    @commands.hybrid_command(name="give", help="Gives the mentioned user a role.", usage="give <user> <role>", aliases=["addrole"])
    @blacklist_check()
    @ignore_check()
    @top_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def give(self, ctx, member: discord.Member, *, role: discord.Role):
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await ctx.send("🃏 I don't have permission to manage roles!")

        if role >= ctx.guild.me.top_role:
            embed = discord.Embed(color=self.color, description="🃏 I can't manage roles higher or equal to mine!")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        if ctx.author != ctx.guild.owner and ctx.author.top_role <= member.top_role:
            embed = discord.Embed(color=self.color, description="🃏 You can't manage roles for a user with a higher or equal role than yours!")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        try:
            if role not in member.roles:
                await member.add_roles(role, reason=f"Role added by {ctx.author} (ID: {ctx.author.id})")
                success = discord.Embed(color=self.color, description=f"🍀 Successfully **added** {role.mention} to {member.mention}.")
                success.set_author(name="Role Added")
            else:
                await member.remove_roles(role, reason=f"Role removed by {ctx.author} (ID: {ctx.author.id})")
                success = discord.Embed(color=self.color, description=f"🍀 Successfully **removed** {role.mention} from {member.mention}.")
                success.set_author(name="Role Removed")
            success.set_footer(**self._footer(ctx))
            await ctx.send(embed=success)
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(color=self.color, description="🃏 I don't have permission to manage roles for this user!"))
        except Exception as e:
            await ctx.send(embed=discord.Embed(color=self.color, description=f"🃏 An unexpected error occurred: {str(e)}"))

    @commands.hybrid_command(name="hideall", help="Hides all channels in the server.", usage="hideall")
    @blacklist_check()
    @ignore_check()
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def hideall(self, ctx):
        if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
            button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji="🍀")
            button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji="🃏")

            async def button_callback(interaction: discord.Interaction):
                a = 0
                if interaction.user == ctx.author:
                    if interaction.guild.me.guild_permissions.manage_roles:
                        embed1 = discord.Embed(color=self.color, description=f"⏳ Hiding all channels in **{ctx.guild.name}**...")
                        await interaction.response.edit_message(embed=embed1, view=None)
                        for channel in interaction.guild.channels:
                            try:
                                await channel.set_permissions(ctx.guild.default_role, view_channel=False,
                                    reason=f"Hideall executed by {ctx.author}")
                                a += 1
                            except Exception:
                                pass
                        await interaction.channel.send(content=f"🍀 Successfully hid {a} channel(s).")
                    else:
                        await interaction.response.edit_message(content="🃏 I'm missing `Manage Channels` permission.", embed=None, view=None)
                else:
                    await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

            async def button1_callback(interaction: discord.Interaction):
                if interaction.user == ctx.author:
                    await interaction.response.edit_message(embed=discord.Embed(color=self.color, description="❌ Cancelled."), view=None)
                else:
                    await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

            embed = discord.Embed(color=self.color, description=f"⏳ Hide all channels in **{ctx.guild.name}**?")
            embed.set_footer(**self._footer(ctx))
            view = View()
            button.callback = button_callback
            button1.callback = button1_callback
            view.add_item(button)
            view.add_item(button1)
            await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)
        else:
            denied = discord.Embed(title="🃏 Access Denied", description="Your role must be above my top role.", color=self.color)
            denied.set_footer(**self._footer(ctx))
            await ctx.send(embed=denied)

    @commands.hybrid_command(name="unhideall", help="Unhides all channels in the server.", usage="unhideall")
    @blacklist_check()
    @ignore_check()
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def unhideall(self, ctx):
        if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
            button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji="🍀")
            button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji="🃏")

            async def button_callback(interaction: discord.Interaction):
                a = 0
                if interaction.user == ctx.author:
                    if interaction.guild.me.guild_permissions.manage_roles:
                        embed1 = discord.Embed(color=self.color, description=f"⏳ Unhiding all channels in **{ctx.guild.name}**...")
                        await interaction.response.edit_message(embed=embed1, view=None)
                        for channel in interaction.guild.channels:
                            try:
                                await channel.set_permissions(ctx.guild.default_role, view_channel=True,
                                    reason=f"Unhideall executed by {ctx.author}")
                                a += 1
                            except Exception:
                                pass
                        await interaction.channel.send(content=f"🍀 Successfully unhid {a} channel(s).")
                    else:
                        await interaction.response.edit_message(content="🃏 I'm missing `Manage Channels` permission.", embed=None, view=None)
                else:
                    await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

            async def button1_callback(interaction: discord.Interaction):
                if interaction.user == ctx.author:
                    await interaction.response.edit_message(embed=discord.Embed(color=self.color, description="❌ Cancelled."), view=None)
                else:
                    await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

            embed = discord.Embed(color=self.color, description=f"⏳ Unhide all channels in **{ctx.guild.name}**?")
            embed.set_footer(**self._footer(ctx))
            view = View()
            button.callback = button_callback
            button1.callback = button1_callback
            view.add_item(button)
            view.add_item(button1)
            await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)
        else:
            denied = discord.Embed(title="🃏 Access Denied", description="Your role must be above my top role.", color=self.color)
            denied.set_footer(**self._footer(ctx))
            await ctx.send(embed=denied)

    @commands.hybrid_command(name="prefix", aliases=["setprefix", "prefixset"], help="Change the bot prefix for this server")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def _prefix(self, ctx: commands.Context, prefix: str):
        if not prefix:
            return await ctx.reply(embed=discord.Embed(title="🃏 Error", description="Prefix cannot be empty.", color=self.color))

        data = await getConfig(ctx.guild.id)
        if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
            data["prefix"] = str(prefix)
            await updateConfig(ctx.guild.id, data)
            embed1 = discord.Embed(
                title="🍀 Success",
                description=f"Prefix for **{ctx.guild.name}** changed to `{prefix}`\nUse `{prefix}help` for more.",
                color=0x57F287
            )
            embed1.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.reply(embed=embed1)
        else:
            denied = discord.Embed(title="🃏 Access Denied", description="Your role must be above my top role.", color=self.color)
            denied.set_footer(**self._footer(ctx))
            await ctx.send(embed=denied)

    @commands.hybrid_command(name="clone", help="Clones a channel.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_channels=True)
    async def clone(self, ctx: commands.Context, channel: discord.TextChannel):
        if not ctx.guild.me.guild_permissions.manage_channels:
            embed = discord.Embed(color=self.color, description="🃏 I don't have permission to manage channels!")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        try:
            await channel.clone()
            success = discord.Embed(color=0x57F287, description=f"🍀 **{channel.name}** has been successfully cloned.")
            success.set_author(name="Channel Cloned")
            success.set_footer(**self._footer(ctx))
            await ctx.send(embed=success)
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(color=self.color, description="🃏 I don't have permission to clone channels!"))
        except Exception as e:
            await ctx.send(embed=discord.Embed(color=self.color, description=f"🃏 An error occurred: {str(e)}"))

    @commands.hybrid_command(name="nick", aliases=["setnick"], help="Change a member's nickname.", usage="nick [member] [name]")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def changenickname(self, ctx: commands.Context, member: discord.Member, *, name: str = None):
        if member == ctx.guild.owner:
            embed = discord.Embed(color=self.color, description="🃏 I can't change the nickname of the server owner!")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        if member.top_role >= ctx.guild.me.top_role:
            embed = discord.Embed(color=self.color, description="🃏 I can't change the nickname of a user with a higher or equal role than mine!")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        if ctx.author != ctx.guild.owner and ctx.author.top_role <= member.top_role:
            embed = discord.Embed(color=self.color, description="🃏 You can't change the nickname of a user with a higher or equal role!")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        try:
            await member.edit(nick=name)
            if name:
                success = discord.Embed(color=0x57F287, description=f"🍀 Changed nickname of {member.mention} to **{name}**.")
                success.set_author(name="Nickname Updated")
            else:
                success = discord.Embed(color=0x57F287, description=f"🍀 Cleared nickname of {member.mention}.")
                success.set_author(name="Nickname Cleared")
            success.set_footer(**self._footer(ctx))
            await ctx.send(embed=success)
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(color=self.color, description="🃏 I don't have permission to manage this user's nickname!"))
        except Exception as e:
            await ctx.send(embed=discord.Embed(color=self.color, description=f"🃏 An error occurred: {str(e)}"))

    @commands.hybrid_command(name="nuke", help="Nukes a channel", usage="nuke")
    @blacklist_check()
    @ignore_check()
    @top_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    @commands.has_permissions(manage_channels=True)
    async def _nuke(self, ctx: commands.Context):
        button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji="🍀")
        button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji="🃏")

        async def button_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.manage_channels:
                    channel = interaction.channel
                    newchannel = await channel.clone()
                    await newchannel.edit(position=channel.position)
                    await channel.delete()
                    embed = discord.Embed(description=f"💥 Channel nuked by **{ctx.author}**.", color=self.color)
                    embed.set_author(name="Channel Nuked")
                    embed.set_footer(text="Lucky Bot • lucky.gg")
                    await newchannel.send(embed=embed)
                else:
                    await interaction.response.edit_message(content="🃏 I'm missing `Manage Channels` permission.", embed=None, view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await interaction.response.edit_message(content="❌ Cancelled — nuke aborted.", embed=None, view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        embed = discord.Embed(color=self.color, description="⚠️ **Are you sure you want to nuke this channel?**")
        embed.set_footer(text="You have 30 seconds to decide!")
        view = View()
        button.callback = button_callback
        button1.callback = button1_callback
        view.add_item(button)
        view.add_item(button1)
        await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)

    @commands.hybrid_command(name="slowmode", help="Changes the slowmode", usage="slowmode [seconds]", aliases=["slow"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    async def _slowmode(self, ctx: commands.Context, seconds: int = 0):
        if seconds > 120:
            embed = discord.Embed(description="🃏 Slowmode cannot exceed 2 minutes.", color=self.color)
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send(embed=discord.Embed(title="Slowmode", description="🍀 Slowmode disabled.", color=0x57F287))
        else:
            embed = discord.Embed(description=f"🍀 Slowmode set to **{seconds}** second(s).", color=0x57F287)
            embed.set_author(name="Slowmode Activated")
            embed.set_footer(**self._footer(ctx))
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="unslowmode", help="Disables slowmode", usage="unslowmode", aliases=["unslow"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def _unslowmode(self, ctx: commands.Context):
        await ctx.channel.edit(slowmode_delay=0)
        embed = discord.Embed(description="🍀 Slowmode disabled.", color=0x57F287)
        embed.set_author(name="Slowmode Removed")
        embed.set_footer(**self._footer(ctx))
        await ctx.send(embed=embed)

    @commands.command(aliases=["deletesticker", "removesticker"], description="Delete a sticker from the server")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_emojis=True)
    @commands.bot_has_permissions(manage_emojis=True)
    async def delsticker(self, ctx: commands.Context, *, name=None):
        if ctx.message.reference is None:
            return await ctx.reply("🃏 No replied message found.")
        msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if len(msg.stickers) == 0:
            return await ctx.reply("🃏 No sticker found in that message.")
        try:
            sname = ""
            for i in msg.stickers:
                sname = i.name
                await ctx.guild.delete_sticker(i)
            await ctx.reply(f"🍀 Successfully deleted sticker named `{sname}`.")
        except Exception:
            await ctx.reply("🃏 Failed to delete the sticker.")

    @commands.command(aliases=["deleteemoji", "removeemoji"], description="Deletes an emoji from the server")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_emojis=True)
    async def delemoji(self, ctx, emoji: str = None):
        init_message = await ctx.reply("⏳ Processing emoji deletion...", mention_author=False)
        message_content = None

        if ctx.message.reference is not None:
            referenced_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            message_content = str(referenced_message.content)
        else:
            message_content = str(ctx.message.content)

        if message_content:
            emoji_pattern = r"<a?:\w+:(\d+)>"
            found_emojis = re.findall(emoji_pattern, message_content)
            delete_count = 0

            if len(found_emojis) != 0:
                if len(found_emojis) > 15:
                    await init_message.delete()
                    return await ctx.reply("🃏 Maximum 15 emojis can be deleted at a time.")

                for emoji_id in found_emojis:
                    try:
                        emoji_to_delete = await ctx.guild.fetch_emoji(int(emoji_id))
                        await emoji_to_delete.delete(reason=f"Deleted by {ctx.author}")
                        delete_count += 1
                    except (discord.NotFound, discord.Forbidden):
                        continue
                await init_message.delete()
                return await ctx.reply(f"🍀 Successfully deleted {delete_count}/{len(found_emojis)} emoji(s).")

        await init_message.delete()
        return await ctx.reply("🃏 No valid emoji found to delete.")

    @commands.command(description="Changes the icon for a role.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def roleicon(self, ctx: commands.Context, role: discord.Role, *, icon: Union[discord.Emoji, discord.PartialEmoji, str] = None):
        if role.position >= ctx.guild.me.top_role.position:
            embed = discord.Embed(color=self.color, description=f"🃏 {role.mention} is higher than my role. Please move my role above it.")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        if ctx.author != ctx.guild.owner and ctx.author.top_role.position <= role.position:
            embed = discord.Embed(color=self.color, description=f"🃏 {role.mention} has the same or higher position than your top role!")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        if icon is None:
            attachment_url = None
            for attachment in ctx.message.attachments:
                attachment_url = attachment.url
                break

            if attachment_url:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(attachment_url) as r:
                            image_data = await r.read()
                    await role.edit(display_icon=image_data)
                    embed = discord.Embed(color=0x57F287, description=f"🍀 Changed icon for {role.mention}.")
                    embed.set_footer(**self._footer(ctx))
                    return await ctx.send(embed=embed)
                except Exception:
                    return await ctx.reply("🃏 Failed to change the icon.")
            else:
                await role.edit(display_icon=None)
                embed = discord.Embed(color=0x57F287, description=f"🍀 Removed icon from {role.mention}.")
                embed.set_footer(**self._footer(ctx))
                return await ctx.reply(embed=embed, mention_author=False)

        if isinstance(icon, (discord.Emoji, discord.PartialEmoji)):
            emoji_url = f"https://cdn.discordapp.com/emojis/{icon.id}.png"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(emoji_url) as r:
                        image_data = await r.read()
                await role.edit(display_icon=image_data)
                embed = discord.Embed(color=0x57F287, description=f"🍀 Changed icon for {role.mention} to {icon}.")
                embed.set_footer(**self._footer(ctx))
                return await ctx.reply(embed=embed, mention_author=False)
            except Exception:
                return await ctx.reply("🃏 Failed to change the icon.")
        else:
            if not icon.startswith("https://"):
                return await ctx.reply("🃏 Please provide a valid HTTPS URL.")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(icon) as r:
                        image_data = await r.read()
                await role.edit(display_icon=image_data)
                embed = discord.Embed(color=0x57F287, description=f"🍀 Changed icon for {role.mention}.")
                embed.set_footer(**self._footer(ctx))
                return await ctx.reply(embed=embed, mention_author=False)
            except Exception:
                return await ctx.reply("🃏 An error occurred while changing the role icon.")

    @commands.hybrid_command(name="unbanall", help="Unbans everyone in the Guild!", aliases=["massunban"], usage="unbanall")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 30, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def unbanall(self, ctx):
        button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji="🍀")
        button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji="🃏")

        async def button_callback(interaction: discord.Interaction):
            a = 0
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.ban_members:
                    await interaction.response.edit_message(content="⏳ Unbanning all banned members...", embed=None, view=None)
                    async for idk in interaction.guild.bans(limit=None):
                        await interaction.guild.unban(user=idk.user, reason=f"Unbanall executed by {ctx.author}")
                        a += 1
                    await interaction.channel.send(content=f"🍀 Successfully unbanned {a} member(s).")
                else:
                    await interaction.response.edit_message(content="🃏 I'm missing `Ban Members` permission.", embed=None, view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await interaction.response.edit_message(content="❌ Cancelled — no one was unbanned.", embed=None, view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        embed = discord.Embed(color=self.color, description="⚠️ **Are you sure you want to unban all members in this guild?**")
        embed.set_footer(**self._footer(ctx))
        view = View()
        button.callback = button_callback
        button1.callback = button1_callback
        view.add_item(button)
        view.add_item(button1)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.hybrid_command(name="audit", help="View recent audit log actions in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(view_audit_log=True)
    @commands.bot_has_permissions(view_audit_log=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def auditlog(self, ctx, limit: int):
        if limit >= 31:
            return await ctx.reply("🃏 Cannot fetch more than `30` entries.", mention_author=False)
        entries = []
        log_str = ""
        async for entry in ctx.guild.audit_logs(limit=limit):
            entries.append(
                f"User: `{entry.user}`\nAction: `{entry.action}`\nTarget: `{entry.target}`\nReason: `{entry.reason}`\n\n"
            )
        for n in entries:
            log_str += n
        log_str = log_str.replace("AuditLogAction.", "")
        embed = discord.Embed(
            title=f"📜 Audit Logs — {ctx.guild.name}",
            description=f">>> {log_str}",
            color=self.color
        )
        embed.set_footer(text=f"Lucky Bot • lucky.gg | Audit logs for {ctx.guild.name}")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot):
    await bot.add_cog(Moderation(bot))

# Lucky Bot — Rewritten
