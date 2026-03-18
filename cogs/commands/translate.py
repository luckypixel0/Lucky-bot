import discord
from discord.ext import commands
from deep_translator import GoogleTranslator


class TranslateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="hinglish",
        help="Translate Hinglish (Hindi + English mix) to proper English.",
        usage="hinglish <text>",
    )
    async def hinglish(self, ctx: commands.Context, *, text: str = None):
        if not text:
            return await ctx.reply(
                "🎴 Please provide some Hinglish text to translate.",
                ephemeral=True if ctx.interaction else False,
                mention_author=False,
            )

        msg = await ctx.reply(
            "🔄 Translating...",
            ephemeral=True if ctx.interaction else False,
            mention_author=False,
        )

        try:
            translated = GoogleTranslator(source="auto", target="en").translate(text)

            embed = discord.Embed(title="🗣️ Hinglish → English", color=0x5865F2)
            embed.add_field(name="Original", value=text[:1024], inline=False)
            embed.add_field(name="Translated", value=translated[:1024], inline=False)
            embed.set_footer(
                text=f"Lucky Bot • lucky.gg  |  Requested by {ctx.author}",
                icon_url=ctx.author.display_avatar.url,
            )
            await msg.edit(content=None, embed=embed)

        except Exception as e:
            await msg.edit(content=f"🃏 Translation failed: `{e}`")

    @commands.hybrid_command(
        name="translate",
        help="Translate text from one language to another.",
        usage="translate <target_lang> <text>",
    )
    async def translate(self, ctx: commands.Context, target: str, *, text: str):
        msg = await ctx.reply("🔄 Translating...", mention_author=False)
        try:
            translated = GoogleTranslator(source="auto", target=target).translate(text)

            embed = discord.Embed(title="🌐 Translation", color=0x5865F2)
            embed.add_field(name="Original", value=text[:1024], inline=False)
            embed.add_field(name=f"Translated ({target.upper()})", value=translated[:1024], inline=False)
            embed.set_footer(
                text=f"Lucky Bot • lucky.gg  |  Requested by {ctx.author}",
                icon_url=ctx.author.display_avatar.url,
            )
            await msg.edit(content=None, embed=embed)

        except Exception as e:
            await msg.edit(content=f"🃏 Translation failed: `{e}`")


async def setup(bot):
    await bot.add_cog(TranslateCog(bot))

# Lucky Bot — Rewritten
