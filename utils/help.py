import discord
import functools
from utils.Tools import *


class Dropdown(discord.ui.Select):

    def __init__(self, ctx, options, placeholder="Choose a Category", row=None):
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options,
            row=row,
        )
        self.invoker = ctx.author

    async def callback(self, interaction: discord.Interaction):
        if self.invoker != interaction.user:
            return await interaction.response.send_message(
                "🃏 You must run this command to interact with it.", ephemeral=True
            )
        index = self.view.find_index_from_select(self.values[0]) or 0
        await self.view.set_page(index, interaction)


class View(discord.ui.View):

    def __init__(
        self,
        mapping: dict,
        ctx: discord.ext.commands.context.Context,
        homeembed: discord.embeds.Embed,
        ui: int,
    ):
        super().__init__(timeout=None)
        self.mapping = mapping
        self.ctx = ctx
        self.home = homeembed
        self.index = 0
        self.buttons = None
        self.current_page = 0

        self.options, self.embeds, self.total_pages = self._gen_embeds()

        if ui == 0:
            self.add_item(Dropdown(ctx=self.ctx, options=self.options))
        elif ui == 1:
            self.buttons = self._add_buttons()
        elif ui == 2:
            self.buttons = self._add_buttons()
            mid = len(self.options) // 2
            opts1 = self.options[:mid]
            opts2 = self.options[mid:]
            if opts1:
                self.add_item(Dropdown(ctx=self.ctx, options=opts1, placeholder="Main Commands", row=1))
            if opts2:
                self.add_item(Dropdown(ctx=self.ctx, options=opts2, placeholder="Extra Commands", row=2))
        else:
            self.buttons = self._add_buttons()
            self.add_item(Dropdown(ctx=self.ctx, options=self.options))

    def _add_buttons(self):
        self.homeB = discord.ui.Button(emoji="⏮️", style=discord.ButtonStyle.secondary)
        self.homeB.callback = self._home_callback

        self.backB = discord.ui.Button(emoji="◀️", style=discord.ButtonStyle.secondary)
        self.backB.callback = self._back_callback

        self.quitB = discord.ui.Button(emoji="🃏", style=discord.ButtonStyle.danger)
        self.quitB.callback = self._quit_callback

        self.nextB = discord.ui.Button(emoji="▶️", style=discord.ButtonStyle.secondary)
        self.nextB.callback = self._next_callback

        self.lastB = discord.ui.Button(emoji="⏭️", style=discord.ButtonStyle.secondary)
        self.lastB.callback = self._last_callback

        for btn in [self.homeB, self.backB, self.quitB, self.nextB, self.lastB]:
            self.add_item(btn)
        return [self.homeB, self.backB, self.quitB, self.nextB, self.lastB]

    async def _home_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("🃏 Not your menu.", ephemeral=True)
        await self.set_page(0, interaction)

    async def _back_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("🃏 Not your menu.", ephemeral=True)
        page = self.index - 1 if self.index > 0 else len(self.embeds) - 1
        await self.set_page(page, interaction)

    async def _quit_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("🃏 Not your menu.", ephemeral=True)
        await interaction.response.defer()
        await interaction.delete_original_response()

    async def _next_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("🃏 Not your menu.", ephemeral=True)
        page = self.index + 1 if self.index < len(self.embeds) - 1 else 0
        await self.set_page(page, interaction)

    async def _last_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("🃏 Not your menu.", ephemeral=True)
        await self.set_page(len(self.embeds) - 1, interaction)

    def find_index_from_select(self, value: str) -> int:
        used_labels: set = set()
        for i, cog in enumerate(self._get_cogs()):
            if not hasattr(cog, "help_custom"):
                continue
            _, label, _ = cog.help_custom()
            orig = label
            c = 1
            while label in used_labels:
                label = f"{orig} {c}"
                c += 1
            used_labels.add(label)
            if label == value or value.startswith(orig + " "):
                return i + 1
        return 0

    def _get_cogs(self):
        return list(self.mapping.keys())

    def _gen_embeds(self):
        options, embeds = [], []
        total = 0
        used_labels: set = set()

        options.append(discord.SelectOption(label="Home", emoji="🍀", description=""))
        embeds.append(self.home)
        total += 1
        used_labels.add("Home")

        for cog in self._get_cogs():
            if not hasattr(cog, "help_custom"):
                continue
            emoji, label, description = cog.help_custom()
            orig = label
            c = 1
            while label in used_labels:
                label = f"{orig} {c}"
                c += 1
            used_labels.add(label)

            options.append(discord.SelectOption(label=label, emoji=emoji, description=description))
            embed = discord.Embed(title=f"{emoji} {orig}", color=0x2F3136)

            for command in cog.get_commands():
                params = "".join(
                    f" <{p}>" for p in command.clean_params if p not in ("self", "ctx")
                )
                help_text = command.help or "No description available."
                if len(help_text) > 1020:
                    help_text = help_text[:1017] + "..."
                embed.add_field(
                    name=f"{command.name}{params}",
                    value=f"{help_text}\n•",
                    inline=False,
                )

            embed.set_footer(text="Lucky Bot • lucky.gg")
            embeds.append(embed)
            total += 1

        self.home.set_footer(
            text=f"🍀 Page 1/{total} • Requested by {self.ctx.author.display_name} | Lucky Bot • lucky.gg",
            icon_url=self.ctx.bot.user.avatar.url if self.ctx.bot.user.avatar else None,
        )
        return options, embeds, total

    async def set_page(self, page: int, interaction: discord.Interaction):
        self.index = page
        self.current_page = page
        embed = self.embeds[self.index]
        embed.set_footer(
            text=f"🍀 Page {self.index + 1}/{self.total_pages} • Requested by {self.ctx.author.display_name} | Lucky Bot • lucky.gg",
            icon_url=self.ctx.bot.user.avatar.url if self.ctx.bot.user.avatar else None,
        )
        if self.buttons:
            self.homeB.disabled = self.index == 0
            self.backB.disabled = self.index == 0
            self.nextB.disabled = self.index == len(self.embeds) - 1
            self.lastB.disabled = self.index == len(self.embeds) - 1
        await interaction.response.edit_message(embed=embed, view=self)

# Lucky Bot — Rewritten
