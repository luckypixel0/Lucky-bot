import discord
from discord.ext import commands
from discord.ui import View, Select, Button
import asyncio
import aiofiles
import json
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pathlib import Path
import os

from utils.Tools import *

LOG_CATEGORIES = [
    "message_events", "join_leave_events", "member_moderation", "voice_events",
    "channel_events", "role_events", "emoji_events", "reaction_events", "system_events"
]

CONFIG_FILE = "jsondb/logging_config.json"
LOGS_DIR = "logs"

Path(LOGS_DIR).mkdir(exist_ok=True)
Path("jsondb").mkdir(exist_ok=True)

EMBED_COLOR = 0x2F3136
SUCCESS_COLOR = 0x57F287
ERROR_COLOR = 0xFF4444
INFO_COLOR = 0x5865F2


# ── UI ─────────────────────────────────────────────────────────────────────────

class ChannelSelectView(View):
    def __init__(self, bot, author, category, parent_view):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.category = category
        self.parent_view = parent_view
        self.all_channels = []
        self.channels_per_page = 20
        self.current_page = 0
        self.total_pages = 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "Only the command author can interact with this menu.", ephemeral=True
            )
            return False
        return True


class LogSetupView(View):
    def __init__(self, bot: commands.Bot, author: discord.Member, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.author = author
        self.selected_channels: Dict[str, Optional[int]] = {cat: None for cat in LOG_CATEGORIES}
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "Only the command author can interact with this menu.", ephemeral=True
                    )
            except (discord.NotFound, discord.HTTPException):
                pass
            return False
        return True

    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass

    @discord.ui.select(placeholder="Choose a logging category to configure...")
    async def category_select(self, interaction: discord.Interaction, select: Select):
        try:
            if select.values[0] == "finish":
                await self.finish_setup(interaction)
                return

            category = select.values[0]
            guild = interaction.guild
            text_channels = [
                ch for ch in guild.text_channels
                if ch.permissions_for(guild.me).send_messages
            ]

            embed = discord.Embed(
                title=f"Select Channel for {category.replace('_', ' ').title()}",
                description=f"Choose where to log {category.replace('_', ' ').lower()} events.",
                color=INFO_COLOR
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")

            if not text_channels:
                await interaction.response.send_message(
                    "No accessible text channels found.", ephemeral=True
                )
                return

            options = [
                discord.SelectOption(
                    label=f"#{ch.name}"[:100],
                    value=str(ch.id),
                    description=f"ID: {ch.id}"
                )
                for ch in text_channels[:25]
            ]
            options.append(discord.SelectOption(label="Disable (remove logging)", value="disable"))

            channel_view = View(timeout=120)
            channel_select = Select(placeholder="Select a channel...", options=options)

            async def ch_callback(i: discord.Interaction):
                if i.user != self.author:
                    return
                val = channel_select.values[0]
                if val == "disable":
                    self.selected_channels[category] = None
                else:
                    self.selected_channels[category] = int(val)

                status_embed = discord.Embed(
                    title="🧩 Logging Setup",
                    description="Configure channels for each logging category below.",
                    color=INFO_COLOR
                )
                for cat in LOG_CATEGORIES:
                    ch_id = self.selected_channels.get(cat)
                    if ch_id:
                        ch_obj = guild.get_channel(ch_id)
                        status_embed.add_field(
                            name=cat.replace('_', ' ').title(),
                            value=ch_obj.mention if ch_obj else "Invalid channel",
                            inline=True
                        )
                    else:
                        status_embed.add_field(
                            name=cat.replace('_', ' ').title(),
                            value="Not configured",
                            inline=True
                        )
                status_embed.set_footer(text="Select 'Finish Setup' when done | Lucky Bot • lucky.gg")

                options_list = [
                    discord.SelectOption(
                        label=cat.replace('_', ' ').title(),
                        value=cat,
                        description=f"Configure {cat.replace('_', ' ').lower()}"
                    )
                    for cat in LOG_CATEGORIES
                ]
                options_list.append(
                    discord.SelectOption(label="Finish Setup", value="finish", description="Complete the setup")
                )
                self.category_select.options = options_list
                await i.response.edit_message(embed=status_embed, view=self)

            channel_select.callback = ch_callback
            channel_view.add_item(channel_select)
            await interaction.response.edit_message(embed=embed, view=channel_view)
        except Exception:
            pass

    async def finish_setup(self, interaction: discord.Interaction):
        configured = {
            cat: ch_id for cat, ch_id in self.selected_channels.items() if ch_id
        }
        if not configured:
            await interaction.response.send_message(
                "Please configure at least one category.", ephemeral=True
            )
            return

        cog = interaction.client.cogs.get("Logging")
        if cog:
            guild_id = interaction.guild.id
            cog.config_cache[guild_id] = {
                "channels": configured,
                "enabled": True,
                "ignored_channels": [],
                "ignored_roles": []
            }
            await cog._save_config()

        embed = discord.Embed(
            title="🍀 Logging Setup Complete",
            description=f"Configured logging for {len(configured)} categories.",
            color=SUCCESS_COLOR
        )
        for cat, ch_id in configured.items():
            ch = interaction.guild.get_channel(ch_id)
            embed.add_field(
                name=cat.replace('_', ' ').title(),
                value=ch.mention if ch else "Unknown",
                inline=True
            )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


# ── Cog ────────────────────────────────────────────────────────────────────────

class Logging(commands.Cog):
    """Comprehensive logging cog with modern UI and expanded event coverage."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config_cache: Dict[int, Dict[str, Any]] = {}
        self.config_lock = asyncio.Lock()
        asyncio.create_task(self._load_config())

    async def _load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                async with aiofiles.open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if content.strip():
                        data = json.loads(content)
                        for guild_id_str, config in data.items():
                            try:
                                self.config_cache[int(guild_id_str)] = config
                            except (ValueError, TypeError):
                                pass
        except Exception:
            self.config_cache = {}

    async def _save_config(self):
        async with self.config_lock:
            try:
                data = {str(k): v for k, v in self.config_cache.items()}
                content = json.dumps(data, indent=2)
                async with aiofiles.open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    await f.write(content)
            except Exception:
                pass

    def get_config(self, guild_id: int) -> Optional[Dict]:
        return self.config_cache.get(guild_id)

    def get_log_channel(self, guild: discord.Guild, category: str) -> Optional[discord.TextChannel]:
        config = self.get_config(guild.id)
        if not config or not config.get("enabled"):
            return None
        ch_id = config.get("channels", {}).get(category)
        if ch_id:
            return guild.get_channel(ch_id)
        return None

    def is_ignored(self, guild_id: int, channel_id: int = None, role_ids: List[int] = None) -> bool:
        config = self.get_config(guild_id)
        if not config:
            return False
        if channel_id and channel_id in config.get("ignored_channels", []):
            return True
        if role_ids:
            for rid in role_ids:
                if rid in config.get("ignored_roles", []):
                    return True
        return False

    def _create_embed(self, title: str, description: str = None, color: int = EMBED_COLOR) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.utcnow())
        embed.set_footer(text="Lucky Bot • lucky.gg")
        return embed

    async def _send_log(self, guild: discord.Guild, category: str, embed: discord.Embed):
        ch = self.get_log_channel(guild, category)
        if ch:
            try:
                await ch.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

    # ── Commands ───────────────────────────────────────────────────────────────

    @commands.group(name="log", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def log(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)

    @log.command(name="setup")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def log_setup(self, ctx: commands.Context):
        view = LogSetupView(self.bot, ctx.author)

        options = [
            discord.SelectOption(
                label=cat.replace('_', ' ').title(),
                value=cat,
                description=f"Configure {cat.replace('_', ' ').lower()}"
            )
            for cat in LOG_CATEGORIES
        ]
        options.append(
            discord.SelectOption(
                label="Finish Setup", value="finish", description="Complete the setup process"
            )
        )
        view.category_select.options = options

        embed = discord.Embed(
            title="🧩 Logging Setup",
            description=(
                "Configure logging channels for each category.\n"
                "Select a category from the dropdown below to assign a log channel."
            ),
            color=INFO_COLOR
        )
        embed.set_footer(text=f"Guild ID: {ctx.guild.id} | Lucky Bot • lucky.gg")

        view.message = await ctx.send(embed=embed, view=view)

    @log.command(name="status")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def log_status(self, ctx: commands.Context):
        config = self.get_config(ctx.guild.id)

        if not config:
            embed = discord.Embed(
                description="🃏 Logging is not configured. Use `log setup` to configure it.",
                color=ERROR_COLOR
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title=f"📋 Logging Status — {ctx.guild.name}",
            color=INFO_COLOR if config.get("enabled") else ERROR_COLOR
        )
        embed.add_field(
            name="Status",
            value="🍀 Enabled" if config.get("enabled") else "🃏 Disabled",
            inline=False
        )

        channels = config.get("channels", {})
        for cat in LOG_CATEGORIES:
            ch_id = channels.get(cat)
            ch = ctx.guild.get_channel(ch_id) if ch_id else None
            embed.add_field(
                name=cat.replace('_', ' ').title(),
                value=ch.mention if ch else "Not set",
                inline=True
            )

        ignored_ch = config.get("ignored_channels", [])
        ignored_roles = config.get("ignored_roles", [])
        if ignored_ch:
            embed.add_field(
                name="Ignored Channels",
                value=", ".join(f"<#{c}>" for c in ignored_ch),
                inline=False
            )
        if ignored_roles:
            embed.add_field(
                name="Ignored Roles",
                value=", ".join(f"<@&{r}>" for r in ignored_roles),
                inline=False
            )
        embed.set_footer(text=f"Guild ID: {ctx.guild.id} | Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @log.command(name="reset")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def log_reset(self, ctx: commands.Context):
        if ctx.guild.id not in self.config_cache:
            embed = discord.Embed(
                description="🃏 No logging configuration to reset.", color=ERROR_COLOR
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        del self.config_cache[ctx.guild.id]
        await self._save_config()

        embed = discord.Embed(
            description="🍀 Logging configuration has been reset.", color=SUCCESS_COLOR
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @log.command(name="toggle")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def log_toggle(self, ctx: commands.Context, category: str, enabled: bool):
        config = self.get_config(ctx.guild.id)
        if not config:
            embed = discord.Embed(
                description="🃏 Logging is not configured. Use `log setup` first.", color=ERROR_COLOR
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        cat = category.lower().replace(" ", "_")
        if cat not in LOG_CATEGORIES:
            embed = discord.Embed(
                description=f"🃏 Unknown category `{category}`. Valid: {', '.join(LOG_CATEGORIES)}",
                color=ERROR_COLOR
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        if enabled:
            config.setdefault("channels", {})[cat] = config.get("channels", {}).get(cat)
        else:
            config.get("channels", {}).pop(cat, None)

        self.config_cache[ctx.guild.id] = config
        await self._save_config()

        status = "🍀 enabled" if enabled else "🃏 disabled"
        embed = discord.Embed(
            description=f"{cat.replace('_', ' ').title()} logging has been {status}.",
            color=SUCCESS_COLOR if enabled else ERROR_COLOR
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @log.command(name="config")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def log_config(self, ctx: commands.Context):
        await self.log_status(ctx)

    @log.command(name="ignore")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def log_ignore(
        self, ctx: commands.Context,
        target: Union[discord.TextChannel, discord.Role]
    ):
        config = self.get_config(ctx.guild.id)
        if not config:
            embed = discord.Embed(
                description="🃏 Logging is not configured. Use `log setup` first.", color=ERROR_COLOR
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        if isinstance(target, discord.TextChannel):
            key = "ignored_channels"
            mention = target.mention
        else:
            key = "ignored_roles"
            mention = target.mention

        ids = config.setdefault(key, [])
        if target.id in ids:
            ids.remove(target.id)
            action = "🍀 Removed from ignore list"
        else:
            ids.append(target.id)
            action = "🍀 Added to ignore list"

        self.config_cache[ctx.guild.id] = config
        await self._save_config()

        embed = discord.Embed(
            description=f"{action}: {mention}", color=SUCCESS_COLOR
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @log.command(name="test")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def log_test(self, ctx: commands.Context, category: str = None):
        config = self.get_config(ctx.guild.id)
        if not config:
            embed = discord.Embed(
                description="🃏 Logging is not configured. Use `log setup` first.", color=ERROR_COLOR
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        test_cat = (category or "message_events").lower().replace(" ", "_")
        if test_cat not in LOG_CATEGORIES:
            embed = discord.Embed(
                description=f"🃏 Unknown category `{category}`.", color=ERROR_COLOR
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        test_embed = self._create_embed(
            "🧪 Log Test",
            f"This is a test log for **{test_cat.replace('_', ' ').title()}**.",
            color=INFO_COLOR
        )
        await self._send_log(ctx.guild, test_cat, test_embed)
        embed = discord.Embed(
            description=f"🍀 Test log sent to the {test_cat.replace('_', ' ').title()} channel.",
            color=SUCCESS_COLOR
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    # ── Listeners ──────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content:
            return
        if self.is_ignored(before.guild.id, before.channel.id):
            return
        embed = self._create_embed("📝 Message Edited", color=INFO_COLOR)
        embed.add_field(name="Author", value=before.author.mention, inline=True)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before", value=before.content[:1024] or "*empty*", inline=False)
        embed.add_field(name="After", value=after.content[:1024] or "*empty*", inline=False)
        embed.add_field(name="Message Link", value=f"[Jump]({after.jump_url})", inline=False)
        await self._send_log(before.guild, "message_events", embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if self.is_ignored(message.guild.id, message.channel.id):
            return
        embed = self._create_embed("🗑️ Message Deleted", color=ERROR_COLOR)
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Content", value=message.content[:1024] or "*empty*", inline=False)
        await self._send_log(message.guild, "message_events", embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = self._create_embed("📥 Member Joined", color=SUCCESS_COLOR)
        embed.add_field(name="Member", value=f"{member.mention} (`{member}`)", inline=True)
        embed.add_field(name="Account Created",
                        value=discord.utils.format_dt(member.created_at, style='R'), inline=True)
        embed.add_field(name="Member Count", value=str(member.guild.member_count), inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(member.guild, "join_leave_events", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = self._create_embed("📤 Member Left", color=ERROR_COLOR)
        embed.add_field(name="Member", value=f"{member.mention} (`{member}`)", inline=True)
        embed.add_field(name="Roles",
                        value=", ".join(r.mention for r in member.roles[1:]) or "None", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(member.guild, "join_leave_events", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if self.is_ignored(before.guild.id, role_ids=[r.id for r in before.roles]):
            return
        changes = []
        if before.nick != after.nick:
            changes.append(f"**Nickname:** `{before.nick}` → `{after.nick}`")
        added_roles = set(after.roles) - set(before.roles)
        removed_roles = set(before.roles) - set(after.roles)
        for role in added_roles:
            changes.append(f"**Role Added:** {role.mention}")
        for role in removed_roles:
            changes.append(f"**Role Removed:** {role.mention}")
        if not changes:
            return
        embed = self._create_embed("👤 Member Updated", color=INFO_COLOR)
        embed.add_field(name="Member", value=after.mention, inline=True)
        embed.add_field(name="Changes", value="\n".join(changes), inline=False)
        await self._send_log(before.guild, "member_moderation", embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: Union[discord.User, discord.Member]):
        embed = self._create_embed("🔨 Member Banned", color=ERROR_COLOR)
        embed.add_field(name="User", value=f"{user.mention} (`{user}`)", inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        await self._send_log(guild, "member_moderation", embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        embed = self._create_embed("✅ Member Unbanned", color=SUCCESS_COLOR)
        embed.add_field(name="User", value=f"{user.mention} (`{user}`)", inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        await self._send_log(guild, "member_moderation", embed)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member,
        before: discord.VoiceState, after: discord.VoiceState
    ):
        if self.is_ignored(member.guild.id, role_ids=[r.id for r in member.roles]):
            return
        if before.channel == after.channel:
            return
        if after.channel and not before.channel:
            desc = f"{member.mention} joined **{after.channel.name}**"
        elif before.channel and not after.channel:
            desc = f"{member.mention} left **{before.channel.name}**"
        else:
            desc = f"{member.mention} moved from **{before.channel.name}** → **{after.channel.name}**"
        embed = self._create_embed("🔊 Voice State Update", description=desc, color=INFO_COLOR)
        await self._send_log(member.guild, "voice_events", embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = self._create_embed("📢 Channel Created", color=SUCCESS_COLOR)
        embed.add_field(name="Channel", value=f"{channel.mention} (`{channel.name}`)", inline=True)
        embed.add_field(name="Type", value=str(channel.type), inline=True)
        await self._send_log(channel.guild, "channel_events", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = self._create_embed("🗑️ Channel Deleted", color=ERROR_COLOR)
        embed.add_field(name="Channel", value=f"`{channel.name}`", inline=True)
        embed.add_field(name="Type", value=str(channel.type), inline=True)
        await self._send_log(channel.guild, "channel_events", embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if hasattr(before, 'topic') and before.topic != after.topic:
            changes.append(f"**Topic:** `{before.topic}` → `{after.topic}`")
        if not changes:
            return
        embed = self._create_embed("✏️ Channel Updated", color=INFO_COLOR)
        embed.add_field(name="Channel", value=after.mention, inline=True)
        embed.add_field(name="Changes", value="\n".join(changes), inline=False)
        await self._send_log(before.guild, "channel_events", embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        embed = self._create_embed("🎭 Role Created", color=SUCCESS_COLOR)
        embed.add_field(name="Role", value=role.mention, inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        await self._send_log(role.guild, "role_events", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        embed = self._create_embed("🗑️ Role Deleted", color=ERROR_COLOR)
        embed.add_field(name="Role", value=f"`{role.name}`", inline=True)
        await self._send_log(role.guild, "role_events", embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.color != after.color:
            changes.append(f"**Color:** `{before.color}` → `{after.color}`")
        if before.permissions != after.permissions:
            changes.append("**Permissions updated**")
        if not changes:
            return
        embed = self._create_embed("✏️ Role Updated", color=INFO_COLOR)
        embed.add_field(name="Role", value=after.mention, inline=True)
        embed.add_field(name="Changes", value="\n".join(changes), inline=False)
        await self._send_log(before.guild, "role_events", embed)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.icon != after.icon:
            changes.append("**Icon updated**")
        if not changes:
            return
        embed = self._create_embed("🏠 Server Updated", color=INFO_COLOR)
        embed.add_field(name="Changes", value="\n".join(changes), inline=False)
        await self._send_log(after, "system_events", embed)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before, after):
        added = set(after) - set(before)
        removed = set(before) - set(after)
        if not added and not removed:
            return
        embed = self._create_embed("😀 Emojis Updated", color=INFO_COLOR)
        if added:
            embed.add_field(
                name="Added", value=" ".join(str(e) for e in added), inline=False
            )
        if removed:
            embed.add_field(
                name="Removed", value=" ".join(f"`{e.name}`" for e in removed), inline=False
            )
        await self._send_log(guild, "emoji_events", embed)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if not reaction.message.guild or user.bot:
            return
        if self.is_ignored(reaction.message.guild.id, reaction.message.channel.id):
            return
        embed = self._create_embed("➕ Reaction Added", color=INFO_COLOR)
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Emoji", value=str(reaction.emoji), inline=True)
        embed.add_field(name="Message", value=f"[Jump]({reaction.message.jump_url})", inline=True)
        await self._send_log(reaction.message.guild, "reaction_events", embed)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if not reaction.message.guild or user.bot:
            return
        if self.is_ignored(reaction.message.guild.id, reaction.message.channel.id):
            return
        embed = self._create_embed("➖ Reaction Removed", color=INFO_COLOR)
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Emoji", value=str(reaction.emoji), inline=True)
        embed.add_field(name="Message", value=f"[Jump]({reaction.message.jump_url})", inline=True)
        await self._send_log(reaction.message.guild, "reaction_events", embed)


async def setup(bot):
    await bot.add_cog(Logging(bot))

# Lucky Bot — Rewritten
