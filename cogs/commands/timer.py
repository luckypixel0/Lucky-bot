import discord
from discord.ext import commands
import asyncio
from utils.Tools import blacklist_check, ignore_check

TIME_UNITS = {"s": 1, "S": 1, "m": 60, "M": 60, "h": 3600, "H": 3600, "d": 86400, "D": 86400}


def parse_time(raw: str) -> int | None:
    """Parse a time string like '30s', '5m', '2h' or plain integer seconds."""
    try:
        return int(raw)
    except ValueError:
        pass
    if len(raw) >= 2 and raw[-1] in TIME_UNITS:
        try:
            return int(raw[:-1]) * TIME_UNITS[raw[-1]]
        except ValueError:
            pass
    return None


def format_time(seconds: int) -> str:
    if seconds >= 3600:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"**{h}** hr **{m}** min **{s}** sec"
    if seconds >= 60:
        m, s = divmod(seconds, 60)
        return f"**{m}** min **{s}** sec"
    return f"**{seconds}** sec"


class TimerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="timer",
        aliases=["tstart"],
        description="Start a countdown timer.",
        usage="timer <time> [title]",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def _timer(self, ctx: commands.Context, times: str, *, title: str = "Timer"):
        seconds = parse_time(times)
        if seconds is None:
            return await ctx.send("🃏 Invalid time format. Use e.g. `30s`, `5m`, `2h`.", delete_after=5)
        if seconds <= 0:
            return await ctx.send("🃏 Timer must be a positive duration.", delete_after=5)
        if seconds > 86400:
            return await ctx.send("🃏 Timers cannot exceed 24 hours.", delete_after=5)

        def build_embed(remaining: int, done: bool = False) -> discord.Embed:
            embed = discord.Embed(
                title=f"⏳ {title}",
                description="⏰ Time's up!" if done else format_time(remaining),
                color=0x57F287 if done else 0x2F3136,
            )
            embed.set_footer(text=f"Lucky Bot • lucky.gg  |  Started by {ctx.author.display_name}")
            return embed

        message = await ctx.send(embed=build_embed(seconds))
        await message.add_reaction("⏱️")

        remaining = seconds
        while remaining > 0:
            await asyncio.sleep(6)
            remaining -= 6
            try:
                await message.edit(embed=build_embed(max(remaining, 0)))
            except Exception:
                break

        try:
            await message.edit(content=ctx.author.mention, embed=build_embed(0, done=True))
        except Exception:
            pass

        # Notify anyone who reacted
        try:
            msg = await ctx.channel.fetch_message(message.id)
            timer_reaction = next((r for r in msg.reactions if str(r.emoji) == "⏱️"), None)
            if timer_reaction:
                users = [u async for u in timer_reaction.users() if not u.bot]
                if users:
                    mentions = ", ".join(u.mention for u in users)
                    await ctx.send(f"⏱️ The timer for **{title}** has ended! {mentions}")
                    return
        except Exception:
            pass

        await ctx.send(f"⏱️ The timer for **{title}** has ended!")


async def setup(bot):
    await bot.add_cog(TimerCog(bot))

# Lucky Bot — Rewritten
