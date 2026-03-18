import discord
import aiosqlite
from discord.ext import commands
from utils.Tools import blacklist_check, ignore_check
from collections import defaultdict
import time

DB_MEDIA = "db/media.db"
DB_BLOCK = "db/block.db"
BYPASS_LIMIT = 25
INFRACTION_WINDOW = 5
INFRACTION_THRESHOLD = 5


class Media(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.infractions: dict[int, list[float]] = defaultdict(list)

    async def _init_db(self):
        async with aiosqlite.connect(DB_MEDIA) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS media_channels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS media_bypass (
                    guild_id INTEGER,
                    user_id INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        await self._init_db()

    def _success(self, description: str) -> discord.Embed:
        e = discord.Embed(description=f"🍀 {description}", color=0x57F287)
        e.set_footer(text="Lucky Bot • lucky.gg")
        return e

    def _error(self, description: str) -> discord.Embed:
        e = discord.Embed(description=f"🃏 {description}", color=0xFF4444)
        e.set_footer(text="Lucky Bot • lucky.gg")
        return e

    def _info(self, title: str, description: str) -> discord.Embed:
        e = discord.Embed(title=title, description=description, color=0x2F3136)
        e.set_footer(text="Lucky Bot • lucky.gg")
        return e

    # ── media group ───────────────────────────────────────────────────────────

    @commands.hybrid_group(
        name="media",
        help="Configure the media-only channel. Users in this channel can only send files.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def media(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @media.command(name="setup", aliases=["set", "add"], help="Set a media-only channel.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx: commands.Context, *, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_MEDIA) as db:
            async with db.execute(
                "SELECT channel_id FROM media_channels WHERE guild_id = ?", (ctx.guild.id,)
            ) as cursor:
                if await cursor.fetchone():
                    return await ctx.reply(
                        embed=self._error("A media channel is already set. Remove it before adding a new one."),
                        mention_author=False,
                    )
            await db.execute(
                "INSERT INTO media_channels (guild_id, channel_id) VALUES (?, ?)",
                (ctx.guild.id, channel.id),
            )
            await db.commit()

        embed = self._success(f"Successfully set {channel.mention} as the media-only channel.")
        embed.set_footer(text="Lucky Bot • lucky.gg  |  Ensure I have Manage Messages permission.")
        await ctx.reply(embed=embed, mention_author=False)

    @media.command(name="remove", aliases=["reset", "delete"], help="Remove the media-only channel.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def remove(self, ctx: commands.Context):
        async with aiosqlite.connect(DB_MEDIA) as db:
            async with db.execute(
                "SELECT channel_id FROM media_channels WHERE guild_id = ?", (ctx.guild.id,)
            ) as cursor:
                if not await cursor.fetchone():
                    return await ctx.reply(
                        embed=self._error("No media channel is currently configured."),
                        mention_author=False,
                    )
            await db.execute("DELETE FROM media_channels WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        await ctx.reply(embed=self._success("Media-only channel removed."), mention_author=False)

    @media.command(name="config", aliases=["settings", "show"], help="Show the current media-only channel.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def config(self, ctx: commands.Context):
        async with aiosqlite.connect(DB_MEDIA) as db:
            async with db.execute(
                "SELECT channel_id FROM media_channels WHERE guild_id = ?", (ctx.guild.id,)
            ) as cursor:
                result = await cursor.fetchone()
        if not result:
            return await ctx.reply(
                embed=self._error("No media channel is configured for this server."), mention_author=False
            )
        channel = self.client.get_channel(result[0])
        ch_mention = channel.mention if channel else f"`<#{result[0]}>`"
        await ctx.reply(
            embed=self._info("🎠 Media Channel", f"The configured media-only channel is {ch_mention}."),
            mention_author=False,
        )

    # ── bypass subgroup ───────────────────────────────────────────────────────

    @media.group(
        name="bypass",
        help="Manage users who can bypass the media-only restriction.",
        invoke_without_command=True,
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @bypass.command(name="add", help="Add a user to the bypass list.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_add(self, ctx: commands.Context, user: discord.Member):
        async with aiosqlite.connect(DB_MEDIA) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM media_bypass WHERE guild_id = ?", (ctx.guild.id,)
            ) as cursor:
                count = (await cursor.fetchone())[0]
            if count >= BYPASS_LIMIT:
                return await ctx.reply(
                    embed=self._error(f"The bypass list is full ({BYPASS_LIMIT} users max)."),
                    mention_author=False,
                )
            async with db.execute(
                "SELECT 1 FROM media_bypass WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id)
            ) as cursor:
                if await cursor.fetchone():
                    return await ctx.reply(
                        embed=self._error(f"{user.mention} is already in the bypass list."),
                        mention_author=False,
                    )
            await db.execute(
                "INSERT INTO media_bypass (guild_id, user_id) VALUES (?, ?)", (ctx.guild.id, user.id)
            )
            await db.commit()
        await ctx.reply(
            embed=self._success(f"{user.mention} has been added to the bypass list."), mention_author=False
        )

    @bypass.command(name="remove", help="Remove a user from the bypass list.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_remove(self, ctx: commands.Context, user: discord.Member):
        async with aiosqlite.connect(DB_MEDIA) as db:
            async with db.execute(
                "SELECT 1 FROM media_bypass WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id)
            ) as cursor:
                if not await cursor.fetchone():
                    return await ctx.reply(
                        embed=self._error(f"{user.mention} is not in the bypass list."), mention_author=False
                    )
            await db.execute(
                "DELETE FROM media_bypass WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, user.id)
            )
            await db.commit()
        await ctx.reply(
            embed=self._success(f"{user.mention} has been removed from the bypass list."), mention_author=False
        )

    @bypass.command(name="show", aliases=["list", "view"], help="List all bypassed users.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_show(self, ctx: commands.Context):
        async with aiosqlite.connect(DB_MEDIA) as db:
            async with db.execute(
                "SELECT user_id FROM media_bypass WHERE guild_id = ?", (ctx.guild.id,)
            ) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await ctx.reply(
                embed=self._info("🎠 Bypass List", "No users are currently bypassed."), mention_author=False
            )

        mentions = "\n".join(
            (m.mention if (m := ctx.guild.get_member(uid)) else f"`<@{uid}>`")
            for (uid,) in rows
        )
        await ctx.reply(embed=self._info("🎠 Bypass List", mentions), mention_author=False)

    # ── on_message enforcement ─────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        async with aiosqlite.connect(DB_MEDIA) as db:
            async with db.execute(
                "SELECT channel_id FROM media_channels WHERE guild_id = ?", (message.guild.id,)
            ) as cursor:
                row = await cursor.fetchone()

        if not row or message.channel.id != row[0]:
            return

        async with aiosqlite.connect(DB_BLOCK) as db:
            async with db.execute(
                "SELECT 1 FROM user_blacklist WHERE user_id = ?", (message.author.id,)
            ) as cursor:
                blacklisted = await cursor.fetchone()

        async with aiosqlite.connect(DB_MEDIA) as db:
            async with db.execute(
                "SELECT 1 FROM media_bypass WHERE guild_id = ? AND user_id = ?",
                (message.guild.id, message.author.id),
            ) as cursor:
                bypassed = await cursor.fetchone()

        if blacklisted or bypassed:
            return

        if not message.attachments:
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention} This channel is media-only. Please only send files here.",
                    delete_after=5,
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

            now = time.time()
            self.infractions[message.author.id].append(now)
            self.infractions[message.author.id] = [
                t for t in self.infractions[message.author.id]
                if now - t <= INFRACTION_WINDOW
            ]

            if len(self.infractions[message.author.id]) >= INFRACTION_THRESHOLD:
                async with aiosqlite.connect(DB_BLOCK) as db:
                    await db.execute(
                        "INSERT OR IGNORE INTO user_blacklist (user_id) VALUES (?)", (message.author.id,)
                    )
                    await db.commit()

                embed = discord.Embed(
                    title="🎴 You Have Been Blacklisted",
                    description=(
                        "You have been blacklisted from Lucky Bot due to repeated spamming in a media channel.\n"
                        f"If you believe this is an error, please contact our support server: "
                        f"https://discord.gg/q2DdzFxheA"
                    ),
                    color=0xFF4444,
                )
                embed.set_footer(text="Lucky Bot • lucky.gg")
                await message.channel.send(f"{message.author.mention}", embed=embed)
                del self.infractions[message.author.id]


async def setup(bot):
    await bot.add_cog(Media(bot))

# Lucky Bot — Rewritten
