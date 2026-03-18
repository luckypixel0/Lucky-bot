import base64
import binascii
import codecs
import secrets

from discord.ext import commands


class Encryption(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _encryptout(self, ctx, label: str, result) -> None:
        if isinstance(result, bytes):
            try:
                result = result.decode("UTF-8")
            except Exception:
                result = repr(result)
        if len(result) > 190000:
            await ctx.send(f"🃏 Result was too long to display, **{ctx.author.name}**.")
            return
        await ctx.send(f"📑 **{label}**```fix\n{result}```")

    # ── encode group ──────────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    async def encode(self, ctx):
        """All encode methods."""
        await ctx.send_help("encode")

    @encode.command(name="base32", aliases=["b32"])
    async def encode_base32(self, ctx, *, txtinput: commands.clean_content):
        """Encode text to Base32."""
        await self._encryptout(ctx, "Text → Base32", base64.b32encode(txtinput.encode("UTF-8")))

    @encode.command(name="base64", aliases=["b64"])
    async def encode_base64(self, ctx, *, txtinput: commands.clean_content):
        """Encode text to Base64."""
        await self._encryptout(ctx, "Text → Base64", base64.urlsafe_b64encode(txtinput.encode("UTF-8")))

    @encode.command(name="rot13", aliases=["r13"])
    async def encode_rot13(self, ctx, *, txtinput: commands.clean_content):
        """Encode text with ROT13."""
        await self._encryptout(ctx, "Text → ROT13", codecs.decode(txtinput, "rot_13"))

    @encode.command(name="hex")
    async def encode_hex(self, ctx, *, txtinput: commands.clean_content):
        """Encode text to hexadecimal."""
        await self._encryptout(ctx, "Text → Hex", binascii.hexlify(txtinput.encode("UTF-8")))

    @encode.command(name="base85", aliases=["b85"])
    async def encode_base85(self, ctx, *, txtinput: commands.clean_content):
        """Encode text to Base85."""
        await self._encryptout(ctx, "Text → Base85", base64.b85encode(txtinput.encode("UTF-8")))

    @encode.command(name="ascii85", aliases=["a85"])
    async def encode_ascii85(self, ctx, *, txtinput: commands.clean_content):
        """Encode text to ASCII85."""
        await self._encryptout(ctx, "Text → ASCII85", base64.a85encode(txtinput.encode("UTF-8")))

    # ── decode group ──────────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    async def decode(self, ctx):
        """All decode methods."""
        await ctx.send_help("decode")

    @decode.command(name="base32", aliases=["b32"])
    async def decode_base32(self, ctx, *, txtinput: str):
        """Decode Base32 to text."""
        try:
            await self._encryptout(ctx, "Base32 → Text", base64.b32decode(txtinput.encode("UTF-8")))
        except Exception:
            await ctx.send("🃏 Invalid Base32 input.")

    @decode.command(name="base64", aliases=["b64"])
    async def decode_base64(self, ctx, *, txtinput: str):
        """Decode Base64 to text."""
        try:
            await self._encryptout(ctx, "Base64 → Text", base64.urlsafe_b64decode(txtinput.encode("UTF-8")))
        except Exception:
            await ctx.send("🃏 Invalid Base64 input.")

    @decode.command(name="rot13", aliases=["r13"])
    async def decode_rot13(self, ctx, *, txtinput: str):
        """Decode ROT13 to text."""
        try:
            await self._encryptout(ctx, "ROT13 → Text", codecs.decode(txtinput, "rot_13"))
        except Exception:
            await ctx.send("🃏 Invalid ROT13 input.")

    @decode.command(name="hex")
    async def decode_hex(self, ctx, *, txtinput: str):
        """Decode hexadecimal to text."""
        try:
            await self._encryptout(ctx, "Hex → Text", binascii.unhexlify(txtinput.encode("UTF-8")))
        except Exception:
            await ctx.send("🃏 Invalid hex input.")

    @decode.command(name="base85", aliases=["b85"])
    async def decode_base85(self, ctx, *, txtinput: str):
        """Decode Base85 to text."""
        try:
            await self._encryptout(ctx, "Base85 → Text", base64.b85decode(txtinput.encode("UTF-8")))
        except Exception:
            await ctx.send("🃏 Invalid Base85 input.")

    @decode.command(name="ascii85", aliases=["a85"])
    async def decode_ascii85(self, ctx, *, txtinput: str):
        """Decode ASCII85 to text."""
        try:
            await self._encryptout(ctx, "ASCII85 → Text", base64.a85decode(txtinput.encode("UTF-8")))
        except Exception:
            await ctx.send("🃏 Invalid ASCII85 input.")

    # ── utility ───────────────────────────────────────────────────────────────

    @commands.command()
    async def password(self, ctx):
        """Generate a secure random password and DM it to you."""
        if ctx.guild is not None:
            await ctx.send(f"🔒 Sending you a private message with your generated password, **{ctx.author.name}**.")
        await ctx.author.send(f"🎁 **Your generated password:**\n`{secrets.token_urlsafe(18)}`")


async def setup(bot):
    await bot.add_cog(Encryption(bot))

# Lucky Bot — Rewritten
