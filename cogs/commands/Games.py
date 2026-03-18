import discord
from discord.ext import commands
from core import Cog, Lucky, Context
import games as games
from games import button_games as btn
from utils.Tools import blacklist_check, ignore_check


class Games(Cog):
    """Lucky Bot Games"""

    def __init__(self, client: Lucky):
        self.client = client

    @commands.hybrid_command(
        name="chess",
        help="Play Chess with another user.",
        usage="chess <user>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(5, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def _chess(self, ctx: Context, player: discord.Member):
        if player == ctx.author:
            return await ctx.send("You cannot play a game against yourself!", mention_author=False)
        if player.bot:
            return await ctx.send("You cannot play with bots!")
        game = btn.BetaChess(white=ctx.author, black=player)
        await game.start(ctx)

    @commands.hybrid_command(
        name="rps",
        help="Play Rock Paper Scissors with the bot or a user.",
        aliases=["rockpaperscissors"],
        usage="rps [user]",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(5, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def _rps(self, ctx: Context, player: discord.Member = None):
        game = btn.BetaRockPaperScissors(player)
        await game.start(ctx, timeout=120)

    @commands.hybrid_command(
        name="tic-tac-toe",
        help="Play Tic-Tac-Toe with another user.",
        aliases=["ttt", "tictactoe"],
        usage="tic-tac-toe <user>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(5, per=commands.BucketType.user, wait=False)
    @commands.guild_only()
    async def _ttt(self, ctx: Context, player: discord.Member):
        if player == ctx.author:
            return await ctx.send("You cannot play against yourself!", mention_author=False)
        if player.bot:
            return await ctx.send("You cannot play with bots!")
        game = btn.BetaTictactoe(cross=ctx.author, circle=player)
        await game.start(ctx, timeout=30)

    @commands.hybrid_command(
        name="wordle",
        help="Play Wordle against the bot.",
        usage="wordle",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(3, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def _wordle(self, ctx: Context):
        game = games.Wordle()
        await game.start(ctx, timeout=120)

    @commands.hybrid_command(
        name="2048",
        help="Play the 2048 game.",
        aliases=["twenty48"],
        usage="2048",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(3, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def _2048(self, ctx: Context):
        game = btn.BetaTwenty48()
        await game.start(ctx, win_at=2048)

    @commands.hybrid_command(
        name="memory-game",
        help="Test your memory!",
        aliases=["memory"],
        usage="memory-game",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(3, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def _memory(self, ctx: Context):
        game = btn.MemoryGame()
        await game.start(ctx)

    @commands.hybrid_command(
        name="number-slider",
        help="Slide numbers to solve the puzzle.",
        aliases=["slider"],
        usage="number-slider",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(3, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def _number_slider(self, ctx: Context):
        game = btn.NumberSlider()
        await game.start(ctx)

    @commands.hybrid_command(
        name="battleship",
        help="Play Battleship with a friend.",
        aliases=["battle-ship"],
        usage="battleship <user>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(3, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def _battle(self, ctx: Context, player: discord.Member):
        game = btn.BetaBattleShip(player1=ctx.author, player2=player)
        await game.start(ctx)

    @commands.group(
        name="country-guesser",
        help="Guess the country by its flag.",
        aliases=["guess", "guesser", "countryguesser"],
        usage="country-guesser",
    )
    @commands.guild_only()
    async def _country_guesser(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help("country-guesser")

    @_country_guesser.command(
        name="start",
        help="Starts the country guesser game. Recommended to use in a dedicated channel.",
    )
    async def _start_country_guesser(self, ctx: Context):
        game = games.CountryGuesser(is_flags=True, hints=2)
        await game.start(ctx)

    @commands.hybrid_command(
        name="connectfour",
        help="Play Connect Four with another user.",
        aliases=["c4", "connect-four", "connect4"],
        usage="connectfour <user>",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.user, wait=False)
    @commands.guild_only()
    async def _connectfour(self, ctx: Context, player: discord.Member):
        if player == ctx.author:
            return await ctx.send("You cannot play against yourself!")
        if player.bot:
            return await ctx.send("You cannot play with bots!")
        game = games.ConnectFour(red=ctx.author, blue=player)
        await game.start(ctx, timeout=300)

    @commands.hybrid_command(
        name="lights-out",
        help="Play the Lights Out puzzle.",
        aliases=["lightsout"],
        usage="lights-out",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(3, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def _lights_out(self, ctx: Context):
        game = btn.LightsOut()
        await game.start(ctx)


async def setup(bot):
    await bot.add_cog(Games(bot))

# Lucky Bot — Rewritten
