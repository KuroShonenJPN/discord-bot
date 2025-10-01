# Discord Bot - KuroBot

## Overview
Discord bot s českými příkazy. Bot generuje kreativní nadávky kombinací odborných termínů a vulgarismů a umí překládat text do Minecraft enchanting table fontu (SGA).

## Project Architecture
- **bot.py**: Hlavní soubor bota - inicializuje Discord bota, načítá cogs, sync příkazů
- **cogs/functions.py**: Obsahuje slash command group `/kurobot` s těmito příkazy:
  - `nadavka @user` - Generuje náhodnou nadávku
  - `encrypt <text>` - Zakóduje text do Minecraft enchanting (SGA) fontu
  - `decode <text>` - Dekóduje text ze SGA fontu zpět do latinky
- **words.json**: Datový soubor s dvěma poli:
  - `odborne`: Odborné/vědecké přídavná jména
  - `vulgarismy`: Vulgarismy
- **requirements.txt**: Python dependencies (discord.py, python-dotenv)

## Setup Requirements
1. **DISCORD_TOKEN**: Token Discord bota
   - Získán z: https://discord.com/developers/applications
   
2. **Discord Bot Permissions**:
   - Bot potřebuje scope: `bot` a `applications.commands`
   - Invite link vygenerovat v Developer Portal → OAuth2 → URL Generator

## Dostupné příkazy
- `/kurobot nadavka @user` - Vygeneruje náhodnou nadávku na vybraného uživatele
- `/kurobot encrypt <text>` - Zakóduje text do Minecraft enchanting table fontu
- `/kurobot decode <text>` - Dekóduje SGA font zpět do normálního textu

## Running the Bot
Bot běží automaticky přes "Discord Bot" workflow. Po přidání DISCORD_TOKEN do .env se bot připojí k Discordu a je připraven k použití.

## Language
Czech (čeština)
