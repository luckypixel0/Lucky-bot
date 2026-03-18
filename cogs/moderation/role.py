import discord
from discord.ext import commands
import asyncio
import re
from typing import Union, Optional
from utils.Tools import *
from discord.ui import Button, View


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


class Role(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF4444

    def _footer(self, ctx):
        return {"text": f"Lucky Bot • lucky.gg | Requested by {ctx.author}",
                "icon_url": ctx.author.display_avatar.url}

    def _access_denied_embed(self, ctx):
        embed = discord.Embed(title="🃏 Access Denied", description="Your role must be above my top role.", color=self.color)
        embed.set_footer(**self._footer(ctx))
        return embed

    def _has_elevation(self, ctx):
        return ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position

    @commands.group(name="role", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(manage_roles=True)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @top_check()
    async def role(self, ctx, member: discord.Member, *, role: discord.Role):
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
                success = discord.Embed(color=0x57F287, description=f"🍀 Successfully **added** {role.mention} to {member.mention}.")
                success.set_author(name="Role Added")
            else:
                await member.remove_roles(role, reason=f"Role removed by {ctx.author} (ID: {ctx.author.id})")
                success = discord.Embed(color=0x57F287, description=f"🍀 Successfully **removed** {role.mention} from {member.mention}.")
                success.set_author(name="Role Removed")
            success.set_footer(**self._footer(ctx))
            await ctx.send(embed=success)
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(color=self.color, description="🃏 I don't have permission to manage roles for this user!"))
        except Exception as e:
            await ctx.send(embed=discord.Embed(color=self.color, description=f"🃏 An unexpected error occurred: {str(e)}"))

    @role.command(help="Give a role to a member for a specified time")
    @commands.bot_has_permissions(manage_roles=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    @commands.has_permissions(manage_roles=True)
    async def temp(self, ctx, role: discord.Role, time, *, user: discord.Member):
        if ctx.author != ctx.guild.owner and role.position >= ctx.author.top_role.position:
            embed = discord.Embed(color=self.color, description="🃏 You can't manage a role higher or equal to your top role!")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        if role.position >= ctx.guild.me.top_role.position:
            embed = discord.Embed(color=self.color, description=f"🃏 {role.mention} is higher than my top role.")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        seconds = convert(time)
        await user.add_roles(role)
        success = discord.Embed(color=0x57F287, description=f"🍀 Added {role.mention} to {user.mention} for `{time}`.")
        success.set_author(name="Temporary Role Added")
        success.set_footer(**self._footer(ctx))
        await ctx.send(embed=success)
        await asyncio.sleep(seconds)
        await user.remove_roles(role)

    @role.command(help="Delete a role from the guild")
    @blacklist_check()
    @ignore_check()
    @top_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def delete(self, ctx, *, role: discord.Role):
        if ctx.author != ctx.guild.owner and role.position >= ctx.author.top_role.position:
            embed = discord.Embed(color=self.color, description="🃏 You cannot delete a role higher or equal to your top role!")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        if role.position >= ctx.guild.me.top_role.position:
            embed = discord.Embed(color=self.color, description=f"🃏 I cannot delete {role.mention} — it's higher than my top role.")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        await role.delete()
        embed = discord.Embed(color=0x57F287, description=f"🍀 Successfully deleted **{role.name}**.")
        embed.set_author(name="Role Deleted")
        embed.set_footer(**self._footer(ctx))
        await ctx.send(embed=embed)

    @role.command(help="Create a role in the guild")
    @blacklist_check()
    @ignore_check()
    @top_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def create(self, ctx, *, name):
        await ctx.guild.create_role(name=name, color=discord.Color.default())
        embed = discord.Embed(color=0x57F287, description=f"🍀 Successfully created role **{name}**.")
        embed.set_author(name="Role Created")
        embed.set_footer(**self._footer(ctx))
        await ctx.send(embed=embed)

    @role.command(help="Rename a role in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def rename(self, ctx, role: discord.Role, *, newname):
        if role.position >= ctx.author.top_role.position:
            embed = discord.Embed(color=self.color, description=f"🃏 You can't manage {role.mention} — it's higher or equal to your top role.")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        if role.position >= ctx.guild.me.top_role.position:
            embed = discord.Embed(color=self.color, description=f"🃏 I can't manage {role.mention} — it's higher than my top role.")
            embed.set_footer(**self._footer(ctx))
            return await ctx.send(embed=embed)

        await role.edit(name=newname)
        embed = discord.Embed(color=0x57F287, description=f"🍀 Role renamed to **{newname}**.")
        embed.set_author(name="Role Renamed")
        embed.set_footer(**self._footer(ctx))
        await ctx.send(embed=embed)

    @role.command(name="humans", help="Give a role to all humans in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def role_humans(self, ctx, *, role: discord.Role):
        if not self._has_elevation(ctx):
            return await ctx.send(embed=self._access_denied_embed(ctx))

        members_without_role = [m for m in ctx.guild.members if not m.bot and role not in m.roles]
        if not members_without_role:
            return await ctx.reply(embed=discord.Embed(color=self.color, description=f"🎴 All humans already have {role.mention}."))

        button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji="🍀")
        button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji="🃏")

        async def button_callback(interaction: discord.Interaction):
            count = 0
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.manage_roles:
                    await interaction.response.edit_message(embed=discord.Embed(color=self.color, description=f"⏳ Assigning {role.mention} to all humans..."), view=None)
                    for member in interaction.guild.members:
                        if not member.bot and role not in member.roles:
                            try:
                                await member.add_roles(role, reason=f"Role Humans by {ctx.author}")
                                count += 1
                            except Exception:
                                pass
                    await interaction.channel.send(content=f"🍀 Assigned {role.mention} to {count} human(s).")
                else:
                    await interaction.response.edit_message(content="🃏 I'm missing required permissions.", embed=None, view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await interaction.response.edit_message(embed=discord.Embed(color=self.color, description="❌ Cancelled."), view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        embed = discord.Embed(color=self.color, description=f"⏳ Assign {role.mention} to {len(members_without_role)} human(s)?")
        view = View()
        button.callback = button_callback
        button1.callback = button1_callback
        view.add_item(button)
        view.add_item(button1)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @role.command(name="bots", help="Give a role to all bots in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def role_bots(self, ctx, *, role: discord.Role):
        if not self._has_elevation(ctx):
            return await ctx.send(embed=self._access_denied_embed(ctx))

        bots_without_role = [m for m in ctx.guild.members if m.bot and role not in m.roles]
        if not bots_without_role:
            return await ctx.reply(embed=discord.Embed(color=self.color, description=f"🎴 All bots already have {role.mention}."))

        button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji="🍀")
        button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji="🃏")

        async def button_callback(interaction: discord.Interaction):
            count = 0
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.manage_roles:
                    await interaction.response.edit_message(embed=discord.Embed(color=self.color, description=f"⏳ Adding {role.mention} to all bots..."), view=None)
                    for member in interaction.guild.members:
                        if member.bot and role not in member.roles:
                            try:
                                await member.add_roles(role, reason=f"Role Bots by {ctx.author}")
                                count += 1
                            except Exception:
                                pass
                    await interaction.channel.send(content=f"🍀 Added {role.mention} to {count} bot(s).")
                else:
                    await interaction.response.edit_message(content="🃏 I'm missing required permissions.", embed=None, view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await interaction.response.edit_message(embed=discord.Embed(color=self.color, description="❌ Cancelled."), view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        embed = discord.Embed(color=self.color, description=f"⏳ Give {role.mention} to {len(bots_without_role)} bot(s)?")
        view = View()
        button.callback = button_callback
        button1.callback = button1_callback
        view.add_item(button)
        view.add_item(button1)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @role.command(name="unverified", help="Give a role to all unverified members in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def role_unverified(self, ctx, *, role: discord.Role):
        if not self._has_elevation(ctx):
            return await ctx.send(embed=self._access_denied_embed(ctx))

        button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji="🍀")
        button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji="🃏")

        async def button_callback(interaction: discord.Interaction):
            count = 0
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.manage_roles:
                    await interaction.response.edit_message(embed=discord.Embed(color=self.color, description=f"⏳ Adding {role.mention} to unverified members..."), view=None)
                    for member in interaction.guild.members:
                        if member.avatar is None and role not in member.roles:
                            try:
                                await member.add_roles(role, reason=f"Role Unverified by {ctx.author}")
                                count += 1
                            except Exception:
                                pass
                    await interaction.channel.send(content=f"🍀 Added {role.mention} to {count} unverified member(s).")
                else:
                    await interaction.response.edit_message(content="🃏 I'm missing required permissions.", embed=None, view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await interaction.response.edit_message(embed=discord.Embed(color=self.color, description="❌ Cancelled."), view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        embed = discord.Embed(color=self.color, description=f"⏳ Give {role.mention} to all unverified members?")
        view = View()
        button.callback = button_callback
        button1.callback = button1_callback
        view.add_item(button)
        view.add_item(button1)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @role.command(name="all", help="Give a role to all members in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def role_all(self, ctx, *, role: discord.Role):
        if not self._has_elevation(ctx):
            return await ctx.send(embed=self._access_denied_embed(ctx))

        members_without_role = [m for m in ctx.guild.members if role not in m.roles]
        if not members_without_role:
            return await ctx.reply(embed=discord.Embed(color=self.color, description=f"🎴 {role.mention} is already assigned to all members."))

        button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji="🍀")
        button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji="🃏")

        async def button_callback(interaction: discord.Interaction):
            count = 0
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.manage_roles:
                    await interaction.response.edit_message(embed=discord.Embed(color=self.color, description=f"⏳ Adding {role.mention} to all members..."), view=None)
                    for member in interaction.guild.members:
                        try:
                            await member.add_roles(role, reason=f"Role All by {ctx.author}")
                            count += 1
                        except Exception:
                            pass
                    await interaction.channel.send(content=f"🍀 Added {role.mention} to {count} member(s).")
                else:
                    await interaction.response.edit_message(content="🃏 I'm missing required permissions.", embed=None, view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await interaction.response.edit_message(embed=discord.Embed(color=self.color, description="❌ Cancelled."), view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        embed = discord.Embed(color=self.color, description=f"⏳ Give {role.mention} to {len(members_without_role)} member(s)?")
        view = View()
        button.callback = button_callback
        button1.callback = button1_callback
        view.add_item(button)
        view.add_item(button1)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.group(name="removerole", invoke_without_command=True, aliases=["rrole"], help="Remove a role from members.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def rrole(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @rrole.command(name="humans", help="Remove a role from all humans in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def rrole_humans(self, ctx, *, role: discord.Role):
        if not self._has_elevation(ctx):
            return await ctx.send(embed=self._access_denied_embed(ctx))

        humans_with_role = [m for m in ctx.guild.members if not m.bot and role in m.roles]
        if not humans_with_role:
            return await ctx.reply(embed=discord.Embed(color=self.color, description=f"🎴 No humans have {role.mention}."))

        button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji="🍀")
        button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji="🃏")

        async def button_callback(interaction: discord.Interaction):
            count = 0
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.manage_roles:
                    await interaction.response.edit_message(embed=discord.Embed(color=self.color, description=f"⏳ Removing {role.mention} from all humans..."), view=None)
                    for member in interaction.guild.members:
                        if not member.bot and role in member.roles:
                            try:
                                await member.remove_roles(role, reason=f"Remove Role Humans by {ctx.author}")
                                count += 1
                            except Exception:
                                pass
                    await interaction.channel.send(content=f"🍀 Removed {role.mention} from {count} human(s).")
                else:
                    await interaction.response.edit_message(content="🃏 I'm missing required permissions.", embed=None, view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await interaction.response.edit_message(embed=discord.Embed(color=self.color, description="❌ Cancelled."), view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        embed = discord.Embed(color=self.color, description=f"⏳ Remove {role.mention} from {len(humans_with_role)} human(s)?")
        view = View()
        button.callback = button_callback
        button1.callback = button1_callback
        view.add_item(button)
        view.add_item(button1)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @rrole.command(name="bots", help="Remove a role from all bots in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def rrole_bots(self, ctx, *, role: discord.Role):
        if not self._has_elevation(ctx):
            return await ctx.send(embed=self._access_denied_embed(ctx))

        bots_with_role = [m for m in ctx.guild.members if m.bot and role in m.roles]
        if not bots_with_role:
            return await ctx.reply(embed=discord.Embed(color=self.color, description=f"🎴 No bots have {role.mention}."))

        button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji="🍀")
        button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji="🃏")

        async def button_callback(interaction: discord.Interaction):
            count = 0
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.manage_roles:
                    await interaction.response.edit_message(embed=discord.Embed(color=self.color, description=f"⏳ Removing {role.mention} from all bots..."), view=None)
                    for member in interaction.guild.members:
                        if member.bot and role in member.roles:
                            try:
                                await member.remove_roles(role, reason=f"Remove Role Bots by {ctx.author}")
                                count += 1
                            except Exception:
                                pass
                    await interaction.channel.send(content=f"🍀 Removed {role.mention} from {count} bot(s).")
                else:
                    await interaction.response.edit_message(content="🃏 I'm missing required permissions.", embed=None, view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await interaction.response.edit_message(embed=discord.Embed(color=self.color, description="❌ Cancelled."), view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        embed = discord.Embed(color=self.color, description=f"⏳ Remove {role.mention} from {len(bots_with_role)} bot(s)?")
        view = View()
        button.callback = button_callback
        button1.callback = button1_callback
        view.add_item(button)
        view.add_item(button1)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @rrole.command(name="all", help="Remove a role from all members in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def rrole_all(self, ctx, *, role: discord.Role):
        if not self._has_elevation(ctx):
            return await ctx.send(embed=self._access_denied_embed(ctx))

        members_with_role = [m for m in ctx.guild.members if role in m.roles]
        if not members_with_role:
            return await ctx.reply(embed=discord.Embed(color=self.color, description=f"🎴 No members have {role.mention}."))

        button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji="🍀")
        button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji="🃏")

        async def button_callback(interaction: discord.Interaction):
            removed_count = 0
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.manage_roles:
                    await interaction.response.edit_message(embed=discord.Embed(color=self.color, description=f"⏳ Removing {role.mention} from all members..."), view=None)
                    for member in interaction.guild.members:
                        if role in member.roles:
                            try:
                                await member.remove_roles(role, reason=f"Remove Role All by {ctx.author}")
                                removed_count += 1
                            except Exception:
                                pass
                    await interaction.channel.send(content=f"🍀 Removed {role.mention} from {removed_count} member(s).")
                else:
                    await interaction.response.edit_message(content="🃏 I'm missing required permissions.", embed=None, view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await interaction.response.edit_message(embed=discord.Embed(color=self.color, description="❌ Cancelled."), view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        embed = discord.Embed(color=self.color, description=f"⏳ Remove {role.mention} from {len(members_with_role)} member(s)?")
        view = View()
        button.callback = button_callback
        button1.callback = button1_callback
        view.add_item(button)
        view.add_item(button1)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @rrole.command(name="unverified", help="Remove a role from all unverified members in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def rrole_unverified(self, ctx, *, role: discord.Role):
        if not self._has_elevation(ctx):
            return await ctx.send(embed=self._access_denied_embed(ctx))

        unverified_members = [m for m in ctx.guild.members if m.avatar is None and role in m.roles]
        if not unverified_members:
            return await ctx.reply(embed=discord.Embed(color=self.color, description=f"🎴 No unverified members have {role.mention}."))

        button = Button(label="Yes", style=discord.ButtonStyle.green, emoji="🍀")
        button1 = Button(label="No", style=discord.ButtonStyle.red, emoji="🃏")

        async def button_callback(interaction: discord.Interaction):
            count = 0
            if interaction.user == ctx.author:
                if interaction.guild.me.guild_permissions.manage_roles:
                    await interaction.response.edit_message(embed=discord.Embed(color=self.color, description=f"⏳ Removing {role.mention} from unverified members..."), view=None)
                    for member in interaction.guild.members:
                        if member.avatar is None and role in member.roles:
                            try:
                                await member.remove_roles(role, reason=f"Remove Role Unverified by {ctx.author}")
                                count += 1
                            except Exception:
                                pass
                    await interaction.channel.send(content=f"🍀 Removed {role.mention} from {count} unverified member(s).")
                else:
                    await interaction.response.edit_message(content="🃏 I'm missing required permissions.", embed=None, view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        async def button1_callback(interaction: discord.Interaction):
            if interaction.user == ctx.author:
                await interaction.response.edit_message(embed=discord.Embed(color=self.color, description="❌ Cancelled."), view=None)
            else:
                await interaction.response.send_message("🃏 This interaction isn't for you.", ephemeral=True)

        embed = discord.Embed(color=self.color, description=f"⏳ Remove {role.mention} from {len(unverified_members)} unverified member(s)?")
        view = View()
        button.callback = button_callback
        button1.callback = button1_callback
        view.add_item(button)
        view.add_item(button1)
        await ctx.reply(embed=embed, view=view, mention_author=False)


async def setup(bot):
    await bot.add_cog(Role(bot))

# Lucky Bot — Rewritten
