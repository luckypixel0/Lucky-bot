import discord
from discord.ext import commands
import urllib.parse
import urllib.request
import re


class Youtube(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="yt",
        aliases=["youtube"],
        help="Search YouTube and return the top result.",
        usage="yt <query>",
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def search_youtube(self, ctx: commands.Context, *, search_query: str):
        query_string = urllib.parse.urlencode({"search_query": search_query})
        try:
            html_content = urllib.request.urlopen(
                "http://www.youtube.com/results?" + query_string
            )
            search_results = re.findall(r"watch\?v=(\S{11})", html_content.read().decode())
        except Exception:
            search_results = []

        if search_results:
            url = f"https://www.youtube.com/watch?v={search_results[0]}"
            embed = discord.Embed(
                title="▶️ YouTube Search",
                description=f"**Query:** {discord.utils.escape_markdown(search_query)}\n\n{url}",
                color=0xFF4444,
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.reply(embed=embed, mention_author=False)
        else:
            embed = discord.Embed(
                description="🃏 No results found for that query.",
                color=0xFF4444,
            )
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.reply(embed=embed, mention_author=False)


async def setup(bot):
    await bot.add_cog(Youtube(bot))

# Lucky Bot — Rewritten
