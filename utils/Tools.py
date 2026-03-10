import json
import sys
import os
import discord
from discord.ext import commands
from core import Context
import aiosqlite
import asyncio


async def setup_db():
    async with aiosqlite.connect("db/prefix.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prefixes (
                guild_id INTEGER PRIMARY KEY,
                prefix TEXT NOT NULL
            )
        """)
        await db.commit()


asyncio.run(setup_db())


async def is_topcheck_enabled(guild_id: int) -> bool:
    async with aiosqlite.connect("db/topcheck.db") as db:
        async with db.execute(
            "SELECT enabled FROM topcheck WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None and row[0] == 1


def read_json(file_path: str) -> dict:
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"guilds": {}}


def write_json(file_path: str, data: dict):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_or_create_guild_config(file_path: str, guild_id: int, default_config: dict) -> dict:
    data = read_json(file_path)
    if "guilds" not in data:
        data["guilds"] = {}
    guild_id_str = str(guild_id)
    if guild_id_str not in data["guilds"]:
        data["guilds"][guild_id_str] = default_config
        write_json(file_path, data)
    return data["guilds"][guild_id_str]


def update_guild_config(file_path: str, guild_id: int, new_data: dict):
    data = read_json(file_path)
    if "guilds" not in data:
        data["guilds"] = {}
    data["guilds"][str(guild_id)] = new_data
    write_json(file_path, data)


def getIgnore(guild_id: int) -> dict:
    default = {
        "channel": [],
        "role": None,
        "user": [],
        "bypassrole": None,
        "bypassuser": [],
        "commands": [],
    }
    return get_or_create_guild_config("ignore.json", guild_id, default)


def updateignore(guild_id: int, data: dict):
    update_guild_config("ignore.json", guild_id, data)


async def getConfig(guild_id: int) -> dict:
    async with aiosqlite.connect("db/prefix.db") as db:
        async with db.execute(
            "SELECT prefix FROM prefixes WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row:
        return {"prefix": row[0]}
    return {"prefix": ">"}


async def updateConfig(guild_id: int, data: dict):
    prefix = data.get("prefix", ">")
    async with aiosqlite.connect("db/prefix.db") as db:
        await db.execute(
            "INSERT OR REPLACE INTO prefixes (guild_id, prefix) VALUES (?, ?)",
            (guild_id, prefix),
        )
        await db.commit()


def is_ignored():
    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.guild:
            return True

        ignore_data = getIgnore(ctx.guild.id)

        if ctx.channel.id in ignore_data.get("channel", []):
            return False

        role_id = ignore_data.get("bypassrole")
        if role_id:
            bypass_role = ctx.guild.get_role(role_id)
            if bypass_role and bypass_role in ctx.author.roles:
                return True

        if ctx.author.id in ignore_data.get("bypassuser", []):
            return True

        if ctx.author.id in ignore_data.get("user", []):
            return False

        role_id = ignore_data.get("role")
        if role_id:
            ignored_role = ctx.guild.get_role(role_id)
            if ignored_role and ignored_role in ctx.author.roles:
                return False

        cmd = ignore_data.get("commands", [])
        if cmd:
            command_name = ctx.command.name.strip().lower()
            aliases = [a.strip().lower() for a in ctx.command.aliases]
            if command_name in cmd or any(a in cmd for a in aliases):
                return False

        return True

    return commands.check(predicate)


def top_check():
    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.guild:
            return True

        if getattr(ctx, "invoked_with", None) in ["help", "h"]:
            return True

        if not await is_topcheck_enabled(ctx.guild.id):
            return True

        if (
            ctx.author != ctx.guild.owner
            and ctx.author.top_role.position <= ctx.guild.me.top_role.position
        ):
            embed = discord.Embed(
                title="🃏 Access Denied",
                description="Your top role must be **higher** than my top role to use this command.",
                color=0xFF4444,
            )
            embed.set_footer(
                text=f'Command "{ctx.command.qualified_name}" — Lucky Bot • lucky.gg',
                icon_url=(
                    ctx.author.avatar.url
                    if ctx.author.avatar
                    else ctx.author.default_avatar.url
                ),
            )
            await ctx.send(embed=embed)
            return False

        return True

    return commands.check(predicate)

# Lucky Bot — Rewritten
