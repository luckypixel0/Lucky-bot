import discord
from discord.ext import commands
import json
import os


class JoinDM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.joindm_messages = {}
        self.load_joindm_messages()

    def load_joindm_messages(self):
        try:
            with open('jsondb/joindm_messages.json', 'r') as f:
                self.joindm_messages = json.load(f)
        except FileNotFoundError:
            self.joindm_messages = {}

    def save_joindm_messages(self):
        os.makedirs('jsondb', exist_ok=True)
        with open('jsondb/joindm_messages.json', 'w') as f:
            json.dump(self.joindm_messages, f)

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def joindm(self, ctx):
        guild_id = str(ctx.guild.id)
        if guild_id in self.joindm_messages:
            embed = discord.Embed(
                description=f"🍀 The current join DM message is: `{self.joindm_messages[guild_id]}`",
                color=0x5865F2
            )
        else:
            embed = discord.Embed(
                description="🃏 No custom join DM message has been set for this server.",
                color=0xFF4444
            )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @joindm.command()
    @commands.has_permissions(administrator=True)
    async def message(self, ctx, *, message=None):
        if message is None:
            embed = discord.Embed(description="🃏 Please provide a custom join DM message.", color=0xFF4444)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        else:
            self.joindm_messages[str(ctx.guild.id)] = message
            self.save_joindm_messages()
            embed = discord.Embed(description="🍀 Custom join DM message set successfully.", color=0x57F287)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)

    @joindm.command()
    @commands.has_permissions(administrator=True)
    async def enable(self, ctx):
        self.bot.add_listener(self.on_member_join, 'on_member_join')
        embed = discord.Embed(
            description="🍀 Join DM module enabled. Custom DM will be sent to new members.",
            color=0x57F287
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @joindm.command()
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx):
        self.bot.remove_listener(self.on_member_join)
        embed = discord.Embed(
            description="🍀 Join DM module disabled. Custom DM will not be sent to new members.",
            color=0x5865F2
        )
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @joindm.command()
    async def test(self, ctx):
        guild_id = str(ctx.guild.id)
        if guild_id in self.joindm_messages:
            message = self.joindm_messages[guild_id]
            join_dm_message = f"{message}\n\n``Sent from {ctx.guild.name}``"
            await ctx.author.send(join_dm_message)
            embed = discord.Embed(description="🎲 Test sent to your DM.", color=0x5865F2)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="🃏 No custom join DM message has been set for this server.",
                color=0xFF4444
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)

    async def on_member_join(self, member):
        guild_id = str(member.guild.id)
        if guild_id in self.joindm_messages:
            message = self.joindm_messages[guild_id]
            dm_channel = await member.create_dm()
            join_dm_message = f"{message}\n\n``Sent from {member.guild.name}``"
            await dm_channel.send(join_dm_message)


async def setup(bot):
    await bot.add_cog(JoinDM(bot))

# Lucky Bot — Rewritten
