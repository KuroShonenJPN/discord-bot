import json
import random
import discord
from discord.ext import commands

# === Převodník Enchant Table (SGA) fontu ===
LATIN_TO_SGA = {
    "a": "ᔑ", "b": "ʖ", "c": "ᓵ", "d": "↸", "e": "ᒷ",
    "f": "⎓", "g": "⎔", "h": "ᓭ", "i": "ℸ", "j": "⚍",
    "k": "⍊", "l": "∷", "m": "ᑑ", "n": "∴", "o": "ᓮ",
    "p": "ᑲ", "q": "ᓷ", "r": "ᓰ", "s": "ᓹ", "t": "ᓻ",
    "u": "ᓿ", "v": "⍖", "w": "ᒷ̸", "x": "⍁", "y": "⍂", "z": "⍃"
}
SGA_TO_LATIN = {v: k for k, v in LATIN_TO_SGA.items()}

class Functions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    kurobot = discord.app_commands.Group(
        name="kurobot",
        description="Kurobot hlavní příkazy"
    )

    @kurobot.command(
        name="nadavka",
        description="Vygeneruje náhodnou nadávku na vybraného uživatele"
    )
    async def nadavka(self, interaction: discord.Interaction, user: discord.Member):
        with open("words.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        odborny = random.choice(data["odborne"])
        vulgar = random.choice(data["vulgarismy"])
        await interaction.response.send_message(
            f"{user.mention}, ty {odborny} {vulgar}!", ephemeral=False
        )

    @kurobot.command(
        name="encrypt",
        description="Zakóduje text do minecraft enchanting (SGA) fontu"
    )
    async def encrypt(self, interaction: discord.Interaction, text: str):
        result = ''.join(LATIN_TO_SGA.get(c.lower(), c) for c in text)
        await interaction.response.send_message(result)

    @kurobot.command(
        name="decode",
        description="Dekóduje text z minecraft enchanting (SGA) fontu do latinky"
    )
    async def decode(self, interaction: discord.Interaction, text: str):
        result = ""
        i = 0
        while i < len(text):
            match = None
            for length in [2, 1]:
                symbol = text[i:i + length]
                if symbol in SGA_TO_LATIN:
                    result += SGA_TO_LATIN[symbol]
                    i += length
                    match = True
                    break
            if not match:
                result += text[i]
                i += 1
        await interaction.response.send_message(result)

async def setup(bot):
    await bot.add_cog(Functions(bot))
