import discord
from discord.ext import commands
import random
import asyncio
from utils.Tools import blacklist_check, ignore_check

# Emoji-based slot reels (no image assets required)
SYMBOLS = ["🍀", "🍋", "🔔", "⭐", "🎰", "💎", "🍒", "🃏"]
WEIGHTS = [20, 18, 15, 12, 10, 8, 6, 5]


def spin_reel() -> str:
    return random.choices(SYMBOLS, weights=WEIGHTS, k=1)[0]


class Slots(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["slot"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def slots(self, ctx: commands.Context):
        s1, s2, s3 = spin_reel(), spin_reel(), spin_reel()

        spinning_embed = discord.Embed(
            title="🎰 Slot Machine",
            description="🎲 | 🎲 | 🎲\nSpinning...",
            color=0x2F3136,
        )
        spinning_embed.set_footer(text="Lucky Bot • lucky.gg")
        msg = await ctx.reply(embed=spinning_embed, mention_author=False)

        await asyncio.sleep(1.5)

        won = s1 == s2 == s3
        result_line = f"{s1} | {s2} | {s3}"
        outcome = "🍀 **You won!** Three of a kind!" if won else "🃏 **No match.** Better luck next time!"

        result_embed = discord.Embed(
            title="🎰 Slot Machine",
            description=f"{result_line}\n\n{outcome}",
            color=0x57F287 if won else 0xFF4444,
        )
        result_embed.set_footer(text="Lucky Bot • lucky.gg")
        await msg.edit(embed=result_embed)


async def setup(bot):
    await bot.add_cog(Slots(bot))

# Lucky Bot — Rewritten
