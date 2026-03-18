import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import random
import string
import io
from PIL import Image, ImageDraw, ImageFont
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from utils.Tools import *


logger = logging.getLogger('discord')

DATABASE_PATH = 'db/verification.db'

COLORS = {
    'primary':   0x5865F2,
    'success':   0x57F287,
    'warning':   0x2F3136,
    'error':     0xFF4444,
    'secondary': 0x2F3136,
    'neutral':   0x2F3136,
}


def utc_to_ist(dt: datetime) -> datetime:
    ist_offset = timedelta(hours=5, minutes=30)
    return dt.replace(tzinfo=timezone.utc).astimezone(timezone(ist_offset))


async def check_bot_permissions(guild: discord.Guild, channel=None) -> dict:
    bot_member = guild.me
    required_perms = {
        'guild': ['manage_roles', 'manage_channels', 'send_messages', 'manage_messages'],
        'channel': ['view_channel', 'send_messages', 'attach_files', 'embed_links', 'manage_messages']
    }
    missing_perms = {'guild': [], 'channel': []}
    for perm in required_perms['guild']:
        if not getattr(bot_member.guild_permissions, perm):
            missing_perms['guild'].append(perm.replace('_', ' ').title())
    if channel:
        for perm in required_perms['channel']:
            if not getattr(channel.permissions_for(bot_member), perm):
                missing_perms['channel'].append(perm.replace('_', ' ').title())
    return missing_perms


def validate_role_hierarchy(guild: discord.Guild, role: discord.Role) -> bool:
    return guild.me.top_role.position > role.position


async def create_verified_role(guild: discord.Guild) -> discord.Role:
    role = await guild.create_role(
        name="Verified",
        color=discord.Color(0x5865F2),
        reason="Lucky Bot Verification System - auto-created verified role"
    )
    for channel in guild.channels:
        try:
            await channel.set_permissions(
                role,
                view_channel=True,
                send_messages=True,
                reason="Lucky Verification - granting access to verified members"
            )
        except (discord.Forbidden, discord.HTTPException):
            pass
    return role


