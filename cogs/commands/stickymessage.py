import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import *

DB_PATH = 'db/stickymessages.db'
THEME_COLOR = 0x5865F2


# ── Modals ─────────────────────────────────────────────────────────────────────

class PlainTextModal(discord.ui.Modal, title="Set Plain Text Message"):
    content = discord.ui.TextInput(label="Message Content", style=discord.TextStyle.paragraph, max_length=2000)

    def __init__(self, view):
        super().__init__()
        self.parent_view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.data["content"] = str(self.content)
        self.parent_view.data["embed"] = None
        await interaction.response.send_message(
            f"🍀 Plain text preview:\n{str(self.content)}", ephemeral=True
        )


class EmbedModal(discord.ui.Modal, title="Set Embed Message"):
    title_input = discord.ui.TextInput(label="Embed Title", required=False, max_length=256)
    desc_input = discord.ui.TextInput(
        label="Embed Description", style=discord.TextStyle.paragraph, required=False, max_length=2048
    )
    color_input = discord.ui.TextInput(
        label="Hex Color (e.g. #5865F2)", required=False, max_length=7, placeholder="#5865F2"
    )

    def __init__(self, view):
        super().__init__()
        self.parent_view = view

    async def on_submit(self, interaction: discord.Interaction):
        color = THEME_COLOR
        try:
            color = int(str(self.color_input).lstrip("#"), 16)
        except (ValueError, AttributeError):
            pass
        self.parent_view.data["content"] = None
        self.parent_view.data["embed"] = {
            "title": str(self.title_input) or None,
            "description": str(self.desc_input) or None,
            "color": color
        }
        embed = discord.Embed(
            title=self.parent_view.data["embed"]["title"],
            description=self.parent_view.data["embed"]["description"],
            color=color
        )
        await interaction.response.send_message("🍀 Embed preview:", embed=embed, ephemeral=True)


class EditPlainTextModal(discord.ui.Modal, title="Edit Plain Text Message"):
    content = discord.ui.TextInput(label="New Message Content", style=discord.TextStyle.paragraph, max_length=2000)

    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE stickymessages SET content=?, embed_data=NULL WHERE channel_id=?",
                (str(self.content), self.channel_id)
            )
            await db.commit()
        await interaction.response.send_message("🍀 Sticky message updated.", ephemeral=True)


class EditEmbedModal(discord.ui.Modal, title="Edit Embed Message"):
    title_input = discord.ui.TextInput(label="New Title", required=False, max_length=256)
    desc_input = discord.ui.TextInput(
        label="New Description", style=discord.TextStyle.paragraph, required=False, max_length=2048
    )
    color_input = discord.ui.TextInput(
        label="Hex Color", required=False, max_length=7, placeholder="#5865F2"
    )

    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction):
        import json
        color = THEME_COLOR
        try:
            color = int(str(self.color_input).lstrip("#"), 16)
        except (ValueError, AttributeError):
            pass
        embed_data = {
            "title": str(self.title_input) or None,
            "description": str(self.desc_input) or None,
            "color": color
        }
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE stickymessages SET content=NULL, embed_data=? WHERE channel_id=?",
                (json.dumps(embed_data), self.channel_id)
            )
            await db.commit()
        await interaction.response.send_message("🍀 Sticky embed updated.", ephemeral=True)


class EditSettingsModal(discord.ui.Modal, title="Edit Sticky Settings"):
    cooldown = discord.ui.TextInput(
        label="Cooldown (seconds)", required=False, max_length=6, placeholder="5"
    )

    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cd = int(str(self.cooldown)) if str(self.cooldown) else 5
        except ValueError:
            cd = 5
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE stickymessages SET cooldown=? WHERE channel_id=?",
                (cd, self.channel_id)
            )
            await db.commit()
        await interaction.response.send_message(f"🍀 Cooldown updated to {cd}s.", ephemeral=True)


# ── Setup views ────────────────────────────────────────────────────────────────

class StickySetupView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=120)
        self.author = author
        self.data = {"content": None, "embed": None, "cooldown": 5}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("Not your setup!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Plain Text", style=discord.ButtonStyle.secondary)
    async def plain_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PlainTextModal(self))

    @discord.ui.button(label="Embed", style=discord.ButtonStyle.secondary)
    async def embed_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmbedModal(self))

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, row=1)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.data["content"] and not self.data["embed"]:
            await interaction.response.send_message(
                "🃏 Set a plain text or embed message first.", ephemeral=True
            )
            return
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.data = None
        self.stop()
        await interaction.response.send_message("🃏 Setup cancelled.", ephemeral=True)


class StickyEditView(discord.ui.View):
    def __init__(self, author: discord.Member, channel_id: int, msg_type: str):
        super().__init__(timeout=120)
        self.author = author
        self.channel_id = channel_id
        self.msg_type = msg_type

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("Not your session!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Edit Message", style=discord.ButtonStyle.primary)
    async def edit_msg(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.msg_type == "plain":
            await interaction.response.send_modal(EditPlainTextModal(self.channel_id))
        else:
            await interaction.response.send_modal(EditEmbedModal(self.channel_id))

    @discord.ui.button(label="Edit Settings", style=discord.ButtonStyle.secondary)
    async def edit_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditSettingsModal(self.channel_id))


