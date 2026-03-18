import discord
from discord.ext import commands, tasks
from discord import app_commands, ui, File
from mcstatus import JavaServer, BedrockServer
import aiosqlite
import os
import re
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io
import asyncio
import base64

# ── Asset paths ──────────────────────────────────────────────────────────────
ASSETS_DIR = "assets"
FONT_PATH = os.path.join(ASSETS_DIR, "fonts", "minecraft.ttf")
BACKGROUND_PATH = os.path.join(ASSETS_DIR, "background", "background.png")
DB_PATH = "db/minecraft.db"

# ── Layout constants ──────────────────────────────────────────────────────────
REFRESH_COOLDOWN = 30
CANVAS_WIDTH = 800
CANVAS_HEIGHT = 125

# ── Status emojis ─────────────────────────────────────────────────────────────
E_ONLINE = "🟢"
E_OFFLINE = "🔴"
E_PLAYERS = "👥"
E_INFO = "💻"
E_OK = "🍀"
E_ERROR = "🃏"
E_WARN = "🎴"
E_CLOCK = "⏳"
E_REFRESH = "🔄"
E_JAVA = "☕"
E_BEDROCK = "📱"
E_PROXY = "🔌"


class SetupModal(ui.Modal, title="Minecraft Server Setup"):
    server_ip = ui.TextInput(label="Server IP Address", placeholder="e.g., play.hypixel.net", required=True)
    server_port = ui.TextInput(label="Server Port (Optional)", placeholder="Leave blank for defaults", required=False)

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ip = self.server_ip.value.strip()
        port_str = self.server_port.value.strip()
        port = int(port_str) if port_str.isdigit() else None

        detected_type, status, _ = await self.cog.auto_detect_server(ip, port)
        if not detected_type or not status or not status["online"]:
            return await interaction.followup.send(
                f"{E_ERROR} Could not reach the server. Check the IP/Port and try again.", ephemeral=True
            )

        embed, file, view = await self.cog.generate_response(interaction.guild, detected_type, ip, port, interaction.user.id)
        sent = await interaction.channel.send(embed=embed, file=file, view=view)
        await self.cog.save_status_message(
            interaction.guild.id, interaction.user.id, interaction.channel.id,
            sent.id, detected_type, ip, port,
        )
        await interaction.followup.send(f"{E_OK} Auto-updating status for `{ip}` set up!", ephemeral=True)


