import json
import random
import discord
from discord.ext import commands

class Insults(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="nadavka", description="Vygeneruje náhodnou nadávku na vybraného uživatele")
    async def nadavka(self, interaction: discord.Interaction, user: discord.Member):
        with open("words.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        odborny = random.choice(data["odborne"])
        vulgar = random.choice(data["vulgarismy"])
        await interaction.response.send_message(
            f"{user.mention}, ty {odborny} {vulgar}!",
            ephemeral=False  # když bys chtěl, aby to viděl jen vyvolávač, dej True
        )

async def setup(bot):
    await bot.add_cog(Insults(bot))