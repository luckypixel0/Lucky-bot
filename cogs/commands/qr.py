import discord
from discord.ext import commands
import aiohttp
import io


class QR(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="qr",
        aliases=["qrcode"],
        help="Generate a QR code for any text or URL.",
        usage="qr <text>",
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def qr(self, ctx: commands.Context, *, text: str):
        await ctx.defer()
        encoded = discord.utils.escape_markdown(text)
        api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={text}"

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    embed = discord.Embed(
                        description="🃏 Failed to generate QR code. Please try again.",
                        color=0xFF4444,
                    )
                    embed.set_footer(text="Lucky Bot • lucky.gg")
                    return await ctx.reply(embed=embed, mention_author=False)

                data = await resp.read()

        file = discord.File(io.BytesIO(data), filename="qrcode.png")
        embed = discord.Embed(
            title="🔲 QR Code",
            description=f"**Input:** {encoded[:200]}",
            color=0x2F3136,
        )
        embed.set_image(url="attachment://qrcode.png")
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.reply(embed=embed, file=file, mention_author=False)

    @qr.error
    async def qr_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("🃏 Please provide text to encode.", mention_author=False)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(
                f"⏳ Cooldown active. Try again in `{round(error.retry_after, 1)}s`.",
                mention_author=False,
            )
        else:
            await ctx.reply(f"🎴 An error occurred: `{error}`", mention_author=False)


async def setup(bot):
    await bot.add_cog(QR(bot))

# Lucky Bot — Rewritten
