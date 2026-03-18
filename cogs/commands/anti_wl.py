import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import *


class Whitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.initialize_db())

    async def initialize_db(self):
        self.db = await aiosqlite.connect('db/anti.db')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS whitelisted_users (
                guild_id INTEGER,
                user_id INTEGER,
                ban BOOLEAN DEFAULT FALSE,
                kick BOOLEAN DEFAULT FALSE,
                prune BOOLEAN DEFAULT FALSE,
                botadd BOOLEAN DEFAULT FALSE,
                serverup BOOLEAN DEFAULT FALSE,
                memup BOOLEAN DEFAULT FALSE,
                chcr BOOLEAN DEFAULT FALSE,
                chdl BOOLEAN DEFAULT FALSE,
                chup BOOLEAN DEFAULT FALSE,
                rlcr BOOLEAN DEFAULT FALSE,
                rlup BOOLEAN DEFAULT FALSE,
                rldl BOOLEAN DEFAULT FALSE,
                meneve BOOLEAN DEFAULT FALSE,
                mngweb BOOLEAN DEFAULT FALSE,
                mngstemo BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        await self.db.commit()

    @commands.hybrid_command(name='whitelist', aliases=['wl'],
                             help="Whitelists a user from antinuke for a specific action.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def whitelist(self, ctx, member: discord.Member = None):
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0xFF4444,
                description="🃏 Your Server Doesn't Meet My 30 Member Criteria"
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        prefix = ctx.prefix

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
                    "Looks like your server hasn't enabled Antinuke.\n\n"
                    "Current Status: 🃏\n\n"
                    f"To enable use `{prefix}antinuke enable`**"
                )
            )
            embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        if not member:
            embed = discord.Embed(
                color=0xFF4444,
                title="**Whitelist Commands**",
                description="**Adding a user to the whitelist means no actions will be taken against them if they trigger the Anti-Nuke Module.**"
            )
            embed.add_field(
                name="**Usage**",
                value=f"🔱 `{prefix}whitelist @user/id`\n🔱 `{prefix}wl @user`"
            )
            embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        async with self.db.execute(
            "SELECT * FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id)
        ) as cursor:
            data = await cursor.fetchone()

        if data:
            embed = discord.Embed(
                title="🃏 Error",
                color=0xFF4444,
                description=f"<@{member.id}> is already a whitelisted member. **Unwhitelist** the user and try again."
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        await self.db.execute(
            "INSERT INTO whitelisted_users (guild_id, user_id) VALUES (?, ?)",
            (ctx.guild.id, member.id)
        )
        await self.db.commit()

        options = [
            discord.SelectOption(label="Ban", description="Whitelist with ban permission", value="ban"),
            discord.SelectOption(label="Kick", description="Whitelist with kick permission", value="kick"),
            discord.SelectOption(label="Prune", description="Whitelist with prune permission", value="prune"),
            discord.SelectOption(label="Bot Add", description="Whitelist with bot add permission", value="botadd"),
            discord.SelectOption(label="Server Update", description="Whitelist with server update permission", value="serverup"),
            discord.SelectOption(label="Member Update", description="Whitelist with member update permission", value="memup"),
            discord.SelectOption(label="Channel Create", description="Whitelist with channel create permission", value="chcr"),
            discord.SelectOption(label="Channel Delete", description="Whitelist with channel delete permission", value="chdl"),
            discord.SelectOption(label="Channel Update", description="Whitelist with channel update permission", value="chup"),
            discord.SelectOption(label="Role Create", description="Whitelist with role create permission", value="rlcr"),
            discord.SelectOption(label="Role Update", description="Whitelist with role update permission", value="rlup"),
            discord.SelectOption(label="Role Delete", description="Whitelist with role delete permission", value="rldl"),
            discord.SelectOption(label="Mention Everyone", description="Whitelist with mention everyone permission", value="meneve"),
            discord.SelectOption(label="Manage Webhook", description="Whitelist with manage webhook permission", value="mngweb"),
        ]

        select = discord.ui.Select(
            placeholder="Choose Your Options",
            min_values=1, max_values=len(options),
            options=options, custom_id="wl"
        )
        button = discord.ui.Button(
            label="Add This User To All Categories",
            style=discord.ButtonStyle.primary,
            custom_id="catWl"
        )

        view = discord.ui.View()
        view.add_item(select)
        view.add_item(button)

        fields = {
            'ban': 'Ban', 'kick': 'Kick', 'prune': 'Prune', 'botadd': 'Bot Add',
            'serverup': 'Server Update', 'memup': 'Member Update',
            'chcr': 'Channel Create', 'chdl': 'Channel Delete', 'chup': 'Channel Update',
            'rlcr': 'Role Create', 'rldl': 'Role Delete', 'rlup': 'Role Update',
            'meneve': 'Mention Everyone', 'mngweb': 'Manage Webhooks'
        }

        embed = discord.Embed(
            title=ctx.guild.name,
            color=0x5865F2,
            description="\n".join(f"🔒 : **{name}**" for name in fields.values())
        )
        embed.add_field(name="**Executor**", value=f"<@!{ctx.author.id}>", inline=True)
        embed.add_field(name="**Target**", value=f"<@!{member.id}>", inline=True)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Lucky Bot • lucky.gg")

        msg = await ctx.send(embed=embed, view=view)

        def check(interaction):
            return interaction.user.id == ctx.author.id and interaction.message.id == msg.id

        try:
            interaction = await self.bot.wait_for("interaction", check=check, timeout=60.0)
            if interaction.data["custom_id"] == "catWl":
                await self.db.execute(
                    "UPDATE whitelisted_users SET ban=?,kick=?,prune=?,botadd=?,serverup=?,memup=?,chcr=?,chdl=?,chup=?,rlcr=?,rldl=?,rlup=?,meneve=?,mngweb=?,mngstemo=? WHERE guild_id=? AND user_id=?",
                    (True, True, True, True, True, True, True, True, True, True, True, True, True, True, True,
                     ctx.guild.id, member.id)
                )
                await self.db.commit()

                embed = discord.Embed(
                    title=ctx.guild.name,
                    color=0x57F287,
                    description="\n".join(f"🍀 : **{name}**" for name in fields.values())
                )
                embed.add_field(name="**Executor**", value=f"<@!{ctx.author.id}>", inline=True)
                embed.add_field(name="**Target**", value=f"<@!{member.id}>", inline=True)
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                embed.set_footer(text="Lucky Bot • lucky.gg")
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                enabled_fields = set(interaction.data["values"])
                for value in enabled_fields:
                    await self.db.execute(
                        f"UPDATE whitelisted_users SET {value}=? WHERE guild_id=? AND user_id=?",
                        (True, ctx.guild.id, member.id)
                    )
                await self.db.commit()

                desc = "\n".join(
                    f"{'🍀' if key in enabled_fields else '🔒'} : **{name}**"
                    for key, name in fields.items()
                )
                embed = discord.Embed(title=ctx.guild.name, color=0x5865F2, description=desc)
                embed.add_field(name="**Executor**", value=f"<@!{ctx.author.id}>", inline=True)
                embed.add_field(name="**Target**", value=f"<@!{member.id}>", inline=True)
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                embed.set_footer(text="Lucky Bot • lucky.gg")
                await interaction.response.edit_message(embed=embed, view=None)
        except TimeoutError:
            await msg.edit(view=None)

    @commands.hybrid_command(name='whitelisted', aliases=['wlist'],
                             help="Shows the list of whitelisted users.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def whitelisted(self, ctx):
        if ctx.guild.member_count < 2:
            embed = discord.Embed(color=0xFF4444, description="🃏 Your Server Doesn't Meet My 30 Member Criteria")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        pre = ctx.prefix

        async with self.db.execute(
            "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
            (ctx.guild.id, ctx.author.id)
        ) as cursor:
            check = await cursor.fetchone()

        async with self.db.execute("SELECT status FROM antinuke WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
            antinuke = await cursor.fetchone()

        is_owner = ctx.author.id == ctx.guild.owner_id
        if not is_owner and not check:
            embed = discord.Embed(title="🃏 Access Denied", color=0xFF4444,
                                  description="Only Server Owner or Extra Owner can Run this Command!")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        if not antinuke or not antinuke[0]:
            embed = discord.Embed(
                color=0xFF4444,
                description=(
                    f"**{ctx.guild.name} security settings\n"
                    "Looks like your server doesn't have security enabled.\n\n"
                    f"Current Status: 🃏\n\nTo enable use `{pre}antinuke enable`**"
                )
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        async with self.db.execute(
            "SELECT user_id FROM whitelisted_users WHERE guild_id = ?", (ctx.guild.id,)
        ) as cursor:
            data = await cursor.fetchall()

        if not data:
            embed = discord.Embed(title="🃏 Error", color=0xFF4444, description="No whitelisted users found.")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        whitelisted_users = [self.bot.get_user(uid[0]) for uid in data]
        whitelisted_str = ", ".join(f"<@!{u.id}>" for u in whitelisted_users if u)

        embed = discord.Embed(
            color=0x5865F2,
            title=f"Whitelisted Users for {ctx.guild.name}",
            description=whitelisted_str
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="whitelistreset", aliases=['wlreset'],
                             help="Resets the whitelisted users.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def whitelistreset(self, ctx):
        if ctx.guild.member_count < 2:
            embed = discord.Embed(color=0xFF4444, description="🃏 Your Server Doesn't Meet My 30 Member Criteria")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        pre = ctx.prefix

        async with self.db.execute(
            "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
            (ctx.guild.id, ctx.author.id)
        ) as cursor:
            check = await cursor.fetchone()

        async with self.db.execute("SELECT status FROM antinuke WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
            antinuke = await cursor.fetchone()

        is_owner = ctx.author.id == ctx.guild.owner_id
        if not is_owner and not check:
            embed = discord.Embed(title="🃏 Access Denied", color=0xFF4444,
                                  description="Only Server Owner or Extra Owner can Run this Command!")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        if not antinuke or not antinuke[0]:
            embed = discord.Embed(
                color=0xFF4444,
                description=(
                    f"**{ctx.guild.name} Security Settings\n"
                    "Looks like your server doesn't have security enabled.\n\n"
                    f"Current Status: 🃏\n\nTo enable use `{pre}antinuke enable`**"
                )
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        async with self.db.execute(
            "SELECT user_id FROM whitelisted_users WHERE guild_id = ?", (ctx.guild.id,)
        ) as cursor:
            data = await cursor.fetchall()

        if not data:
            embed = discord.Embed(title="🃏 Error", color=0xFF4444, description="No whitelisted users found.")
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)

        await self.db.execute("DELETE FROM whitelisted_users WHERE guild_id = ?", (ctx.guild.id,))
        await self.db.commit()
        embed = discord.Embed(
            title="🍀 Success",
            color=0x57F287,
            description=f"Removed all whitelisted members from {ctx.guild.name}"
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Whitelist(bot))

# Lucky Bot — Rewritten
