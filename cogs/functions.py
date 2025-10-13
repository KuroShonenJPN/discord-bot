import json
import random
import discord
import aiohttp
from discord.ext import commands
from datetime import datetime

# === PŘEVODNÍK ENCHANT TABLE (SGA) FONTU ===
LATIN_TO_SGA = {
    "a": "ᔑ",
    "b": "ʖ",
    "c": "ᓵ",
    "d": "↸",
    "e": "ᒷ",
    "f": "⎓",
    "g": "⎔",
    "h": "ᓭ",
    "i": "ℸ",
    "j": "⚍",
    "k": "⍊",
    "l": "∷",
    "m": "ᑑ",
    "n": "∴",
    "o": "ᓮ",
    "p": "ᑲ",
    "q": "ᓷ",
    "r": "ᓰ",
    "s": "ᓹ",
    "t": "ᓻ",
    "u": "ᓿ",
    "v": "⍖",
    "w": "ᒷ̸",
    "x": "⍁",
    "y": "⍂",
    "z": "⍃"
}
SGA_TO_LATIN = {v: k for k, v in LATIN_TO_SGA.items()}


# === HLAVNÍ COG S FUNKCEMI ===
class Functions(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # === KUROBOT SKUPINA PŘÍKAZŮ ===
    kurobot = discord.app_commands.Group(name="kurobot",
                                         description="Kurobot hlavní příkazy")

    # === NADÁVKA PŘÍKAZ ===
    @kurobot.command(
        name="nadavka",
        description="Vygeneruje náhodnou nadávku na vybraného uživatele")
    async def nadavka(self, interaction: discord.Interaction,
                      user: discord.Member):
        try:
            with open("words.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            odborny = random.choice(data["odborne"])
            vulgar = random.choice(data["vulgarismy"])
            await interaction.response.send_message(
                f"{user.mention}, ty {odborny} {vulgar}!", ephemeral=False)
        except FileNotFoundError:
            await interaction.response.send_message("Slovník nebyl nalezen.",
                                                    ephemeral=True)
        except KeyError:
            await interaction.response.send_message(
                "Slovník má neplatný formát.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Došlo k chybě: {e}",
                                                    ephemeral=True)

    # === ŠIFROVÁNÍ PŘÍKAZ ===
    @kurobot.command(
        name="encrypt",
        description="Zakóduje text do minecraft enchanting (SGA) fontu")
    async def encrypt(self, interaction: discord.Interaction, text: str):
        try:
            if len(text) > 1000:
                await interaction.response.send_message(
                    "Text je příliš dlouhý (max 1000 znaků)", ephemeral=True)
                return

            result = ''.join(LATIN_TO_SGA.get(c.lower(), c) for c in text)
            await interaction.response.send_message(result)
        except Exception as e:
            await interaction.response.send_message(f"Došlo k chybě: {e}",
                                                    ephemeral=True)

    # === DEŠIFROVÁNÍ PŘÍKAZ ===
    @kurobot.command(
        name="decode",
        description=
        "Dekóduje text z minecraft enchanting (SGA) fontu do latinky")
    async def decode(self, interaction: discord.Interaction, text: str):
        try:
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
        except Exception as e:
            await interaction.response.send_message(f"Došlo k chybě: {e}",
                                                    ephemeral=True)

    # === MAL STATISTIKY PŘÍKAZ ===
    @discord.app_commands.command(
        name="mal", description="Zobrazí statistiky uživatele z MyAnimeList")
    async def mal_stats(self, interaction: discord.Interaction, username: str):
        """Zobrazí MAL statistiky pro daného uživatele"""
        await interaction.response.defer()

        try:
            async with aiohttp.ClientSession() as session:
                # Získání statistik uživatele
                async with session.get(
                        f'https://api.jikan.moe/v4/users/{username}/statistics'
                ) as response:
                    if response.status == 200:
                        stats_data = await response.json()
                    else:
                        await interaction.followup.send(
                            "❌ Uživatel nebyl nalezen nebo došlo k chybě!")
                        return

                # Získání profilových informací
                async with session.get(
                        f'https://api.jikan.moe/v4/users/{username}/full'
                ) as response:
                    if response.status == 200:
                        profile_data = await response.json()
                    else:
                        profile_data = None

            # Zpracování dat
            stats = stats_data['data']['anime']

            # Vytvoření URL odkazu na MAL profil
            mal_profile_url = f"https://myanimelist.net/profile/{username}"

            # Vytvoření embedu - jméno je klikatelné v popisku
            embed = discord.Embed(
                title="📊 MAL Statistiky",
                description=f"Profil: **[ {username} ]({mal_profile_url})**",
                color=0x2E51A2,  # MAL modrá barva
                timestamp=datetime.now())

            # Přidání polí s statistikami
            embed.add_field(name="🎬 Celkem Anime",
                            value=f"**{stats['completed']}** dokončených\n"
                            f"**{stats['watching']}** sleduji\n"
                            f"**{stats['plan_to_watch']}** v plánu\n"
                            f"**{stats['on_hold']}** pozastaveno\n"
                            f"**{stats['dropped']}** dropped",
                            inline=True)

            embed.add_field(
                name="📈 Detaily",
                value=f"**{stats['total_entries']}** položek celkem\n"
                f"**{stats['episodes_watched']}** zhlédnutých epizod\n"
                f"**{stats['days_watched']}** dní sledování\n"
                f"**{stats['mean_score']}** průměrné hodnocení",
                inline=True)

            # Přidání obrázku profilu pokud existuje
            if profile_data and 'images' in profile_data['data']:
                profile_url = profile_data['data']['images']['jpg'][
                    'image_url']
                embed.set_thumbnail(url=profile_url)

            embed.set_footer(text="Data z MyAnimeList via Jikan API")

            await interaction.followup.send(embed=embed)

        except aiohttp.ClientError:
            await interaction.followup.send(
                "❌ Chyba při připojování k MAL API!")
        except KeyError:
            await interaction.followup.send("❌ Neplatná data z API!")
        except Exception as e:
            await interaction.followup.send(f"❌ Došlo k neočekávané chybě: {e}"
                                            )


# === NASTAVENÍ COG ===
async def setup(bot):
    await bot.add_cog(Functions(bot))
