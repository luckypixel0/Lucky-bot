import discord
import aiosqlite
from discord.ext import commands
from utils import getConfig
from utils.Tools import getIgnore


class MentionDropdown(discord.ui.Select):
    def __init__(self, message: discord.Message, bot: commands.Bot, prefix: str):
        self.message = message
        self.bot = bot
        self.prefix = prefix

        options = [
            discord.SelectOption(label="Home", emoji="🍀", description="Main menu"),
            discord.SelectOption(label="About Lucky", emoji="🔮", description="Info about this bot"),
            discord.SelectOption(label="Links", emoji="🎴", description="Useful links"),
        ]
        super().__init__(placeholder="Get started with Lucky", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.message.author.id:
            return await interaction.response.send_message(
                "🃏 This menu isn't for you!", ephemeral=True
            )

        embed = discord.Embed(color=0x2F3136)
        embed.set_thumbnail(url=self.bot.user.avatar.url)

        if self.values[0] == "Home":
            embed.title = f"🍀 {self.message.guild.name}"
            embed.description = (
                f"> 🎭 **Hey {interaction.user.mention}!**\n"
                f"> 🔮 Server prefix: `{self.prefix}`\n\n"
                f"Type `{self.prefix}help` to see all commands."
            )
        elif self.values[0] == "About Lucky":
            embed.title = "🔮 About Lucky"
            embed.description = (
                "Lucky is a feature-rich Discord bot built for server protection, "
                "moderation, music, games, and more.\n\n"
                "Visit **[lucky.gg](https://lucky.gg)** to learn more."
            )
        elif self.values[0] == "Links":
            embed.title = "🎴 Important Links"
            embed.description = (
                "**[Invite Lucky](https://discord.com/oauth2/authorize)**\n"
                "**[Support Server](https://discord.gg/lucky)**\n"
                "**[Website](https://lucky.gg)**"
            )

        embed.set_footer(text="Lucky Bot • lucky.gg", icon_url=self.bot.user.avatar.url)
        await interaction.response.edit_message(embed=embed, view=self.view)


class MentionView(discord.ui.View):
    def __init__(self, message: discord.Message, bot: commands.Bot, prefix: str):
        super().__init__(timeout=None)
        self.add_item(MentionDropdown(message, bot, prefix))


class Mention(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _is_blacklisted(self, message: discord.Message) -> bool:
        async with aiosqlite.connect("db/block.db") as db:
            async with db.execute(
                "SELECT 1 FROM guild_blacklist WHERE guild_id = ?", (message.guild.id,)
            ) as cur:
                if await cur.fetchone():
                    return True
            async with db.execute(
                "SELECT 1 FROM user_blacklist WHERE user_id = ?", (message.author.id,)
            ) as cur:
                if await cur.fetchone():
                    return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if await self._is_blacklisted(message):
            return

        ignore = getIgnore(message.guild.id)
        if str(message.author.id) in [str(u) for u in ignore.get("user", [])]:
            return
        if str(message.channel.id) in [str(c) for c in ignore.get("channel", [])]:
            return

        # Only respond when bot is mentioned alone
        if self.bot.user in message.mentions and len(message.content.strip().split()) == 1:
            data = await getConfig(message.guild.id)
            prefix = data.get("prefix", ">")

            embed = discord.Embed(
                title=f"🍀 {message.guild.name}",
                description=(
                    f"> 🎭 **Hey {message.author.mention}!**\n"
                    f"> 🔮 Server prefix: `{prefix}`\n\n"
                    f"Type `{prefix}help` to see all commands."
                ),
                color=0x2F3136,
            )
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text="Lucky Bot • lucky.gg", icon_url=self.bot.user.avatar.url)

            view = MentionView(message, self.bot, prefix)
            await message.channel.send(embed=embed, view=view)

# Lucky Bot — Rewritten
