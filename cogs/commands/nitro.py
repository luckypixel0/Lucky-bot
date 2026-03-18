import discord
from discord.ext import commands
from discord.ui import Button, View


class Nitro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="nitro",
        help="Send a fake Nitro gift message for fun.",
        usage="nitro",
    )
    async def nitro(self, ctx: commands.Context):
        embed = discord.Embed(title="", color=0x2B2D31)
        embed.add_field(
            name="A Wild Nitro Gift Appears?",
            value="Expires in 12 hours\n\nClick the button below to claim!",
            inline=False,
        )
        embed.set_footer(
            text=f"Lucky Bot • lucky.gg  |  Requested by {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )
        embed.set_thumbnail(url="https://i.pinimg.com/originals/23/a6/51/23a6518aebdc551e72a6eab23bd2c282.gif")

        claim_button = Button(
            style=discord.ButtonStyle.primary,
            label="Claim Nitro",
            url="https://discord.gg/q2DdzFxheA",
        )
        view = View()
        view.add_item(claim_button)

        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Nitro(bot))

# Lucky Bot — Rewritten