# ── Cog ────────────────────────────────────────────────────────────────────────

class StickyMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_sticky: dict = {}
        self.bot.loop.create_task(self.initialize_db())

    async def initialize_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS stickymessages (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    content TEXT,
                    embed_data TEXT,
                    last_msg_id INTEGER,
                    cooldown INTEGER DEFAULT 5,
                    enabled INTEGER DEFAULT 1
                )
            ''')
            await db.commit()

    @commands.group(name='stickymessage', aliases=['sticky', 'sm'], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def sticky(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)

    @sticky.command(name='setup')
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    async def setup(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM stickymessages WHERE channel_id=?", (channel.id,)
            ) as cursor:
                if await cursor.fetchone():
                    embed = discord.Embed(
                        description=f"🎴 A sticky message already exists in {channel.mention}. Use `sticky edit` to modify it.",
                        color=0xFF4444
                    )
                    embed.set_footer(text="Lucky Bot • lucky.gg")
                    return await ctx.send(embed=embed)

        view = StickySetupView(ctx.author)
        embed = discord.Embed(
            title="🗒️ Sticky Message Setup",
            description=f"Configure a sticky message for {channel.mention}.\nChoose a message type below.",
            color=THEME_COLOR
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()

        if not view.data:
            return

        import json
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO stickymessages (channel_id, guild_id, content, embed_data, cooldown) VALUES (?,?,?,?,?)",
                (
                    channel.id, ctx.guild.id,
                    view.data.get("content"),
                    json.dumps(view.data["embed"]) if view.data.get("embed") else None,
                    view.data.get("cooldown", 5)
                )
            )
            await db.commit()

        await msg.delete()
        confirm = discord.Embed(description=f"🍀 Sticky message set in {channel.mention}.", color=0x57F287)
        confirm.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=confirm)

    @sticky.command(name='remove')
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    async def remove(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        async with aiosqlite.connect(DB_PATH) as db:
            result = await db.execute(
                "DELETE FROM stickymessages WHERE channel_id=? AND guild_id=?", (channel.id, ctx.guild.id)
            )
            await db.commit()

        if result.rowcount == 0:
            embed = discord.Embed(
                description=f"🃏 No sticky message found in {channel.mention}.", color=0xFF4444
            )
        else:
            embed = discord.Embed(
                description=f"🍀 Sticky message removed from {channel.mention}.", color=0x57F287
            )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @sticky.command(name='list')
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    async def list(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT channel_id, content, embed_data FROM stickymessages WHERE guild_id=?", (ctx.guild.id,)
            ) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            embed = discord.Embed(
                description="🃏 No sticky messages configured in this server.", color=0xFF4444
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        embed = discord.Embed(title="📌 Sticky Messages", color=THEME_COLOR)
        for channel_id, content, embed_data in rows:
            ch = ctx.guild.get_channel(channel_id)
            ch_mention = ch.mention if ch else f"<#{channel_id}>"
            msg_type = "Embed" if embed_data else "Plain Text"
            embed.add_field(name=ch_mention, value=f"Type: {msg_type}", inline=False)
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @sticky.command(name='edit')
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    async def edit(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT content, embed_data FROM stickymessages WHERE channel_id=?", (channel.id,)
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            embed = discord.Embed(
                description=f"🃏 No sticky message found in {channel.mention}.", color=0xFF4444
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        msg_type = "plain" if row[0] else "embed"
        view = StickyEditView(ctx.author, channel.id, msg_type)
        embed = discord.Embed(
            title="✏️ Edit Sticky Message",
            description=f"Editing sticky message in {channel.mention}.",
            color=THEME_COLOR
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT content, embed_data, last_msg_id, cooldown, enabled FROM stickymessages WHERE channel_id=?",
                (message.channel.id,)
            ) as cursor:
                row = await cursor.fetchone()

        if not row or not row[4]:
            return

        content, embed_data, last_msg_id, cooldown, _ = row

        if last_msg_id:
            try:
                old_msg = await message.channel.fetch_message(last_msg_id)
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        import json
        try:
            if embed_data:
                data = json.loads(embed_data)
                embed = discord.Embed(
                    title=data.get("title"),
                    description=data.get("description"),
                    color=data.get("color", THEME_COLOR)
                )
                embed.set_footer(text="📌 Sticky | Lucky Bot • lucky.gg")
                new_msg = await message.channel.send(embed=embed)
            else:
                new_msg = await message.channel.send(content)

            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE stickymessages SET last_msg_id=? WHERE channel_id=?",
                    (new_msg.id, message.channel.id)
                )
                await db.commit()
        except discord.Forbidden:
            pass


async def setup(bot):
    await bot.add_cog(StickyMessage(bot))

# Lucky Bot — Rewritten
