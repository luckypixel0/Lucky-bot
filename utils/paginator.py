from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
import discord
from discord.ext import commands, menus
from discord.ext.commands import Context
from discord import Interaction, ButtonStyle


class Paginator(discord.ui.View):

    def __init__(
        self,
        source: menus.PageSource,
        *,
        ctx: Context | Interaction,
        check_embeds: bool = True,
    ):
        super().__init__()
        self.source = source
        self.check_embeds = check_embeds
        self.ctx = ctx
        self.message: Optional[discord.Message] = None
        self.current_page: int = 0
        self.clear_items()
        self.fill_items()

    def fill_items(self) -> None:
        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_ends = max_pages is not None and max_pages >= 2
            if use_ends:
                self.add_item(self.first_page_button)
            self.add_item(self.previous_page_button)
            self.add_item(self.stop_button)
            self.add_item(self.next_page_button)
            if use_ends:
                self.add_item(self.last_page_button)

    async def _get_kwargs_from_page(self, page: int) -> Dict[str, Any]:
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {"content": value, "embed": None}
        elif isinstance(value, discord.Embed):
            return {"embed": value, "content": None}
        return {}

    async def show_page(self, interaction: discord.Interaction, page_number: int) -> None:
        page = await self.source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(page_number)
        if kwargs:
            if interaction.response.is_done():
                if self.message:
                    await self.message.edit(**kwargs, view=self)
            else:
                await interaction.response.edit_message(**kwargs, view=self)

    def _update_labels(self, page_number: int) -> None:
        self.first_page_button.disabled = page_number == 0
        self.previous_page_button.disabled = page_number == 0
        self.next_page_button.disabled = False
        max_pages = self.source.get_max_pages()
        if max_pages:
            self.last_page_button.disabled = (page_number + 1) >= max_pages
            self.next_page_button.disabled = (page_number + 1) >= max_pages

    async def show_checked_page(self, interaction: discord.Interaction, page_number: int) -> None:
        max_pages = self.source.get_max_pages()
        try:
            if max_pages is None or max_pages > page_number >= 0:
                await self.show_page(interaction, page_number)
        except IndexError:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if isinstance(self.ctx, Interaction):
            owner = getattr(self.ctx.client, "owner_id", None)
            user = self.ctx.user
        else:
            owner = getattr(self.ctx.bot, "owner_id", None)
            user = self.ctx.author

        if interaction.user and interaction.user.id in (owner, user.id if user else None):
            return True

        await interaction.response.send_message(
            "🃏 That menu doesn't belong to you.", ephemeral=True
        )
        return False

    async def on_timeout(self) -> None:
        if self.message:
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        msg = "🃏 An error occurred."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    def update_styles(self, **kwargs):
        self.first_page_button.emoji = kwargs.get("first_button_emoji") or "⏮️"
        self.previous_page_button.emoji = kwargs.get("previous_button_emoji") or "◀️"
        self.stop_button.emoji = kwargs.get("stop_button_emoji") or "🃏"
        self.next_page_button.emoji = kwargs.get("next_button_emoji") or "▶️"
        self.last_page_button.emoji = kwargs.get("last_button_emoji") or "⏭️"

        self.first_page_button.style = kwargs.get("first_button_style") or ButtonStyle.secondary
        self.previous_page_button.style = kwargs.get("previous_button_style") or ButtonStyle.secondary
        self.stop_button.style = kwargs.get("stop_button_style") or ButtonStyle.danger
        self.next_page_button.style = kwargs.get("next_button_style") or ButtonStyle.secondary
        self.last_page_button.style = kwargs.get("last_button_style") or ButtonStyle.secondary

    async def paginate(self, *, content: Optional[str] = None, ephemeral: bool = False, **kwargs) -> None:
        self.update_styles(**kwargs)
        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kw = await self._get_kwargs_from_page(page)
        if content:
            kw.setdefault("content", content)
        self._update_labels(0)

        if isinstance(self.ctx, Interaction):
            self.message = await self.ctx.response.send_message(**kw, view=self, ephemeral=ephemeral)
        else:
            self.message = await self.ctx.send(**kw, view=self, ephemeral=ephemeral)

    @discord.ui.button()
    async def first_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_page(interaction, 0)

    @discord.ui.button()
    async def previous_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_checked_page(interaction, self.current_page - 1)

    @discord.ui.button()
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

    @discord.ui.button()
    async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_checked_page(interaction, self.current_page + 1)

    @discord.ui.button()
    async def last_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_page(interaction, self.source.get_max_pages() - 1)

# Lucky Bot — Rewritten
