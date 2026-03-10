import os
import asyncio
import random
import time

import aiohttp
import discord
from discord.ext import commands

from core import Context
from core.Cog import Cog
from core.lucky import Lucky
from utils.Tools import *
from utils.config import *

import jishaku
import cogs

os.environ["JISHAKU_NO_DM_TRACEBACK"] = "False"
os.environ["JISHAKU_HIDE"] = "True"
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_FORCE_PAGINATOR"] = "True"

from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TOKEN")
SERVER_COUNT_CHANNEL_ID = int(os.getenv("SERVER_COUNT_CHANNEL_ID", 0))
USER_COUNT_CHANNEL_ID = int(os.getenv("USER_COUNT_CHANNEL_ID", 0))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))
CMD_LOG_WEBHOOK = os.getenv("CMD_LOG_WEBHOOK", "")

client = Lucky()
tree = client.tree


async def update_stats():
    """Background task to keep server/user stat channels updated."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            servers = len(client.guilds)
            users = sum(g.member_count for g in client.guilds if g.member_count)

            server_ch = client.get_channel(SERVER_COUNT_CHANNEL_ID)
            user_ch = client.get_channel(USER_COUNT_CHANNEL_ID)

            if server_ch:
                await server_ch.edit(name=f"Servers: {servers}")
            if user_ch:
                await user_ch.edit(name=f"Users: {users}")
        except Exception as e:
            print(f"[Lucky] Stats update error: {e}")

        await asyncio.sleep(600)


@client.event
async def on_ready():
    await client.wait_until_ready()

    print("""
    \033[1;32m
 ██╗     ██╗   ██╗ ██████╗██╗  ██╗██╗   ██╗
 ██║     ██║   ██║██╔════╝██║ ██╔╝╚██╗ ██╔╝
 ██║     ██║   ██║██║     █████╔╝  ╚████╔╝
 ██║     ██║   ██║██║     ██╔═██╗   ╚██╔╝
 ███████╗╚██████╔╝╚██████╗██║  ██╗   ██║
 ╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝   ╚═╝
    \033[0m
    """)

    print("🍀 Lucky Bot — Loaded & Online!")
    print(f"   Logged in as : {client.user}")
    print(f"   Guilds       : {len(client.guilds)}")
    print(f"   Users        : {len(client.users)}")

    try:
        synced = await client.tree.sync()
        all_cmds = list(client.commands)
        print(f"   Commands     : {len(all_cmds)} prefix | {len(synced)} slash")
    except Exception as e:
        print(f"[Lucky] Sync error: {e}")

    client.loop.create_task(update_stats())


@client.event
async def on_guild_join(guild: discord.Guild):
    log_channel = client.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(
            description=f"🌸 Lucky has joined **{guild.name}** (`{guild.id}`)",
            color=0x57F287
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await log_channel.send(embed=embed)


@client.event
async def on_command_completion(context: commands.Context) -> None:
    if not CMD_LOG_WEBHOOK:
        return

    full_command_name = context.command.qualified_name
    executed_command = full_command_name.split("\n")[0]

    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(CMD_LOG_WEBHOOK, session=session)
        embed = discord.Embed(color=0x5865F2)
        avatar_url = context.author.display_avatar.url
        embed.set_author(name=f"Command: {executed_command}", icon_url=avatar_url)

        if context.guild:
            embed.add_field(name="User", value=f"{context.author.mention} (`{context.author.id}`)", inline=False)
            embed.add_field(name="Server", value=f"{context.guild.name} (`{context.guild.id}`)", inline=False)
            embed.add_field(name="Channel", value=f"{context.channel.mention} (`{context.channel.id}`)", inline=False)
        else:
            embed.add_field(name="User (DM)", value=f"{context.author.mention} (`{context.author.id}`)", inline=False)

        embed.timestamp = discord.utils.utcnow()
        embed.set_footer(text="Lucky Bot • lucky.gg", icon_url=client.user.display_avatar.url)

        try:
            await webhook.send(embed=embed)
        except Exception as e:
            print(f"[Lucky] Command log webhook error: {e}")


@client.command(name="spotify")
async def spotify_status(ctx: Context, user: discord.Member = None):
    """Shows what a user is currently listening to on Spotify."""
    user = user or ctx.author
    activity = next(
        (a for a in user.activities if isinstance(a, discord.Spotify)), None
    )

    if not activity:
        embed = discord.Embed(
            description=f"🃏 **{user.display_name}** is not listening to Spotify right now.",
            color=0x2F3136
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        return await ctx.send(embed=embed)

    embed = discord.Embed(
        title=f"🎰 {user.display_name}'s Spotify",
        color=0x1DB954
    )
    embed.add_field(name="Track", value=activity.title, inline=False)
    embed.add_field(name="Artist", value=activity.artist, inline=True)
    embed.add_field(name="Album", value=activity.album, inline=True)
    embed.set_footer(text="Lucky Bot • lucky.gg")
    await ctx.send(embed=embed)


@client.command(name="makeinvite", aliases=["createinvite", "makeinv"])
@commands.is_owner()
async def make_invite(ctx: Context, guild_id: int = None):
    """Creates an invite for a guild (owner only)."""
    if guild_id is None:
        return await ctx.send("🃏 Please provide a Guild ID.")

    guild = client.get_guild(guild_id)
    if not guild:
        return await ctx.send("🃏 I am not in that server.")

    channels = ([guild.system_channel] if guild.system_channel else []) + list(guild.text_channels)
    for channel in channels:
        if channel and channel.permissions_for(guild.me).create_instant_invite:
            try:
                invite = await channel.create_invite(max_age=0, max_uses=0, unique=True)
                return await ctx.send(f"🍀 Invite for **{guild.name}**:\n{invite.url}")
            except Exception:
                continue

    await ctx.send(f"🃏 No invite permissions in **{guild.name}**.")


@client.command(name="create_hook", aliases=["makehook"])
@commands.has_permissions(administrator=True)
async def create_hook(ctx: Context, *, name: str = None):
    """Creates a webhook in the current channel."""
    if not name:
        return await ctx.send("🃏 Please provide a name for the webhook.")

    try:
        webhook = await ctx.channel.create_webhook(name=name, reason=f"Requested by {ctx.author}")
        embed = discord.Embed(
            title="🍀 Webhook Created",
            description=f"Webhook **{webhook.name}** has been created.",
            color=0x57F287
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        try:
            await ctx.author.send(
                f"Webhook URL for **{webhook.name}** in **{ctx.channel.name}**:\n||{webhook.url}||",
                embed=embed
            )
            await ctx.send("🍀 Webhook created. URL sent to your DMs.")
        except discord.Forbidden:
            await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("🃏 I don't have permission to create webhooks here.")


@client.command(name="delete_hook", aliases=["delhook"])
@commands.has_permissions(administrator=True)
async def delete_hook(ctx: Context, webhook_url: str = None):
    """Deletes a webhook by its URL."""
    if not webhook_url:
        return await ctx.send("🃏 Please provide the webhook URL.")

    try:
        async with aiohttp.ClientSession() as session:
            webhook = await discord.Webhook.from_url(webhook_url, session=session)
            await webhook.delete(reason=f"Deleted by {ctx.author}")
        await ctx.send("🍀 Webhook deleted successfully.")
    except (discord.NotFound, ValueError):
        await ctx.send("🃏 Webhook not found or URL is invalid.")


@client.command(name="list_hooks", aliases=["hooks"])
@commands.has_permissions(administrator=True)
async def list_hooks(ctx: Context):
    """Lists all webhooks in the current channel."""
    try:
        webhooks = await ctx.channel.webhooks()
        if not webhooks:
            return await ctx.send("🔮 No webhooks found in this channel.")

        embed = discord.Embed(
            title=f"🔮 Webhooks in #{ctx.channel.name}",
            color=0x5865F2
        )
        embed.description = "\n".join(
            [f"**{wh.name}** — `{wh.id}`" for wh in webhooks]
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("🃏 I don't have permission to view webhooks here.")


@client.command()
async def reaction(ctx: Context):
    """Reaction speed test — click the right emoji fast!"""
    emojis = ["🍀", "🃏", "🎴", "🔮", "🎰", "⚜️", "💎", "🌠"]
    correct = random.choice(emojis)
    shuffled = emojis.copy()
    random.shuffle(shuffled)

    embed = discord.Embed(
        title="🎯 Reaction Test",
        description="An emoji will appear soon — click it as fast as you can!",
        color=0x2F3136
    )
    embed.set_footer(text="Lucky Bot • lucky.gg")
    msg = await ctx.send(embed=embed)

    for emoji in shuffled:
        await msg.add_reaction(emoji)

    await asyncio.sleep(random.uniform(2.0, 7.0))

    embed.description = f"**React to: {correct}**"
    await msg.edit(embed=embed)
    start = time.time()

    def check(r, u):
        return r.message.id == msg.id and str(r.emoji) == correct and u == ctx.author

    try:
        _, user = await client.wait_for("reaction_add", timeout=15.0, check=check)
        elapsed = time.time() - start
        embed.description = f"🍀 {user.mention} got **{correct}** in **{elapsed:.2f}s**!"
    except asyncio.TimeoutError:
        embed.description = "⏳ Time's up! You were too slow."

    await msg.edit(embed=embed)


# Keep-alive server (optional for hosting platforms)
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "Lucky Bot • lucky.gg"

def _run_server():
    app.run(host="0.0.0.0", port=19346)

def keep_alive():
    Thread(target=_run_server, daemon=True).start()

keep_alive()


async def main():
    async with client:
        os.system("clear")
        await client.load_extension("jishaku")

        for attempt in range(5):
            try:
                await client.start(TOKEN)
                break
            except discord.HTTPException as e:
                if e.status == 429:
                    wait = min((2 ** attempt) + random.random(), 60)
                    print(f"[Lucky] Rate limited. Retrying in {wait:.2f}s...")
                    await asyncio.sleep(wait)
                else:
                    raise
        else:
            raise RuntimeError("Lucky Bot failed to start after 5 retries.")


if __name__ == "__main__":
    asyncio.run(main())

# Lucky Bot — Rewritten
