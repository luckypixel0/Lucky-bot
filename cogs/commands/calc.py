import discord
from discord.ext import commands
from discord.ui import View, Button, button


class CalculatorView(View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=120)
        self.author = author
        self.value = ""
        self.message = None

    def _build_embed(self, display: str) -> discord.Embed:
        embed = discord.Embed(
            title="🧮 Calculator",
            description=f"```\n{display}\n```",
            color=0x5865F2,
        )
        embed.set_footer(
            text=f"Lucky Bot • lucky.gg  |  Used by {self.author.display_name}",
            icon_url=self.author.display_avatar.url,
        )
        return embed

    async def _check_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "🃏 This calculator isn't yours.", ephemeral=True
            )
            return False
        return True

    async def update_value(self, interaction: discord.Interaction, value: str):
        if not await self._check_author(interaction):
            return
        if value == "Clear":
            self.value = ""
        else:
            self.value += value
        await interaction.response.edit_message(embed=self._build_embed(self.value or "0"), view=self)
        self.message = interaction.message

    @button(label="1", style=discord.ButtonStyle.grey, row=0)
    async def one(self, interaction, btn): await self.update_value(interaction, "1")

    @button(label="2", style=discord.ButtonStyle.grey, row=0)
    async def two(self, interaction, btn): await self.update_value(interaction, "2")

    @button(label="3", style=discord.ButtonStyle.grey, row=0)
    async def three(self, interaction, btn): await self.update_value(interaction, "3")

    @button(label="4", style=discord.ButtonStyle.grey, row=1)
    async def four(self, interaction, btn): await self.update_value(interaction, "4")

    @button(label="5", style=discord.ButtonStyle.grey, row=1)
    async def five(self, interaction, btn): await self.update_value(interaction, "5")

    @button(label="6", style=discord.ButtonStyle.grey, row=1)
    async def six(self, interaction, btn): await self.update_value(interaction, "6")

    @button(label="7", style=discord.ButtonStyle.grey, row=2)
    async def seven(self, interaction, btn): await self.update_value(interaction, "7")

    @button(label="8", style=discord.ButtonStyle.grey, row=2)
    async def eight(self, interaction, btn): await self.update_value(interaction, "8")

    @button(label="9", style=discord.ButtonStyle.grey, row=2)
    async def nine(self, interaction, btn): await self.update_value(interaction, "9")

    @button(label="0", style=discord.ButtonStyle.grey, row=3)
    async def zero(self, interaction, btn): await self.update_value(interaction, "0")

    @button(label="+", style=discord.ButtonStyle.blurple, row=3)
    async def add(self, interaction, btn): await self.update_value(interaction, "+")

    @button(label="-", style=discord.ButtonStyle.blurple, row=3)
    async def subtract(self, interaction, btn): await self.update_value(interaction, "-")

    @button(label="*", style=discord.ButtonStyle.blurple, row=3)
    async def multiply(self, interaction, btn): await self.update_value(interaction, "*")

    @button(label="/", style=discord.ButtonStyle.blurple, row=3)
    async def divide(self, interaction, btn): await self.update_value(interaction, "/")

    @button(label="=", style=discord.ButtonStyle.green, row=4)
    async def equals(self, interaction: discord.Interaction, btn: Button):
        if not await self._check_author(interaction):
            return
        try:
            expression = self.value.strip()
            result = str(eval(expression))  # noqa: S307
            self.value = result
            await interaction.response.edit_message(embed=self._build_embed(result), view=self)
        except Exception:
            await interaction.response.edit_message(embed=self._build_embed("Error"), view=self)
        self.message = interaction.message

    @button(label="Clear", style=discord.ButtonStyle.red, row=4)
    async def clear(self, interaction: discord.Interaction, btn: Button):
        await self.update_value(interaction, "Clear")


class Calculator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="calculator",
        help="Open an interactive button calculator.",
        aliases=["calc", "calculate", "math"],
    )
    async def calculator(self, ctx: commands.Context):
        view = CalculatorView(author=ctx.author)
        embed = discord.Embed(
            title="🧮 Calculator",
            description="```\n0\n```",
            color=0x5865F2,
        )
        embed.set_footer(
            text=f"Lucky Bot • lucky.gg  |  Used by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url,
        )
        view.message = await ctx.send(embed=embed, view=view, mention_author=False)


async def setup(bot):
    await bot.add_cog(Calculator(bot))

# Lucky Bot — Rewritten
