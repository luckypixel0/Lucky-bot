import discord
from discord.ext import commands


class Lock(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF4444

    @commands.hybrid_command(
        name="lock",
        description="Locks a channel to prevent sending messages.",
        aliases=["lockchannel"]
    )
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock_command(self, ctx: commands.Context, channel: discord.TextChannel = None):
        channel = channel or ctx.channel

        if not channel.permissions_for(ctx.guild.default_role).send_messages:
            embed = discord.Embed(
                description=f"🎴 **{channel.mention} is already locked.**",
                color=self.color
            )
            embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}")
            return await ctx.send(embed=embed)

        await channel.set_permissions(ctx.guild.default_role, send_messages=False)

        embed = discord.Embed(
            title="Lucky Bot | Lockdown",
            description=f"✔ Successfully locked {channel.mention}.",
            color=self.color
        )
        embed.set_footer(text=f"Lucky Bot • lucky.gg | Requested by {ctx.author}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Lock(bot))

# Lucky Bot — Rewritten