async def auto_fix_permissions(guild: discord.Guild, verification_channel: discord.TextChannel,
                                verified_role: discord.Role):
    try:
        everyone_role = guild.default_role
        await verification_channel.set_permissions(
            everyone_role, view_channel=True, send_messages=False,
            reason="Lucky Verification - locking verification channel"
        )
        await verification_channel.set_permissions(
            verified_role, view_channel=False,
            reason="Lucky Verification - hiding channel from verified members"
        )
        for channel in guild.channels:
            if channel.id != verification_channel.id:
                try:
                    await channel.set_permissions(
                        everyone_role, view_channel=False,
                        reason="Lucky Verification - hiding channels from unverified"
                    )
                    await channel.set_permissions(
                        verified_role, view_channel=True,
                        reason="Lucky Verification - showing channels to verified"
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass
    except Exception as e:
        logger.error(f"Error fixing permissions: {e}")


class VerificationModal(discord.ui.Modal, title="Enter Verification Code"):
    def __init__(self, bot, captcha_code: str, guild_id: int):
        super().__init__()
        self.bot = bot
        self.captcha_code = captcha_code
        self.guild_id = guild_id

    captcha_input = discord.ui.TextInput(
        label="Verification Code",
        placeholder="Enter the 6-character code from the image",
        required=True,
        max_length=6,
        min_length=6
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if self.captcha_input.value.strip() != self.captcha_code:
                embed = discord.Embed(
                    title="Incorrect Code",
                    description="The code you entered is incorrect. Please try again by clicking the verification button in the server.",
                    color=COLORS['error']
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                await interaction.response.send_message("Server not found.", ephemeral=True)
                return

            member = guild.get_member(interaction.user.id)
            if not member:
                await interaction.response.send_message("You are not in the server.", ephemeral=True)
                return

            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute(
                        "SELECT verified_role_id FROM verification_config WHERE guild_id = ? AND enabled = 1",
                        (guild.id,)
                    )
                    result = await cur.fetchone()
                    if not result:
                        await interaction.response.send_message("Verification system is not configured.", ephemeral=True)
                        return
                    verified_role = guild.get_role(result[0])
                    if not verified_role:
                        await interaction.response.send_message("Verified role not found.", ephemeral=True)
                        return
                    if verified_role in member.roles:
                        embed = discord.Embed(
                            title="Already Verified",
                            description="You are already verified in this server!",
                            color=COLORS['success']
                        )
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                        return

            await member.add_roles(verified_role, reason="CAPTCHA verification completed")
            await self.log_verification(guild.id, member.id, "captcha")

            current_time = utc_to_ist(discord.utils.utcnow())
            embed = discord.Embed(
                title="Verification Successful",
                description=f"Welcome to **{guild.name}**!\n\nYou have been successfully verified and can now access all channels.",
                color=COLORS['success'],
                timestamp=current_time
            )
            embed.set_footer(text=f"Verified at {current_time.strftime('%I:%M %p IST')} | Lucky Bot • lucky.gg")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await self.send_verification_log(guild, member, "CAPTCHA", True)

        except discord.Forbidden:
            await interaction.response.send_message("Bot lacks permission to assign roles.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in verification modal: {e}")

    async def log_verification(self, guild_id: int, user_id: int, method: str):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    current_time = utc_to_ist(discord.utils.utcnow())
                    await cur.execute(
                        "INSERT INTO verification_logs (guild_id, user_id, verification_method, verified_at) VALUES (?, ?, ?, ?)",
                        (guild_id, user_id, method, current_time.isoformat())
                    )
                    await db.commit()
        except Exception as e:
            logger.error(f"Error logging verification: {e}")

    async def send_verification_log(self, guild: discord.Guild, user: discord.Member, method: str, success: bool):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute(
                        "SELECT log_channel_id FROM verification_config WHERE guild_id = ?", (guild.id,))
                    result = await cur.fetchone()
                    if result and result[0]:
                        log_channel = guild.get_channel(result[0])
                        if log_channel and log_channel.permissions_for(guild.me).send_messages:
                            current_time = utc_to_ist(discord.utils.utcnow())
                            embed = discord.Embed(
                                title="User Verification Log",
                                color=COLORS['success'] if success else COLORS['error'],
                                timestamp=current_time
                            )
                            embed.add_field(
                                name="User Information",
                                value=f"**User:** {user.mention}\n**ID:** {user.id}\n**Username:** {user.name}",
                                inline=False
                            )
                            embed.add_field(
                                name="Verification Details",
                                value=f"**Method:** {method}\n**Status:** {'Success' if success else 'Failed'}\n**Time:** {current_time.strftime('%I:%M %p IST')}",
                                inline=False
                            )
                            embed.set_thumbnail(url=user.display_avatar.url)
                            embed.set_footer(text="Lucky Bot • lucky.gg")
                            await log_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error sending verification log: {e}")


class VerificationView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Quick Verify", style=discord.ButtonStyle.green, custom_id="verify_button_quick")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute(
                        "SELECT verified_role_id, verification_method FROM verification_config WHERE guild_id = ? AND enabled = 1",
                        (interaction.guild.id,)
                    )
                    result = await cur.fetchone()
                    if not result:
                        embed = discord.Embed(title="System Unavailable",
                                              description="Verification system is not configured or disabled.",
                                              color=COLORS['error'])
                        return await interaction.response.send_message(embed=embed, ephemeral=True)
                    verified_role = interaction.guild.get_role(result[0])
                    verification_method = result[1]
                    if not verified_role:
                        embed = discord.Embed(description="Verified role not found. Please contact an administrator.",
                                              color=COLORS['error'])
                        return await interaction.response.send_message(embed=embed, ephemeral=True)
                    if verified_role in interaction.user.roles:
                        embed = discord.Embed(title="Already Verified",
                                              description="You are already verified! You can access all channels.",
                                              color=COLORS['success'])
                        return await interaction.response.send_message(embed=embed, ephemeral=True)

            if verification_method not in ["button", "both"]:
                embed = discord.Embed(title="CAPTCHA Required",
                                      description="This server requires CAPTCHA verification. Please use the CAPTCHA button.",
                                      color=COLORS['warning'])
                return await interaction.response.send_message(embed=embed, ephemeral=True)

            await interaction.user.add_roles(verified_role, reason="Quick button verification")
            modal = VerificationModal(self.bot, "", interaction.guild.id)
            await modal.log_verification(interaction.guild.id, interaction.user.id, "button")
            await modal.send_verification_log(interaction.guild, interaction.user, "BUTTON", True)

            current_time = utc_to_ist(discord.utils.utcnow())
            embed = discord.Embed(
                title="Welcome to the Server",
                description=f"**{interaction.user.mention}** has been verified!\n\nWelcome to {interaction.guild.name}!\nYou now have access to all channels.",
                color=COLORS['success'],
                timestamp=current_time
            )
            embed.set_footer(text=f"Verified at {current_time.strftime('%I:%M %p IST')} | Lucky Bot • lucky.gg")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except discord.Forbidden:
            embed = discord.Embed(description="Bot lacks permission to assign roles. Please contact an administrator.",
                                  color=COLORS['error'])
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in verify button: {e}")

    @discord.ui.button(label="CAPTCHA Verify", style=discord.ButtonStyle.primary, custom_id="verify_captcha_secure")
    async def verify_captcha(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute(
                        "SELECT verified_role_id FROM verification_config WHERE guild_id = ? AND enabled = 1",
                        (interaction.guild.id,)
                    )
                    result = await cur.fetchone()
                    if not result:
                        embed = discord.Embed(title="System Unavailable",
                                              description="Verification system is not configured or disabled.",
                                              color=COLORS['error'])
                        return await interaction.response.send_message(embed=embed, ephemeral=True)
                    verified_role = interaction.guild.get_role(result[0])
                    if not verified_role:
                        embed = discord.Embed(description="Verified role not found. Please contact an administrator.",
                                              color=COLORS['error'])
                        return await interaction.response.send_message(embed=embed, ephemeral=True)
                    if verified_role in interaction.user.roles:
                        embed = discord.Embed(title="Already Verified",
                                              description="You are already verified! You can access all channels.",
                                              color=COLORS['success'])
                        return await interaction.response.send_message(embed=embed, ephemeral=True)

            captcha_code = self.generate_captcha_code()
            captcha_image = self.create_captcha_image(captcha_code)

            try:
                file = discord.File(captcha_image, filename="captcha.png")
                embed = discord.Embed(
                    title="CAPTCHA Verification",
                    description=f"**Server:** {interaction.guild.name}\n\nPlease solve the CAPTCHA below to verify yourself.\nClick the button below to enter your answer.\n\n**Important:** The code is case-sensitive!",
                    color=COLORS['secondary']
                )
                embed.set_image(url="attachment://captcha.png")
                embed.set_footer(text="This CAPTCHA will expire in 10 minutes | Lucky Bot • lucky.gg")

                modal = VerificationModal(self.bot, captcha_code, interaction.guild.id)
                view = CaptchaModalView(modal)
                await interaction.user.send(embed=embed, file=file, view=view)

                embed = discord.Embed(
                    title="Check Your DMs",
                    description="I've sent you a CAPTCHA in your direct messages.\n\n**Steps:**\n1. Check your DMs from me\n2. Solve the CAPTCHA image\n3. Click the button to enter your answer\n\nMake sure your DMs are open!",
                    color=COLORS['secondary']
                )
                embed.set_footer(text="CAPTCHA expires in 10 minutes | Lucky Bot • lucky.gg")
                await interaction.response.send_message(embed=embed, ephemeral=True)

            except discord.Forbidden:
                embed = discord.Embed(
                    title="DMs Disabled",
                    description=f"I couldn't send you a DM! Please enable DMs from server members and try again.\n\n**How to enable DMs:**\n1. Right-click on **{interaction.guild.name}**\n2. Go to **Privacy Settings**\n3. Enable **Direct Messages**\n4. Try verification again",
                    color=COLORS['error']
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in verify captcha: {e}")

    def generate_captcha_code(self) -> str:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

    def create_captcha_image(self, code: str) -> io.BytesIO:
        width, height = 300, 120
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)

        for y in range(height):
            color_value = 255 - int((y / height) * 50)
            for x in range(width):
                draw.point((x, y), fill=(color_value, color_value, 255))

        for _ in range(200):
            x = random.randint(0, width)
            y = random.randint(0, height)
            draw.point((x, y), fill=(random.randint(150, 200), random.randint(150, 200), random.randint(150, 200)))

        for _ in range(8):
            x1, y1 = random.randint(0, width), random.randint(0, height)
            x2, y2 = random.randint(0, width), random.randint(0, height)
            draw.line([(x1, y1), (x2, y2)],
                      fill=(random.randint(100, 150), random.randint(100, 150), random.randint(100, 150)), width=2)

        try:
            font = ImageFont.truetype("games/assets/ClearSans-Bold.ttf", 40)
        except Exception:
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None

        if font:
            bbox = draw.textbbox((0, 0), code, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        else:
            text_width = len(code) * 20
            text_height = 20

        start_x = (width - text_width) // 2
        start_y = (height - text_height) // 2

        for i, char in enumerate(code):
            char_x = start_x + (i * text_width // len(code)) + random.randint(-8, 8)
            char_y = start_y + random.randint(-15, 15)
            color = (random.randint(0, 100), random.randint(0, 100), random.randint(0, 100))
            if font:
                draw.text((char_x, char_y), char, fill=color, font=font)
            else:
                draw.text((char_x, char_y), char, fill=color)

        draw.rectangle([(0, 0), (width - 1, height - 1)], outline='black', width=2)

        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG', quality=95)
        img_buffer.seek(0)
        return img_buffer


class CaptchaOnlyVerificationView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Verify with CAPTCHA", style=discord.ButtonStyle.primary, custom_id="verify_captcha_only")
    async def verify_captcha(self, interaction: discord.Interaction, button: discord.ui.Button):
        view_instance = VerificationView(self.bot)
        await view_instance.verify_captcha(interaction, button)

    def generate_captcha_code(self) -> str:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

    def create_captcha_image(self, code: str) -> io.BytesIO:
        v = VerificationView(self.bot)
        return v.create_captcha_image(code)


class CaptchaModalView(discord.ui.View):
    def __init__(self, modal: VerificationModal):
        super().__init__(timeout=600)
        self.modal = modal

    @discord.ui.button(label="Enter CAPTCHA Code", style=discord.ButtonStyle.primary)
    async def enter_captcha(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self.modal)


class VerificationSetupView(discord.ui.View):
    def __init__(self, bot, ctx):
        super().__init__(timeout=300)
        self.bot = bot
        self.ctx = ctx
        self.verification_channel = None
        self.log_channel = None
        self.verification_method = None

    @discord.ui.channel_select(placeholder="Select verification channel...", channel_types=[discord.ChannelType.text])
    async def verification_channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
        self.verification_channel = select.values[0]
        await interaction.response.send_message(
            f"🍀 Verification channel set to {self.verification_channel.mention}", ephemeral=True)

    @discord.ui.channel_select(placeholder="Select log channel (optional)...", channel_types=[discord.ChannelType.text], min_values=0)
    async def log_channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
        self.log_channel = select.values[0] if select.values else None
        msg = f"🍀 Log channel set to {self.log_channel.mention}" if self.log_channel else "🍀 No log channel set."
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.select(placeholder="Select verification method...", options=[
        discord.SelectOption(label="Button Only", value="button", description="Users click a button to verify"),
        discord.SelectOption(label="CAPTCHA Only", value="captcha", description="Users must solve a CAPTCHA"),
        discord.SelectOption(label="Both Methods", value="both", description="Both button and CAPTCHA available"),
    ])
    async def method_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
        self.verification_method = select.values[0]
        await interaction.response.send_message(f"🍀 Verification method set to: **{self.verification_method}**", ephemeral=True)

    @discord.ui.button(label="Complete Setup", style=discord.ButtonStyle.success, row=4)
    async def setup_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Only the command author can complete setup.", ephemeral=True)
        if not self.verification_channel or not self.verification_method:
            return await interaction.response.send_message(
                "🃏 Please select a verification channel and method first.", ephemeral=True)

        await interaction.response.defer()

        try:
            verified_role = await create_verified_role(interaction.guild)
            await auto_fix_permissions(interaction.guild, self.verification_channel, verified_role)

            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO verification_config
                    (guild_id, verification_channel_id, verified_role_id, log_channel_id, verification_method, enabled)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (interaction.guild.id, self.verification_channel.id, verified_role.id,
                      self.log_channel.id if self.log_channel else None, self.verification_method))
                await db.commit()

            await self.send_verification_panel(interaction, verified_role)

            embed = discord.Embed(
                title="🍀 Verification System Configured",
                description=(
                    f"**Verification Channel:** {self.verification_channel.mention}\n"
                    f"**Verified Role:** {verified_role.mention}\n"
                    f"**Log Channel:** {self.log_channel.mention if self.log_channel else 'None'}\n"
                    f"**Method:** {self.verification_method}\n\n"
                    f"The verification panel has been sent to {self.verification_channel.mention}."
                ),
                color=COLORS['success']
            )
            embed.add_field(
                name="🍀 Verification system is now ENABLED and ready to use!",
                value="Members will need to verify themselves to access your server.",
                inline=False
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await interaction.followup.send(embed=embed)
            self.stop()

        except Exception as e:
            logger.error(f"Error in verification setup: {e}")
            await interaction.followup.send(f"🃏 Setup failed: {e}", ephemeral=True)

    async def send_verification_panel(self, interaction: discord.Interaction, verified_role: discord.Role):
        embed = discord.Embed(
            title=f"Welcome to {interaction.guild.name}",
            description="To access the server, you need to verify yourself.\n\nClick the button below to start the verification process.",
            color=COLORS['primary']
        )
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else self.bot.user.display_avatar.url)
        embed.set_footer(text="Lucky Bot • lucky.gg")

        if self.verification_method == "button":
            view = ButtonOnlyVerificationView(self.bot)
        elif self.verification_method == "captcha":
            view = CaptchaOnlyVerificationView(self.bot)
        else:
            view = VerificationView(self.bot)

        await self.verification_channel.send(embed=embed, view=view)


class ButtonOnlyVerificationView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Click to Verify", style=discord.ButtonStyle.success, custom_id="verify_button_only")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute(
                        "SELECT verified_role_id FROM verification_config WHERE guild_id = ? AND enabled = 1",
                        (interaction.guild.id,)
                    )
                    result = await cur.fetchone()
                    if not result:
                        embed = discord.Embed(title="System Unavailable",
                                              description="Verification system is not configured or disabled.",
                                              color=COLORS['error'])
                        return await interaction.response.send_message(embed=embed, ephemeral=True)
                    verified_role = interaction.guild.get_role(result[0])
                    if not verified_role:
                        embed = discord.Embed(description="Verified role not found. Please contact an administrator.",
                                              color=COLORS['error'])
                        return await interaction.response.send_message(embed=embed, ephemeral=True)
                    if verified_role in interaction.user.roles:
                        embed = discord.Embed(title="Already Verified",
                                              description="You are already verified! You can access all channels.",
                                              color=COLORS['success'])
                        return await interaction.response.send_message(embed=embed, ephemeral=True)

            await interaction.user.add_roles(verified_role, reason="Button verification")
            modal = VerificationModal(self.bot, "", interaction.guild.id)
            await modal.log_verification(interaction.guild.id, interaction.user.id, "button")
            await modal.send_verification_log(interaction.guild, interaction.user, "BUTTON", True)

            current_time = utc_to_ist(discord.utils.utcnow())
            embed = discord.Embed(
                title="Welcome to the Server",
                description=f"**{interaction.user.mention}** has been verified!\n\nWelcome to {interaction.guild.name}!\nYou now have access to all channels.",
                color=COLORS['success'],
                timestamp=current_time
            )
            embed.set_footer(text=f"Verified at {current_time.strftime('%I:%M %p IST')} | Lucky Bot • lucky.gg")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except discord.Forbidden:
            embed = discord.Embed(description="Bot lacks permission to assign roles.", color=COLORS['error'])
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in button-only verify: {e}")


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.create_tables())
        self.bot.add_view(VerificationView(self.bot))
        self.bot.add_view(ButtonOnlyVerificationView(self.bot))
        self.bot.add_view(CaptchaOnlyVerificationView(self.bot))

    async def create_tables(self):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS verification_config (
                        guild_id INTEGER PRIMARY KEY,
                        verification_channel_id INTEGER NOT NULL,
                        verified_role_id INTEGER NOT NULL,
                        log_channel_id INTEGER,
                        verification_method TEXT DEFAULT 'both',
                        enabled BOOLEAN DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS verification_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        verification_method TEXT NOT NULL,
                        verified_at TEXT NOT NULL,
                        FOREIGN KEY (guild_id) REFERENCES verification_config (guild_id)
                    )
                """)
                await db.commit()
        except Exception as e:
            logger.error(f"Error creating verification tables: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute(
                        "SELECT verification_channel_id FROM verification_config WHERE guild_id = ? AND enabled = 1",
                        (message.guild.id,)
                    )
                    result = await cur.fetchone()
                    if result and result[0] == message.channel.id:
                        if not message.author.guild_permissions.manage_messages:
                            try:
                                await message.delete()
                                embed = discord.Embed(
                                    title="Message Deleted",
                                    description="This channel is for verification only. Please use the buttons above to verify.",
                                    color=COLORS['warning']
                                )
                                try:
                                    await message.author.send(embed=embed)
                                except discord.Forbidden:
                                    pass
                            except discord.Forbidden:
                                pass
        except Exception as e:
            logger.error(f"Error in verification message handler: {e}")

    @commands.hybrid_group(name="verification", invoke_without_command=True,
                           description="Advanced verification system management.")
    @commands.has_permissions(administrator=True)
    async def verification(self, ctx):
        await ctx.send_help(ctx.command)

    @verification.command(name="setup", description="Set up the advanced verification system.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def verification_setup(self, ctx):
        try:
            missing_perms = await check_bot_permissions(ctx.guild)
            if missing_perms['guild']:
                embed = discord.Embed(
                    title="Missing Permissions",
                    description=f"Bot is missing required server permissions: {', '.join(missing_perms['guild'])}\n\nPlease grant these permissions and try again.",
                    color=COLORS['error']
                )
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

            current_time = utc_to_ist(discord.utils.utcnow())
            embed = discord.Embed(
                title="Verification System Setup",
                description=(
                    "**Welcome to the Lucky Bot verification system!**\n\n"
                    "• **Auto-creates verified role** with proper permissions\n"
                    "• **DM-based CAPTCHA** system for enhanced security\n"
                    "• **Smart channel management** — hides verification after verification\n"
                    "• **Auto-permission fixing** for seamless setup\n"
                    "• **Auto-message deletion** in verification channel\n"
                    "• **Comprehensive logging** and analytics\n\n"
                    "**Configure your system using the dropdowns below:**"
                ),
                color=COLORS['primary'],
                timestamp=current_time
            )
            embed.set_footer(text=f"Setup wizard started at {current_time.strftime('%I:%M %p IST')} | Lucky Bot • lucky.gg")
            view = VerificationSetupView(self.bot, ctx)
            await ctx.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error in verification setup: {e}")
            embed = discord.Embed(description="An error occurred during setup.", color=COLORS['error'])
            await ctx.send(embed=embed)

    @verification.command(name="status", description="Check verification system status and analytics.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def verification_status(self, ctx):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute(
                        "SELECT * FROM verification_config WHERE guild_id = ?", (ctx.guild.id,))
                    config = await cur.fetchone()

            if not config:
                embed = discord.Embed(
                    title="Verification Not Configured",
                    description=f"Verification system has not been set up for {ctx.guild.name}.\n\nUse `{ctx.prefix}verification setup` to configure it.",
                    color=COLORS['error']
                )
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

            guild_id, v_channel_id, role_id, log_ch_id, method, enabled, created_at = config
            v_channel = ctx.guild.get_channel(v_channel_id)
            verified_role = ctx.guild.get_role(role_id)
            log_channel = ctx.guild.get_channel(log_ch_id) if log_ch_id else None

            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute(
                        "SELECT COUNT(*) FROM verification_logs WHERE guild_id = ?", (ctx.guild.id,))
                    total_verifications = (await cur.fetchone())[0]

            embed = discord.Embed(
                title=f"Verification Status for {ctx.guild.name}",
                color=COLORS['success'] if enabled else COLORS['error']
            )
            embed.add_field(name="Status", value="🍀 Enabled" if enabled else "🃏 Disabled", inline=True)
            embed.add_field(name="Method", value=method.title(), inline=True)
            embed.add_field(name="Total Verifications", value=str(total_verifications), inline=True)
            embed.add_field(name="Verification Channel",
                            value=v_channel.mention if v_channel else "Deleted", inline=True)
            embed.add_field(name="Verified Role",
                            value=verified_role.mention if verified_role else "Deleted", inline=True)
            embed.add_field(name="Log Channel",
                            value=log_channel.mention if log_channel else "None", inline=True)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in verification status: {e}")

    @verification.command(name="fix", description="Auto-fix verification system permissions.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def verification_fix(self, ctx):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute(
                        "SELECT verification_channel_id, verified_role_id FROM verification_config WHERE guild_id = ? AND enabled = 1",
                        (ctx.guild.id,))
                    result = await cur.fetchone()

            if not result:
                embed = discord.Embed(
                    description=f"Verification system is not configured. Use `{ctx.prefix}verification setup` first.",
                    color=COLORS['error']
                )
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

            v_channel = ctx.guild.get_channel(result[0])
            verified_role = ctx.guild.get_role(result[1])

            if not v_channel or not verified_role:
                embed = discord.Embed(description="Verification channel or role not found.", color=COLORS['error'])
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

            msg = await ctx.send("🔧 Auto-fixing verification permissions...")
            await auto_fix_permissions(ctx.guild, v_channel, verified_role)
            embed = discord.Embed(
                title="🍀 Permissions Fixed",
                description="Verification system permissions have been automatically fixed.",
                color=COLORS['success']
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await msg.edit(content=None, embed=embed)

        except Exception as e:
            logger.error(f"Error in verification fix: {e}")

    @verification.command(name="disable", description="Disable the verification system.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def verification_disable(self, ctx):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute(
                        "SELECT enabled FROM verification_config WHERE guild_id = ?", (ctx.guild.id,))
                    result = await cur.fetchone()

            if not result:
                embed = discord.Embed(description="Verification system is not configured.", color=COLORS['error'])
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

            if not result[0]:
                embed = discord.Embed(description="Verification system is already disabled.", color=COLORS['error'])
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute("UPDATE verification_config SET enabled = 0 WHERE guild_id = ?", (ctx.guild.id,))
                await db.commit()

            embed = discord.Embed(
                title="🍀 Verification Disabled",
                description=f"Verification system has been disabled for {ctx.guild.name}.",
                color=COLORS['success']
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in verification disable: {e}")

    @verification.command(name="enable", description="Enable the verification system.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def verification_enable(self, ctx):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute(
                        "SELECT enabled FROM verification_config WHERE guild_id = ?", (ctx.guild.id,))
                    result = await cur.fetchone()

            if not result:
                embed = discord.Embed(
                    description=f"Verification system is not configured. Use `{ctx.prefix}verification setup` first.",
                    color=COLORS['error']
                )
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

            if result[0]:
                embed = discord.Embed(description="Verification system is already enabled.", color=COLORS['error'])
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute("UPDATE verification_config SET enabled = 1 WHERE guild_id = ?", (ctx.guild.id,))
                await db.commit()

            embed = discord.Embed(
                title="🍀 Verification Enabled",
                description=f"Verification system has been re-enabled for {ctx.guild.name}.",
                color=COLORS['success']
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in verification enable: {e}")

    @verification.command(name="logs", description="View recent verification logs.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def verification_logs(self, ctx, limit: int = 10):
        try:
            limit = min(max(limit, 1), 25)
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute(
                        "SELECT user_id, verification_method, verified_at FROM verification_logs WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
                        (ctx.guild.id, limit)
                    )
                    logs = await cur.fetchall()

            if not logs:
                embed = discord.Embed(description="No verification logs found.", color=COLORS['neutral'])
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

            embed = discord.Embed(
                title=f"Recent Verification Logs for {ctx.guild.name}",
                color=COLORS['primary']
            )
            for user_id, method, verified_at in logs:
                user = self.bot.get_user(user_id)
                user_str = user.mention if user else f"User ID: {user_id}"
                embed.add_field(name=user_str, value=f"Method: {method}\nTime: {verified_at}", inline=False)
            embed.set_footer(text=f"Showing last {len(logs)} logs | Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in verification logs: {e}")

    @verification.command(name="reset", description="Reset the verification system configuration.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def verification_reset(self, ctx):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute("SELECT 1 FROM verification_config WHERE guild_id = ?", (ctx.guild.id,))
                    exists = await cur.fetchone()

            if not exists:
                embed = discord.Embed(description="Verification system is not configured.", color=COLORS['error'])
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

            embed = discord.Embed(
                title="Reset Verification System",
                description="Are you sure you want to reset the verification system? This will delete all configuration and logs.",
                color=COLORS['warning']
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")

            confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.danger)
            cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
            view = discord.ui.View(timeout=30)
            view.add_item(confirm_button)
            view.add_item(cancel_button)

            async def confirm_reset(interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Only the command author can confirm.", ephemeral=True)
                async with aiosqlite.connect(DATABASE_PATH) as db:
                    await db.execute("DELETE FROM verification_config WHERE guild_id = ?", (ctx.guild.id,))
                    await db.execute("DELETE FROM verification_logs WHERE guild_id = ?", (ctx.guild.id,))
                    await db.commit()
                reset_embed = discord.Embed(
                    title="🍀 Verification Reset",
                    description="Verification system has been completely reset.",
                    color=COLORS['success']
                )
                reset_embed.set_footer(text="Lucky Bot • lucky.gg")
                await interaction.response.edit_message(embed=reset_embed, view=None)

            async def cancel_reset(interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Only the command author can cancel.", ephemeral=True)
                cancel_embed = discord.Embed(description="Reset cancelled.", color=COLORS['neutral'])
                cancel_embed.set_footer(text="Lucky Bot • lucky.gg")
                await interaction.response.edit_message(embed=cancel_embed, view=None)

            confirm_button.callback = confirm_reset
            cancel_button.callback = cancel_reset
            await ctx.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error in verification reset: {e}")

    @verification.command(name="verify", description="Manually verify a user.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def verification_verify(self, ctx, user: discord.Member):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.cursor() as cur:
                    await cur.execute(
                        "SELECT verified_role_id FROM verification_config WHERE guild_id = ? AND enabled = 1",
                        (ctx.guild.id,))
                    result = await cur.fetchone()

            if not result:
                embed = discord.Embed(
                    description=f"Verification system is not configured. Use `{ctx.prefix}verification setup` first.",
                    color=COLORS['error']
                )
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

            verified_role = ctx.guild.get_role(result[0])
            if not verified_role:
                embed = discord.Embed(description="Verified role not found.", color=COLORS['error'])
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

            if verified_role in user.roles:
                embed = discord.Embed(description=f"{user.mention} is already verified.", color=COLORS['error'])
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)

            await user.add_roles(verified_role, reason=f"Manually verified by {ctx.author}")
            modal = VerificationModal(self.bot, "", ctx.guild.id)
            await modal.log_verification(ctx.guild.id, user.id, "manual")
            await modal.send_verification_log(ctx.guild, user, "MANUAL", True)

            embed = discord.Embed(
                title="🍀 User Verified",
                description=f"{user.mention} has been manually verified by {ctx.author.mention}.",
                color=COLORS['success']
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)

        except discord.Forbidden:
            embed = discord.Embed(description="Bot lacks permission to assign roles.", color=COLORS['error'])
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in verification verify: {e}")


async def setup(bot):
    await bot.add_cog(Verification(bot))

# Lucky Bot — Rewritten
