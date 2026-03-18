import discord
from discord.ext import commands
import re
from typing import Union
from utils.Tools import *
from collections import Counter


time_regex = re.compile(r"(?:(\d{1,5})(h|s|m|d))+?")
time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400}


def convert(argument):
    args = argument.lower()
    matches = re.findall(time_regex, args)
    time = 0
    for key, value in matches:
        try:
            time += time_dict[value] * float(key)
        except KeyError:
            raise commands.BadArgument(f"{value} is an invalid time key! h|m|s|d are valid arguments")
        except ValueError:
            raise commands.BadArgument(f"{key} is not a number!")
    return round(time)


async def do_removal(ctx, limit, predicate, *, before=None, after=None):
    if limit > 2000:
        return await ctx.send("🃏 Too many messages to search given ({}/2000)".format(limit))

    if before is None:
        before = ctx.message
    else:
        before = discord.Object(id=before)

    if after is not None:
        after = discord.Object(id=after)

    try:
        deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
    except discord.Forbidden:
        return await ctx.send("🃏 I do not have permissions to delete messages.")
    except discord.HTTPException as e:
        return await ctx.send(f"🃏 Error: {e} (try a smaller search?)")

    spammers = Counter(m.author.display_name for m in deleted)
    deleted = len(deleted)
    messages = [f'🍀 {deleted} message{"" if deleted == 1 else "s"} removed.']
    if deleted:
        messages.append("")
        spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
        messages.extend(f"**{name}**: {count}" for name, count in spammers)

    to_send = "\n".join(messages)
    if len(to_send) > 2000:
        await ctx.send(f"🍀 Successfully removed {deleted} messages.", delete_after=7)
    else:
        await ctx.send(to_send, delete_after=7)


class Message(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF4444

    @commands.group(invoke_without_command=True, aliases=["purge"], help="Clears messages from the channel")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clear(self, ctx, Choice: Union[discord.Member, int], Amount: int = None):
        await ctx.message.delete()
        if isinstance(Choice, discord.Member):
            search = Amount or 5
            return await do_removal(ctx, search, lambda e: e.author == Choice)
        elif isinstance(Choice, int):
            return await do_removal(ctx, Choice, lambda e: True)

    @clear.command(help="Clears messages containing embeds")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def embeds(self, ctx, search=100):
        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: len(e.embeds))

    @clear.command(help="Clears messages containing files")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def files(self, ctx, search=100):
        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: len(e.attachments))

    @clear.command(help="Clears messages containing images")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def images(self, ctx, search=100):
        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: len(e.embeds) or len(e.attachments))

    @clear.command(name="all", help="Clears all messages")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def _remove_all(self, ctx, search=100):
        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: True)

    @clear.command(help="Clears messages from a specific user")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def user(self, ctx, member: discord.Member, search=100):
        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: e.author == member)

    @clear.command(help="Clears messages containing a specific string")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def contains(self, ctx, *, string: str):
        await ctx.message.delete()
        if len(string) < 3:
            await ctx.send("🃏 The substring length must be at least 3 characters.")
        else:
            await do_removal(ctx, 100, lambda e: string in e.content)

    @clear.command(name="bot", aliases=["bots", "b"], help="Clears messages sent by bots")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def _bot(self, ctx, prefix=None, search=100):
        await ctx.message.delete()

        def predicate(m):
            return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))

        await do_removal(ctx, search, predicate)

    @clear.command(name="emoji", aliases=["emojis"], help="Clears messages containing custom emojis")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def _emoji(self, ctx, search=100):
        await ctx.message.delete()
        custom_emoji = re.compile(r"<a?:[a-zA-Z0-9\_]+:([0-9]+)>")

        def predicate(m):
            return custom_emoji.search(m.content)

        await do_removal(ctx, search, predicate)

    @clear.command(name="reactions", help="Removes reactions from messages")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def _reactions(self, ctx, search=100):
        await ctx.message.delete()
        if search > 2000:
            return await ctx.send(f"🃏 Too many messages to search ({search}/2000)")

        total_reactions = 0
        async for message in ctx.history(limit=search, before=ctx.message):
            if len(message.reactions):
                total_reactions += sum(r.count for r in message.reactions)
                await message.clear_reactions()

        await ctx.send(f"🍀 Successfully removed {total_reactions} reactions.")

    @commands.command(
        name="purgebots",
        aliases=["cleanup", "pb", "clearbot", "clearbots"],
        help="Clear recent bot messages in channel")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def _purgebot(self, ctx, prefix=None, search=100):
        await ctx.message.delete()

        def predicate(m):
            return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))

        await do_removal(ctx, search, predicate)

    @commands.command(
        name="purgeuser",
        aliases=["pu", "cu", "clearuser"],
        help="Clear recent messages from a user in channel")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purguser(self, ctx, member: discord.Member, search=100):
        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: e.author == member)


async def setup(bot):
    await bot.add_cog(Message(bot))

# Lucky Bot — Rewritten
