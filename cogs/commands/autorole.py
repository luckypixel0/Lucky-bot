import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import *


DB_PATH = 'db/autorole.db'


class BasicView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need Administrator permission to use this.", ephemeral=True
            )
            return False
        return True


class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.initialize_db())

    async def initialize_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS autorole (
                    guild_id INTEGER,
                    role_id INTEGER,
                    role_type TEXT,
                    PRIMARY KEY (guild_id, role_id)
                )
            ''')
            await db.commit()

    @commands.group(name='autorole', invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def autorole(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    # --- config ---
    @autorole.command(name='config')
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def config(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT role_id, role_type FROM autorole WHERE guild_id = ?", (ctx.guild.id,)
            ) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            embed = discord.Embed(
                description="🃏 No autoroles configured in this server.",
                color=0xFF4444
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        humans, bots, all_roles = [], [], []
        for role_id, role_type in rows:
            role = ctx.guild.get_role(role_id)
            mention = role.mention if role else f"Deleted Role ({role_id})"
            if role_type == 'humans':
                humans.append(mention)
            elif role_type == 'bots':
                bots.append(mention)
            else:
                all_roles.append(mention)

        embed = discord.Embed(title=f"🧩 Autorole Config — {ctx.guild.name}", color=0x5865F2)
        embed.add_field(name="👤 Humans", value=", ".join(humans) or "None", inline=False)
        embed.add_field(name="🤖 Bots", value=", ".join(bots) or "None", inline=False)
        embed.add_field(name="🌐 All Members", value=", ".join(all_roles) or "None", inline=False)
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    # --- reset ---
    @autorole.group(name='reset', invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def reset(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)

    @reset.command(name='humans')
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def reset_humans(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM autorole WHERE guild_id = ? AND role_type = 'humans'", (ctx.guild.id,)
            )
            await db.commit()
        embed = discord.Embed(description="🍀 Human autoroles have been reset.", color=0x57F287)
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @reset.command(name='bots')
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def reset_bots(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM autorole WHERE guild_id = ? AND role_type = 'bots'", (ctx.guild.id,)
            )
            await db.commit()
        embed = discord.Embed(description="🍀 Bot autoroles have been reset.", color=0x57F287)
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @reset.command(name='all')
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def reset_all(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM autorole WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
        embed = discord.Embed(description="🍀 All autoroles have been reset.", color=0x57F287)
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    # --- humans ---
    @autorole.group(name='humans', invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def humans(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)

    @humans.command(name='add')
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def humans_add(self, ctx, role: discord.Role):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM autorole WHERE guild_id = ? AND role_type = 'humans'", (ctx.guild.id,)
            ) as cursor:
                count = (await cursor.fetchone())[0]
            if count >= 5:
                embed = discord.Embed(
                    description="🎴 You can only set up to 5 human autoroles.", color=0xFF4444
                )
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)
            await db.execute(
                "INSERT OR IGNORE INTO autorole (guild_id, role_id, role_type) VALUES (?, ?, 'humans')",
                (ctx.guild.id, role.id)
            )
            await db.commit()
        embed = discord.Embed(
            description=f"🍀 {role.mention} added as a human autorole.", color=0x57F287
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @humans.command(name='remove')
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def humans_remove(self, ctx, role: discord.Role):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM autorole WHERE guild_id = ? AND role_id = ? AND role_type = 'humans'",
                (ctx.guild.id, role.id)
            )
            await db.commit()
        embed = discord.Embed(
            description=f"🍀 {role.mention} removed from human autoroles.", color=0x57F287
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    # --- bots ---
    @autorole.group(name='bots', invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def bots(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)

    @bots.command(name='add')
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bots_add(self, ctx, role: discord.Role):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM autorole WHERE guild_id = ? AND role_type = 'bots'", (ctx.guild.id,)
            ) as cursor:
                count = (await cursor.fetchone())[0]
            if count >= 5:
                embed = discord.Embed(
                    description="🎴 You can only set up to 5 bot autoroles.", color=0xFF4444
                )
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)
            await db.execute(
                "INSERT OR IGNORE INTO autorole (guild_id, role_id, role_type) VALUES (?, ?, 'bots')",
                (ctx.guild.id, role.id)
            )
            await db.commit()
        embed = discord.Embed(
            description=f"🍀 {role.mention} added as a bot autorole.", color=0x57F287
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @bots.command(name='remove')
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bots_remove(self, ctx, role: discord.Role):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM autorole WHERE guild_id = ? AND role_id = ? AND role_type = 'bots'",
                (ctx.guild.id, role.id)
            )
            await db.commit()
        embed = discord.Embed(
            description=f"🍀 {role.mention} removed from bot autoroles.", color=0x57F287
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        role_type = 'bots' if member.bot else 'humans'
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT role_id FROM autorole WHERE guild_id = ? AND (role_type = ? OR role_type = 'all')",
                (member.guild.id, role_type)
            ) as cursor:
                rows = await cursor.fetchall()

        for (role_id,) in rows:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Lucky Bot Autorole")
                except (discord.Forbidden, discord.HTTPException):
                    pass


async def setup(bot):
    await bot.add_cog(AutoRole(bot))

# Lucky Bot — Rewritten
