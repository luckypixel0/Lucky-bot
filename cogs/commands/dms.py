import discord
import os
from discord.ext import commands


class StaffDMCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="dmstaff")
    async def dm_staff(self, ctx, member: discord.Member, *, message: str):
        """Allows authorized staff to DM a user through the bot."""

        owner_ids = [int(x) for x in os.getenv("OWNER_IDS", "").split(",") if x.strip()]
        if ctx.author.id not in owner_ids:
            await ctx.reply("🃏 You do not have permission to use this command.")
            return

        try:
            embed = discord.Embed(
                title="📢 A Message from the Staff Team",
                description=message,
                color=0x5865F2
            )
            embed.set_footer(text=f"Lucky Bot • lucky.gg | Sent by {ctx.author.name}")

            await member.send(embed=embed)
            await ctx.reply(f"🍀 Your message has been successfully sent to **{member.name}**.")

        except discord.Forbidden:
            await ctx.reply(f"🃏 Could not send the message. **{member.name}** may have their DMs disabled.")
        except Exception as e:
            await ctx.reply(f"🎴 Something went wrong. Error: {e}")


async def setup(bot):
    await bot.add_cog(StaffDMCog(bot))

# Lucky Bot — Rewritten
