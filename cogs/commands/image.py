import discord
from discord.ext import commands
import aiohttp
import os
import random


PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")


class ImageCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_pexels_image(self, query: str) -> str | None:
        if not PEXELS_API_KEY:
            return None
        headers = {"Authorization": PEXELS_API_KEY}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.pexels.com/v1/search?query={query}&per_page=50",
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if data.get("photos"):
                    return random.choice(data["photos"])["src"]["original"]
                return None

    async def fetch_waifu_image(self, category: str = "waifu") -> str | None:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.waifu.pics/sfw/{category}") as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("url")

    def _image_embed(self, title: str, url: str) -> discord.Embed:
        embed = discord.Embed(title=title, color=0x2F3136)
        embed.set_image(url=url)
        embed.set_footer(text="Lucky Bot • lucky.gg")
        return embed

    @commands.command(name="boy", help="Fetch a random image of a handsome guy.")
    async def boy_image(self, ctx: commands.Context):
        url = await self.fetch_pexels_image("handsome boy")
        if url:
            await ctx.send(embed=self._image_embed("👦 Boy Pic", url))
        else:
            await ctx.send("🃏 No image found. Make sure `PEXELS_API_KEY` is set.")

    @commands.command(name="couple", help="Fetch a random romantic couple image.")
    async def couple_image(self, ctx: commands.Context):
        url = await self.fetch_pexels_image("romantic couple")
        if url:
            await ctx.send(embed=self._image_embed("💑 Couple Pic", url))
        else:
            await ctx.send("🃏 No image found. Make sure `PEXELS_API_KEY` is set.")

    @commands.command(name="anime", help="Fetch a random anime waifu image.")
    async def anime_image(self, ctx: commands.Context):
        url = await self.fetch_waifu_image("waifu")
        if url:
            await ctx.send(embed=self._image_embed("🧚 Anime Waifu", url))
        else:
            await ctx.send("🃏 Could not fetch an anime image right now.")


async def setup(bot):
    await bot.add_cog(ImageCommands(bot))

# Lucky Bot — Rewritten
