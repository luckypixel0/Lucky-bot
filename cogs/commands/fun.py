import discord
from discord.ext import commands
import random
import aiohttp
import os
from utils.Tools import blacklist_check, ignore_check


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.giphy_api_key = os.getenv("GIPHY_API_KEY")

    def _lucky_embed(self, title: str, description: str) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=0x2F3136)
        embed.set_footer(text="Lucky Bot • lucky.gg")
        return embed

    async def fetch_giphy(self, query: str) -> str | None:
        if not self.giphy_api_key:
            return None
        async with aiohttp.ClientSession() as session:
            url = (
                f"https://api.giphy.com/v1/gifs/search"
                f"?api_key={self.giphy_api_key}&q={query}&limit=30&rating=pg"
            )
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if data["data"]:
                    return random.choice(data["data"])["images"]["original"]["url"]
                return None

    def random_emoji(self) -> str:
        return random.choice(["😂", "🤣", "😆", "😳", "🥴", "🙃", "😜"])

    async def action_command(self, ctx, user: discord.Member, action: str):
        gif_url = await self.fetch_giphy(action)
        if not gif_url:
            await ctx.send("🃏 GIF fetch failed, try again later!")
            return
        embed = discord.Embed(
            description=f"**{ctx.author.mention} {action}s {user.mention} {self.random_emoji()}**",
            color=0x2F3136,
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @commands.command(name="shipp")
    @blacklist_check()
    @ignore_check()
    async def shipp(self, ctx, user1: discord.Member, user2: discord.Member):
        percentage = random.randint(0, 100)
        embed = self._lucky_embed(
            f"{self.random_emoji()} Ship Result",
            f"**{user1.mention} x {user2.mention} = {percentage}% Love**",
        )
        await ctx.send(embed=embed)

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def hug(self, ctx, user: discord.Member):
        await self.action_command(ctx, user, "hug")

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def kiss(self, ctx, user: discord.Member):
        await self.action_command(ctx, user, "kiss")

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def pat(self, ctx, user: discord.Member):
        await self.action_command(ctx, user, "pat")

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def slap(self, ctx, user: discord.Member):
        await self.action_command(ctx, user, "slap")

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def tickle(self, ctx, user: discord.Member):
        await self.action_command(ctx, user, "tickle")

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def coinflip(self, ctx):
        result = random.choice(["Heads", "Tails"])
        embed = self._lucky_embed("🪙 Coin Flip", f"**Result: {result}**")
        await ctx.send(embed=embed)

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def dice(self, ctx):
        result = random.randint(1, 6)
        embed = self._lucky_embed("🎲 Dice Roll", f"**You rolled a {result}!**")
        await ctx.send(embed=embed)

    @commands.command(name="8ball")
    @blacklist_check()
    @ignore_check()
    async def eight_ball(self, ctx, *, question: str):
        responses = [
            "It is certain.", "Without a doubt.", "You may rely on it.",
            "Ask again later.", "Better not tell you now.",
            "Don't count on it.", "My sources say no.", "Very doubtful.",
        ]
        embed = self._lucky_embed(
            "🎱 Magic 8Ball",
            f"**Q:** {question}\n**A:** {random.choice(responses)}",
        )
        await ctx.send(embed=embed)

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def roast(self, ctx, user: discord.Member):
        roasts = [
            f"{user.mention} you're the reason shampoo has instructions!",
            f"{user.mention} you have something on your chin... no, the third one down!",
            f"{user.mention} your secrets are safe with me. I never even listen when you tell me them.",
        ]
        embed = self._lucky_embed("🔥 Roast Time", random.choice(roasts))
        await ctx.send(embed=embed)

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def iq(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        iq_value = random.randint(50, 200)
        embed = self._lucky_embed("🧠 IQ Test", f"**{user.mention} has an IQ of {iq_value}!**")
        await ctx.send(embed=embed)

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def dumb(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        dumbness = random.randint(0, 100)
        embed = self._lucky_embed("🤪 Dumbness Test", f"**{user.mention} is {dumbness}% dumb!**")
        await ctx.send(embed=embed)

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def simprate(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        simp_level = random.randint(0, 100)
        embed = self._lucky_embed("😳 Simp Rate", f"**{user.mention} is {simp_level}% simp!**")
        await ctx.send(embed=embed)

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def toxic(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        toxic_level = random.randint(0, 100)
        embed = self._lucky_embed("☠️ Toxic Meter", f"**{user.mention} is {toxic_level}% toxic!**")
        await ctx.send(embed=embed)

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def intelligence(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        intelligence = random.randint(0, 200)
        embed = self._lucky_embed(
            "🧠 Intelligence Meter",
            f"**{user.mention} has {intelligence} IQ Points!**",
        )
        await ctx.send(embed=embed)

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def genius(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        genius_level = random.randint(0, 100)
        embed = self._lucky_embed("🤓 Genius Rate", f"**{user.mention} is {genius_level}% genius!**")
        await ctx.send(embed=embed)

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def brainrate(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        brain_power = random.randint(0, 100)
        embed = self._lucky_embed(
            "🧠 Brain Power",
            f"**{user.mention} is using {brain_power}% of their brain!**",
        )
        await ctx.send(embed=embed)

    @commands.command()
    @blacklist_check()
    @ignore_check()
    async def howhot(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        hotness = random.randint(0, 100)
        embed = self._lucky_embed("🔥 Hotness Meter", f"**{user.mention} is {hotness}% hot!**")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Fun(bot))

# Lucky Bot — Rewritten
