import discord
from discord.ext import commands
import os
import random
import asyncio
from typing import List, Tuple, Union
from PIL import Image
from utils.Tools import blacklist_check, ignore_check

CARDS_PATH = "data/cards/"


class Card:
    suits = ["clubs", "diamonds", "hearts", "spades"]

    def __init__(self, suit: str, value: int, down: bool = False):
        self.suit = suit
        self.value = value
        self.down = down
        self.symbol = self.name[0].upper()

    @property
    def name(self) -> str:
        if self.value <= 10:
            return str(self.value)
        return {11: "jack", 12: "queen", 13: "king", 14: "ace"}[self.value]

    @property
    def image(self) -> str:
        prefix = self.symbol if self.name != "10" else "10"
        return f"{prefix}{self.suit[0].upper()}.png" if not self.down else "red_back.png"

    def flip(self) -> "Card":
        self.down = not self.down
        return self

    def __str__(self) -> str:
        return f"{self.name.title()} of {self.suit.title()}"

    def __repr__(self) -> str:
        return str(self)


class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def hand_to_images(hand: List[Card]) -> List[Image.Image]:
        return [Image.open(os.path.join(CARDS_PATH, card.image)) for card in hand]

    @staticmethod
    def center(*hands: Tuple[List[Image.Image]]) -> Image.Image:
        bg = Image.open(os.path.join(CARDS_PATH, "table.png"))
        bg_cx, bg_cy = bg.size[0] // 2, bg.size[1] // 2
        img_w, img_h = hands[0][0].size

        start_y = bg_cy - (((len(hands) * img_h) + ((len(hands) - 1) * 15)) // 2)
        for hand in hands:
            start_x = bg_cx - (((len(hand) * img_w) + ((len(hand) - 1) * 10)) // 2)
            for card in hand:
                bg.alpha_composite(card, (start_x, start_y))
                start_x += img_w + 10
            start_y += img_h + 15
        return bg

    def output(self, name: str, *hands: Tuple[List[Card]]) -> None:
        self.center(*map(self.hand_to_images, hands)).save(f"data/{name}.png")

    @staticmethod
    def calc_hand(hand: List[Card]) -> int:
        non_aces = [c for c in hand if c.symbol != "A"]
        aces = [c for c in hand if c.symbol == "A"]
        total = 0
        for card in non_aces:
            if not card.down:
                total += 10 if card.symbol in "JQK" else card.value
        for card in aces:
            if not card.down:
                total += 11 if total <= 10 else 1
        return total

    @commands.command(
        aliases=["bj", "blackjacks"],
        help="Play a game of Blackjack.",
        usage="blackjack",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def blackjack(self, ctx: commands.Context):
        try:
            deck = [Card(suit, num) for num in range(2, 15) for suit in Card.suits]
            random.shuffle(deck)

            player_hand: List[Card] = []
            dealer_hand: List[Card] = []

            player_hand.append(deck.pop())
            dealer_hand.append(deck.pop())
            player_hand.append(deck.pop())
            dealer_hand.append(deck.pop())

            dealer_hand[1] = dealer_hand[1].flip()

            async def out_table(**kwargs) -> discord.Message:
                self.output(ctx.author.id, dealer_hand, player_hand)
                embed = discord.Embed(**kwargs)
                embed.set_footer(text="Lucky Bot • lucky.gg")
                file = discord.File(f"data/{ctx.author.id}.png", filename=f"{ctx.author.id}.png")
                embed.set_image(url=f"attachment://{ctx.author.id}.png")
                return await ctx.send(file=file, embed=embed)

            def check(reaction: discord.Reaction, user: Union[discord.Member, discord.User]) -> bool:
                return (
                    str(reaction.emoji) in ("🇸", "🇭")
                    and user == ctx.author
                    and user != self.bot.user
                    and reaction.message == msg
                )

            standing = False
            result = None

            while True:
                player_score = self.calc_hand(player_hand)
                dealer_score = self.calc_hand(dealer_hand)

                if player_score == 21:
                    result = ("Blackjack!", "won")
                    break
                if player_score > 21:
                    result = ("Player busts", "lost")
                    break

                msg = await out_table(
                    title="Your Turn",
                    description=f"Your hand: {player_score}\nDealer's hand: {dealer_score}",
                    color=0x2F3136,
                )
                await msg.add_reaction("🇭")
                await msg.add_reaction("🇸")

                try:
                    reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=check)
                except asyncio.TimeoutError:
                    await msg.delete()
                    return

                if str(reaction.emoji) == "🇭":
                    player_hand.append(deck.pop())
                    await msg.delete()
                    continue
                elif str(reaction.emoji) == "🇸":
                    standing = True
                    break

            if standing:
                dealer_hand[1] = dealer_hand[1].flip()
                player_score = self.calc_hand(player_hand)
                dealer_score = self.calc_hand(dealer_hand)

                while dealer_score < 17:
                    dealer_hand.append(deck.pop())
                    dealer_score = self.calc_hand(dealer_hand)

                if dealer_score == 21:
                    result = ("Dealer blackjack", "lost")
                elif dealer_score > 21:
                    result = ("Dealer busts", "won")
                elif dealer_score == player_score:
                    result = ("Tie!", "kept")
                elif dealer_score > player_score:
                    result = ("You lose!", "lost")
                else:
                    result = ("You win!", "won")

            color = (
                0xFF4444 if result[1] == "lost"
                else 0x57F287 if result[1] == "won"
                else 0x5865F2
            )

            try:
                await msg.delete()
            except Exception:
                pass

            msg = await out_table(
                title=result[0],
                color=color,
                description=f"**You {result[1]}**\nYour hand: {player_score}\nDealer's hand: {dealer_score}",
            )

            img_path = f"data/{ctx.author.id}.png"
            if os.path.exists(img_path):
                os.remove(img_path)

        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(Blackjack(bot))

# Lucky Bot — Rewritten
