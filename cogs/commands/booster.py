from __future__ import annotations
import discord, asyncio, logging, aiosqlite, json, re
from discord.ext import commands
from utils.Tools import *
from core import Cog, Lucky, Context
from typing import *

class Booster(Cog):
    def __init__(self, bot: Lucky):
        self.bot = bot
        self.color = 0xFF4444
        self.db_path = "db/boost.db"
        self.bot.loop.create_task(self.setup_database())
        self.url_pattern = re.compile(
            r'^(?:http|ftp)s?://(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::\d+)?(?:/?|[/?]\S+)$',
            re.IGNORECASE)

    async def setup_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS boost_config (guild_id INTEGER PRIMARY KEY, config TEXT NOT NULL)")
            await db.commit()

    async def get_boost_config(self, guild_id: int) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT config FROM boost_config WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return json.loads(row[0])
                default = {"boost": {"channel": [], "message": "{user.mention} just boosted {server.name}! 🎉", "embed": True, "ping": False, "image": "", "thumbnail": "", "autodel": 0}, "boost_roles": {"roles": []}}
                await self.update_boost_config(guild_id, default)
                return default

    async def update_boost_config(self, guild_id: int, config: dict):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO boost_config (guild_id, config) VALUES (?, ?)", (guild_id, json.dumps(config)))
            await db.commit()

    def is_authorized(self, ctx) -> bool:
        return ctx.author == ctx.guild.owner or ctx.author.guild_permissions.administrator or ctx.author.top_role.position >= ctx.guild.me.top_role.position

    def format_boost_message(self, message: str, user: discord.Member, guild: discord.Guild) -> str:
        replacements = {
            "{server.name}": guild.name, "{server.id}": str(guild.id), "{server.owner}": str(guild.owner),
            "{server.icon}": guild.icon.url if guild.icon else "", "{server.boost_count}": str(guild.premium_subscription_count),
            "{server.boost_level}": f"Level {guild.premium_tier}", "{server.member_count}": str(guild.member_count),
            "{user.name}": user.display_name, "{user.mention}": user.mention, "{user.tag}": str(user),
            "{user.id}": str(user.id), "{user.avatar}": user.display_avatar.url,
            "{user.created_at}": f"<t:{int(user.created_at.timestamp())}:F>",
            "{user.joined_at}": f"<t:{int(user.joined_at.timestamp())}:F>" if user.joined_at else "Unknown",
            "{user.top_role}": user.top_role.name if user.top_role else "None",
            "{user.is_booster}": str(bool(user.premium_since)), "{user.is_mobile}": str(user.is_on_mobile()),
            "{user.boosted_at}": f"<t:{int(user.premium_since.timestamp())}:F>" if user.premium_since else "Unknown",
        }
        for old, new in replacements.items():
            message = message.replace(old, new)
        return message

    async def send_permission_error(self, ctx):
        embed = discord.Embed(description="```diff\n- You must have Administrator permission.\n- Your top role should be above my top role.\n```", color=self.color)
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    def _embed(self, description, ctx=None):
        e = discord.Embed(color=self.color, description=description)
        if ctx:
            e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        e.set_footer(text="Lucky Bot • lucky.gg")
        return e

    @commands.group(name="boost", aliases=["bst"], invoke_without_command=True, help="Boost message configuration commands")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _boost(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @_boost.command(name="thumbnail")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _boost_thumbnail(self, ctx, thumbnail_url: str):
        if not self.is_authorized(ctx):
            return await self.send_permission_error(ctx)
        if not self.url_pattern.match(thumbnail_url):
            return await ctx.send(embed=self._embed("🃏 Please provide a valid URL.", ctx))
        data = await self.get_boost_config(ctx.guild.id)
        data["boost"]["thumbnail"] = thumbnail_url
        await self.update_boost_config(ctx.guild.id, data)
        await ctx.send(embed=self._embed("🍀 Successfully updated the boost thumbnail URL.", ctx))

    @_boost.command(name="image")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _boost_image(self, ctx, *, image_url: str):
        if not self.is_authorized(ctx):
            return await self.send_permission_error(ctx)
        if not self.url_pattern.match(image_url):
            return await ctx.send(embed=self._embed("🃏 Please provide a valid URL.", ctx))
        data = await self.get_boost_config(ctx.guild.id)
        data["boost"]["image"] = image_url
        await self.update_boost_config(ctx.guild.id, data)
        await ctx.send(embed=self._embed("🍀 Successfully updated the boost image URL.", ctx))

    @_boost.command(name="autodel")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _boost_autodel(self, ctx, seconds: int):
        if not self.is_authorized(ctx):
            return await self.send_permission_error(ctx)
        if seconds < 0:
            return await ctx.send(embed=self._embed("🃏 Auto-delete timer must be 0 or greater.", ctx))
        data = await self.get_boost_config(ctx.guild.id)
        data["boost"]["autodel"] = seconds
        await self.update_boost_config(ctx.guild.id, data)
        desc = "🍀 Auto-delete has been disabled." if seconds == 0 else f"🍀 Auto-delete timer set to {seconds} seconds."
        await ctx.send(embed=self._embed(desc, ctx))

    @_boost.command(name="message")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _boost_message(self, ctx):
        if not self.is_authorized(ctx):
            return await self.send_permission_error(ctx)
        embed = discord.Embed(color=self.color, title="🍀 Boost Message Setup",
            description="Send your boost message now.\n\nVariables: `{user.mention}`, `{user.name}`, `{server.name}`, `{server.boost_count}`, etc.")
        embed.set_footer(text="You have 60 seconds to respond")
        await ctx.send(embed=embed)
        def check(m): return m.author == ctx.author and m.channel == ctx.channel
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=60.0)
        except asyncio.TimeoutError:
            return await ctx.send(embed=self._embed("⏰ Timeout! Please try again.", ctx))
        data = await self.get_boost_config(ctx.guild.id)
        data["boost"]["message"] = msg.content
        await self.update_boost_config(ctx.guild.id, data)
        await ctx.send(embed=self._embed("🍀 Successfully updated the boost message.", ctx))

    @_boost.command(name="embed")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _boost_embed(self, ctx):
        if not self.is_authorized(ctx):
            return await self.send_permission_error(ctx)
        data = await self.get_boost_config(ctx.guild.id)
        data["boost"]["embed"] = not data["boost"]["embed"]
        await self.update_boost_config(ctx.guild.id, data)
        status = "enabled" if data["boost"]["embed"] else "disabled"
        await ctx.send(embed=self._embed(f"🍀 Embed formatting has been **{status}**.", ctx))

    @_boost.command(name="ping")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _boost_ping(self, ctx):
        if not self.is_authorized(ctx):
            return await self.send_permission_error(ctx)
        data = await self.get_boost_config(ctx.guild.id)
        data["boost"]["ping"] = not data["boost"]["ping"]
        await self.update_boost_config(ctx.guild.id, data)
        status = "enabled" if data["boost"]["ping"] else "disabled"
        await ctx.send(embed=self._embed(f"🍀 Booster pinging has been **{status}**.", ctx))

    @_boost.group(name="channel")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _boost_channel(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)

    @_boost_channel.command(name="add")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _boost_channel_add(self, ctx, channel: discord.TextChannel):
        if not self.is_authorized(ctx):
            return await self.send_permission_error(ctx)
        data = await self.get_boost_config(ctx.guild.id)
        channels = data["boost"]["channel"]
        if len(channels) >= 3:
            return await ctx.send(embed=self._embed("🃏 Maximum boost channel limit reached (3 channels).", ctx))
        if str(channel.id) in channels:
            return await ctx.send(embed=self._embed("🃏 This channel is already in the boost channels list.", ctx))
        channels.append(str(channel.id))
        await self.update_boost_config(ctx.guild.id, data)
        await ctx.send(embed=self._embed(f"🍀 Successfully added {channel.mention} to boost channels list.", ctx))

    @_boost_channel.command(name="remove")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _boost_channel_remove(self, ctx, channel: discord.TextChannel):
        if not self.is_authorized(ctx):
            return await self.send_permission_error(ctx)
        data = await self.get_boost_config(ctx.guild.id)
        channels = data["boost"]["channel"]
        if not channels:
            return await ctx.send(embed=self._embed("🃏 No boost channels are currently set up.", ctx))
        if str(channel.id) not in channels:
            return await ctx.send(embed=self._embed("🃏 This channel is not in the boost channels list.", ctx))
        channels.remove(str(channel.id))
        await self.update_boost_config(ctx.guild.id, data)
        await ctx.send(embed=self._embed(f"🍀 Successfully removed {channel.mention} from boost channels list.", ctx))

    @_boost.command(name="test")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _boost_test(self, ctx):
        data = await self.get_boost_config(ctx.guild.id)
        channels = data["boost"]["channel"]
        if not channels:
            return await ctx.send(embed=self._embed("🃏 Please set up a boost channel first.", ctx))
        formatted_message = self.format_boost_message(data["boost"]["message"], ctx.author, ctx.guild)
        channel = self.bot.get_channel(int(channels[0]))
        if not channel:
            return await ctx.send(embed=self._embed("🃏 The configured boost channel no longer exists.", ctx))
        try:
            if data["boost"]["embed"]:
                embed = discord.Embed(description=formatted_message, color=self.color)
                embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
                embed.timestamp = discord.utils.utcnow()
                if data["boost"]["image"]:
                    embed.set_image(url=data["boost"]["image"])
                if data["boost"]["thumbnail"]:
                    embed.set_thumbnail(url=data["boost"]["thumbnail"])
                embed.set_footer(text="Lucky Bot • lucky.gg")
                ping_content = ctx.author.mention if data["boost"]["ping"] else ""
                await channel.send(ping_content, embed=embed)
            else:
                await channel.send(formatted_message)
        except discord.Forbidden:
            await ctx.send(embed=self._embed("🃏 I don't have permission to send messages in the boost channel.", ctx))
        except Exception as e:
            await ctx.send(embed=self._embed(f"🃏 An error occurred: `{str(e)}`", ctx))

    @_boost.command(name="config")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def _boost_config(self, ctx):
        data = await self.get_boost_config(ctx.guild.id)
        channels = data["boost"]["channel"]
        if not channels:
            return await ctx.send(embed=self._embed("🃏 Please set up a boost channel first.", ctx))
        embed = discord.Embed(color=self.color, title=f"✨ Boost Configuration for {ctx.guild.name}")
        embed.set_footer(text="Lucky Bot • lucky.gg")
        channel_mentions = [self.bot.get_channel(int(cid)).mention for cid in channels if self.bot.get_channel(int(cid))]
        embed.add_field(name="Channels", value="\n".join(channel_mentions) if channel_mentions else "None", inline=False)
        embed.add_field(name="Message", value=f"```{data['boost']['message']}```", inline=False)
        embed.add_field(name="Embed", value="🍀 Enabled" if data["boost"]["embed"] else "🃏 Disabled", inline=True)
        embed.add_field(name="Ping", value="🍀 Enabled" if data["boost"]["ping"] else "🃏 Disabled", inline=True)
        embed.add_field(name="Auto-delete", value=f"{data['boost']['autodel']}s" if data["boost"]["autodel"] else "Disabled", inline=True)
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        await ctx.send(embed=embed)

    @_boost.command(name="reset")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def _boost_reset(self, ctx):
        if not self.is_authorized(ctx):
            return await self.send_permission_error(ctx)
        data = await self.get_boost_config(ctx.guild.id)
        if not data["boost"]["channel"]:
            return await ctx.send(embed=self._embed("🃏 No boost configuration found to reset.", ctx))
        data["boost"].update({"channel": [], "image": "", "message": "{user.mention} just boosted {server.name}! 🎉", "thumbnail": "", "embed": True, "ping": False, "autodel": 0})
        await self.update_boost_config(ctx.guild.id, data)
        await ctx.send(embed=self._embed("🍀 Successfully reset all boost configuration.", ctx))

    @commands.group(name="boostrole", invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def _boostrole(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @_boostrole.command(name="config")
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def _boostrole_config(self, ctx):
        data = await self.get_boost_config(ctx.guild.id)
        role_ids = data["boost_roles"]["roles"]
        if not role_ids:
            embed = discord.Embed(color=self.color, title=f"Boost Roles - {ctx.guild.name}", description="No boost roles configured.")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)
        roles = [ctx.guild.get_role(int(r)).mention for r in role_ids if ctx.guild.get_role(int(r))]
        embed = discord.Embed(color=self.color, title=f"Boost Roles - {ctx.guild.name}")
        embed.add_field(name="Roles", value="\n".join(roles) if roles else "No valid roles found", inline=False)
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @_boostrole.command(name="add")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _boostrole_add(self, ctx, role: discord.Role):
        if not self.is_authorized(ctx):
            return await self.send_permission_error(ctx)
        data = await self.get_boost_config(ctx.guild.id)
        roles = data["boost_roles"]["roles"]
        if len(roles) >= 10:
            return await ctx.send(embed=self._embed("🃏 Maximum boost role limit reached (10 roles).", ctx))
        if str(role.id) in roles:
            return await ctx.send(embed=self._embed(f"🃏 {role.mention} is already a boost role.", ctx))
        roles.append(str(role.id))
        await self.update_boost_config(ctx.guild.id, data)
        await ctx.send(embed=self._embed(f"🍀 {role.mention} has been added as a boost role.", ctx))

    @_boostrole.command(name="remove")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _boostrole_remove(self, ctx, role: discord.Role):
        if not self.is_authorized(ctx):
            return await self.send_permission_error(ctx)
        data = await self.get_boost_config(ctx.guild.id)
        roles = data["boost_roles"]["roles"]
        if not roles:
            return await ctx.send(embed=self._embed("🃏 No boost roles are currently configured.", ctx))
        if str(role.id) not in roles:
            return await ctx.send(embed=self._embed(f"🃏 {role.mention} is not a boost role.", ctx))
        roles.remove(str(role.id))
        await self.update_boost_config(ctx.guild.id, data)
        await ctx.send(embed=self._embed(f"🍀 {role.mention} has been removed from boost roles.", ctx))

    @_boostrole.command(name="reset")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def _boostrole_reset(self, ctx):
        if not self.is_authorized(ctx):
            return await self.send_permission_error(ctx)
        data = await self.get_boost_config(ctx.guild.id)
        if not data["boost_roles"]["roles"]:
            return await ctx.send(embed=self._embed("🃏 No boost roles are currently configured.", ctx))
        data["boost_roles"]["roles"] = []
        await self.update_boost_config(ctx.guild.id, data)
        await ctx.send(embed=self._embed("🍀 Successfully cleared all boost roles.", ctx))


async def setup(bot):
    await bot.add_cog(Booster(bot))

# Lucky Bot — Rewritten
