import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio
import json
import re
import random
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
import io
import os
import requests
import logging

logger = logging.getLogger("discord")

FONT_PATH = "games/assets/ClearSans-Bold.ttf"
FONT_PATH_REGULAR = "games/assets/ClearSans-Bold.ttf"


def utc_to_local(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc)


def format_number(num: int) -> str:
    return f"{num:,}"


def calculate_level_from_xp(xp: int) -> int:
    if xp < 0:
        return 0
    return int(math.sqrt(xp / 100))


def calculate_xp_for_level(level: int) -> int:
    return level * level * 100


def get_level_progress(xp: int) -> tuple:
    current_level = calculate_level_from_xp(xp)
    current_level_xp = calculate_xp_for_level(current_level)
    next_level_xp = calculate_xp_for_level(current_level + 1)
    progress = xp - current_level_xp
    needed = next_level_xp - current_level_xp
    return current_level, progress, needed


def get_progress_bar(current: int, total: int, length: int = 10) -> str:
    if total == 0:
        return "▱" * length
    filled = int((current / total) * length)
    return "▰" * filled + "▱" * (length - filled)


def validate_hex_color(color: str) -> bool:
    if not color.startswith("#"):
        return False
    return bool(re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", color))


def hex_to_int(hex_color: str) -> int:
    try:
        if not hex_color.startswith("#"):
            hex_color = "#" + hex_color
        return int(hex_color.lstrip("#"), 16)
    except (ValueError, TypeError):
        return 0xFF4444


class PlaceholdersView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Show Placeholders", style=discord.ButtonStyle.secondary, emoji="📝")
    async def show_placeholders(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📝 Available Placeholders",
            description=(
                "**You can use these placeholders in your level up message:**\n\n"
                "`{user}` - Mentions the user (@username)\n"
                "`{username}` - User's display name\n"
                "`{level}` - The new level reached\n"
                "`{server}` - Server name\n\n"
                "**Example:**\n"
                "`Congratulations {user}! You've reached level {level} in {server}!`"
            ),
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class LevelConfigModal(discord.ui.Modal, title="Leveling System Configuration"):
    def __init__(self, cog, current_settings):
        super().__init__()
        self.cog = cog

        self.xp_per_message = discord.ui.TextInput(
            label="XP per Message",
            placeholder="Amount of XP per message (default: 20)",
            default=str(current_settings.get("xp_per_message", 20)),
            required=True,
            max_length=3,
        )

        self.level_up_message = discord.ui.TextInput(
            label="Level Up Message",
            placeholder="Use {user}, {level}, {username}, {server} as placeholders",
            default=current_settings.get(
                "level_message", "Congratulations {user}! You have reached level {level}!"
            ),
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=2000,
        )

        current_color = current_settings.get("embed_color", "#000000")
        if isinstance(current_color, int):
            current_color = f"#{current_color:06x}"
        elif not isinstance(current_color, str):
            current_color = "#000000"
        if not current_color.startswith("#"):
            current_color = "#000000"

        self.embed_color = discord.ui.TextInput(
            label="Embed Color (Hex)",
            placeholder="#FF0000",
            default=current_color,
            required=True,
            max_length=7,
        )

        self.level_up_image = discord.ui.TextInput(
            label="Level Up Image URL (Optional)",
            placeholder="Direct image URL for level up embeds",
            default=current_settings.get("level_image", ""),
            required=False,
            max_length=500,
        )

        self.thumbnail_enabled = discord.ui.TextInput(
            label="Show User Avatar Thumbnail (true/false)",
            placeholder="true or false",
            default=str(current_settings.get("thumbnail_enabled", True)).lower(),
            required=True,
            max_length=5,
        )

        self.add_item(self.xp_per_message)
        self.add_item(self.level_up_message)
        self.add_item(self.embed_color)
        self.add_item(self.level_up_image)
        self.add_item(self.thumbnail_enabled)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not interaction or not hasattr(interaction, "response"):
                logger.error("Invalid interaction object in LevelConfigModal")
                return

            await interaction.response.defer(ephemeral=True)

            try:
                xp_value = int(self.xp_per_message.value)
                if xp_value < 1 or xp_value > 999:
                    raise ValueError("XP per message must be between 1 and 999")
            except ValueError as ve:
                logger.error(f"XP validation error: {ve}")
                await interaction.followup.send(
                    "🃏 Invalid XP per message value! Must be between 1 and 999.", ephemeral=True
                )
                return

            color_value = self.embed_color.value.strip()
            if not color_value.startswith("#"):
                color_value = "#" + color_value

            if not validate_hex_color(color_value):
                await interaction.followup.send(
                    "🃏 Invalid hex color format! Use format like #FF0000", ephemeral=True
                )
                return

            thumbnail_bool = self.thumbnail_enabled.value.lower() in ["true", "yes", "1", "on"]

            try:
                embed_color_int = hex_to_int(color_value)
            except Exception as e:
                logger.error(f"Color conversion error: {e}")
                embed_color_int = 0

            image_value = (
                self.level_up_image.value.strip()
                if self.level_up_image.value and self.level_up_image.value.strip()
                else None
            )

            try:
                async with aiosqlite.connect("db/leveling.db") as db:
                    async with db.execute(
                        "SELECT guild_id FROM leveling_settings WHERE guild_id = ?",
                        (interaction.guild.id,),
                    ) as cursor:
                        exists = await cursor.fetchone()

                    if exists:
                        await db.execute(
                            """
                            UPDATE leveling_settings
                            SET enabled = ?, xp_per_message = ?, level_message = ?, embed_color = ?,
                                level_image = ?, thumbnail_enabled = ?
                            WHERE guild_id = ?
                            """,
                            (
                                1,
                                xp_value,
                                self.level_up_message.value,
                                embed_color_int,
                                image_value,
                                1 if thumbnail_bool else 0,
                                interaction.guild.id,
                            ),
                        )
                    else:
                        await db.execute(
                            """
                            INSERT INTO leveling_settings
                            (guild_id, enabled, xp_per_message, level_message, embed_color, level_image, thumbnail_enabled,
                             min_xp, max_xp, cooldown_seconds, dm_level_up, channel_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                interaction.guild.id,
                                1,
                                xp_value,
                                self.level_up_message.value,
                                embed_color_int,
                                image_value,
                                1 if thumbnail_bool else 0,
                                15,
                                25,
                                60,
                                0,
                                None,
                            ),
                        )
                    await db.commit()
            except Exception as e:
                logger.error(f"DB error in LevelConfigModal: {e}")
                return

            embed = discord.Embed(
                title="🍀 Leveling Configuration Updated",
                description=(
                    f"**XP per Message:** {xp_value}\n"
                    f"**Level Up Message:** {self.level_up_message.value[:50]}"
                    f"{'...' if len(self.level_up_message.value) > 50 else ''}\n"
                    f"**Embed Color:** {color_value}\n"
                    f"**Level Up Image:** {'Set' if image_value else 'None'}\n"
                    f"**Thumbnail Enabled:** {thumbnail_bool}"
                ),
                color=0x57F287,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")

            view = PlaceholdersView()
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Critical error in LevelConfigModal: {e}")
            await interaction.followup.send(
                f"🃏 An unexpected error occurred: {str(e)}", ephemeral=True
            )


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_cooldowns = {}
        self.last_level_cache = {}
        self.db_path = "db/leveling.db"

    @commands.group(name="level", invoke_without_command=True, description="Leveling system")
    async def level(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    async def cog_load(self):
        try:
            await self.init_database()
        except Exception as e:
            logger.error(f"Error loading Leveling cog: {e}")

    async def init_database(self):
        try:
            async with aiosqlite.connect("db/leveling.db") as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_xp (
                        guild_id INTEGER,
                        user_id INTEGER,
                        xp INTEGER DEFAULT 0,
                        messages INTEGER DEFAULT 0,
                        last_message_time TEXT,
                        PRIMARY KEY (guild_id, user_id)
                    )
                """)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS leveling_settings (
                        guild_id INTEGER PRIMARY KEY,
                        enabled INTEGER DEFAULT 0,
                        channel_id INTEGER,
                        level_message TEXT DEFAULT 'Congratulations {user}! You have reached level {level}!',
                        embed_color INTEGER DEFAULT 0,
                        level_image TEXT,
                        thumbnail_enabled INTEGER DEFAULT 1,
                        xp_per_message INTEGER DEFAULT 20,
                        min_xp INTEGER DEFAULT 15,
                        max_xp INTEGER DEFAULT 25,
                        cooldown_seconds INTEGER DEFAULT 60,
                        dm_level_up INTEGER DEFAULT 0
                    )
                """)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS level_rewards (
                        guild_id INTEGER,
                        level INTEGER,
                        role_id INTEGER,
                        remove_previous INTEGER DEFAULT 0,
                        PRIMARY KEY (guild_id, level)
                    )
                """)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS xp_multipliers (
                        guild_id INTEGER,
                        target_id INTEGER,
                        target_type TEXT,
                        multiplier REAL,
                        PRIMARY KEY (guild_id, target_id, target_type)
                    )
                """)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS leveling_blacklist (
                        guild_id INTEGER,
                        target_id INTEGER,
                        target_type TEXT,
                        PRIMARY KEY (guild_id, target_id, target_type)
                    )
                """)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        guild_id INTEGER,
                        user_id INTEGER,
                        xp INTEGER DEFAULT 0,
                        level INTEGER DEFAULT 1,
                        PRIMARY KEY (guild_id, user_id)
                    )
                """)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS level_roles (
                        guild_id INTEGER,
                        level INTEGER,
                        role_id INTEGER,
                        PRIMARY KEY (guild_id, level)
                    )
                """)

                async with db.cursor() as cursor:
                    await cursor.execute("PRAGMA table_info(leveling_blacklist)")
                    columns = [col[1] for col in await cursor.fetchall()]
                    if "target_type" not in columns:
                        await cursor.execute(
                            "ALTER TABLE leveling_blacklist ADD COLUMN target_type TEXT"
                        )

                await db.commit()
        except Exception as e:
            logger.error(f"Database initialization error: {e}")

    async def get_guild_settings(self, guild_id: int) -> dict:
        max_retries = 5
        for attempt in range(max_retries):
            try:
                async with aiosqlite.connect("db/leveling.db") as db:
                    async with db.execute(
                        "SELECT * FROM leveling_settings WHERE guild_id = ?", (guild_id,)
                    ) as cursor:
                        row = await cursor.fetchone()

                    if not row:
                        async with aiosqlite.connect("db/leveling.db") as db2:
                            await db2.execute(
                                "INSERT INTO leveling_settings (guild_id, enabled) VALUES (?, 0)",
                                (guild_id,),
                            )
                            await db2.commit()
                        return {
                            "enabled": False, "channel_id": None,
                            "level_message": "Congratulations {user}! You have reached level {level}!",
                            "embed_color": "#000000", "level_image": None, "thumbnail_enabled": True,
                            "xp_per_message": 20, "min_xp": 15, "max_xp": 25, "cooldown_seconds": 60,
                            "dm_level_up": False,
                        }

                    embed_color = row[4] if len(row) > 4 and row[4] is not None else 0
                    if isinstance(embed_color, int):
                        color_hex = f"#{embed_color:06x}"
                    else:
                        color_hex = "#FF4444"

                    return {
                        "enabled": bool(row[1]) if len(row) > 1 else False,
                        "channel_id": row[2] if len(row) > 2 else None,
                        "level_message": row[3] if len(row) > 3 else "Congratulations {user}! You have reached level {level}!",
                        "embed_color": color_hex,
                        "level_image": row[5] if len(row) > 5 else None,
                        "thumbnail_enabled": bool(row[6]) if len(row) > 6 else True,
                        "xp_per_message": row[7] if len(row) > 7 else 20,
                        "min_xp": row[8] if len(row) > 8 else 15,
                        "max_xp": row[9] if len(row) > 9 else 25,
                        "cooldown_seconds": row[10] if len(row) > 10 else 60,
                        "dm_level_up": bool(row[11]) if len(row) > 11 else False,
                    }

            except aiosqlite.OperationalError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Database locked, retrying... (attempt {attempt + 1})")
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                else:
                    logger.error(f"Database error after {max_retries} attempts: {e}")
                    break
            except Exception as e:
                logger.error(f"Error getting guild settings: {e}")
                break

        return {
            "enabled": False, "channel_id": None,
            "level_message": "Congratulations {user}! You have reached level {level}!",
            "embed_color": "#000000", "level_image": None, "thumbnail_enabled": True,
            "xp_per_message": 20, "min_xp": 15, "max_xp": 25, "cooldown_seconds": 60,
            "dm_level_up": False,
        }

    async def is_blacklisted(self, guild_id: int, user_id: int, channel_id: int) -> bool:
        try:
            async with aiosqlite.connect("db/leveling.db") as db:
                async with db.cursor() as cursor:
                    await cursor.execute("PRAGMA table_info(leveling_blacklist)")
                    columns = [col[1] for col in await cursor.fetchall()]
                    if "target_type" not in columns:
                        logger.warning("target_type column missing from leveling_blacklist table")
                        return False

                async with db.execute(
                    "SELECT 1 FROM leveling_blacklist WHERE guild_id = ? AND target_id = ? AND target_type = 'channel'",
                    (guild_id, channel_id),
                ) as cursor:
                    if await cursor.fetchone():
                        return True

                guild = self.bot.get_guild(guild_id)
                if guild:
                    member = guild.get_member(user_id)
                    if member:
                        async with db.execute(
                            "SELECT target_id FROM leveling_blacklist WHERE guild_id = ? AND target_type = 'role'",
                            (guild_id,),
                        ) as cursor:
                            blacklisted_roles = [row[0] for row in await cursor.fetchall()]
                            if any(role.id in blacklisted_roles for role in member.roles):
                                return True
                return False
        except Exception as e:
            logger.error(f"Error checking blacklist: {e}")
            return False

    async def get_xp_multiplier(self, guild_id: int, user_id: int, channel_id: int) -> float:
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return 1.0
            member = guild.get_member(user_id)
            if not member:
                return 1.0

            total_multiplier = 1.0
            async with aiosqlite.connect("db/leveling.db") as db:
                async with db.execute(
                    "SELECT target_id, multiplier FROM xp_multipliers WHERE guild_id = ? AND target_type = 'role'",
                    (guild_id,),
                ) as cursor:
                    role_multipliers = await cursor.fetchall()

                for role_id, multiplier in role_multipliers:
                    if any(role.id == role_id for role in member.roles):
                        total_multiplier *= multiplier

                async with db.execute(
                    "SELECT multiplier FROM xp_multipliers WHERE guild_id = ? AND target_id = ? AND target_type = 'channel'",
                    (guild_id, channel_id),
                ) as cursor:
                    channel_mult = await cursor.fetchone()
                    if channel_mult:
                        total_multiplier *= channel_mult[0]

            return total_multiplier
        except Exception as e:
            logger.error(f"Error getting XP multiplier: {e}")
            return 1.0

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id
        channel_id = message.channel.id

        cooldown_key = f"{guild_id}_{user_id}"
        now = datetime.now()

        if cooldown_key in self.message_cooldowns:
            if now < self.message_cooldowns[cooldown_key]:
                return

        try:
            settings = await self.get_guild_settings(guild_id)
            if not settings.get("enabled", False):
                return

            if await self.is_blacklisted(guild_id, user_id, channel_id):
                return

            cooldown_seconds = settings.get("cooldown_seconds", 60)
            self.message_cooldowns[cooldown_key] = now + timedelta(seconds=cooldown_seconds)

            base_xp = settings.get("xp_per_message", 20) or 20
            multiplier = await self.get_xp_multiplier(guild_id, user_id, channel_id) or 1.0
            final_xp = int(base_xp * multiplier)

            async with aiosqlite.connect("db/leveling.db") as db:
                async with db.execute(
                    "SELECT xp, messages FROM user_xp WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id),
                ) as cursor:
                    row = await cursor.fetchone()

                if row and len(row) >= 2:
                    current_xp = row[0] if row[0] is not None else 0
                    current_messages = row[1] if row[1] is not None else 0
                    old_level = calculate_level_from_xp(current_xp)
                    new_xp = current_xp + final_xp
                    new_level = calculate_level_from_xp(new_xp)
                    new_messages = current_messages + 1

                    await db.execute(
                        """
                        UPDATE user_xp
                        SET xp = ?, messages = ?, last_message_time = ?
                        WHERE guild_id = ? AND user_id = ?
                        """,
                        (new_xp, new_messages, now.isoformat(), guild_id, user_id),
                    )
                else:
                    old_level = 0
                    new_level = calculate_level_from_xp(final_xp)
                    new_xp = final_xp
                    new_messages = 1

                    await db.execute(
                        """
                        INSERT INTO user_xp (guild_id, user_id, xp, messages, last_message_time)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (guild_id, user_id, final_xp, new_messages, now.isoformat()),
                    )

                await db.execute(
                    """
                    INSERT OR REPLACE INTO users (guild_id, user_id, xp, level)
                    VALUES (?, ?, ?, ?)
                    """,
                    (guild_id, user_id, new_xp, new_level),
                )
                await db.commit()

            if new_level > old_level:
                await self.handle_level_up(message, new_level, settings)

        except Exception as e:
            logger.error(f"Error handling message XP: {e}")

    async def handle_level_up(self, message, new_level, settings):
        try:
            channel_id = settings.get("channel_id")
            channel = None

            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel and not channel.permissions_for(message.guild.me).send_messages:
                    logger.warning(f"No permission to send in level channel {channel_id}")
                    channel = None

            if not channel:
                if not channel_id:
                    channel = message.channel
                else:
                    logger.error(f"Configured level channel {channel_id} not found or not accessible")
                    return

            level_message = settings.get(
                "level_message", "Congratulations {user}! You have reached level {level}!"
            )
            level_message = level_message.replace("{user}", message.author.mention)
            level_message = level_message.replace("{level}", str(new_level))
            level_message = level_message.replace("{username}", message.author.display_name)
            level_message = level_message.replace("{server}", message.guild.name)

            embed = discord.Embed(
                title="🎉 Level Up!",
                description=level_message,
                color=0x57F287,
                timestamp=datetime.now(timezone.utc),
            )

            if settings.get("thumbnail_enabled", True):
                embed.set_thumbnail(url=message.author.display_avatar.url)

            if settings.get("level_image"):
                embed.set_image(url=settings["level_image"])

            embed.set_footer(text=f"Level {new_level} • Lucky Bot • lucky.gg")

            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                logger.error(f"No permission to send level up message in channel {channel.id}")
            except discord.NotFound:
                logger.error(f"Level up channel {channel.id} not found")
            except Exception as e:
                logger.error(f"Error sending level up message: {e}")

            await self.give_level_rewards(message.guild, message.author, new_level)
            await self.apply_level_roles(message.guild, message.author, new_level)

        except Exception as e:
            logger.error(f"Error handling level up: {e}")

    async def give_level_rewards(self, guild, member, level):
        try:
            async with aiosqlite.connect("db/leveling.db") as db:
                async with db.execute(
                    "SELECT role_id, remove_previous FROM level_rewards WHERE guild_id = ? AND level <= ? ORDER BY level DESC",
                    (guild.id, level),
                ) as cursor:
                    rewards = await cursor.fetchall()

            for role_id, remove_previous in rewards:
                role = guild.get_role(role_id)
                if role and role not in member.roles:
                    await member.add_roles(role, reason=f"Level {level} reward")
                    if remove_previous:
                        async with aiosqlite.connect("db/leveling.db") as db:
                            async with db.execute(
                                "SELECT role_id FROM level_rewards WHERE guild_id = ? AND level < ?",
                                (guild.id, level),
                            ) as cursor:
                                prev_rewards = await cursor.fetchall()
                        for (prev_role_id,) in prev_rewards:
                            prev_role = guild.get_role(prev_role_id)
                            if prev_role and prev_role in member.roles:
                                await member.remove_roles(prev_role, reason=f"Upgraded to level {level}")

        except Exception as e:
            logger.error(f"Error giving level rewards: {e}")

    async def apply_level_roles(self, guild, member, level):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?",
                    (guild.id, level),
                ) as cursor:
                    result = await cursor.fetchone()
                    if result:
                        role_id = result[0]
                        role = guild.get_role(role_id)
                        if role:
                            try:
                                await member.add_roles(role, reason=f"Reached level {level}")
                            except discord.Forbidden:
                                logger.error(f"Missing permissions to add role {role.name} to {member.name}")
                            except discord.HTTPException as e:
                                logger.error(f"Failed to add role {role.name} to {member.name}: {e}")
                        else:
                            logger.warning(f"Role with ID {role_id} not found in {guild.name}")
        except Exception as e:
            logger.error(f"Error applying level roles: {e}")

    async def get_user_data(self, guild_id: int, user_id: int) -> tuple:
        try:
            async with aiosqlite.connect("db/leveling.db") as db:
                async with db.execute(
                    "SELECT xp, messages FROM user_xp WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        xp, messages = row
                        level = calculate_level_from_xp(xp if xp is not None else 0)
                        return xp if xp is not None else 0, level, messages if messages is not None else 0
                    return 0, 0, 0
        except Exception as e:
            logger.error(f"Error getting user data: {e}")
            return 0, 0, 0

    async def get_user_rank(self, guild_id: int, user_id: int) -> int:
        try:
            async with aiosqlite.connect("db/leveling.db") as db:
                async with db.execute(
                    "SELECT COUNT(*) + 1 FROM user_xp WHERE guild_id = ? AND xp > (SELECT COALESCE(xp, 0) FROM user_xp WHERE guild_id = ? AND user_id = ?)",
                    (guild_id, guild_id, user_id),
                ) as cursor:
                    rank = (await cursor.fetchone())[0]
                    return rank
        except Exception as e:
            logger.error(f"Error getting user rank: {e}")
            return 1

    def create_simple_rank_card(self, member, xp, level, rank, messages):
        try:
            current_level, progress, needed = get_level_progress(xp)
            progress_bar = get_progress_bar(progress, needed, 20)

            rank_text = f"""
┌─────────────────────────────────────────┐
│ 🎮 RANK CARD - {member.display_name[:20]}
├─────────────────────────────────────────┤
│ 📊 Rank: #{rank:,}
│ ⭐ Level: {level:,}
│ 💬 Messages: {messages:,}
│ 🎯 XP: {xp:,}
├─────────────────────────────────────────┤
│ Progress to Level {level + 1}:
│ {progress_bar}
│ {progress:,} / {needed:,} XP
└─────────────────────────────────────────┘
            """
            return rank_text.strip()
        except Exception as e:
            logger.error(f"Error creating simple rank card: {e}")
            return f"**{member.display_name}** - Level {level} - Rank #{rank}"

    async def create_rank_card(self, member, guild_id):
        try:
            xp, level, messages = await self.get_user_data(guild_id, member.id)
            rank = await self.get_user_rank(guild_id, member.id)

            if PIL_AVAILABLE:
                try:
                    design_number = random.randint(1, 7)
                    return await self.create_rank_card_design(member, xp, level, rank, messages, design_number)
                except Exception as e:
                    logger.error(f"PIL error, falling back to text: {e}")
                    return self.create_simple_rank_card(member, xp, level, rank, messages)
            else:
                return self.create_simple_rank_card(member, xp, level, rank, messages)

        except Exception as e:
            logger.error(f"Error creating rank card: {e}")
            return None

    def _load_fonts(self, sizes):
        fonts = []
        for size in sizes:
            try:
                fonts.append(ImageFont.truetype(FONT_PATH, size))
            except (OSError, IOError):
                fonts.append(ImageFont.load_default())
        return fonts

    async def create_rank_card_design(self, member, xp, level, rank, messages, design_number):
        current_level, progress, needed = get_level_progress(xp)
        width, height = 900, 300

        font_large, font_medium, font_small = self._load_fonts([28, 20, 16])

        if design_number == 1:
            return await self.create_classic_design(member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small)
        elif design_number == 2:
            return await self.create_neon_design(member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small)
        elif design_number == 3:
            return await self.create_space_design(member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small)
        elif design_number == 4:
            return await self.create_minimal_design(member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small)
        elif design_number == 5:
            return await self.create_gaming_design(member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small)
        elif design_number == 6:
            return await self.create_elegant_design(member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small)
        else:
            return await self.create_cyberpunk_design(member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small)

    def _paste_avatar(self, draw, img, member, avatar_x, avatar_y, avatar_size, circular=True):
        try:
            avatar_url = str(member.display_avatar.with_size(256).url)
            response = requests.get(avatar_url, timeout=10)
            if response.status_code == 200:
                avatar_img = Image.open(io.BytesIO(response.content))
                avatar_img = avatar_img.resize((avatar_size, avatar_size))
                if circular:
                    mask = Image.new("L", (avatar_size, avatar_size), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                    avatar_img.putalpha(mask)
                img.paste(avatar_img, (avatar_x, avatar_y), avatar_img)
                return True
        except Exception:
            pass
        return False

    def _save_image(self, img):
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        img.close()
        return img_bytes

    async def create_classic_design(self, member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small):
        img = Image.new("RGB", (width, height), (32, 34, 37))
        draw = ImageDraw.Draw(img)

        color_schemes = [
            [(45, 52, 54), (99, 110, 114)],
            [(74, 144, 226), (80, 227, 194)],
            [(245, 166, 35), (242, 112, 156)],
            [(165, 94, 234), (74, 144, 226)],
            [(255, 118, 117), (255, 204, 128)],
            [(18, 194, 233), (196, 113, 237)],
        ]
        scheme = color_schemes[level % len(color_schemes)]

        for x in range(width):
            for y in range(height):
                factor = ((x / width) + (y / height)) / 2
                r = int(scheme[0][0] + (scheme[1][0] - scheme[0][0]) * factor)
                g = int(scheme[0][1] + (scheme[1][1] - scheme[0][1]) * factor)
                b = int(scheme[0][2] + (scheme[1][2] - scheme[0][2]) * factor)
                draw.point((x, y), fill=(r, g, b))

        draw.rounded_rectangle((15, 15, width - 15, height - 15), radius=20, fill=(0, 0, 0, 100))
        draw.rounded_rectangle((15, 15, width - 15, height - 15), radius=20, outline=(255, 255, 255, 50), width=2)

        await self.add_avatar_and_content_classic(draw, member, level, rank, messages, xp, progress, needed, width, height, font_large, font_medium, font_small)
        return self._save_image(img)

    async def create_neon_design(self, member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small):
        img = Image.new("RGB", (width, height), (10, 10, 25))
        draw = ImageDraw.Draw(img)

        grid_color = (0, 255, 255, 30)
        for x in range(0, width, 50):
            draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
        for y in range(0, height, 50):
            draw.line([(0, y), (width, y)], fill=grid_color, width=1)
        for i in range(5):
            draw.rounded_rectangle((15 - i, 15 - i, width - 15 + i, height - 15 + i), radius=20 + i, outline=(0, 255, 255, 50 - i * 10), width=1)
        draw.rounded_rectangle((20, 20, width - 20, height - 20), radius=15, fill=(5, 5, 20))

        await self.add_avatar_and_content_neon(draw, member, level, rank, messages, xp, progress, needed, width, height, font_large, font_medium, font_small)
        return self._save_image(img)

    async def create_space_design(self, member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small):
        img = Image.new("RGB", (width, height), (5, 5, 20))
        draw = ImageDraw.Draw(img)

        for _ in range(100):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(1, 3)
            brightness = random.randint(150, 255)
            draw.ellipse((x, y, x + size, y + size), fill=(brightness, brightness, brightness))

        draw.rounded_rectangle((20, 20, width - 20, height - 20), radius=15, fill=(0, 0, 0, 150))
        await self.add_avatar_and_content_space(draw, member, level, rank, messages, xp, progress, needed, width, height, font_large, font_medium, font_small)
        return self._save_image(img)

    async def create_minimal_design(self, member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small):
        img = Image.new("RGB", (width, height), (248, 249, 250))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((10, 10, width - 10, height - 10), radius=15, outline=(220, 220, 220), width=2, fill=(255, 255, 255))
        await self.add_avatar_and_content_minimal(draw, member, level, rank, messages, xp, progress, needed, width, height, font_large, font_medium, font_small)
        return self._save_image(img)

    async def create_gaming_design(self, member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small):
        img = Image.new("RGB", (width, height), (20, 20, 20))
        draw = ImageDraw.Draw(img)
        colors = [(255, 0, 0), (255, 127, 0), (255, 255, 0), (0, 255, 0), (0, 0, 255), (139, 0, 255)]
        for i, color in enumerate(colors):
            offset = i * 2
            draw.rounded_rectangle((10 + offset, 10 + offset, width - 10 - offset, height - 10 - offset), radius=20 - offset, outline=color, width=2)
        draw.rounded_rectangle((25, 25, width - 25, height - 25), radius=10, fill=(15, 15, 15))
        await self.add_avatar_and_content_gaming(draw, member, xp, progress, needed, messages, level, rank, width, height, font_large, font_medium, font_small)
        return self._save_image(img)

    async def create_elegant_design(self, member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small):
        img = Image.new("RGB", (width, height), (25, 25, 25))
        draw = ImageDraw.Draw(img)
        for i in range(10):
            alpha = 255 - (i * 25)
            draw.rounded_rectangle((5 + i, 5 + i, width - 5 - i, height - 5 - i), radius=20 + i, outline=(255, 215, 0, alpha), width=1)
        draw.rounded_rectangle((20, 20, width - 20, height - 20), radius=15, fill=(35, 35, 35))
        await self.add_avatar_and_content_elegant(draw, member, xp, progress, needed, messages, level, rank, width, height, font_large, font_medium, font_small)
        return self._save_image(img)

    async def create_cyberpunk_design(self, member, xp, level, rank, messages, current_level, progress, needed, width, height, font_large, font_medium, font_small):
        img = Image.new("RGB", (width, height), (15, 15, 15))
        draw = ImageDraw.Draw(img)
        line_color = (75, 0, 130)
        for i in range(20):
            y = int(height / 20 * i)
            draw.line((0, y, width, y), fill=line_color, width=1)
        draw.rounded_rectangle((20, 20, width - 20, height - 20), radius=15, fill=(25, 25, 25))
        await self.add_avatar_and_content_cyberpunk(draw, member, xp, progress, needed, messages, level, rank, width, height, font_large, font_medium, font_small)
        return self._save_image(img)

    async def add_avatar_and_content_classic(self, draw, member, level, rank, messages, xp, progress, needed, width, height, font_large, font_medium, font_small):
        avatar_size, avatar_x, avatar_y = 120, 30, 90
        img = draw._image

        if not self._paste_avatar(draw, img, member, avatar_x, avatar_y, avatar_size):
            draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill=(64, 68, 75))

        info_x = 180
        username = member.display_name[:18]
        draw.text((info_x + 2, 42), username, font=font_large, fill=(0, 0, 0))
        draw.text((info_x, 40), username, font=font_large, fill=(255, 255, 255))
        draw.text((info_x, 80), f"🏆 Level {level}", font=font_medium, fill=(255, 215, 0))
        draw.text((info_x, 110), f"📊 Rank #{rank}", font=font_medium, fill=(135, 206, 250))

        bar_x, bar_y = info_x, 150
        bar_width, bar_height = 500, 25
        draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), radius=12, fill=(32, 34, 37))
        if needed > 0:
            progress_width = int((progress / needed) * bar_width)
            for i in range(progress_width):
                factor = i / progress_width if progress_width > 0 else 0
                r = int(100 + (255 - 100) * factor)
                g = int(150 + (105 - 150) * factor)
                b = int(255 - 50 * factor)
                draw.line([(bar_x + i, bar_y + 2), (bar_x + i, bar_y + bar_height - 2)], fill=(r, g, b))

        xp_text = f"{progress:,} / {needed:,} XP"
        text_bbox = draw.textbbox((0, 0), xp_text, font=font_small)
        text_x = bar_x + (bar_width - (text_bbox[2] - text_bbox[0])) // 2
        draw.text((text_x, bar_y + 5), xp_text, font=font_small, fill=(255, 255, 255))

        stats_x = 720
        draw.text((stats_x, 80), "💬 Messages", font=font_small, fill=(255, 255, 255))
        draw.text((stats_x, 100), f"{messages:,}", font=font_medium, fill=(0, 255, 127))
        draw.text((stats_x, 130), "⭐ Total XP", font=font_small, fill=(255, 255, 255))
        draw.text((stats_x, 150), f"{xp:,}", font=font_medium, fill=(255, 165, 0))
        percentage = (progress / needed * 100) if needed > 0 else 100
        draw.text((stats_x, 180), "📈 Progress", font=font_small, fill=(255, 255, 255))
        draw.text((stats_x, 200), f"{percentage:.1f}%", font=font_medium, fill=(255, 105, 180))

    async def add_avatar_and_content_neon(self, draw, member, level, rank, messages, xp, progress, needed, width, height, font_large, font_medium, font_small):
        avatar_size, avatar_x, avatar_y = 100, 40, 100
        img = draw._image
        if not self._paste_avatar(draw, img, member, avatar_x, avatar_y, avatar_size):
            draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill=(0, 50, 50))

        info_x = 170
        username = member.display_name[:15]
        draw.text((info_x, 50), username, font=font_large, fill=(0, 255, 255))
        draw.text((info_x, 85), f"⚡ Level {level}", font=font_medium, fill=(0, 255, 255))
        draw.text((info_x, 115), f"🎯 Rank #{rank}", font=font_medium, fill=(0, 255, 255))

        bar_x, bar_y = info_x, 160
        bar_width, bar_height = 480, 20
        draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), radius=10, fill=(0, 20, 20))
        if needed > 0:
            progress_width = int((progress / needed) * bar_width)
            if progress_width > 0:
                draw.rounded_rectangle((bar_x + 2, bar_y + 2, bar_x + progress_width - 2, bar_y + bar_height - 2), radius=8, fill=(0, 255, 255))

        xp_text = f"{progress:,} / {needed:,} XP"
        text_bbox = draw.textbbox((0, 0), xp_text, font=font_small)
        text_x = bar_x + (bar_width - (text_bbox[2] - text_bbox[0])) // 2
        draw.text((text_x, bar_y + 2), xp_text, font=font_small, fill=(255, 255, 255))

        stats_x = 700
        draw.text((stats_x, 80), f"💬 {messages:,}", font=font_small, fill=(0, 255, 255))
        draw.text((stats_x, 105), f"⭐ {xp:,} XP", font=font_small, fill=(0, 255, 255))
        percentage = (progress / needed * 100) if needed > 0 else 100
        draw.text((stats_x, 130), f"📈 {percentage:.1f}%", font=font_small, fill=(0, 255, 255))

    async def add_avatar_and_content_space(self, draw, member, level, rank, messages, xp, progress, needed, width, height, font_large, font_medium, font_small):
        avatar_size, avatar_x, avatar_y = 110, 35, 95
        img = draw._image
        if not self._paste_avatar(draw, img, member, avatar_x, avatar_y, avatar_size):
            draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill=(20, 30, 60))

        info_x = 175
        username = member.display_name[:16]
        draw.text((info_x, 45), username, font=font_large, fill=(255, 255, 255))
        draw.text((info_x, 80), f"🌟 Level {level}", font=font_medium, fill=(255, 215, 0))
        draw.text((info_x, 110), f"🛸 Rank #{rank}", font=font_medium, fill=(100, 200, 255))

        bar_x, bar_y = info_x, 155
        bar_width, bar_height = 490, 22
        draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), radius=11, fill=(10, 10, 30))
        if needed > 0:
            progress_width = int((progress / needed) * bar_width)
            for i in range(progress_width):
                factor = i / progress_width if progress_width > 0 else 0
                draw.line([(bar_x + i, bar_y + 2), (bar_x + i, bar_y + bar_height - 2)], fill=(int(50 + 200 * factor), int(100 + 150 * factor), 255))

        xp_text = f"{progress:,} / {needed:,} XP"
        text_bbox = draw.textbbox((0, 0), xp_text, font=font_small)
        text_x = bar_x + (bar_width - (text_bbox[2] - text_bbox[0])) // 2
        draw.text((text_x, bar_y + 3), xp_text, font=font_small, fill=(255, 255, 255))

        stats_x = 720
        draw.text((stats_x, 85), f"📡 Messages", font=font_small, fill=(200, 200, 255))
        draw.text((stats_x, 105), f"{messages:,}", font=font_medium, fill=(255, 255, 255))
        draw.text((stats_x, 135), "⭐ Total XP", font=font_small, fill=(200, 200, 255))
        draw.text((stats_x, 155), f"{xp:,}", font=font_medium, fill=(255, 215, 0))
        percentage = (progress / needed * 100) if needed > 0 else 100
        draw.text((stats_x, 185), f"🌌 {percentage:.1f}%", font=font_small, fill=(100, 200, 255))

    async def add_avatar_and_content_minimal(self, draw, member, level, rank, messages, xp, progress, needed, width, height, font_large, font_medium, font_small):
        avatar_size, avatar_x, avatar_y = 100, 40, 100
        img = draw._image
        if not self._paste_avatar(draw, img, member, avatar_x, avatar_y, avatar_size):
            draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill=(240, 240, 240))

        info_x = 170
        username = member.display_name[:18]
        draw.text((info_x, 50), username, font=font_large, fill=(50, 50, 50))
        draw.text((info_x, 85), f"Level {level}", font=font_medium, fill=(100, 100, 100))
        draw.text((info_x, 115), f"Rank #{rank}", font=font_medium, fill=(150, 150, 150))

        bar_x, bar_y = info_x, 160
        bar_width, bar_height = 480, 18
        draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), radius=9, fill=(240, 240, 240))
        if needed > 0:
            progress_width = int((progress / needed) * bar_width)
            if progress_width > 0:
                draw.rounded_rectangle((bar_x + 2, bar_y + 2, bar_x + progress_width - 2, bar_y + bar_height - 2), radius=7, fill=(220, 220, 220))

        xp_text = f"{progress:,} / {needed:,} XP"
        text_bbox = draw.textbbox((0, 0), xp_text, font=font_small)
        text_x = bar_x + (bar_width - (text_bbox[2] - text_bbox[0])) // 2
        draw.text((text_x, bar_y + 2), xp_text, font=font_small, fill=(100, 100, 100))

        stats_x = 700
        draw.text((stats_x, 85), f"Messages: {messages:,}", font=font_small, fill=(120, 120, 120))
        draw.text((stats_x, 115), f"Total XP: {xp:,}", font=font_small, fill=(120, 120, 120))
        percentage = (progress / needed * 100) if needed > 0 else 100
        draw.text((stats_x, 145), f"Progress: {percentage:.1f}%", font=font_small, fill=(120, 120, 120))

    async def add_avatar_and_content_gaming(self, draw, member, xp, progress, needed, messages, level, rank, width, height, font_large, font_medium, font_small):
        avatar_size, avatar_x, avatar_y = 110, 35, 95
        img = draw._image
        if not self._paste_avatar(draw, img, member, avatar_x, avatar_y, avatar_size):
            draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill=(30, 30, 30))

        info_x = 175
        username = member.display_name[:16]
        draw.text((info_x, 45), username, font=font_large, fill=(200, 200, 200))
        draw.text((info_x, 80), f"Level {level}", font=font_medium, fill=(150, 150, 150))
        draw.text((info_x, 110), f"Rank #{rank}", font=font_medium, fill=(100, 100, 100))

        bar_x, bar_y = info_x, 155
        bar_width, bar_height = 490, 22
        draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), radius=11, fill=(30, 30, 30))
        if needed > 0:
            progress_width = int((progress / needed) * bar_width)
            for i in range(progress_width):
                factor = i / progress_width if progress_width > 0 else 0
                draw.line([(bar_x + i, bar_y + 2), (bar_x + i, bar_y + bar_height - 2)], fill=(int(50 + 150 * factor), int(100 + 100 * factor), 200))

        xp_text = f"{progress:,} / {needed:,} XP"
        text_bbox = draw.textbbox((0, 0), xp_text, font=font_small)
        text_x = bar_x + (bar_width - (text_bbox[2] - text_bbox[0])) // 2
        draw.text((text_x, bar_y + 3), xp_text, font=font_small, fill=(200, 200, 200))

        stats_x = 720
        draw.text((stats_x, 85), f"Messages: {messages:,}", font=font_small, fill=(150, 150, 150))
        draw.text((stats_x, 115), f"Total XP: {xp:,}", font=font_small, fill=(150, 150, 150))
        percentage = (progress / needed * 100) if needed > 0 else 100
        draw.text((stats_x, 145), f"Progress: {percentage:.1f}%", font=font_small, fill=(150, 150, 150))

    async def add_avatar_and_content_elegant(self, draw, member, xp, progress, needed, messages, level, rank, width, height, font_large, font_medium, font_small):
        avatar_size, avatar_x, avatar_y = 110, 35, 95
        img = draw._image
        if not self._paste_avatar(draw, img, member, avatar_x, avatar_y, avatar_size):
            draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill=(45, 45, 45))

        info_x = 175
        username = member.display_name[:16]
        draw.text((info_x, 45), username, font=font_large, fill=(230, 230, 230))
        draw.text((info_x, 80), f"Level {level}", font=font_medium, fill=(200, 170, 0))
        draw.text((info_x, 110), f"Rank #{rank}", font=font_medium, fill=(180, 180, 180))

        bar_x, bar_y = info_x, 155
        bar_width, bar_height = 490, 22
        draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), radius=11, fill=(40, 40, 40))
        if needed > 0:
            progress_width = int((progress / needed) * bar_width)
            for i in range(progress_width):
                factor = i / progress_width if progress_width > 0 else 0
                draw.line([(bar_x + i, bar_y + 2), (bar_x + i, bar_y + bar_height - 2)], fill=(255, int(150 + 65 * factor), 0))

        xp_text = f"{progress:,} / {needed:,} XP"
        text_bbox = draw.textbbox((0, 0), xp_text, font=font_small)
        text_x = bar_x + (bar_width - (text_bbox[2] - text_bbox[0])) // 2
        draw.text((text_x, bar_y + 3), xp_text, font=font_small, fill=(220, 220, 220))

        stats_x = 720
        draw.text((stats_x, 85), f"Messages: {messages:,}", font=font_small, fill=(180, 180, 180))
        draw.text((stats_x, 115), f"Total XP: {xp:,}", font=font_small, fill=(255, 215, 0))
        percentage = (progress / needed * 100) if needed > 0 else 100
        draw.text((stats_x, 145), f"Progress: {percentage:.1f}%", font=font_small, fill=(200, 200, 200))

    async def add_avatar_and_content_cyberpunk(self, draw, member, xp, progress, needed, messages, level, rank, width, height, font_large, font_medium, font_small):
        avatar_size, avatar_x, avatar_y = 100, 40, 100
        img = draw._image
        if not self._paste_avatar(draw, img, member, avatar_x, avatar_y, avatar_size, circular=False):
            draw.rectangle((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill=(45, 45, 45))

        text_color = (148, 0, 211)
        info_x = 170
        username = member.display_name[:15]
        draw.text((info_x, 50), username, font=font_large, fill=text_color)
        draw.text((info_x, 85), f"Level {level}", font=font_medium, fill=text_color)
        draw.text((info_x, 115), f"Rank #{rank}", font=font_medium, fill=text_color)

        bar_x, bar_y = info_x, 160
        bar_width, bar_height = 480, 20
        draw.rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), fill=(30, 30, 30))
        if needed > 0:
            progress_width = int((progress / needed) * bar_width)
            if progress_width > 0:
                draw.rectangle((bar_x, bar_y, bar_x + progress_width, bar_y + bar_height), fill=text_color)

        xp_text = f"{progress:,} / {needed:,} XP"
        text_bbox = draw.textbbox((0, 0), xp_text, font=font_small)
        text_x = bar_x + (bar_width - (text_bbox[2] - text_bbox[0])) // 2
        draw.text((text_x, bar_y + 2), xp_text, font=font_small, fill=(220, 220, 220))

        stats_x = 700
        draw.text((stats_x, 85), f"Messages: {messages:,}", font=font_small, fill=text_color)
        draw.text((stats_x, 115), f"Total XP: {xp:,}", font=font_small, fill=text_color)
        percentage = (progress / needed * 100) if needed > 0 else 100
        draw.text((stats_x, 145), f"Progress: {percentage:.1f}%", font=font_small, fill=text_color)

    @level.command(name="rank", description="View your current rank and level")
    async def rank(self, ctx, member: Optional[discord.Member] = None):
        member = member or ctx.author
        guild_id = ctx.guild.id

        try:
            rank_card = await self.create_rank_card(member, guild_id)
            if rank_card:
                if isinstance(rank_card, str):
                    await ctx.send(rank_card)
                else:
                    file = discord.File(fp=rank_card, filename="rank_card.png")
                    await ctx.send(file=file)
                    try:
                        rank_card.close()
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error in rank command: {e}")

    @level.command(name="settings", description="Configure leveling settings", aliases=["config"])
    @commands.has_permissions(administrator=True)
    async def settings(self, ctx):
        try:
            current_settings = await self.get_guild_settings(ctx.guild.id)
            if hasattr(ctx, "interaction") and ctx.interaction:
                modal = LevelConfigModal(self, current_settings)
                await ctx.interaction.response.send_modal(modal)
            else:
                await self.interactive_setup(ctx, current_settings)
        except Exception as e:
            logger.error(f"Error in settings command: {e}")

    async def interactive_setup(self, ctx, current_settings):
        try:
            embed = discord.Embed(
                title="🔧 Interactive Leveling Setup",
                description=(
                    "Let's configure your leveling system!\n"
                    "Type `cancel` at any time to stop, or `skip` to keep current value.\n\n"
                    "**Current Settings:**"
                ),
                color=0x5865F2,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(
                name="Current Configuration",
                value=(
                    f"🔧 Status: {'🍀 Enabled' if current_settings.get('enabled', False) else '🃏 Disabled'}\n"
                    f"💎 XP per Message: {current_settings.get('xp_per_message', 20)}\n"
                    f"🎨 Embed Color: {current_settings.get('embed_color', '#000000')}\n"
                    f"🖼️ Thumbnail: {'🍀 Yes' if current_settings.get('thumbnail_enabled', True) else '🃏 No'}\n"
                    f"📢 Level Channel: {'Set' if current_settings.get('channel_id') else 'Not set'}"
                ),
                inline=False,
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            await ctx.send(
                f"💎 **How much XP should users get per message?** (1-999)\nCurrent: `{current_settings.get('xp_per_message', 20)}`"
            )
            try:
                xp_msg = await self.bot.wait_for("message", check=check, timeout=60)
                if xp_msg.content.lower() == "cancel":
                    await ctx.send("🃏 Setup cancelled.")
                    return
                if xp_msg.content.lower() == "skip":
                    xp_per_message = current_settings.get("xp_per_message", 20)
                else:
                    xp_per_message = int(xp_msg.content)
                    if xp_per_message < 1 or xp_per_message > 999:
                        await ctx.send("🃏 XP must be between 1 and 999. Using current value.")
                        xp_per_message = current_settings.get("xp_per_message", 20)
            except (ValueError, asyncio.TimeoutError):
                await ctx.send("⏰ Timeout or invalid input. Using current value.")
                xp_per_message = current_settings.get("xp_per_message", 20)

            current_msg = current_settings.get("level_message", "Congratulations {user}! You have reached level {level}!")
            await ctx.send(
                f"💬 **What should the level-up message say?**\n"
                f"Placeholders: `{{user}}`, `{{username}}`, `{{level}}`, `{{server}}`\n"
                f"Current: `{current_msg[:100]}{'...' if len(current_msg) > 100 else ''}`"
            )
            try:
                msg_response = await self.bot.wait_for("message", check=check, timeout=120)
                if msg_response.content.lower() == "cancel":
                    await ctx.send("🃏 Setup cancelled.")
                    return
                level_message = current_msg if msg_response.content.lower() == "skip" else msg_response.content
            except asyncio.TimeoutError:
                await ctx.send("⏰ Timeout. Using current value.")
                level_message = current_msg

            current_color = current_settings.get("embed_color", "#000000")
            await ctx.send(f"🎨 **What color should the level-up embeds be?** (hex, e.g. #FF0000)\nCurrent: `{current_color}`")
            try:
                color_msg = await self.bot.wait_for("message", check=check, timeout=60)
                if color_msg.content.lower() == "cancel":
                    await ctx.send("🃏 Setup cancelled.")
                    return
                if color_msg.content.lower() == "skip":
                    embed_color = current_color
                else:
                    color_input = color_msg.content.strip()
                    if not color_input.startswith("#"):
                        color_input = "#" + color_input
                    embed_color = color_input if validate_hex_color(color_input) else current_color
            except asyncio.TimeoutError:
                await ctx.send("⏰ Timeout. Using current value.")
                embed_color = current_color

            current_image = current_settings.get("level_image", "")
            await ctx.send(f"🖼️ **Level-up image URL** (optional)\nCurrent: `{'Set' if current_image else 'None'}`")
            try:
                image_msg = await self.bot.wait_for("message", check=check, timeout=60)
                if image_msg.content.lower() == "cancel":
                    await ctx.send("🃏 Setup cancelled.")
                    return
                level_image = current_image if image_msg.content.lower() == "skip" else (
                    image_msg.content.strip() if image_msg.content.strip() != "none" else None
                )
            except asyncio.TimeoutError:
                await ctx.send("⏰ Timeout. Using current value.")
                level_image = current_image

            current_thumb = current_settings.get("thumbnail_enabled", True)
            await ctx.send(f"🖼️ **Show user avatar thumbnail?** (yes/no)\nCurrent: `{'Yes' if current_thumb else 'No'}`")
            try:
                thumb_msg = await self.bot.wait_for("message", check=check, timeout=60)
                if thumb_msg.content.lower() == "cancel":
                    await ctx.send("🃏 Setup cancelled.")
                    return
                thumbnail_enabled = current_thumb if thumb_msg.content.lower() == "skip" else (
                    thumb_msg.content.lower() in ["yes", "y", "true", "1", "on", "enable"]
                )
            except asyncio.TimeoutError:
                await ctx.send("⏰ Timeout. Using current value.")
                thumbnail_enabled = current_thumb

            embed_color_int = hex_to_int(embed_color)
            level_image_final = level_image if level_image and level_image.strip() else None

            async with aiosqlite.connect("db/leveling.db") as db:
                async with db.execute(
                    "SELECT guild_id FROM leveling_settings WHERE guild_id = ?", (ctx.guild.id,)
                ) as cursor:
                    exists = await cursor.fetchone()

                if exists:
                    await db.execute(
                        """
                        UPDATE leveling_settings
                        SET enabled = 1, xp_per_message = ?, level_message = ?, embed_color = ?,
                            level_image = ?, thumbnail_enabled = ?
                        WHERE guild_id = ?
                        """,
                        (xp_per_message, level_message, embed_color_int, level_image_final, 1 if thumbnail_enabled else 0, ctx.guild.id),
                    )
                else:
                    await db.execute(
                        """
                        INSERT INTO leveling_settings
                        (guild_id, enabled, xp_per_message, level_message, embed_color, level_image, thumbnail_enabled,
                         min_xp, max_xp, cooldown_seconds, dm_level_up, channel_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (ctx.guild.id, 1, xp_per_message, level_message, embed_color_int, level_image_final, 1 if thumbnail_enabled else 0, 15, 25, 60, 0, None),
                    )
                await db.commit()

            final_embed = discord.Embed(
                title="🍀 Leveling System Configured!",
                description="Your leveling system has been successfully set up with these settings:",
                color=embed_color_int,
                timestamp=datetime.now(timezone.utc),
            )
            final_embed.add_field(
                name="📊 Configuration Summary",
                value=(
                    f"🔧 **Status:** Enabled\n"
                    f"💎 **XP per Message:** {xp_per_message}\n"
                    f"💬 **Level-up Message:** {level_message[:50]}{'...' if len(level_message) > 50 else ''}\n"
                    f"🎨 **Embed Color:** {embed_color}\n"
                    f"🖼️ **Level-up Image:** {'Set' if level_image_final else 'None'}\n"
                    f"🖼️ **Show Thumbnail:** {'Yes' if thumbnail_enabled else 'No'}"
                ),
                inline=False,
            )
            final_embed.add_field(
                name="🚀 Next Steps",
                value=(
                    "• Use `!level channel #channel` to set announcement channel\n"
                    "• Use `!level rewards add <level> @role` to add level rewards\n"
                    "• Use `!level leaderboard` to view the server leaderboard\n"
                    "• Users will now gain XP from messages!"
                ),
                inline=False,
            )
            final_embed.set_footer(text="Lucky Bot • lucky.gg")
            view = PlaceholdersView()
            await ctx.send(embed=final_embed, view=view)

        except Exception as e:
            logger.error(f"Error in interactive setup: {e}")

    @level.command(name="setxp", description="Set XP amount per message")
    @commands.has_permissions(administrator=True)
    async def setxp(self, ctx, amount: int):
        try:
            if amount < 1 or amount > 999:
                await ctx.send("🃏 XP per message must be between 1 and 999!")
                return

            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT guild_id FROM leveling_settings WHERE guild_id = ?", (ctx.guild.id,)
                ) as cursor:
                    exists = await cursor.fetchone()
                if exists:
                    await db.execute(
                        "UPDATE leveling_settings SET xp_per_message = ? WHERE guild_id = ?",
                        (amount, ctx.guild.id),
                    )
                else:
                    await db.execute(
                        "INSERT INTO leveling_settings (guild_id, xp_per_message) VALUES (?, ?)",
                        (ctx.guild.id, amount),
                    )
                await db.commit()

            embed = discord.Embed(
                title="🍀 XP Amount Updated",
                description=f"XP per message has been set to **{amount} XP**",
                color=0x57F287,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error setting XP amount: {e}")

    @level.command(name="setmessage", description="Set level-up message")
    @commands.has_permissions(administrator=True)
    async def setmessage(self, ctx, *, message: str):
        try:
            if len(message) > 2000:
                await ctx.send("🃏 Level-up message must be less than 2000 characters!")
                return

            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT guild_id FROM leveling_settings WHERE guild_id = ?", (ctx.guild.id,)
                ) as cursor:
                    exists = await cursor.fetchone()
                if exists:
                    await db.execute(
                        "UPDATE leveling_settings SET level_message = ? WHERE guild_id = ?",
                        (message, ctx.guild.id),
                    )
                else:
                    await db.execute(
                        "INSERT INTO leveling_settings (guild_id, level_message) VALUES (?, ?)",
                        (ctx.guild.id, message),
                    )
                await db.commit()

            embed = discord.Embed(
                title="🍀 Level-Up Message Updated",
                description=f"Level-up message has been set to:\n```{message}```",
                color=0x57F287,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error setting level message: {e}")

    @level.command(name="setcolor", description="Set embed color")
    @commands.has_permissions(administrator=True)
    async def setcolor(self, ctx, color: str):
        try:
            if not color.startswith("#"):
                color = "#" + color
            if not validate_hex_color(color):
                await ctx.send("🃏 Invalid hex color format! Use format like #FF0000")
                return
            color_int = hex_to_int(color)

            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT guild_id FROM leveling_settings WHERE guild_id = ?", (ctx.guild.id,)
                ) as cursor:
                    exists = await cursor.fetchone()
                if exists:
                    await db.execute(
                        "UPDATE leveling_settings SET embed_color = ? WHERE guild_id = ?",
                        (color_int, ctx.guild.id),
                    )
                else:
                    await db.execute(
                        "INSERT INTO leveling_settings (guild_id, embed_color) VALUES (?, ?)",
                        (ctx.guild.id, color_int),
                    )
                await db.commit()

            embed = discord.Embed(
                title="🍀 Embed Color Updated",
                description=f"Embed color has been set to **{color}**",
                color=color_int,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error setting embed color: {e}")

    @level.command(name="thumbnail", description="Toggle user thumbnail in level-up messages")
    @commands.has_permissions(administrator=True)
    async def thumbnail(self, ctx, setting: str):
        try:
            setting = setting.lower()
            if setting not in ["on", "off", "true", "false", "yes", "no", "enable", "disable"]:
                await ctx.send("🃏 Use: `on/off`, `true/false`, `yes/no`, or `enable/disable`")
                return
            enabled = setting in ["on", "true", "yes", "enable"]

            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT guild_id FROM leveling_settings WHERE guild_id = ?", (ctx.guild.id,)
                ) as cursor:
                    exists = await cursor.fetchone()
                if exists:
                    await db.execute(
                        "UPDATE leveling_settings SET thumbnail_enabled = ? WHERE guild_id = ?",
                        (1 if enabled else 0, ctx.guild.id),
                    )
                else:
                    await db.execute(
                        "INSERT INTO leveling_settings (guild_id, thumbnail_enabled) VALUES (?, ?)",
                        (ctx.guild.id, 1 if enabled else 0),
                    )
                await db.commit()

            embed = discord.Embed(
                title="🍀 Thumbnail Setting Updated",
                description=f"User thumbnails in level-up messages: **{'Enabled' if enabled else 'Disabled'}**",
                color=0x57F287,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error setting thumbnail: {e}")

    @level.command(name="cooldown", description="Set message cooldown in seconds")
    @commands.has_permissions(administrator=True)
    async def cooldown(self, ctx, seconds: int):
        try:
            if seconds < 0 or seconds > 3600:
                await ctx.send("🃏 Cooldown must be between 0 and 3600 seconds (1 hour)!")
                return

            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT guild_id FROM leveling_settings WHERE guild_id = ?", (ctx.guild.id,)
                ) as cursor:
                    exists = await cursor.fetchone()
                if exists:
                    await db.execute(
                        "UPDATE leveling_settings SET cooldown_seconds = ? WHERE guild_id = ?",
                        (seconds, ctx.guild.id),
                    )
                else:
                    await db.execute(
                        "INSERT INTO leveling_settings (guild_id, cooldown_seconds) VALUES (?, ?)",
                        (ctx.guild.id, seconds),
                    )
                await db.commit()

            embed = discord.Embed(
                title="🍀 Cooldown Updated",
                description=f"Message cooldown has been set to **{seconds} seconds**",
                color=0x57F287,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error setting cooldown: {e}")

    @level.group(name="rewards", invoke_without_command=True, description="Manage level rewards")
    async def rewards(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @rewards.command(name="add", description="Add a level reward")
    @commands.has_permissions(administrator=True)
    async def rewards_add(self, ctx, level: int, role: discord.Role, remove_previous: bool = False):
        try:
            if level <= 0:
                await ctx.send("Level must be greater than 0.")
                return
            async with aiosqlite.connect("db/leveling.db") as db:
                await db.execute(
                    "INSERT OR REPLACE INTO level_rewards (guild_id, level, role_id, remove_previous) VALUES (?, ?, ?, ?)",
                    (ctx.guild.id, level, role.id, int(remove_previous)),
                )
                await db.commit()
            await ctx.send(f"🍀 Added reward {role.mention} for level {level} (Remove Previous: {remove_previous})")
        except Exception as e:
            logger.error(f"Error in rewards add command: {e}")

    @rewards.command(name="remove", description="Remove a level reward")
    @commands.has_permissions(administrator=True)
    async def rewards_remove(self, ctx, level: int):
        try:
            async with aiosqlite.connect("db/leveling.db") as db:
                await db.execute(
                    "DELETE FROM level_rewards WHERE guild_id = ? AND level = ?",
                    (ctx.guild.id, level),
                )
                await db.commit()
            await ctx.send(f"🍀 Removed reward for level {level}")
        except Exception as e:
            logger.error(f"Error in rewards remove command: {e}")

    @rewards.command(name="list", description="List all level rewards")
    @commands.has_permissions(administrator=True)
    async def rewards_list(self, ctx):
        try:
            async with aiosqlite.connect("db/leveling.db") as db:
                async with db.execute(
                    "SELECT level, role_id, remove_previous FROM level_rewards WHERE guild_id = ? ORDER BY level",
                    (ctx.guild.id,),
                ) as cursor:
                    rewards = await cursor.fetchall()

            if not rewards:
                await ctx.send("No level rewards configured.")
                return

            embed = discord.Embed(
                title="Level Rewards",
                color=0x5865F2,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            for level, role_id, remove_previous in rewards:
                role = ctx.guild.get_role(role_id)
                role_name = role.mention if role else "Role not found"
                embed.add_field(
                    name=f"Level {level}",
                    value=f"Role: {role_name} (Remove Previous: {bool(remove_previous)})",
                    inline=False,
                )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in rewards list command: {e}")

    @level.group(name="multiplier", invoke_without_command=True, description="Manage XP multipliers")
    async def multiplier(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @multiplier.command(name="add", description="Add an XP multiplier")
    @commands.has_permissions(administrator=True)
    async def multiplier_add(self, ctx, target_type: str, target: str, multiplier: float):
        try:
            if target_type not in ["role", "channel"]:
                await ctx.send("Invalid target type. Must be 'role' or 'channel'.")
                return
            if multiplier <= 0:
                await ctx.send("Multiplier must be greater than 0.")
                return
            if target_type == "role":
                try:
                    target_id = ctx.guild.get_role(int(target)).id
                except Exception:
                    await ctx.send("Invalid role ID.")
                    return
            else:
                try:
                    target_id = ctx.guild.get_channel(int(target)).id
                except Exception:
                    await ctx.send("Invalid channel ID.")
                    return

            async with aiosqlite.connect("db/leveling.db") as db:
                await db.execute(
                    "INSERT OR REPLACE INTO xp_multipliers (guild_id, target_id, target_type, multiplier) VALUES (?, ?, ?, ?)",
                    (ctx.guild.id, target_id, target_type, multiplier),
                )
                await db.commit()
            await ctx.send(f"🍀 Added {multiplier}x multiplier for {target_type} {target}")
        except Exception as e:
            logger.error(f"Error in multiplier add command: {e}")

    @multiplier.command(name="remove", description="Remove an XP multiplier")
    @commands.has_permissions(administrator=True)
    async def multiplier_remove(self, ctx, target_type: str, target: str):
        try:
            if target_type not in ["role", "channel"]:
                await ctx.send("Invalid target type. Must be 'role' or 'channel'.")
                return
            if target_type == "role":
                try:
                    target_id = ctx.guild.get_role(int(target)).id
                except Exception:
                    await ctx.send("Invalid role ID.")
                    return
            else:
                try:
                    target_id = ctx.guild.get_channel(int(target)).id
                except Exception:
                    await ctx.send("Invalid channel ID.")
                    return

            async with aiosqlite.connect("db/leveling.db") as db:
                await db.execute(
                    "DELETE FROM xp_multipliers WHERE guild_id = ? AND target_id = ? AND target_type = ?",
                    (ctx.guild.id, target_id, target_type),
                )
                await db.commit()
            await ctx.send(f"🍀 Removed multiplier for {target_type} {target}")
        except Exception as e:
            logger.error(f"Error in multiplier remove command: {e}")

    @multiplier.command(name="list", description="List all XP multipliers")
    @commands.has_permissions(administrator=True)
    async def multiplier_list(self, ctx):
        try:
            async with aiosqlite.connect("db/leveling.db") as db:
                async with db.execute(
                    "SELECT target_id, target_type, multiplier FROM xp_multipliers WHERE guild_id = ?",
                    (ctx.guild.id,),
                ) as cursor:
                    multipliers = await cursor.fetchall()

            if not multipliers:
                await ctx.send("No XP multipliers configured.")
                return

            embed = discord.Embed(title="XP Multipliers", color=0x5865F2, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            for target_id, target_type, mult in multipliers:
                if target_type == "role":
                    role = ctx.guild.get_role(target_id)
                    target_name = role.mention if role else "Role not found"
                else:
                    channel = ctx.guild.get_channel(target_id)
                    target_name = channel.mention if channel else "Channel not found"
                embed.add_field(
                    name=f"{target_type.capitalize()}: {target_name}",
                    value=f"Multiplier: {mult}x",
                    inline=False,
                )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in multiplier list command: {e}")

    @level.group(name="blacklist", invoke_without_command=True, description="Manage leveling blacklists")
    async def blacklist(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @blacklist.command(name="add", description="Add to the leveling blacklist")
    @commands.has_permissions(administrator=True)
    async def blacklist_add(self, ctx, target_type: str, target: str):
        try:
            if target_type not in ["role", "channel"]:
                await ctx.send("Invalid target type. Must be 'role' or 'channel'.")
                return
            if target_type == "role":
                try:
                    target_id = ctx.guild.get_role(int(target)).id
                except Exception:
                    await ctx.send("Invalid role ID.")
                    return
            else:
                try:
                    target_id = ctx.guild.get_channel(int(target)).id
                except Exception:
                    await ctx.send("Invalid channel ID.")
                    return

            async with aiosqlite.connect("db/leveling.db") as db:
                await db.execute(
                    "INSERT OR REPLACE INTO leveling_blacklist (guild_id, target_id, target_type) VALUES (?, ?, ?)",
                    (ctx.guild.id, target_id, target_type),
                )
                await db.commit()
            await ctx.send(f"🍀 Added {target_type} {target} to the leveling blacklist.")
        except Exception as e:
            logger.error(f"Error in blacklist add command: {e}")

    @blacklist.command(name="remove", description="Remove from the leveling blacklist")
    @commands.has_permissions(administrator=True)
    async def blacklist_remove(self, ctx, target_type: str, target: str):
        try:
            if target_type not in ["role", "channel"]:
                await ctx.send("Invalid target type. Must be 'role' or 'channel'.")
                return
            if target_type == "role":
                try:
                    target_id = ctx.guild.get_role(int(target)).id
                except Exception:
                    await ctx.send("Invalid role ID.")
                    return
            else:
                try:
                    target_id = ctx.guild.get_channel(int(target)).id
                except Exception:
                    await ctx.send("Invalid channel ID.")
                    return

            async with aiosqlite.connect("db/leveling.db") as db:
                await db.execute(
                    "DELETE FROM leveling_blacklist WHERE guild_id = ? AND target_id = ? AND target_type = ?",
                    (ctx.guild.id, target_id, target_type),
                )
                await db.commit()
            await ctx.send(f"🍀 Removed {target_type} {target} from the leveling blacklist.")
        except Exception as e:
            logger.error(f"Error in blacklist remove command: {e}")

    @blacklist.command(name="list", description="List the leveling blacklist")
    @commands.has_permissions(administrator=True)
    async def blacklist_list(self, ctx):
        try:
            async with aiosqlite.connect("db/leveling.db") as db:
                async with db.execute(
                    "SELECT target_id, target_type FROM leveling_blacklist WHERE guild_id = ?",
                    (ctx.guild.id,),
                ) as cursor:
                    blacklisted = await cursor.fetchall()

            if not blacklisted:
                await ctx.send("The leveling blacklist is empty.")
                return

            embed = discord.Embed(title="Leveling Blacklist", color=0x5865F2, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            for target_id, target_type in blacklisted:
                if target_type == "role":
                    role = ctx.guild.get_role(target_id)
                    target_name = role.mention if role else "Role not found"
                else:
                    channel = ctx.guild.get_channel(target_id)
                    target_name = channel.mention if channel else "Channel not found"
                embed.add_field(name=f"{target_type.capitalize()}: {target_name}", value="", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in blacklist list command: {e}")

    @commands.hybrid_command(name="setlevelrole", description="Set a role for a specific level (admin only)")
    @commands.has_permissions(administrator=True)
    async def set_level_role(self, ctx, level: int, role: discord.Role):
        try:
            if level <= 0:
                await ctx.send("Level must be greater than 0.")
                return
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)",
                    (ctx.guild.id, level, role.id),
                )
                await db.commit()
            await ctx.send(f"🍀 Set role {role.mention} for level {level}.")
        except Exception as e:
            logger.error(f"Error setting level role: {e}")

    @commands.hybrid_command(name="removelevelrole", description="Remove a level role (admin only)")
    @commands.has_permissions(administrator=True)
    async def remove_level_role(self, ctx, level: int):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM level_roles WHERE guild_id = ? AND level = ?",
                    (ctx.guild.id, level),
                )
                await db.commit()
            await ctx.send(f"🍀 Removed role for level {level}.")
        except Exception as e:
            logger.error(f"Error removing level role: {e}")

    @commands.hybrid_command(name="listlevelroles", description="List all level roles (admin only)")
    @commands.has_permissions(administrator=True)
    async def list_level_roles(self, ctx):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT level, role_id FROM level_roles WHERE guild_id = ?", (ctx.guild.id,)
                ) as cursor:
                    roles = await cursor.fetchall()

            if not roles:
                await ctx.send("No level roles set for this server.")
                return

            embed = discord.Embed(title="Level Roles", color=0x5865F2, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            for level, role_id in roles:
                role = ctx.guild.get_role(role_id)
                embed.add_field(name=f"Level {level}", value=f"Role: {role.mention if role else 'Not found'}", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error listing level roles: {e}")

    @commands.hybrid_command(name="resetxp", description="Reset a user's XP (admin only)")
    @commands.has_permissions(administrator=True)
    async def reset_xp(self, ctx, member: discord.Member):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET xp = 0, level = 1 WHERE guild_id = ? AND user_id = ?",
                    (ctx.guild.id, member.id),
                )
                await db.commit()
            await ctx.send(f"🍀 Successfully reset XP for {member.mention}.")
        except Exception as e:
            logger.error(f"Error resetting XP: {e}")

    @commands.hybrid_command(name="setxp", description="Set a user's XP (admin only)")
    @commands.has_permissions(administrator=True)
    async def set_xp(self, ctx, member: discord.Member, xp: int):
        try:
            level = calculate_level_from_xp(xp)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?",
                    (xp, level, ctx.guild.id, member.id),
                )
                await db.commit()
            await ctx.send(f"🍀 Successfully set XP for {member.mention} to {xp:,}.")
        except Exception as e:
            logger.error(f"Error setting XP: {e}")

    @commands.hybrid_command(name="setlevel", description="Set a user's level (admin only)")
    @commands.has_permissions(administrator=True)
    async def set_level(self, ctx, member: discord.Member, level: int):
        try:
            xp = calculate_xp_for_level(level)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?",
                    (xp, level, ctx.guild.id, member.id),
                )
                await db.commit()
            await ctx.send(f"🍀 Successfully set level for {member.mention} to {level:,}.")
        except Exception as e:
            logger.error(f"Error setting level: {e}")

    @level.command(name="leaderboard", description="View the server level leaderboard")
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def level_leaderboard(self, ctx):
        try:
            if isinstance(ctx, discord.Interaction):
                await ctx.response.defer()

            async with aiosqlite.connect("db/leveling.db") as db:
                cursor = await db.execute(
                    "SELECT user_id, xp, messages FROM user_xp WHERE guild_id = ? ORDER BY xp DESC LIMIT 10",
                    (ctx.guild.id,),
                )
                top_users = await cursor.fetchall()

            if not top_users:
                embed = discord.Embed(
                    title="📊 Server Level Leaderboard",
                    description="No users found in the leaderboard yet!",
                    color=0x5865F2,
                )
                embed.set_footer(text="Lucky Bot • lucky.gg")
                await ctx.send(embed=embed)
                return

            leaderboard_image = await self.create_leaderboard_image(ctx.guild, top_users)

            if leaderboard_image:
                if isinstance(leaderboard_image, str):
                    await ctx.send(leaderboard_image)
                else:
                    file = discord.File(fp=leaderboard_image, filename="level_leaderboard.png")
                    await ctx.send(file=file)
                    try:
                        leaderboard_image.close()
                    except Exception:
                        pass
            else:
                await ctx.send("Failed to generate leaderboard.")

        except Exception as e:
            logger.error(f"Error in level leaderboard command: {e}")
            await ctx.send(f"An error occurred: {e}")

    async def create_leaderboard_image(self, guild, top_users):
        try:
            if not PIL_AVAILABLE:
                return self.create_text_leaderboard(guild, top_users)

            width, height = 1920, 1080
            img = Image.new("RGB", (width, height), (15, 15, 25))
            draw_temp = ImageDraw.Draw(img)

            for y in range(height):
                factor = y / height
                r = int(15 + (45 - 15) * factor)
                g = int(15 + (55 - 15) * factor)
                b = int(25 + (85 - 25) * factor)
                draw_temp.line([(0, y), (width, y)], fill=(min(255, max(0, r)), min(255, max(0, g)), min(255, max(0, b))))

            draw = ImageDraw.Draw(img)

            try:
                title_font = ImageFont.truetype(FONT_PATH, 54)
                name_font = ImageFont.truetype(FONT_PATH, 32)
                stats_font = ImageFont.truetype(FONT_PATH, 22)
                rank_font = ImageFont.truetype(FONT_PATH, 40)
                small_font = ImageFont.truetype(FONT_PATH_REGULAR, 19)
            except (OSError, IOError):
                title_font = ImageFont.load_default()
                name_font = ImageFont.load_default()
                stats_font = ImageFont.load_default()
                rank_font = ImageFont.load_default()
                small_font = ImageFont.load_default()

            title = f"🏆 {guild.name} Level Leaderboard"
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (width - title_width) // 2
            title_y = 25

            draw.rounded_rectangle(
                (title_x - 50, title_y, title_x + title_width + 50, title_y + 90),
                radius=25, fill=(0, 0, 0, 160),
            )
            draw.text((title_x, title_y + 20), title, font=title_font, fill=(255, 215, 0))

            start_y = 180
            entry_height = 120
            margin_left = 100
            margin_right = 100

            for i, (user_id, xp, messages) in enumerate(top_users):
                user = guild.get_member(user_id)
                if not user:
                    continue

                y = start_y + (i * entry_height)
                level = calculate_level_from_xp(xp)

                if i == 0:
                    rank_color = (255, 215, 0)
                elif i == 1:
                    rank_color = (192, 192, 192)
                elif i == 2:
                    rank_color = (205, 127, 50)
                else:
                    rank_color = (120, 180, 255)

                draw.rounded_rectangle(
                    (margin_left, y - 15, width - margin_right, y - 15 + entry_height - 10),
                    radius=20, fill=(0, 0, 0, 180),
                )

                rank_text = f"#{i + 1}"
                rank_x = margin_left + 40
                rank_circle_size = 55
                rank_circle_y = y + 20
                draw.ellipse(
                    (rank_x - 5, rank_circle_y, rank_x + rank_circle_size, rank_circle_y + rank_circle_size),
                    outline=rank_color, width=3,
                )
                rank_bbox = draw.textbbox((0, 0), rank_text, font=rank_font)
                rank_text_x = rank_x + (rank_circle_size - (rank_bbox[2] - rank_bbox[0])) // 2 - 5
                rank_text_y = rank_circle_y + (rank_circle_size - (rank_bbox[3] - rank_bbox[1])) // 2
                draw.text((rank_text_x, rank_text_y), rank_text, font=rank_font, fill=rank_color)

                avatar_x = margin_left + 140
                avatar_y = y + 20
                avatar_size = 70

                try:
                    avatar_url = str(user.display_avatar.with_size(512).url)
                    response = requests.get(avatar_url, timeout=10)
                    if response.status_code == 200:
                        avatar_img = Image.open(io.BytesIO(response.content))
                        avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                        mask = Image.new("L", (avatar_size, avatar_size), 0)
                        mask_draw = ImageDraw.Draw(mask)
                        mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                        avatar_img.putalpha(mask)
                        img.paste(avatar_img, (avatar_x, avatar_y), avatar_img)
                except Exception:
                    draw.ellipse((avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size), fill=(40, 40, 50))

                info_x = margin_left + 240
                username = user.display_name[:18]
                draw.text((info_x, y + 15), username, font=name_font, fill=(255, 255, 255))

                level_text = f"Level {level:,}"
                level_badge_x = info_x
                level_badge_y = y + 55
                level_bbox = draw.textbbox((0, 0), level_text, font=stats_font)
                level_width = level_bbox[2] - level_bbox[0]
                draw.rounded_rectangle(
                    (level_badge_x - 8, level_badge_y - 5, level_badge_x + level_width + 16, level_badge_y + 25),
                    radius=12, fill=(*rank_color, 70),
                )
                draw.text((level_badge_x, level_badge_y), level_text, font=stats_font, fill=(255, 255, 255))

                xp_text = f"💎 {format_number(xp)} XP"
                msg_text = f"💬 {format_number(messages or 0)} msgs"
                xp_x = info_x + level_width + 30
                msg_x = xp_x + 140
                draw.text((xp_x, level_badge_y), xp_text, font=stats_font, fill=(200, 220, 255))
                draw.text((msg_x, level_badge_y), msg_text, font=stats_font, fill=(255, 200, 150))

                bar_x = width - margin_right - 380
                bar_y = y + 25
                bar_width_inner = 320
                bar_height = 28
                draw.rounded_rectangle(
                    (bar_x, bar_y, bar_x + bar_width_inner, bar_y + bar_height),
                    radius=14, fill=(20, 20, 30, 200),
                )

                current_level, progress, needed = get_level_progress(xp)
                if needed > 0:
                    progress_width = int((progress / needed) * (bar_width_inner - 6))
                    if progress_width > 0:
                        for px in range(progress_width):
                            factor = px / progress_width if progress_width > 0 else 0
                            brightness = 0.4 + 0.6 * factor
                            draw.line(
                                [(bar_x + 3 + px, bar_y + 3), (bar_x + 3 + px, bar_y + bar_height - 3)],
                                fill=(
                                    min(255, int(rank_color[0] * brightness)),
                                    min(255, int(rank_color[1] * brightness)),
                                    min(255, int(rank_color[2] * brightness)),
                                ),
                            )

                percentage = (progress / needed * 100) if needed > 0 else 100
                progress_text = f"{percentage:.1f}% to Level {level + 1}"
                progress_bbox = draw.textbbox((0, 0), progress_text, font=small_font)
                progress_text_x = bar_x + (bar_width_inner - (progress_bbox[2] - progress_bbox[0])) // 2
                draw.text((progress_text_x, bar_y + bar_height + 8), progress_text, font=small_font, fill=(255, 255, 255))

            footer_y = height - 80
            draw.rounded_rectangle((60, footer_y, width - 60, footer_y + 50), radius=15, fill=(0, 0, 0, 150))
            footer_text = f"✨ Generated • {len(top_users)} Active Members • {guild.name} • Lucky Bot"
            footer_bbox = draw.textbbox((0, 0), footer_text, font=small_font)
            footer_x = (width - (footer_bbox[2] - footer_bbox[0])) // 2
            draw.text((footer_x, footer_y + 15), footer_text, font=small_font, fill=(220, 220, 240))

            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            img.close()
            return img_bytes

        except Exception as e:
            logger.error(f"Error creating leaderboard image: {e}")
            return self.create_text_leaderboard(guild, top_users)

    def create_text_leaderboard(self, guild, top_users):
        try:
            leaderboard_text = f"🏆 **{guild.name} Level Leaderboard** 🏆\n\n"
            for i, (user_id, xp, messages) in enumerate(top_users):
                user = guild.get_member(user_id)
                if not user:
                    continue
                level = calculate_level_from_xp(xp)
                emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"#{i + 1}"
                leaderboard_text += f"{emoji} **{user.display_name}**\n"
                leaderboard_text += f"    Level {level:,} • {format_number(xp)} XP • {format_number(messages or 0)} messages\n\n"
            return leaderboard_text
        except Exception as e:
            logger.error(f"Error creating text leaderboard: {e}")
            return "Failed to generate leaderboard."

    @level.command(name="placeholders", description="Show available placeholders for level-up messages")
    async def placeholders(self, ctx):
        embed = discord.Embed(
            title="📝 Available Placeholders",
            description=(
                "**You can use these placeholders in your level-up message:**\n\n"
                "`{user}` - Mentions the user (@username)\n"
                "`{username}` - User's display name\n"
                "`{level}` - The new level reached\n"
                "`{server}` - Server name\n\n"
                "**Example:**\n"
                "`Congratulations {user}! You've reached level {level} in {server}!`"
            ),
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @level.command(name="enable", description="Enable the leveling system")
    @commands.has_permissions(administrator=True)
    async def enable(self, ctx):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT enabled FROM leveling_settings WHERE guild_id = ?", (ctx.guild.id,)
                ) as cursor:
                    result = await cursor.fetchone()

                if result:
                    if result[0] == 1:
                        await ctx.send("🎴 Leveling system is already enabled!")
                        return
                    await db.execute(
                        "UPDATE leveling_settings SET enabled = 1 WHERE guild_id = ?", (ctx.guild.id,)
                    )
                else:
                    await db.execute(
                        "INSERT INTO leveling_settings (guild_id, enabled) VALUES (?, 1)", (ctx.guild.id,)
                    )
                await db.commit()

            embed = discord.Embed(
                title="🍀 Leveling System Enabled",
                description=(
                    "The leveling system has been successfully enabled for this server!\n\n"
                    "**Next Steps:**\n"
                    "• Use `/level settings` to configure XP rates and messages\n"
                    "• Use `/level channel` to set level-up announcement channel\n"
                    "• Use `/level rewards add` to set up level rewards"
                ),
                color=0x57F287,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error enabling leveling system: {e}")

    @level.command(name="disable", description="Disable the leveling system")
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT enabled FROM leveling_settings WHERE guild_id = ?", (ctx.guild.id,)
                ) as cursor:
                    result = await cursor.fetchone()

                if not result:
                    await ctx.send("🎴 Leveling system is not configured for this server!")
                    return
                if result[0] == 0:
                    await ctx.send("🎴 Leveling system is already disabled!")
                    return

                await db.execute(
                    "UPDATE leveling_settings SET enabled = 0 WHERE guild_id = ?", (ctx.guild.id,)
                )
                await db.commit()

            embed = discord.Embed(
                title="🃏 Leveling System Disabled",
                description=(
                    "The leveling system has been disabled for this server.\n\n"
                    "**What this means:**\n"
                    "• Users will no longer gain XP from messages\n"
                    "• Level-up notifications will stop\n"
                    "• Existing user data is preserved\n"
                    "• Use `/level enable` to re-enable anytime"
                ),
                color=0xFF4444,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error disabling leveling system: {e}")

    @level.command(name="stats", description="View detailed level statistics")
    async def stats(self, ctx, member: Optional[discord.Member] = None):
        member = member or ctx.author
        guild_id = ctx.guild.id

        try:
            xp, level, messages = await self.get_user_data(guild_id, member.id)
            rank = await self.get_user_rank(guild_id, member.id)

            current_level, progress, needed = get_level_progress(xp)
            next_level = level + 1
            percentage = (progress / needed * 100) if needed > 0 else 100

            async with aiosqlite.connect("db/leveling.db") as db:
                async with db.execute(
                    "SELECT COUNT(*) FROM user_xp WHERE guild_id = ? AND xp > 0", (guild_id,)
                ) as cursor:
                    total_members = (await cursor.fetchone())[0]

            avg_xp_per_message = (xp / messages) if messages > 0 else 0
            xp_to_next_level = needed - progress

            embed = discord.Embed(
                title=f"📊 Level Statistics for {member.display_name}",
                color=0x5865F2,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(
                name="🎯 Basic Stats",
                value=(
                    f"**Level:** {level:,}\n"
                    f"**Total XP:** {format_number(xp)}\n"
                    f"**Server Rank:** #{rank:,} / {total_members:,}\n"
                    f"**Messages Sent:** {format_number(messages)}"
                ),
                inline=True,
            )
            embed.add_field(
                name=f"📈 Progress to Level {next_level}",
                value=(
                    f"**Current Progress:** {format_number(progress)} / {format_number(needed)} XP\n"
                    f"**Percentage:** {percentage:.1f}%\n"
                    f"**XP Needed:** {format_number(xp_to_next_level)}\n"
                    f"**Progress Bar:** {get_progress_bar(progress, needed, 15)}"
                ),
                inline=True,
            )
            embed.add_field(
                name="📊 Additional Stats",
                value=(
                    f"**Avg XP/Message:** {avg_xp_per_message:.1f}\n"
                    f"**XP for Level {level}:** {format_number(calculate_xp_for_level(level))}\n"
                    f"**XP for Level {next_level}:** {format_number(calculate_xp_for_level(next_level))}\n"
                    f"**Total Levels Gained:** {level - 1:,}"
                ),
                inline=True,
            )

            percentile = ((total_members - rank + 1) / total_members * 100) if total_members > 0 else 0
            if rank == 1:
                tier, tier_color = "🏆 Champion", 0xFFD700
            elif rank <= 3:
                tier, tier_color = "🥇 Elite", 0xC0C0C0
            elif rank <= 10:
                tier, tier_color = "⭐ Expert", 0xCD7F32
            elif percentile >= 90:
                tier, tier_color = "💎 Advanced", 0x00FFFF
            elif percentile >= 70:
                tier, tier_color = "🔥 Experienced", 0xFF4500
            elif percentile >= 50:
                tier, tier_color = "⚡ Intermediate", 0xFFFF00
            elif percentile >= 25:
                tier, tier_color = "🌟 Beginner", 0x90EE90
            else:
                tier, tier_color = "🌱 Newcomer", 0x98FB98

            embed.add_field(
                name="🏅 Rank Information",
                value=(
                    f"**Tier:** {tier}\n"
                    f"**Percentile:** Top {100 - percentile:.1f}%\n"
                    f"**Users Below:** {total_members - rank:,}\n"
                    f"**Users Above:** {rank - 1:,}"
                ),
                inline=False,
            )
            embed.color = tier_color
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(
                text=f"Requested by {ctx.author.display_name} • Lucky Bot • lucky.gg",
                icon_url=ctx.author.display_avatar.url,
            )

            rank_card = await self.create_rank_card(member, guild_id)
            if rank_card and not isinstance(rank_card, str):
                file = discord.File(fp=rank_card, filename="rank_card.png")
                embed.set_image(url="attachment://rank_card.png")
                await ctx.send(embed=embed, file=file)
                try:
                    rank_card.close()
                except Exception:
                    pass
            else:
                await ctx.send(embed=embed)
                if isinstance(rank_card, str):
                    await ctx.send(f"```{rank_card}```")

        except Exception as e:
            logger.error(f"Error in level stats command: {e}")

    @level.command(name="channel", description="Set the level-up announcement channel")
    @commands.has_permissions(administrator=True)
    async def channel(self, ctx, channel: discord.TextChannel):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT guild_id FROM leveling_settings WHERE guild_id = ?", (ctx.guild.id,)
                ) as cursor:
                    result = await cursor.fetchone()
                if result:
                    await db.execute(
                        "UPDATE leveling_settings SET channel_id = ? WHERE guild_id = ?",
                        (channel.id, ctx.guild.id),
                    )
                else:
                    await db.execute(
                        "INSERT INTO leveling_settings (guild_id, channel_id) VALUES (?, ?)",
                        (ctx.guild.id, channel.id),
                    )
                await db.commit()

            embed = discord.Embed(
                title="📢 Level-Up Channel Set",
                description=(
                    f"Level-up messages will now be sent in {channel.mention}\n\n"
                    "**Note:** Make sure the bot has permission to send messages in this channel!"
                ),
                color=0x5865F2,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error setting level channel: {e}")


async def setup(bot):
    await bot.add_cog(Leveling(bot))

# Lucky Bot — Rewritten
