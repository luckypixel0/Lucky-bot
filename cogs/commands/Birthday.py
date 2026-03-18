import discord
from discord.ext import commands, tasks
import json
import datetime
import asyncio
import os

DB_BIRTHDAYS = "jsondb/birthdays.json"
DB_BIRTHDAY_LOGS = "jsondb/birthday_logs.json"


def read_db(filename: str) -> dict:
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}


def write_db(filename: str, data: dict) -> None:
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)


class Birthdays(commands.Cog):
    """Birthday tracking and notifications."""

    def __init__(self, client: commands.Bot):
        self.client = client
        self.check_birthdays.start()

    def cog_unload(self):
        self.check_birthdays.cancel()

    def _success_embed(self, description: str) -> discord.Embed:
        embed = discord.Embed(description=f"🍀 {description}", color=0x57F287)
        embed.set_footer(text="Lucky Bot • lucky.gg")
        return embed

    def _error_embed(self, description: str) -> discord.Embed:
        embed = discord.Embed(description=f"🃏 {description}", color=0xFF4444)
        embed.set_footer(text="Lucky Bot • lucky.gg")
        return embed

    @commands.command(
        name="birthdaysetup",
        help="Set the birthday announcement channel and role.",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def birthday_setup(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        role: discord.Role,
    ):
        db = read_db(DB_BIRTHDAY_LOGS)
        guild_id = str(ctx.guild.id)
        db.setdefault(guild_id, {})
        db[guild_id]["birthday_channel_id"] = channel.id
        db[guild_id]["birthday_role_id"] = role.id
        write_db(DB_BIRTHDAY_LOGS, db)
        await ctx.send(
            embed=self._success_embed(
                f"Birthday channel set to {channel.mention} and role set to {role.mention}."
            )
        )

    @commands.command(name="setbirthday", help="Set your birthday.")
    @commands.guild_only()
    async def set_birthday(self, ctx: commands.Context):
        def check(msg):
            return msg.author.id == ctx.author.id and msg.channel.id == ctx.channel.id

        await ctx.send("Please enter your birth day **(DD):**")
        try:
            msg = await self.client.wait_for("message", timeout=60.0, check=check)
            day = msg.content.strip().zfill(2)
            if not day.isdigit() or int(day) not in range(1, 32):
                return await ctx.send(embed=self._error_embed("Invalid day. Must be between 01 and 31."))

            await ctx.send("Please enter your birth month **(MM):**")
            msg = await self.client.wait_for("message", timeout=60.0, check=check)
            month = msg.content.strip().zfill(2)
            if not month.isdigit() or int(month) not in range(1, 13):
                return await ctx.send(embed=self._error_embed("Invalid month. Must be between 01 and 12."))

            await ctx.send("Please enter your birth year **(YYYY):**")
            msg = await self.client.wait_for("message", timeout=60.0, check=check)
            year = msg.content.strip()
            if not year.isdigit() or len(year) != 4:
                return await ctx.send(embed=self._error_embed("Invalid year. Please enter a 4-digit year."))

            date = f"{month}-{day}-{year}"
            db = read_db(DB_BIRTHDAYS)
            db[str(ctx.author.id)] = date
            write_db(DB_BIRTHDAYS, db)
            await ctx.send(embed=self._success_embed(f"Your birthday has been set to **{date}**."))

        except asyncio.TimeoutError:
            await ctx.send(embed=self._error_embed("Timed out. Please try again."))

    @commands.command(name="removebirthday", help="Remove your birthday from the bot.")
    @commands.guild_only()
    async def remove_birthday(self, ctx: commands.Context):
        db = read_db(DB_BIRTHDAYS)
        if str(ctx.author.id) in db:
            del db[str(ctx.author.id)]
            write_db(DB_BIRTHDAYS, db)
            await ctx.send(embed=self._success_embed("Your birthday has been removed."))
        else:
            await ctx.send(embed=self._error_embed("You have no birthday set."))

    @commands.command(name="listbirthdays", help="List members with a birthday today.")
    @commands.guild_only()
    async def list_birthdays(self, ctx: commands.Context):
        today = datetime.datetime.now().strftime("%m-%d")
        db = read_db(DB_BIRTHDAYS)
        members = [
            ctx.guild.get_member(int(uid))
            for uid, date in db.items()
            if date.startswith(today)
        ]
        members = [m for m in members if m]

        if members:
            mentions = ", ".join(m.mention for m in members)
            embed = discord.Embed(
                title="🎂 Birthdays Today",
                description=mentions,
                color=0x5865F2,
            )
        else:
            embed = discord.Embed(
                title="🎂 Birthdays Today",
                description="No birthdays today.",
                color=0x2F3136,
            )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @commands.command(name="birthday", help="Check your registered birthday.")
    @commands.guild_only()
    async def check_birthday(self, ctx: commands.Context):
        db = read_db(DB_BIRTHDAYS)
        if str(ctx.author.id) in db:
            date = db[str(ctx.author.id)]
            await ctx.send(embed=self._success_embed(f"Your birthday is set to **{date}**."))
        else:
            await ctx.send(embed=self._error_embed("You haven't set your birthday yet."))

    @tasks.loop(hours=24)
    async def check_birthdays(self):
        today = datetime.datetime.now().strftime("%m-%d")
        db = read_db(DB_BIRTHDAYS)
        guild_settings = read_db(DB_BIRTHDAY_LOGS)

        for user_id, birthday in db.items():
            if not birthday.startswith(today):
                continue
            user = self.client.get_user(int(user_id))
            if not user:
                continue
            for guild_id, settings in guild_settings.items():
                channel_id = settings.get("birthday_channel_id")
                role_id = settings.get("birthday_role_id")
                if not channel_id:
                    continue
                channel = self.client.get_channel(channel_id)
                if not channel:
                    continue
                embed = discord.Embed(
                    title="🎂 Happy Birthday!",
                    description=f"Wishing {user.mention} a wonderful birthday! 🍀🎉",
                    color=0x5865F2,
                )
                embed.set_footer(text="Lucky Bot • lucky.gg")
                await channel.send(embed=embed)
                role = discord.utils.get(channel.guild.roles, id=role_id)
                member = channel.guild.get_member(int(user_id))
                if role and member:
                    try:
                        await member.add_roles(role)
                    except discord.Forbidden:
                        pass
                break

    @check_birthdays.before_loop
    async def before_check_birthdays(self):
        await self.client.wait_until_ready()
        now = datetime.datetime.now()
        midnight = datetime.datetime.combine(now.date(), datetime.time(hour=0))
        if now >= midnight:
            midnight += datetime.timedelta(days=1)
        await asyncio.sleep((midnight - now).total_seconds())


async def setup(client: commands.Bot):
    await client.add_cog(Birthdays(client))

# Lucky Bot — Rewritten
