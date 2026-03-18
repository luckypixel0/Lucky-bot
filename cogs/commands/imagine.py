import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import time
import os
from utils.ai_utils import generate_image_prodia
from prodia.constants import Model
from utils.Tools import blacklist_check, ignore_check

BLACKLISTED_WORDS = {
    "naked", "nude", "nudes", "porn", "xnxx", "bitch", "loli", "hentai",
    "explicit", "pornography", "adult", "xxx", "sex", "erotic", "dick",
    "vagina", "pussy", "lick", "creampie", "nsfw", "hardcore", "ass",
    "anal", "anus", "boobs", "tits", "cum", "cunnilingus", "squirt",
    "penis", "masturbate", "masturbation", "orgasm", "orgy", "fap",
    "fapping", "fuck", "fucking", "handjob", "cowgirl", "doggystyle",
    "blowjob", "boobjob", "boobies", "horny", "nudity",
}

BLOCKED_WORDS = {
    "minor", "minors", "kid", "kids", "child", "children", "baby",
    "babies", "toddler", "childporn", "underage",
}


class CooldownManager:
    def __init__(self, rate: int, per: float):
        self.rate = rate
        self.per = per
        self.cooldowns: dict[int, list[float]] = {}

    def check_cooldown(self, user_id: int) -> float | None:
        now = time.time()
        self.cooldowns.setdefault(user_id, [])
        self.cooldowns[user_id] = [t for t in self.cooldowns[user_id] if now - t < self.per]
        if len(self.cooldowns[user_id]) >= self.rate:
            return self.per - (now - self.cooldowns[user_id][0])
        self.cooldowns[user_id].append(now)
        return None


_cooldown = CooldownManager(rate=1, per=60.0)


class AiStuffCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.guild_only()
    @app_commands.command(name="imagine", description="Generate an image using AI.")
    @discord.app_commands.choices(
        model=[
            discord.app_commands.Choice(name="✨ Elldreth Vivid Mix", value="ELLDRETHVIVIDMIX"),
            discord.app_commands.Choice(name="💪 Deliberate v2", value="DELIBERATE"),
            discord.app_commands.Choice(name="🔮 Dreamshaper", value="DREAMSHAPER_6"),
            discord.app_commands.Choice(name="🎼 Lyriel", value="LYRIEL_V16"),
            discord.app_commands.Choice(name="💥 Anything Diffusion (Anime)", value="ANYTHING_V4"),
            discord.app_commands.Choice(name="🌅 Openjourney", value="OPENJOURNEY"),
            discord.app_commands.Choice(name="🏞️ Realistic", value="REALISTICVS_V20"),
            discord.app_commands.Choice(name="👨‍🎨 Portrait", value="PORTRAIT"),
            discord.app_commands.Choice(name="🌟 Rev Animated", value="REV_ANIMATED"),
            discord.app_commands.Choice(name="🤖 Analog", value="ANALOG"),
            discord.app_commands.Choice(name="🌌 AbyssOrangeMix", value="ABYSSORANGEMIX"),
            discord.app_commands.Choice(name="🌌 Dreamlike v1", value="DREAMLIKE_V1"),
            discord.app_commands.Choice(name="🌌 Dreamlike v2", value="DREAMLIKE_V2"),
            discord.app_commands.Choice(name="🌌 Dreamshaper 5", value="DREAMSHAPER_5"),
            discord.app_commands.Choice(name="🌌 MechaMix", value="MECHAMIX"),
            discord.app_commands.Choice(name="🌌 MeinaMix", value="MEINAMIX"),
            discord.app_commands.Choice(name="🌌 Stable Diffusion v1.4", value="SD_V14"),
            discord.app_commands.Choice(name="🌌 Stable Diffusion v1.5", value="SD_V15"),
            discord.app_commands.Choice(name="🌌 Timeless", value="TIMELESS"),
        ],
        sampler=[
            discord.app_commands.Choice(name="📏 Euler (Recommended)", value="Euler"),
            discord.app_commands.Choice(name="📏 Euler a", value="Euler a"),
            discord.app_commands.Choice(name="📐 Heun", value="Heun"),
            discord.app_commands.Choice(name="💥 DPM++ 2M Karras", value="DPM++ 2M Karras"),
            discord.app_commands.Choice(name="💥 DPM++ SDE Karras", value="DPM++ SDE Karras"),
            discord.app_commands.Choice(name="🔍 DDIM", value="DDIM"),
        ],
    )
    @discord.app_commands.describe(
        prompt="Describe the image you want to generate.",
        model="AI model to use.",
        sampler="Denoising sampler.",
        negative="What the model should avoid generating.",
        seed="Optional seed for reproducible results.",
    )
    async def imagine(
        self,
        interaction: discord.Interaction,
        prompt: str,
        model: discord.app_commands.Choice[str],
        sampler: discord.app_commands.Choice[str],
        negative: str = None,
        seed: int = None,
    ):
        retry_after = _cooldown.check_cooldown(interaction.user.id)
        if retry_after:
            return await interaction.response.send_message(
                f"⏳ Cooldown active. Try again in `{retry_after:.1f}s`.", ephemeral=True
            )

        await interaction.response.defer()

        prompt_lower = prompt.lower()

        if any(w in prompt_lower for w in BLOCKED_WORDS):
            return await interaction.followup.send(
                "🚫 That prompt contains restricted content and cannot be processed.", ephemeral=True
            )

        is_nsfw = any(w in prompt_lower for w in BLACKLISTED_WORDS)
        if is_nsfw and not getattr(interaction.channel, "nsfw", False):
            return await interaction.followup.send(
                "🔞 NSFW prompts can only be used in age-restricted channels.", ephemeral=True
            )

        model_uid = Model[model.value].value[0]

        try:
            imagefileobj = await generate_image_prodia(prompt, model_uid, sampler.value, seed, negative)
        except aiohttp.ClientPayloadError:
            return await interaction.followup.send(
                "🃏 Image generation failed due to a network error. Please try again.", ephemeral=True
            )
        except Exception as e:
            return await interaction.followup.send(f"🎴 Unexpected error: `{e}`", ephemeral=True)

        display_prompt = f"||{prompt}||" if is_nsfw else prompt
        img_file = discord.File(
            imagefileobj,
            filename="image.png",
            spoiler=is_nsfw,
            description=prompt,
        )

        embed = discord.Embed(
            title=f"🎨 Generated by {interaction.user.display_name}",
            color=0xFF4444 if is_nsfw else 0x5865F2,
        )
        embed.add_field(name="Prompt", value=f"- {display_prompt[:1000]}", inline=False)
        embed.add_field(
            name="Details",
            value=f"- **Model:** {model.value}\n- **Sampler:** {sampler.value}\n- **Seed:** {seed}",
            inline=True,
        )
        if negative:
            embed.add_field(name="Negative Prompt", value=f"- {negative[:500]}", inline=False)
        if is_nsfw:
            embed.add_field(name="NSFW", value="- Yes", inline=True)
        embed.set_footer(
            text="Lucky Bot • lucky.gg",
            icon_url=self.bot.user.display_avatar.url,
        )

        await interaction.followup.send(embed=embed, file=img_file, ephemeral=is_nsfw)


async def setup(bot):
    await bot.add_cog(AiStuffCog(bot))

# Lucky Bot — Rewritten
