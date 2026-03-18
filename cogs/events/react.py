import discord
import asyncio
from discord.ext import commands


class React(commands.Cog):
    """Auto-reacts with Lucky emojis when an owner is mentioned."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        for owner_id in self.bot.owner_ids:
            if f"<@{owner_id}>" not in message.content:
                continue
            try:
                for emoji in ["🍀", "🎴", "🔮"]:
                    try:
                        await message.add_reaction(emoji)
                    except discord.HTTPException:
                        pass
            except discord.errors.RateLimited as e:
                await asyncio.sleep(e.retry_after)
            except Exception as e:
                print(f"[Lucky] React error: {e}")

# Lucky Bot — Rewritten
