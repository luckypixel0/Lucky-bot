import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context
import aiosqlite
import asyncio
from utils.Tools import *
from typing import List, Tuple

DATABASE_PATH = 'db/customrole.db'

class Customrole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldown = {}
        self.rate_limit = {}
        self.rate_limit_timeout = 5
        self.bot.loop.create_task(self.create_tables())

    async def reset_rate_limit(self, user_id):
        await asyncio.sleep(self.rate_limit_timeout)
        self.rate_limit.pop(user_id, None)

    async def add_role(self, *, role_id: int, member: discord.Member):
        if member.guild.me.guild_permissions.manage_roles:
            await member.add_roles(discord.Object(id=role_id), reason="Lucky Bot Customrole | Role Added")
        else:
            raise discord.Forbidden("Bot does not have permission to manage roles.")

    async def remove_role(self, *, role_id: int, member: discord.Member):
        if member.guild.me.guild_permissions.manage_roles:
            await member.remove_roles(discord.Object(id=role_id), reason="Lucky Bot Customrole | Role Removed")
        else:
            raise discord.Forbidden("Bot does not have permission to manage roles.")

    async def add_role2(self, *, role: int, member: discord.Member):
        if member.guild.me.guild_permissions.manage_roles:
            await member.add_roles(discord.Object(id=int(role)), reason="Lucky Bot Customrole | Role Added")

    async def remove_role2(self, *, role: int, member: discord.Member):
        if member.guild.me.guild_permissions.manage_roles:
            await member.remove_roles(discord.Object(id=int(role)), reason="Lucky Bot Customrole | Role Removed")

    async def handle_role_command(self, context: Context, member: discord.Member, role_type: str):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(f"SELECT reqrole, {role_type} FROM roles WHERE guild_id = ?", (context.guild.id,)) as cursor:
                data = await cursor.fetchone()
                if data:
                    reqrole_id, role_id = data
                    reqrole = context.guild.get_role(reqrole_id)
                    role = context.guild.get_role(role_id)
                    if reqrole:
                        if context.author == context.guild.owner or reqrole in context.author.roles:
                            if role:
                                if role not in member.roles:
                                    await self.add_role2(role=role_id, member=member)
                                    embed = discord.Embed(title="🍀 Success", description=f"**Given** <@&{role.id}> To {member.mention}", color=0x57F287)
                                else:
                                    await self.remove_role2(role=role_id, member=member)
                                    embed = discord.Embed(title="🍀 Success", description=f"**Removed** <@&{role.id}> From {member.mention}", color=0x57F287)
                                embed.set_footer(text="Lucky Bot • lucky.gg")
                                await context.reply(embed=embed)
                            else:
                                embed = discord.Embed(title="🃏 Error", description=f"{role_type.capitalize()} role is not set up in {context.guild.name}", color=0xFF4444)
                                embed.set_footer(text="Lucky Bot • lucky.gg")
                                await context.reply(embed=embed)
                        else:
                            embed = discord.Embed(title="🎴 Access Denied", description=f"You need {reqrole.mention} to run this command.", color=0xFF4444)
                            embed.set_footer(text="Lucky Bot • lucky.gg")
                            await context.reply(embed=embed)
                    else:
                        embed = discord.Embed(title="🎴 Access Denied", description=f"Required role is not set up in {context.guild.name}", color=0xFF4444)
                        embed.set_footer(text="Lucky Bot • lucky.gg")
                        await context.reply(embed=embed)
                else:
                    embed = discord.Embed(title="🃏 Error", description=f"Roles configuration is not set up in {context.guild.name}", color=0xFF4444)
                    embed.set_footer(text="Lucky Bot • lucky.gg")
                    await context.reply(embed=embed)

    async def create_tables(self):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS roles (
                    guild_id INTEGER PRIMARY KEY,
                    staff INTEGER, girl INTEGER, vip INTEGER,
                    guest INTEGER, frnd INTEGER, reqrole INTEGER
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS custom_roles (
                    guild_id INTEGER, name TEXT, role_id INTEGER,
                    PRIMARY KEY (guild_id, name)
                )
            ''')
            await db.commit()

    @commands.hybrid_group(name="setup", description="Setups custom roles for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def set(self, context: Context):
        if context.subcommand_passed is None:
            await context.send_help(context.command)
            context.command.reset_cooldown(context)

    async def fetch_role_data(self, guild_id):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT staff, girl, vip, guest, frnd, reqrole FROM roles WHERE guild_id = ?", (guild_id,)) as cursor:
                return await cursor.fetchone()

    async def update_role_data(self, guild_id, column, value):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(f"INSERT OR REPLACE INTO roles (guild_id, {column}) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET {column} = ?", (guild_id, value, value))
                await db.commit()
        except Exception as e:
            pass

    async def fetch_custom_role_data(self, guild_id):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT name, role_id FROM custom_roles WHERE guild_id = ?", (guild_id,)) as cursor:
                return await cursor.fetchall()

    def _auth(self, context):
        return context.author == context.guild.owner or context.author.top_role.position > context.guild.me.top_role.position

    def _denied(self):
        e = discord.Embed(title="🎴 Access Denied", description="Your role should be above my top role.", color=0xFF4444)
        e.set_footer(text="Lucky Bot • lucky.gg")
        return e

    @set.command(name="staff", description="Setup staff role in guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to be added")
    async def staff(self, context: Context, role: discord.Role):
        if not self._auth(context): return await context.reply(embed=self._denied())
        await self.update_role_data(context.guild.id, 'staff', role.id)
        e = discord.Embed(title="🍀 Success", description=f"Added {role.mention} to `Staff` Role\n\nUse `staff <user>` to assign/remove.", color=0x57F287)
        e.set_footer(text="Lucky Bot • lucky.gg")
        await context.reply(embed=e)

    @set.command(name="girl", description="Setup girl role in the Guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to be added")
    async def girl(self, context: Context, role: discord.Role):
        if not self._auth(context): return await context.reply(embed=self._denied())
        await self.update_role_data(context.guild.id, 'girl', role.id)
        e = discord.Embed(title="🍀 Success", description=f"Added {role.mention} to `Girl` Role", color=0x57F287)
        e.set_footer(text="Lucky Bot • lucky.gg")
        await context.reply(embed=e)

    @set.command(name="vip", description="Setups vip role in the Guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to be added")
    async def vip(self, context: Context, role: discord.Role):
        if not self._auth(context): return await context.reply(embed=self._denied())
        await self.update_role_data(context.guild.id, 'vip', role.id)
        e = discord.Embed(description=f"Added {role.mention} to `VIP` Role", color=0x57F287)
        e.set_footer(text="Lucky Bot • lucky.gg")
        await context.reply(embed=e)

    @set.command(name="guest", description="Setup guest role in the Guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to be added")
    async def guest(self, context: Context, role: discord.Role):
        if not self._auth(context): return await context.reply(embed=self._denied())
        await self.update_role_data(context.guild.id, 'guest', role.id)
        e = discord.Embed(description=f"Added {role.mention} to `Guest` Role", color=0x57F287)
        e.set_footer(text="Lucky Bot • lucky.gg")
        await context.reply(embed=e)

    @set.command(name="friend", description="Setup friend role in the Guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to be added")
    async def friend(self, context: Context, role: discord.Role):
        if not self._auth(context): return await context.reply(embed=self._denied())
        await self.update_role_data(context.guild.id, 'frnd', role.id)
        e = discord.Embed(description=f"Added {role.mention} to `Friend` Role", color=0x57F287)
        e.set_footer(text="Lucky Bot • lucky.gg")
        await context.reply(embed=e)

    @set.command(name="reqrole", description="Setup required role for custom role commands")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to be added")
    async def req_role(self, context: Context, role: discord.Role):
        if not self._auth(context): return await context.reply(embed=self._denied())
        await self.update_role_data(context.guild.id, 'reqrole', role.id)
        e = discord.Embed(title="🍀 Success", description=f"Added {role.mention} as required role for custom role commands.", color=0x57F287)
        e.set_footer(text="Lucky Bot • lucky.gg")
        await context.reply(embed=e)

    @set.command(name="config", description="Shows the current custom role configuration.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def config(self, context: Context):
        role_data = await self.fetch_role_data(context.guild.id)
        if role_data:
            embed = discord.Embed(title="Custom Role Configuration", color=0x2F3136)
            embed.add_field(name="Staff Role", value=context.guild.get_role(role_data[0]).mention if role_data[0] else "None", inline=False)
            embed.add_field(name="Girl Role", value=context.guild.get_role(role_data[1]).mention if role_data[1] else "None", inline=False)
            embed.add_field(name="VIP Role", value=context.guild.get_role(role_data[2]).mention if role_data[2] else "None", inline=False)
            embed.add_field(name="Guest Role", value=context.guild.get_role(role_data[3]).mention if role_data[3] else "None", inline=False)
            embed.add_field(name="Friend Role", value=context.guild.get_role(role_data[4]).mention if role_data[4] else "None", inline=False)
            embed.add_field(name="Required Role", value=context.guild.get_role(role_data[5]).mention if role_data[5] else "None", inline=False)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await context.reply(embed=embed)
        else:
            e = discord.Embed(title="🃏 Error", description="No custom role configuration found.", color=0xFF4444)
            e.set_footer(text="Lucky Bot • lucky.gg")
            await context.reply(embed=e)

    @set.command(name="create", description="Creates a custom role command.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(name="Command name", role="Role to be assigned")
    async def create(self, context: Context, name: str, role: discord.Role):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM custom_roles WHERE guild_id = ?", (context.guild.id,)) as cursor:
                count = await cursor.fetchone()
                if count[0] >= 56:
                    e = discord.Embed(title="🎴 Access Denied", description="Maximum limit of 56 custom role commands reached.", color=0xFF4444)
                    e.set_footer(text="Lucky Bot • lucky.gg")
                    return await context.reply(embed=e)
            async with db.execute("SELECT name FROM custom_roles WHERE guild_id = ?", (context.guild.id,)) as cursor:
                existing = await cursor.fetchall()
                if any(name == row[0] for row in existing):
                    e = discord.Embed(title="🃏 Error", description=f"A custom role command `{name}` already exists.", color=0xFF4444)
                    e.set_footer(text="Lucky Bot • lucky.gg")
                    return await context.reply(embed=e)
            await db.execute("INSERT INTO custom_roles (guild_id, name, role_id) VALUES (?, ?, ?)", (context.guild.id, name, role.id))
            await db.commit()
        e = discord.Embed(title="🍀 Success", description=f"Custom role command `{name}` created for {role.mention}.\nUse `{name} <user>` to assign/remove.", color=0x57F287)
        e.set_footer(text="Lucky Bot • lucky.gg")
        await context.reply(embed=e)

    @set.command(name="delete", aliases=["remove"], description="Deletes a custom role command.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(name="Command name to be deleted")
    async def delete(self, context: Context, name: str):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT name FROM custom_roles WHERE guild_id = ? AND name = ?", (context.guild.id, name)) as cursor:
                existing = await cursor.fetchone()
        if not existing:
            e = discord.Embed(title="🃏 Error", description=f"No custom role command `{name}` found.", color=0xFF4444)
            e.set_footer(text="Lucky Bot • lucky.gg")
            return await context.reply(embed=e)
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("DELETE FROM custom_roles WHERE guild_id = ? AND name = ?", (context.guild.id, name))
            await db.commit()
        e = discord.Embed(title="🍀 Success", description=f"Custom role command `{name}` deleted.", color=0x57F287)
        e.set_footer(text="Lucky Bot • lucky.gg")
        await context.reply(embed=e)

    @set.command(name="list", description="List all the custom roles setup for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def list(self, context: Context):
        custom_roles = await self.fetch_custom_role_data(context.guild.id)
        if not custom_roles:
            e = discord.Embed(title="🃏 Error", description="No custom roles have been created for this server.", color=0xFF4444)
            e.set_footer(text="Lucky Bot • lucky.gg")
            return await context.reply(embed=e)
        def chunk_list(data, chunk_size):
            for i in range(0, len(data), chunk_size):
                yield data[i:i + chunk_size]
        chunks = list(chunk_list(custom_roles, 7))
        for i, chunk in enumerate(chunks):
            embed = discord.Embed(title="Custom Roles", color=0x2F3136)
            for name, role_id in chunk:
                role = context.guild.get_role(role_id)
                if role:
                    embed.add_field(name=f"Name: {name}", value=f"Role: {role.mention}", inline=False)
            embed.set_footer(text=f"Page {i+1}/{len(chunks)} • Lucky Bot • lucky.gg")
            await context.reply(embed=embed)

    @set.command(name="reset", description="Resets custom role configuration.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def reset(self, context: Context):
        if not self._auth(context): return await context.reply(embed=self._denied())
        removed_roles = []
        role_data = await self.fetch_role_data(context.guild.id)
        if role_data:
            roles_names = ["staff", "girl", "vip", "guest", "frnd", "reqrole"]
            for i, role_name in enumerate(roles_names):
                role_id = role_data[i]
                if role_id:
                    role = context.guild.get_role(role_id)
                    if role:
                        removed_roles.append(f"**{role_name.capitalize()}:** {role.mention}")
                    await self.update_role_data(context.guild.id, role_name, None)
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute("DELETE FROM custom_roles WHERE guild_id = ?", (context.guild.id,))
                await db.commit()
            embed = discord.Embed(title="Custom Role Configuration Reset",
                description=("Deleted all custom role commands 🍀\n\n**Removed Roles:**\n" + "\n".join(removed_roles)) if removed_roles else "No roles were previously set.",
                color=0x57F287)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await context.reply(embed=embed)
        else:
            e = discord.Embed(description="No configuration found for this server.", color=0x2F3136)
            e.set_footer(text="Lucky Bot • lucky.gg")
            await context.reply(embed=e)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return
        prefixes = await self.bot.get_prefix(message)
        if not prefixes:
            return
        if not any(message.content.startswith(prefix) for prefix in prefixes):
            return
        for prefix in prefixes:
            if message.content.startswith(prefix):
                command_name = message.content[len(prefix):].split()[0]
                break
        else:
            return
        guild_id = message.guild.id
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT role_id FROM custom_roles WHERE guild_id = ? AND name = ?", (guild_id, command_name)) as cursor:
                result = await cursor.fetchone()
        if result:
            role_id = result[0]
            role = message.guild.get_role(role_id)
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.execute("SELECT reqrole FROM roles WHERE guild_id = ?", (guild_id,)) as cursor:
                    reqrole_result = await cursor.fetchone()
            reqrole_id = reqrole_result[0] if reqrole_result else None
            reqrole = message.guild.get_role(reqrole_id) if reqrole_id else None
            if reqrole is None:
                await message.channel.send("🎴 The required role is not set up. Please use `setup reqrole`.")
                return
            if reqrole not in message.author.roles:
                await message.channel.send(embed=discord.Embed(description=f"🎴 You need the {reqrole.mention} role to use this command.", color=0xFF4444))
                return
            member = message.mentions[0] if message.mentions else None
            if not member:
                await message.channel.send("Please mention a user to assign the role.")
                return
            now = asyncio.get_event_loop().time()
            if guild_id not in self.cooldown or now - self.cooldown[guild_id] >= 10:
                self.cooldown[guild_id] = now
            else:
                await message.channel.send("You're on a cooldown of 10 seconds.", delete_after=5)
                return
            try:
                if role in member.roles:
                    await self.remove_role(role_id=role_id, member=member)
                    await message.channel.send(embed=discord.Embed(title="🍀 Success", description=f"**Removed** {role.mention} from {member.mention}.", color=0x57F287))
                else:
                    await self.add_role(role_id=role_id, member=member)
                    await message.channel.send(embed=discord.Embed(title="🍀 Success", description=f"**Added** {role.mention} to {member.mention}.", color=0x57F287))
            except discord.Forbidden:
                await message.channel.send("I do not have permission to manage this role.")

    @commands.hybrid_command(name="staff", description="Gives the staff role to the user.", aliases=["official"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _staff(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, 'staff')

    @commands.hybrid_command(name="girl", description="Gives the girl role to the user.", aliases=["qt"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _girl(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, 'girl')

    @commands.hybrid_command(name="vip", description="Gives the VIP role to the user.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _vip(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, 'vip')

    @commands.hybrid_command(name="guest", description="Gives the guest role to the user.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _guest(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, 'guest')

    @commands.hybrid_command(name="friend", description="Gives the friend role to the user.", aliases=["frnd"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _friend(self, context: Context, member: discord.Member):
        await self.handle_role_command(context, member, 'frnd')


async def setup(bot):
    await bot.add_cog(Customrole(bot))

# Lucky Bot — Rewritten
