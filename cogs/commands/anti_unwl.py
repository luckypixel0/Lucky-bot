import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import *


class Unwhitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.initialize_db())

    async def initialize_db(self):
        self.db = await aiosqlite.connect('db/anti.db')

    @commands.hybrid_command(name='unwhitelist', aliases=['unwl'],
                             help="Unwhitelist a user from antinuke")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def unwhitelist(self, ctx, member: discord.Member = None):
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0xFF4444,
                description="🃏 Your Server Doesn't Meet My 30 Member Criteria"
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        async with self.db.execute(
            "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
            (ctx.guild.id, ctx.author.id)
        ) as cursor:
            check = await cursor.fetchone()

        async with self.db.execute(
            "SELECT status FROM antinuke WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            antinuke = await cursor.fetchone()

        is_owner = ctx.author.id == ctx.guild.owner_id
        if not is_owner and not check:
            embed = discord.Embed(
                title="🃏 Access Denied",
                color=0xFF4444,
                description="Only Server Owner or Extra Owner can Run this Command!"
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        if not antinuke or not antinuke[0]:
            embed = discord.Embed(
                color=0xFF4444,
                description=(
                    f"**{ctx.guild.name} Security Settings\n"
                    "Looks like your server hasn't enabled security.\n\n"
                    "Current Status: 🃏\n\n"
                    "To enable use `antinuke enable`**"
                )
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        if not member:
            embed = discord.Embed(
                color=0xFF4444,
                title="**Unwhitelist Commands**",
                description="**Removes user from whitelisted users — antinuke will now take action on them if triggered.**"
            )
            embed.add_field(name="**Usage**",
                            value="🔱 `unwhitelist @user/id`\n🔱 `unwl @user`")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        async with self.db.execute(
            "SELECT * FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id)
        ) as cursor:
            data = await cursor.fetchone()

        if not data:
            embed = discord.Embed(
                title="🃏 Error",
                color=0xFF4444,
                description=f"<@{member.id}> is not a whitelisted member."
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        await self.db.execute(
            "DELETE FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id)
        )
        await self.db.commit()

        embed = discord.Embed(
            title="🍀 Success",
            color=0x57F287,
            description=f"User <@!{member.id}> has been removed from the whitelist."
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Unwhitelist(bot))

# Lucky Bot — Rewritten
