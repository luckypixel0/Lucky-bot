import discord
from discord.ext import commands
from discord.ui import View, Select, Button
import aiosqlite
import asyncio
import re
import json
from utils.Tools import *


class VariableButton(Button):
    def __init__(self, author):
        super().__init__(label="Variables", style=discord.ButtonStyle.secondary)
        self.author = author

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message(
                "Only the command author can use this button.", ephemeral=True
            )
            return

        variables = {
            "{user}": "Mentions the user (e.g., @UserName).",
            "{user_avatar}": "The user's avatar URL.",
            "{user_name}": "The user's username.",
            "{user_id}": "The user's ID number.",
            "{user_nick}": "The user's nickname in the server.",
            "{user_joindate}": "The user's join date in the server (formatted as Day, Month Day, Year).",
            "{user_createdate}": "The user's account creation date (formatted as Day, Month Day, Year).",
            "{server_name}": "The server's name.",
            "{server_id}": "The server's ID number.",
            "{server_membercount}": "The server's total member count.",
            "{server_icon}": "The server's icon URL.",
        }

        embed = discord.Embed(
            title="Available Placeholders",
            description="Use these placeholders in your welcome message:",
            color=0x5865F2
        )
        for var, desc in variables.items():
            embed.add_field(name=var, value=desc, inline=False)
        embed.set_footer(text="Add placeholders directly in the welcome message or embed fields.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class Welcomer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self._create_table())

    async def _create_table(self):
        async with aiosqlite.connect("db/welcome.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS welcome (
                    guild_id INTEGER PRIMARY KEY,
                    welcome_type TEXT,
                    welcome_message TEXT,
                    channel_id INTEGER,
                    embed_data TEXT,
                    auto_delete_duration INTEGER
                )
            """)
            await db.commit()

    def _build_placeholders(self, member: discord.Member):
        return {
            "user": member.mention,
            "user_avatar": member.display_avatar.url,
            "user_name": member.name,
            "user_id": member.id,
            "user_nick": member.display_name,
            "user_joindate": member.joined_at.strftime("%a, %b %d, %Y") if member.joined_at else "N/A",
            "user_createdate": member.created_at.strftime("%a, %b %d, %Y"),
            "server_name": member.guild.name,
            "server_id": member.guild.id,
            "server_membercount": member.guild.member_count,
            "server_icon": member.guild.icon.url if member.guild.icon else "",
        }

    @staticmethod
    def safe_format(text, placeholders):
        lower = {k.lower(): v for k, v in placeholders.items()}

        def replace_var(match):
            return str(lower.get(match.group(1).lower(), f"{{{match.group(1)}}}"))

        return re.sub(r"\{(\w+)\}", replace_var, text or "")

    @commands.hybrid_group(invoke_without_command=True, name="greet",
                           help="Shows all the greet commands.")
    @blacklist_check()
    @ignore_check()
    async def greet(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @greet.command(name="setup",
                   help="Configures a welcome message for new members joining the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_setup(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT 1 FROM welcome WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if row:
            embed = discord.Embed(
                description=f"A welcome message has already been set in {ctx.guild.name}. "
                            f"Use `{ctx.prefix}greet reset` to reconfigure.",
                color=0xFF4444
            )
            embed.set_author(name="Error")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        options_view = View(timeout=600)

        async def option_callback(interaction: discord.Interaction, button: Button):
            if interaction.user != ctx.author:
                await interaction.response.send_message(
                    "You cannot interact with this setup.", ephemeral=True
                )
                return
            await interaction.response.defer()
            if button.custom_id == "simple":
                await interaction.message.delete()
                await self.simple_setup(ctx)
            elif button.custom_id == "embed":
                await interaction.message.delete()
                await self.embed_setup(ctx)
            elif button.custom_id == "cancel":
                await interaction.message.delete()

        btn_simple = Button(label="Simple", style=discord.ButtonStyle.success, custom_id="simple")
        btn_simple.callback = lambda i: option_callback(i, btn_simple)
        btn_embed = Button(label="Embed", style=discord.ButtonStyle.success, custom_id="embed")
        btn_embed.callback = lambda i: option_callback(i, btn_embed)
        btn_cancel = Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="cancel")
        btn_cancel.callback = lambda i: option_callback(i, btn_cancel)

        options_view.add_item(btn_simple)
        options_view.add_item(btn_embed)
        options_view.add_item(btn_cancel)

        embed = discord.Embed(
            title="Welcome Message Setup",
            description="Choose the type of welcome message you want to create:",
            color=0x5865F2
        )
        embed.add_field(
            name="Simple",
            value="Send a plain text welcome message with placeholders.",
            inline=False
        )
        embed.add_field(
            name="Embed",
            value="Send a welcome message in an embed format with customizable fields.",
            inline=False
        )
        embed.set_footer(
            text="Click the buttons below to choose the welcome message type. | Lucky Bot • lucky.gg",
            icon_url=self.bot.user.display_avatar.url
        )
        await ctx.send(embed=embed, view=options_view)

    async def simple_setup(self, ctx):
        setup_view = View(timeout=600)
        first = View(timeout=600)
        message_content = []

        async def update_preview(content):
            ph = self._build_placeholders(ctx.author)
            preview = self.safe_format(content, ph)
            await preview_message.edit(
                content=f"**Preview:** {preview}", view=setup_view
            )

        first.add_item(VariableButton(ctx.author))
        preview_message = await ctx.send(
            "__**Simple Message Setup**__ \nEnter your welcome message here:", view=first
        )

        async def submit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message(
                    "You cannot interact with this setup.", ephemeral=True
                )
                return
            if message_content:
                await self._save_welcome_data(ctx.guild.id, "simple", message_content[0])
                await interaction.response.send_message("🍀 Welcome message setup completed!")
                for item in setup_view.children:
                    item.disabled = True
                await preview_message.edit(view=setup_view)
            else:
                await interaction.response.send_message(
                    "No message entered to submit.", ephemeral=True
                )

        async def edit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message(
                    "You cannot interact with this setup.", ephemeral=True
                )
                return
            await interaction.response.defer()
            await ctx.send("Enter the updated welcome message:")
            try:
                msg = await self.bot.wait_for(
                    "message", timeout=600,
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel
                )
                message_content.clear()
                message_content.append(msg.content)
                await update_preview(msg.content)
            except asyncio.TimeoutError:
                await ctx.send("Editing timed out.")

        async def cancel_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message(
                    "You cannot interact with this setup.", ephemeral=True
                )
                return
            await preview_message.delete()

        submit_btn = Button(label="Submit", style=discord.ButtonStyle.success)
        submit_btn.callback = submit_callback
        edit_btn = Button(label="Edit", style=discord.ButtonStyle.primary)
        edit_btn.callback = edit_callback
        cancel_btn = Button(emoji="✖️", style=discord.ButtonStyle.secondary)
        cancel_btn.callback = cancel_callback

        setup_view.add_item(submit_btn)
        setup_view.add_item(edit_btn)
        setup_view.add_item(VariableButton(ctx.author))
        setup_view.add_item(cancel_btn)

        try:
            msg = await self.bot.wait_for(
                "message", timeout=600,
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel
            )
            message_content.append(msg.content)
            await update_preview(msg.content)
        except asyncio.TimeoutError:
            await ctx.send("Setup timed out.")

    async def _save_welcome_data(self, guild_id, welcome_type, message, embed_data=None):
        async with aiosqlite.connect("db/welcome.db") as db:
            await db.execute("""
                INSERT OR REPLACE INTO welcome (guild_id, welcome_type, welcome_message, embed_data)
                VALUES (?, ?, ?, ?)
            """, (guild_id, welcome_type, message,
                  json.dumps(embed_data) if embed_data else None))
            await db.commit()

    async def embed_setup(self, ctx):
        setup_view = View(timeout=600)
        embed_data = {
            "message": None, "title": None, "description": None, "color": None,
            "footer_text": None, "footer_icon": None, "author_name": None,
            "author_icon": None, "thumbnail": None, "image": None,
        }
        ph = self._build_placeholders(ctx.author)

        async def update_preview():
            content = self.safe_format(embed_data["message"], ph) or "Message Content."
            e = discord.Embed(
                title=self.safe_format(embed_data["title"] or "", ph),
                description=self.safe_format(
                    embed_data["description"] or "", ph
                ) or "```Customize your welcome embed, use variables.```",
                color=discord.Color(embed_data["color"]) if embed_data["color"] else discord.Color(0x5865F2)
            )
            if embed_data["footer_text"]:
                e.set_footer(
                    text=self.safe_format(embed_data["footer_text"], ph),
                    icon_url=self.safe_format(embed_data.get("footer_icon") or "", ph) or None
                )
            if embed_data["author_name"]:
                e.set_author(
                    name=self.safe_format(embed_data["author_name"], ph),
                    icon_url=self.safe_format(embed_data.get("author_icon") or "", ph) or None
                )
            if embed_data["thumbnail"]:
                e.set_thumbnail(url=self.safe_format(embed_data["thumbnail"], ph))
            if embed_data["image"]:
                e.set_image(url=self.safe_format(embed_data["image"], ph))
            await preview_message.edit(content="**Embed Preview:** " + content, embed=e, view=setup_view)

        preview_message = await ctx.send("Configuring embed welcome message...")

        async def handle_selection(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message(
                    "You cannot interact with this setup.", ephemeral=True
                )
                return
            selected_option = select_menu.values[0]
            await interaction.response.defer()
            try:
                if selected_option == "color":
                    await ctx.send("Enter a hex color (e.g., #3498db or 3498db):")
                    msg = await self.bot.wait_for(
                        "message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel
                    )
                    code = msg.content.lstrip("#")
                    if all(c in "0123456789abcdefABCDEF" for c in code) and len(code) in {3, 6}:
                        embed_data["color"] = int(code, 16)
                    else:
                        await ctx.send("Invalid color code.")
                elif selected_option in ["footer_icon", "author_icon", "thumbnail", "image"]:
                    await ctx.send(f"Enter the URL for {selected_option.replace('_', ' ')}:")
                    msg = await self.bot.wait_for(
                        "message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel
                    )
                    url = msg.content
                    if url.startswith("http") or url in ["{user_avatar}", "{server_icon}"]:
                        embed_data[selected_option] = url
                    else:
                        await ctx.send("Invalid URL.")
                else:
                    await ctx.send(f"Enter value for {selected_option.replace('_', ' ')}:")
                    msg = await self.bot.wait_for(
                        "message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel
                    )
                    embed_data[selected_option] = msg.content
                await update_preview()
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond.")
            except Exception as e:
                await ctx.send(f"An error occurred: {e}")

        select_menu = Select(
            placeholder="Choose an option to edit the Embed",
            options=[
                discord.SelectOption(label="Message Content", value="message"),
                discord.SelectOption(label="Title", value="title"),
                discord.SelectOption(label="Description", value="description"),
                discord.SelectOption(label="Color", value="color"),
                discord.SelectOption(label="Footer Text", value="footer_text"),
                discord.SelectOption(label="Footer Icon", value="footer_icon"),
                discord.SelectOption(label="Author Name", value="author_name"),
                discord.SelectOption(label="Author Icon", value="author_icon"),
                discord.SelectOption(label="Thumbnail", value="thumbnail"),
                discord.SelectOption(label="Image", value="image"),
            ]
        )
        select_menu.callback = handle_selection
        setup_view.add_item(select_menu)

        async def submit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message(
                    "You cannot interact with this setup.", ephemeral=True
                )
                return
            if not any(embed_data[k] for k in ["title", "description"]):
                await interaction.response.send_message(
                    "Please provide at least a title or description before submitting.", ephemeral=True
                )
                return
            await self._save_welcome_data(
                ctx.guild.id, "embed", embed_data["message"] or "", embed_data
            )
            await interaction.response.send_message("🍀 Embed welcome message setup completed!")
            for item in setup_view.children:
                item.disabled = True
            await preview_message.edit(view=setup_view)

        async def cancel_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message(
                    "You cannot interact with this setup.", ephemeral=True
                )
                return
            await preview_message.delete()
            await interaction.response.send_message("Embed setup cancelled.", ephemeral=True)

        submit_btn = Button(label="Submit", style=discord.ButtonStyle.success)
        submit_btn.callback = submit_callback
        cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.danger)
        cancel_btn.callback = cancel_callback

        setup_view.add_item(submit_btn)
        setup_view.add_item(VariableButton(ctx.author))
        setup_view.add_item(cancel_btn)

        await update_preview()

    @greet.command(name="reset", aliases=["disable"],
                   help="Resets and deletes the current welcome configuration for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_reset(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            cursor = await db.execute("SELECT 1 FROM welcome WHERE guild_id = ?", (ctx.guild.id,))
            is_set_up = await cursor.fetchone()

        if not is_set_up:
            embed = discord.Embed(
                description=f"No welcome message has been set for {ctx.guild.name}! "
                            f"Please set one first using `{ctx.prefix}greet setup`",
                color=0xFF4444
            )
            embed.set_author(name="Greet is not configured!")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title="Are you sure?",
            description="This will remove all welcome configurations for this server!",
            color=0x5865F2
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")

        yes_btn = Button(label="Confirm", style=discord.ButtonStyle.danger)
        no_btn = Button(label="Cancel", style=discord.ButtonStyle.secondary)

        async def yes_cb(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message(
                    "Only the command author can confirm this action.", ephemeral=True
                )
                return
            async with aiosqlite.connect("db/welcome.db") as db:
                await db.execute("DELETE FROM welcome WHERE guild_id = ?", (ctx.guild.id,))
                await db.commit()
            embed.color = 0x57F287
            embed.title = "🍀 Success"
            embed.description = "Welcome message configuration has been successfully reset."
            await interaction.message.edit(embed=embed, view=None)

        async def no_cb(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message(
                    "Only the command author can cancel this action.", ephemeral=True
                )
                return
            embed.title = "Cancelled"
            embed.description = "Greet reset operation has been cancelled."
            await interaction.message.edit(embed=embed, view=None)

        yes_btn.callback = yes_cb
        no_btn.callback = no_cb

        view = View()
        view.add_item(yes_btn)
        view.add_item(no_btn)
        await ctx.send(embed=embed, view=view)

    @greet.command(name="channel",
                   help="Sets the channel where welcome messages will be sent.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_channel(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute(
                "SELECT welcome_type, channel_id FROM welcome WHERE guild_id = ?", (ctx.guild.id,)
            ) as cursor:
                result = await cursor.fetchone()

        if not result or not result[0]:
            embed = discord.Embed(
                description=f"No welcome message set for {ctx.guild.name}. "
                            f"Use `{ctx.prefix}greet setup` first.",
                color=0xFF4444
            )
            embed.set_author(name="Greet is not configured!")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        welcome_channel = ctx.guild.get_channel(result[1]) if result[1] else None
        channels = ctx.guild.text_channels
        chunk_size = 25
        chunks = [channels[i:i + chunk_size] for i in range(0, len(channels), chunk_size)]
        current_page = [0]

        embed = discord.Embed(
            title=f"Welcome Channel for {ctx.guild.name}",
            description=f"Current Welcome Channel: {welcome_channel.mention if welcome_channel else 'None'}",
            color=0x5865F2
        )
        embed.set_footer(text="Use the dropdown to select a channel. | Lucky Bot • lucky.gg")

        def generate_view(page):
            sel = Select(
                placeholder="Select a channel for welcome messages",
                options=[
                    discord.SelectOption(label=ch.name, emoji="🎠", value=str(ch.id))
                    for ch in chunks[page]
                ]
            )

            async def sel_cb(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message(
                        "You are not authorized.", ephemeral=True
                    )
                    return
                ch_id = int(sel.values[0])
                sel_ch = ctx.guild.get_channel(ch_id)
                async with aiosqlite.connect("db/welcome.db") as db:
                    await db.execute(
                        "UPDATE welcome SET channel_id = ? WHERE guild_id = ?", (ch_id, ctx.guild.id)
                    )
                    await db.commit()
                embed.description = f"Current Welcome Channel: {sel_ch.mention}"
                await interaction.response.edit_message(embed=embed, view=None)
                await ctx.send(f"🍀 Welcome channel has been set to {sel_ch.mention}")

            sel.callback = sel_cb

            next_btn = Button(
                label="Next", style=discord.ButtonStyle.secondary,
                disabled=page >= len(chunks) - 1
            )
            prev_btn = Button(
                label="Previous", style=discord.ButtonStyle.secondary,
                disabled=page <= 0
            )

            async def next_cb(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Not authorized.", ephemeral=True)
                    return
                current_page[0] += 1
                await interaction.response.edit_message(
                    embed=embed, view=generate_view(current_page[0])
                )

            async def prev_cb(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Not authorized.", ephemeral=True)
                    return
                current_page[0] -= 1
                await interaction.response.edit_message(
                    embed=embed, view=generate_view(current_page[0])
                )

            next_btn.callback = next_cb
            prev_btn.callback = prev_cb

            v = View()
            v.add_item(sel)
            v.add_item(prev_btn)
            v.add_item(next_btn)
            return v

        await ctx.send(embed=embed, view=generate_view(current_page[0]))

    @greet.command(name="test",
                   help="Sends a test welcome message to preview the setup.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_test(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute(
                "SELECT welcome_type, welcome_message, channel_id, embed_data FROM welcome WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                row = await cursor.fetchone()

        if row is None:
            embed = discord.Embed(
                description=f"No welcome message set for {ctx.guild.name}. "
                            f"Use `{ctx.prefix}greet setup` first.",
                color=0xFF4444
            )
            embed.set_author(name="Greet is not configured!")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        welcome_type, welcome_message, channel_id, embed_data = row
        welcome_channel = self.bot.get_channel(channel_id)

        if not welcome_channel:
            embed = discord.Embed(
                description=f"Welcome channel not set or invalid. Use `{ctx.prefix}greet channel` to set one.",
                color=0xFF4444
            )
            embed.set_author(name="Channel not set")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        ph = self._build_placeholders(ctx.author)

        if welcome_type == "simple" and welcome_message:
            await welcome_channel.send(self.safe_format(welcome_message, ph))

        elif welcome_type == "embed" and embed_data:
            try:
                embed_info = json.loads(embed_data)
                color_value = embed_info.get("color", None)
                embed_color = 0x5865F2
                if color_value and isinstance(color_value, str) and color_value.startswith("#"):
                    embed_color = int(color_value.lstrip("#"), 16)
                elif isinstance(color_value, int):
                    embed_color = color_value
            except (ValueError, json.JSONDecodeError):
                await ctx.send("Invalid embed data format. Please reconfigure.")
                return

            content = self.safe_format(embed_info.get("message", ""), ph) or None
            embed = discord.Embed(
                title=self.safe_format(embed_info.get("title", ""), ph),
                description=self.safe_format(embed_info.get("description", ""), ph),
                color=embed_color
            )
            embed.timestamp = discord.utils.utcnow()
            if embed_info.get("footer_text"):
                embed.set_footer(
                    text=self.safe_format(embed_info["footer_text"], ph),
                    icon_url=self.safe_format(embed_info.get("footer_icon", ""), ph) or None
                )
            if embed_info.get("author_name"):
                embed.set_author(
                    name=self.safe_format(embed_info["author_name"], ph),
                    icon_url=self.safe_format(embed_info.get("author_icon", ""), ph) or None
                )
            if embed_info.get("thumbnail"):
                embed.set_thumbnail(url=self.safe_format(embed_info["thumbnail"], ph))
            if embed_info.get("image"):
                embed.set_image(url=self.safe_format(embed_info["image"], ph))
            await welcome_channel.send(content=content, embed=embed)

    @greet.command(name="config",
                   help="Shows the current welcome configuration.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_config(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT * FROM welcome WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if row:
            _, welcome_type, welcome_message, channel_id, embed_data, auto_delete_duration = row
            embed = discord.Embed(
                title=f"Greet Configuration for {ctx.guild.name}",
                color=0x5865F2
            )
            embed.add_field(
                name="Response Type",
                value="Simple" if welcome_type == "simple" else "Embed",
                inline=False
            )
            if welcome_type == "simple":
                embed.add_field(
                    name="Details",
                    value=(f"Message Content: {welcome_message or 'None'}")[:1024],
                    inline=False
                )
            else:
                embed_details = json.loads(embed_data) if embed_data else {}
                formatted = "\n".join(
                    f"{k.replace('_', ' ').title()}: {v or 'None'}"
                    for k, v in embed_details.items()
                ) or "None"
                for i, chunk in enumerate(
                    [formatted[x:x+1024] for x in range(0, len(formatted), 1024)]
                ):
                    embed.add_field(name=f"Embed Data Part {i+1}", value=chunk, inline=False)

            greet_ch = self.bot.get_channel(channel_id)
            embed.add_field(name="Greet Channel", value=greet_ch.mention if greet_ch else "None", inline=False)
            embed.add_field(
                name="Auto Delete Duration",
                value=f"{auto_delete_duration} seconds" if auto_delete_duration else "None",
                inline=False
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f"No welcome message has been set for {ctx.guild.name}! "
                            f"Use `{ctx.prefix}greet setup` first.",
                color=0xFF4444
            )
            embed.set_author(name="Greet is not configured!")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)

    @greet.command(name="autodelete", aliases=["autodel"],
                   help="Sets the auto-delete duration for the welcome message.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_autodelete(self, ctx, time: str):
        if time.endswith("s"):
            seconds = int(time[:-1])
            if not 3 <= seconds <= 300:
                return await ctx.send("Auto delete time should be between 3 seconds and 300 seconds.")
            auto_delete_duration = seconds
        elif time.endswith("m"):
            minutes = int(time[:-1])
            if not 1 <= minutes <= 5:
                return await ctx.send("Auto delete time should be between 1 minute and 5 minutes.")
            auto_delete_duration = minutes * 60
        else:
            return await ctx.send("Invalid time format. Use 's' for seconds and 'm' for minutes.")

        async with aiosqlite.connect("db/welcome.db") as db:
            await db.execute(
                "UPDATE welcome SET auto_delete_duration = ? WHERE guild_id = ?",
                (auto_delete_duration, ctx.guild.id)
            )
            await db.commit()
        embed = discord.Embed(
            description=f"🍀 Auto delete duration set to **{auto_delete_duration}** seconds.",
            color=0x57F287
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @greet.command(name="edit",
                   help="Edits the current welcome message settings for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_edit(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute(
                "SELECT welcome_type, welcome_message, embed_data FROM welcome WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                row = await cursor.fetchone()

        if row is None:
            embed = discord.Embed(
                description=f"No welcome message set for {ctx.guild.name}. "
                            f"Use `{ctx.prefix}greet setup` first.",
                color=0xFF4444
            )
            embed.set_author(name="Greet is not configured!")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        welcome_type, welcome_message, embed_data = row

        if welcome_type == "simple":
            embed = discord.Embed(
                title="Edit Welcome Message",
                description=f"**Response Type:** Simple\n**Message Content:** {welcome_message or 'None'}",
                color=0x5865F2
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            cancel_flag = [False]

            edit_btn = Button(label="Edit", style=discord.ButtonStyle.primary)
            cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.danger)

            async def cancel_cb(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Not authorized.", ephemeral=True)
                    return
                cancel_flag[0] = True
                view.clear_items()
                await interaction.message.edit(embed=embed, view=view)

            cancel_btn.callback = cancel_cb

            async def edit_cb(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Not authorized.", ephemeral=True)
                    return
                await interaction.response.send_message(
                    "Please provide the new welcome message:", ephemeral=True
                )
                try:
                    new_msg = await self.bot.wait_for(
                        "message",
                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                        timeout=600
                    )
                    if cancel_flag[0]:
                        return
                    await new_msg.delete()
                    async with aiosqlite.connect("db/welcome.db") as db:
                        await db.execute(
                            "UPDATE welcome SET welcome_message = ? WHERE guild_id = ?",
                            (new_msg.content, ctx.guild.id)
                        )
                        await db.commit()
                    embed.description = (
                        f"**Response Type:** Simple\n**Message Content:** {new_msg.content}"
                    )
                    edit_btn.disabled = True
                    cancel_btn.disabled = True
                    await interaction.message.edit(embed=embed, view=view)
                    await ctx.send("Welcome message successfully updated.")
                except asyncio.TimeoutError:
                    await ctx.send("You took too long to respond.")

            edit_btn.callback = edit_cb
            view = View()
            view.add_item(edit_btn)
            view.add_item(VariableButton(ctx.author))
            view.add_item(cancel_btn)
            await ctx.send(embed=embed, view=view)

        elif welcome_type == "embed":
            embed_data_json = json.loads(embed_data) if embed_data else {}
            formatted = "\n".join(
                f"{k.replace('_', ' ').title()}: {v or 'None'}"
                for k, v in embed_data_json.items()
            ) or "None"
            embed = discord.Embed(
                title="Edit Welcome Message",
                description=f"**Response Type:** Embed\n**Embed Data:**\n```{formatted}```",
                color=0x5865F2
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            cancel_flag = [False]

            sel = Select(
                placeholder="Select an embed field to edit",
                options=[
                    discord.SelectOption(label=f.replace('_', ' ').title(), value=f)
                    for f in embed_data_json.keys()
                ]
            )
            cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.danger)

            async def cancel_cb(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Not authorized.", ephemeral=True)
                    return
                cancel_flag[0] = True
                view.clear_items()
                await interaction.message.edit(embed=embed, view=view)

            cancel_btn.callback = cancel_cb

            async def sel_cb(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Not authorized.", ephemeral=True)
                    return
                selected = sel.values[0]
                await interaction.response.defer()
                try:
                    if selected == "color":
                        await ctx.send("Enter a hex color (e.g., #3498db):")
                        msg = await self.bot.wait_for(
                            "message",
                            check=lambda m: m.author == ctx.author and m.channel == ctx.channel
                        )
                        code = msg.content.lstrip("#")
                        if all(c in "0123456789abcdefABCDEF" for c in code) and len(code) in {3, 6}:
                            embed_data_json["color"] = int(code, 16)
                        else:
                            return await ctx.send("Invalid color code.")
                    elif selected in ["footer_icon", "author_icon", "thumbnail", "image"]:
                        await ctx.send(f"Enter the URL for {selected.replace('_', ' ')}:")
                        msg = await self.bot.wait_for(
                            "message",
                            check=lambda m: m.author == ctx.author and m.channel == ctx.channel
                        )
                        if msg.content.startswith("http") or msg.content in ["{user_avatar}", "{server_icon}"]:
                            embed_data_json[selected] = msg.content
                        else:
                            return await ctx.send("Invalid URL.")
                    else:
                        await ctx.send(f"Enter the new value for {selected.replace('_', ' ')}:")
                        msg = await self.bot.wait_for(
                            "message",
                            check=lambda m: m.author == ctx.author and m.channel == ctx.channel
                        )
                        embed_data_json[selected] = msg.content

                    async with aiosqlite.connect("db/welcome.db") as db:
                        await db.execute(
                            "UPDATE welcome SET embed_data = ? WHERE guild_id = ?",
                            (json.dumps(embed_data_json), ctx.guild.id)
                        )
                        await db.commit()
                    embed.description = (
                        f"**Response Type:** Embed\n**Embed Data:**\n"
                        f"```{json.dumps(embed_data_json, indent=4)}```"
                    )
                    await interaction.message.edit(embed=embed, view=None)
                    await ctx.send("Embed data successfully updated.")
                except asyncio.TimeoutError:
                    await ctx.send("You took too long to respond.")
                except Exception as e:
                    await ctx.send(f"An error occurred: {e}")

            sel.callback = sel_cb
            view = View()
            view.add_item(sel)
            view.add_item(VariableButton(ctx.author))
            view.add_item(cancel_btn)
            await ctx.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute(
                "SELECT welcome_type, welcome_message, channel_id, embed_data, auto_delete_duration "
                "FROM welcome WHERE guild_id = ?",
                (member.guild.id,)
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return

        welcome_type, welcome_message, channel_id, embed_data, auto_delete_duration = row
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        ph = self._build_placeholders(member)

        try:
            if welcome_type == "simple" and welcome_message:
                msg = await channel.send(self.safe_format(welcome_message, ph))
            elif welcome_type == "embed" and embed_data:
                embed_info = json.loads(embed_data)
                color_value = embed_info.get("color", 0x5865F2)
                if isinstance(color_value, str) and color_value.startswith("#"):
                    color_value = int(color_value.lstrip("#"), 16)

                embed = discord.Embed(
                    title=self.safe_format(embed_info.get("title", ""), ph),
                    description=self.safe_format(embed_info.get("description", ""), ph),
                    color=color_value
                )
                if embed_info.get("footer_text"):
                    embed.set_footer(
                        text=self.safe_format(embed_info["footer_text"], ph),
                        icon_url=self.safe_format(embed_info.get("footer_icon", ""), ph) or None
                    )
                if embed_info.get("author_name"):
                    embed.set_author(
                        name=self.safe_format(embed_info["author_name"], ph),
                        icon_url=self.safe_format(embed_info.get("author_icon", ""), ph) or None
                    )
                if embed_info.get("thumbnail"):
                    embed.set_thumbnail(url=self.safe_format(embed_info["thumbnail"], ph))
                if embed_info.get("image"):
                    embed.set_image(url=self.safe_format(embed_info["image"], ph))

                content = self.safe_format(embed_info.get("message", ""), ph) or None
                msg = await channel.send(content=content, embed=embed)
            else:
                return

            if auto_delete_duration:
                await asyncio.sleep(auto_delete_duration)
                await msg.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot):
    await bot.add_cog(Welcomer(bot))

# Lucky Bot — Rewritten