class MinecraftView(ui.View):
    def __init__(self, bot, server_type, ip, port, user_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.server_type = server_type
        self.ip = ip
        self.port = port
        self.user_id = user_id
        self.last_refresh = None

    @ui.button(label="Refresh", style=discord.ButtonStyle.secondary, custom_id="mc_refresh", emoji=E_REFRESH)
    async def refresh_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(f"{E_ERROR} You can't refresh this panel.", ephemeral=True)
        now = datetime.utcnow()
        if self.last_refresh and (now - self.last_refresh).total_seconds() < REFRESH_COOLDOWN:
            return await interaction.response.send_message(
                f"{E_CLOCK} Cooldown active. Wait `{REFRESH_COOLDOWN}` seconds.", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        cog = self.bot.get_cog("Minecraft")
        embed, file, view = await cog.generate_response(interaction.guild, self.server_type, self.ip, self.port, self.user_id)
        await interaction.message.edit(embed=embed, attachments=[file] if file else [], view=view)
        await interaction.followup.send(f"{E_OK} Status refreshed.", ephemeral=True)
        self.last_refresh = now


class Minecraft(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.bot.loop.create_task(self.init_db())
        self.refresh_all_statuses.start()

    def cog_unload(self):
        self.refresh_all_statuses.cancel()

    async def init_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mc_status_messages (
                    guild_id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    channel_id INTEGER,
                    message_id INTEGER,
                    server_type TEXT,
                    server_ip TEXT,
                    server_port INTEGER
                )
            """)
            await db.commit()

    def clean_motd(self, motd: str) -> str:
        return re.sub(r"§.", "", motd).strip()

    async def auto_detect_server(self, ip: str, port: int = None):
        try:
            java_port = port or 25565
            server = JavaServer(ip, java_port)
            status = await asyncio.wait_for(server.async_status(tries=1), timeout=5)
            version_lower = status.version.name.lower()
            if "velocity" in version_lower:
                stype = "velocity"
            elif "bungee" in version_lower:
                stype = "bungeecord"
            else:
                stype = "java"
            motd_raw = status.description
            if isinstance(motd_raw, dict):
                full_text = "".join(p.get("text", "") for p in motd_raw.get("extra", [])) or motd_raw.get("text", "")
            else:
                full_text = str(motd_raw)
            return stype, {
                "motd": self.clean_motd(full_text) or "A Minecraft Server",
                "players_online": status.players.online,
                "players_max": status.players.max,
                "players_sample": status.players.sample,
                "version": status.version.name,
                "online": True,
            }, getattr(status, "favicon", None)
        except Exception:
            pass

        try:
            bedrock_port = port or 19132
            server = BedrockServer(ip, bedrock_port)
            status = await asyncio.wait_for(server.async_status(tries=1), timeout=5)
            return "bedrock", {
                "motd": self.clean_motd(status.motd) or "A Minecraft Server",
                "players_online": status.players.online,
                "players_max": status.players.max,
                "players_sample": None,
                "version": status.version.name,
                "online": True,
            }, None
        except Exception:
            pass

        return None, {"online": False}, None

    async def create_status_image(self, status_data, ip, port, server_type, server_icon_b64):
        try:
            bg = Image.open(BACKGROUND_PATH).convert("RGBA")
            img = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT))
            for i in range(0, img.width, bg.width):
                for j in range(0, img.height, bg.height):
                    img.paste(bg, (i, j))

            draw = ImageDraw.Draw(img)
            font_lg = ImageFont.truetype(FONT_PATH, 24)
            font_md = ImageFont.truetype(FONT_PATH, 20)
            font_sm = ImageFont.truetype(FONT_PATH, 16)

            if server_icon_b64:
                icon_data = base64.b64decode(server_icon_b64.split(",")[-1])
                icon = Image.open(io.BytesIO(icon_data)).convert("RGBA").resize((80, 80), Image.Resampling.LANCZOS)
                img.paste(icon, (20, (CANVAS_HEIGHT - 80) // 2), icon)

            default_port = 19132 if server_type == "bedrock" else 25565
            full_ip = f"{ip}:{port}" if port and port != default_port else ip

            draw.text((120, 15), f"IP: {full_ip}", font=font_md, fill=(255, 255, 255))
            player_text = f"{status_data.get('players_online', 0)}/{status_data.get('players_max', 0)}"
            bbox = draw.textbbox((0, 0), player_text, font=font_md)
            draw.text((CANVAS_WIDTH - (bbox[2] - bbox[0]) - 20, 15), player_text, font=font_md, fill=(255, 255, 255))

            motd = (status_data.get("motd") or "A Minecraft Server").split("\n")[0]
            bbox = draw.textbbox((0, 0), motd, font=font_lg)
            draw.text(((CANVAS_WIDTH - (bbox[2] - bbox[0])) // 2, 60), motd, font=font_lg, fill=(0, 255, 255))

            watermark = "Lucky Bot • lucky.gg"
            bbox = draw.textbbox((0, 0), watermark, font=font_sm)
            draw.text((CANVAS_WIDTH - (bbox[2] - bbox[0]) - 15, CANVAS_HEIGHT - 25), watermark, font=font_sm, fill=(170, 170, 170))

            buffer = io.BytesIO()
            img.save(buffer, "PNG")
            buffer.seek(0)
            return File(buffer, filename="status.png")
        except Exception:
            return None

    async def generate_response(self, guild, server_type, ip, port, user_id):
        _, status, favicon = await self.auto_detect_server(ip, port)
        if not status:
            status = {"online": False}
        file = await self.create_status_image(status, ip, port, server_type, favicon)
        is_online = status.get("online", False)

        embed = discord.Embed(
            title=f"{E_ONLINE if is_online else E_OFFLINE} Minecraft Server Status",
            color=0x57F287 if is_online else 0xFF4444,
        )

        default_port = 19132 if server_type == "bedrock" else 25565
        full_ip = f"{ip}:{port}" if port and port != default_port else ip
        type_emoji = {
            "java": E_JAVA, "bedrock": E_BEDROCK,
            "velocity": E_PROXY, "bungeecord": E_PROXY,
        }.get(server_type, E_INFO)

        embed.add_field(
            name=f"{E_INFO} Server Info",
            value=(
                f"**IP:** `{full_ip}`\n"
                f"**Type:** {type_emoji} {server_type.capitalize()}\n"
                f"**Version:** `{status.get('version', 'Unknown')}`"
            ),
            inline=False,
        )

        players_online = status.get("players_online", 0)
        players_max = status.get("players_max", 0)
        player_str = f"**Online:** `{players_online}/{players_max}`\n"
        sample = status.get("players_sample")
        if sample:
            names = [p.name for p in sample]
            player_str += "\n".join(f"`{i+1}.` {n}" for i, n in enumerate(names[:10]))
            if len(names) > 10:
                player_str += f"\n*...and {len(names) - 10} more*"
        elif is_online:
            player_str += "*Player list hidden or unavailable.*"

        embed.add_field(name=f"{E_PLAYERS} Players", value=player_str, inline=False)

        if file:
            embed.set_image(url="attachment://status.png")

        embed.set_footer(text="Lucky Bot • lucky.gg")
        embed.timestamp = datetime.utcnow()

        view = MinecraftView(self.bot, server_type, ip, port, user_id)
        return embed, file, view

    async def save_status_message(self, guild_id, user_id, channel_id, message_id, server_type, ip, port):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO mc_status_messages
                    (guild_id, user_id, channel_id, message_id, server_type, server_ip, server_port)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    user_id=excluded.user_id, channel_id=excluded.channel_id,
                    message_id=excluded.message_id, server_type=excluded.server_type,
                    server_ip=excluded.server_ip, server_port=excluded.server_port
            """, (guild_id, user_id, channel_id, message_id, server_type, ip, port))
            await db.commit()

    async def delete_status_message(self, guild_id) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT channel_id, message_id FROM mc_status_messages WHERE guild_id = ?", (guild_id,)
            )
            row = await cursor.fetchone()
            if row:
                try:
                    ch = await self.bot.fetch_channel(row[0])
                    msg = await ch.fetch_message(row[1])
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
                await db.execute("DELETE FROM mc_status_messages WHERE guild_id = ?", (guild_id,))
                await db.commit()
                return True
        return False

    @tasks.loop(minutes=2)
    async def refresh_all_statuses(self):
        await self.bot.wait_until_ready()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT guild_id, user_id, channel_id, message_id, server_type, server_ip, server_port FROM mc_status_messages"
            ) as cursor:
                async for row in cursor:
                    try:
                        guild = self.bot.get_guild(row[0])
                        if not guild:
                            continue
                        channel = guild.get_channel(row[2])
                        if not channel:
                            continue
                        message = await channel.fetch_message(row[3])
                        embed, file, view = await self.generate_response(guild, row[4], row[5], row[6], row[1])
                        await message.edit(embed=embed, attachments=[file] if file else [], view=view)
                        await asyncio.sleep(2)
                    except discord.NotFound:
                        await self.delete_status_message(row[0])
                    except Exception:
                        pass

    # ── Slash commands ────────────────────────────────────────────────────────

    minecraft = app_commands.Group(name="minecraft", description="Minecraft server status commands.")

    @minecraft.command(name="setup", description="Set up an auto-updating Minecraft server status panel.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_slash(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            existing = await (await db.execute(
                "SELECT 1 FROM mc_status_messages WHERE guild_id = ?", (interaction.guild.id,)
            )).fetchone()
            if existing:
                return await interaction.response.send_message(
                    f"{E_WARN} A setup already exists. Use `/minecraft reset` first.", ephemeral=True
                )
        await interaction.response.send_modal(SetupModal(self))

    @minecraft.command(name="reset", description="Remove the Minecraft server status setup.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reset_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        removed = await self.delete_status_message(interaction.guild.id)
        msg = f"{E_OK} Status panel removed." if removed else f"{E_WARN} No setup found for this server."
        await interaction.followup.send(msg, ephemeral=True)

    @minecraft.command(name="status", description="View the current status of the configured server.")
    async def status_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with aiosqlite.connect(DB_PATH) as db:
            row = await (await db.execute(
                "SELECT server_type, server_ip, server_port, user_id FROM mc_status_messages WHERE guild_id = ?",
                (interaction.guild.id,),
            )).fetchone()
        if not row:
            return await interaction.followup.send(
                f"{E_WARN} No server configured. Use `/minecraft setup` first.", ephemeral=True
            )
        embed, file, _ = await self.generate_response(interaction.guild, row[0], row[1], row[2], row[3])
        await interaction.followup.send(embed=embed, file=file)


async def setup(bot: commands.Bot):
    await bot.add_cog(Minecraft(bot))

# Lucky Bot — Rewritten
