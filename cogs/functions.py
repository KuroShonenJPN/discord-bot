import json
import random
import discord
import aiohttp
import asyncio
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import sqlite3
import os

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


# === DATABÁZE PRO SLEDOVÁNÍ ===
class MALDatabase:

    def __init__(self):
        self.conn = sqlite3.connect('mal_tracker.db')
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watched_channels (
                channel_id INTEGER PRIMARY KEY,
                guild_id INTEGER,
                username TEXT,
                watch_type TEXT, -- 'user', 'all', 'events'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_notifications (
                anime_id INTEGER,
                channel_id INTEGER,
                notification_type TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (anime_id, channel_id, notification_type)
            )
        ''')
        self.conn.commit()

    def add_watched_channel(self, channel_id, guild_id, username, watch_type):
        cursor = self.conn.cursor()
        cursor.execute(
            '''
            INSERT OR REPLACE INTO watched_channels 
            (channel_id, guild_id, username, watch_type) 
            VALUES (?, ?, ?, ?)
        ''', (channel_id, guild_id, username, watch_type))
        self.conn.commit()

    def remove_watched_channel(self, channel_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM watched_channels WHERE channel_id = ?',
                       (channel_id, ))
        cursor.execute('DELETE FROM sent_notifications WHERE channel_id = ?',
                       (channel_id, ))
        self.conn.commit()

    def get_watched_channels(self, watch_type=None):
        cursor = self.conn.cursor()
        if watch_type:
            cursor.execute(
                'SELECT * FROM watched_channels WHERE watch_type = ?',
                (watch_type, ))
        else:
            cursor.execute('SELECT * FROM watched_channels')
        return cursor.fetchall()

    def get_watched_channel_by_id(self, channel_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM watched_channels WHERE channel_id = ?',
                       (channel_id, ))
        return cursor.fetchone()

    def add_sent_notification(self, anime_id, channel_id, notification_type):
        cursor = self.conn.cursor()
        cursor.execute(
            '''
            INSERT OR IGNORE INTO sent_notifications 
            (anime_id, channel_id, notification_type) 
            VALUES (?, ?, ?)
        ''', (anime_id, channel_id, notification_type))
        self.conn.commit()

    def is_notification_sent(self, anime_id, channel_id, notification_type):
        cursor = self.conn.cursor()
        cursor.execute(
            '''
            SELECT 1 FROM sent_notifications 
            WHERE anime_id = ? AND channel_id = ? AND notification_type = ?
        ''', (anime_id, channel_id, notification_type))
        return cursor.fetchone() is not None


# === HLAVNÍ COG S FUNKCEMI ===
class Functions(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.db = MALDatabase()
        self.mal_checker.start()

    def cog_unload(self):
        self.mal_checker.cancel()

    # === SKUPINY PŘÍKAZŮ ===
    kurobot = discord.app_commands.Group(name="kurobot",
                                         description="Kurobot hlavní příkazy")

    mal = discord.app_commands.Group(name="mal",
                                     description="MyAnimeList příkazy")

    # === AUTOMATICKÁ KONTROLA NOVÝCH ANIME ===
    @tasks.loop(hours=24)
    async def mal_checker(self):
        await self.bot.wait_until_ready()

        watched_channels = self.db.get_watched_channels()
        for channel_data in watched_channels:
            channel_id = channel_data[0]
            guild_id = channel_data[1]
            username = channel_data[2]
            watch_type = channel_data[3]

            channel = self.bot.get_channel(channel_id)

            if not channel:
                continue

            try:
                if watch_type in ['user', 'all']:
                    await self.check_user_plan_to_watch(channel, username)

                if watch_type in ['events', 'all']:
                    await self.check_new_anime_releases(channel)

            except Exception as e:
                print(f"Chyba při kontrole pro {username}: {e}")

    async def check_user_plan_to_watch(self, channel, username):
        """Kontroluje nová anime v Plan to Watch uživatele"""
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                        f'https://api.jikan.moe/v4/users/{username}/animelist?status=plan_to_watch'
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        new_releases = []

                        for anime in data['data']:
                            anime_id = anime['anime']['mal_id']

                            if not self.db.is_notification_sent(
                                    anime_id, channel.id, 'user_plan'):
                                async with session.get(
                                        f'https://api.jikan.moe/v4/anime/{anime_id}'
                                ) as anime_response:
                                    if anime_response.status == 200:
                                        anime_data = await anime_response.json(
                                        )
                                        anime_info = anime_data['data']

                                        if anime_info[
                                                'status'] == 'Currently Airing':
                                            new_releases.append(anime_info)
                                            self.db.add_sent_notification(
                                                anime_id, channel.id,
                                                'user_plan')

                        return new_releases
            return []
        except asyncio.TimeoutError:
            print(f"Timeout při kontrole plan to watch pro {username}")
            return []
        except Exception as e:
            print(f"Chyba při kontrole plan to watch: {e}")
            return []

    async def check_new_anime_releases(self, channel, days_back=1):
        """Kontroluje nová anime z MAL events"""
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Získání aktuální sezóny a roku
                now = datetime.now()
                current_season = self.get_season(now.month)
                current_year = now.year

                # Pokud chceme starší data, upravíme sezónu/rok
                if days_back > 7:  # Pokud chceme více než týden zpět
                    # Přizpůsobíme sezónu a rok
                    target_date = now - timedelta(days=days_back)
                    current_season = self.get_season(target_date.month)
                    current_year = target_date.year

                async with session.get(
                        f'https://api.jikan.moe/v4/seasons/{current_year}/{current_season}'
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        new_releases = []

                        for anime in data['data']:
                            anime_id = anime['mal_id']

                            # Kontrola data vydání
                            if self.is_recent_release(anime, days_back):
                                if not self.db.is_notification_sent(
                                        anime_id, channel.id, 'new_release'):
                                    new_releases.append(anime)
                                    self.db.add_sent_notification(
                                        anime_id, channel.id, 'new_release')

                        return new_releases
            return []
        except asyncio.TimeoutError:
            print("Timeout při kontrole nových anime")
            return []
        except Exception as e:
            print(f"Chyba při kontrole nových anime: {e}")
            return []

    def get_season(self, month):
        """Určí sezónu podle měsíce"""
        if month in [1, 2, 3]:
            return 'winter'
        elif month in [4, 5, 6]:
            return 'spring'
        elif month in [7, 8, 9]:
            return 'summer'
        else:
            return 'fall'

    def is_recent_release(self, anime, days_back):
        """Kontroluje zda anime vyšlo v posledních X dnech"""
        if not anime.get('aired', {}).get('from'):
            return False

        try:
            aired_date_str = anime['aired']['from']
            if not aired_date_str:
                return False

            # Převod stringu na datum
            aired_date = datetime.fromisoformat(
                aired_date_str.replace('Z', '+00:00'))
            current_date = datetime.now().replace(tzinfo=aired_date.tzinfo)

            # Rozdíl ve dnech
            days_diff = (current_date - aired_date).days

            return 0 <= days_diff <= days_back
        except:
            return False

    # === MAL STATISTIKY PŘÍKAZ ===
    @mal.command(name="stats",
                 description="Zobrazí statistiky uživatele z MyAnimeList")
    async def mal_stats(self, interaction: discord.Interaction, username: str):
        """Zobrazí MAL statistiky pro daného uživatele"""
        await interaction.response.defer()

        try:
            # Přidání timeoutu
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Testovací hláška
                await interaction.followup.send("🔄 Načítám data z MAL...",
                                                ephemeral=True)

                async with session.get(
                        f'https://api.jikan.moe/v4/users/{username}/statistics'
                ) as response:
                    if response.status == 200:
                        stats_data = await response.json()
                    else:
                        await interaction.followup.send(
                            "❌ Uživatel nebyl nalezen nebo došlo k chybě!")
                        return

                async with session.get(
                        f'https://api.jikan.moe/v4/users/{username}/full'
                ) as response:
                    if response.status == 200:
                        profile_data = await response.json()
                    else:
                        profile_data = None

            stats = stats_data['data']['anime']
            mal_profile_url = f"https://myanimelist.net/profile/{username}"

            embed = discord.Embed(
                title="📊 MAL Statistiky",
                description=f"Profil: **[ {username} ]({mal_profile_url})**",
                color=0x2E51A2,
                timestamp=datetime.now())

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

            if profile_data and 'images' in profile_data['data']:
                profile_url = profile_data['data']['images']['jpg'][
                    'image_url']
                embed.set_thumbnail(url=profile_url)

            embed.set_footer(text="Data z MyAnimeList via Jikan API")

            await interaction.followup.send(embed=embed)

        except asyncio.TimeoutError:
            await interaction.followup.send(
                "⏰ Timeout: MAL API neodpovídá. Zkus to prosím za chvíli.")
        except aiohttp.ClientError:
            await interaction.followup.send(
                "🔌 Chyba připojení: Nelze se připojit k MAL API.")
        except Exception as e:
            await interaction.followup.send(
                f"❌ Došlo k neočekávané chybě: {str(e)}")

    # === SLEDOVÁNÍ NOTIFIKACÍ ===
    @mal.command(name="watch",
                 description="Spustí sledování nových anime z MAL")
    async def mal_watch(self,
                        interaction: discord.Interaction,
                        watch_type: str,
                        username: str = None):
        """Spustí sledování nových anime"""

        if watch_type not in ['user', 'events', 'all']:
            await interaction.response.send_message(
                "❌ Neplatný typ sledování. Použij: `user`, `events` nebo `all`",
                ephemeral=True)
            return

        if watch_type in ['user', 'all'] and not username:
            await interaction.response.send_message(
                "❌ Pro tento typ sledování musíš zadat MAL username",
                ephemeral=True)
            return

        if watch_type == 'events':
            username = 'events'

        # Uložení nastavení
        self.db.add_watched_channel(interaction.channel_id,
                                    interaction.guild_id, username, watch_type)

        # Popisy typů sledování
        type_descriptions = {
            'user':
            f"sledování Plan to Watch uživatele **{username}**",
            'events':
            "sledování všech nových anime z MAL",
            'all':
            f"sledování Plan to Watch uživatele **{username}** i všech nových anime"
        }

        embed = discord.Embed(
            title="🔔 Sledování MAL spuštěno",
            description=f"Bylo spuštěno {type_descriptions[watch_type]}.",
            color=0x00FF00,
            timestamp=datetime.now())

        embed.add_field(name="📋 Detaily",
                        value=f"**Kanál:** <#{interaction.channel_id}>\n"
                        f"**Typ:** {watch_type}\n"
                        f"**Kontrola:** Každých 24 hodin",
                        inline=False)

        embed.set_footer(text="Použij /mal stop pro zastavení sledování")

        await interaction.response.send_message(embed=embed)

    # === ZASTAVENÍ SLEDOVÁNÍ ===
    @mal.command(name="stop",
                 description="Zastaví sledování MAL notifikací v tomto kanálu")
    async def mal_stop(self, interaction: discord.Interaction):
        """Zastaví sledování v aktuálním kanálu"""

        self.db.remove_watched_channel(interaction.channel_id)

        embed = discord.Embed(
            title="🔕 Sledování zastaveno",
            description=
            "Sledování MAL notifikací bylo zastaveno v tomto kanálu.",
            color=0xFF0000,
            timestamp=datetime.now())

        await interaction.response.send_message(embed=embed)

    # === OKAMŽITÁ KONTROLA - POUZE PRO ADMINY ===
    @mal.command(name="checknow",
                 description="OKAMŽITÁ KONTROLA - Pouze pro administrátory")
    @commands.has_permissions(administrator=True)
    async def mal_checknow(self,
                           interaction: discord.Interaction,
                           days: int = 1):
        """Okamžitá kontrola nových anime - pouze pro adminy"""
        await interaction.response.defer()

        # Odeslání průběhové zprávy a uložení její reference
        progress_msg = await interaction.followup.send(
            f"🔍 Kontroluji posledních **{days}** dní...")

        try:
            # OKAMŽITÁ ODPOVĚĎ - maximálně 15 vteřin (více času na více anime)
            async with asyncio.timeout(15):
                # Získání nastavení pro tento kanál
                channel_data = self.db.get_watched_channel_by_id(
                    interaction.channel_id)

                if not channel_data:
                    embed = discord.Embed(
                        title="❌ Chyba",
                        description=
                        "Tento kanál nemá nastavené sledování MAL notifikací.",
                        color=0xFF0000)
                    # Smazání průběhové zprávy před odesláním chyby
                    await progress_msg.delete()
                    await interaction.followup.send(embed=embed)
                    return

                # SPRÁVNÉ UNPACKOVÁNÍ DAT - použijeme indexy místo unpackingu
                channel_id = channel_data[0]
                guild_id = channel_data[1]
                username = channel_data[2]
                watch_type = channel_data[3]

                found_any = False
                results_embed = discord.Embed(
                    title="🔍 Výsledky kontroly MAL",
                    description=f"Kontrola za posledních **{days}** dní",
                    color=0x2E51A2,
                    timestamp=datetime.now())

                # Kontrola Plan to Watch
                if watch_type in ['user', 'all']:
                    user_releases = await self.check_user_plan_to_watch(
                        interaction.channel, username)

                    if user_releases:
                        found_any = True
                        results_embed.add_field(
                            name="🎉 Nová anime z Plan to Watch",
                            value=
                            f"**{len(user_releases)}** nových anime začalo vycházet!",
                            inline=False)

                        # ZVÝŠENO NA 10 ANIME
                        for i, anime in enumerate(user_releases[:10], 1):
                            results_embed.add_field(
                                name=f"🎬 {i}. {anime['title']}",
                                value=
                                f"⭐ {anime.get('score', 'N/A')} | [MAL]({anime['url']})",
                                inline=False)

                        if len(user_releases) > 10:
                            results_embed.add_field(
                                name="📝 Další anime",
                                value=
                                f"Zobrazeno 10 z {len(user_releases)} anime",
                                inline=False)
                    else:
                        results_embed.add_field(
                            name="📋 Plan to Watch",
                            value="❌ Žádná nová anime z tvého seznamu",
                            inline=True)

                # Kontrola nových anime z MAL
                if watch_type in ['events', 'all']:
                    mal_releases = await self.check_new_anime_releases(
                        interaction.channel, days_back=days)

                    if mal_releases:
                        found_any = True
                        results_embed.add_field(
                            name="🔥 Nová anime z MAL",
                            value=
                            f"**{len(mal_releases)}** nových anime za posledních {days} dní",
                            inline=False)

                        # ZVÝŠENO NA 10 ANIME
                        for i, anime in enumerate(mal_releases[:10], 1):
                            aired_date = "Dnes"
                            if anime.get('aired', {}).get('from'):
                                try:
                                    aired_str = anime['aired']['from']
                                    aired_date = datetime.fromisoformat(
                                        aired_str.replace(
                                            'Z',
                                            '+00:00')).strftime('%d.%m.%Y')
                                except:
                                    aired_date = "Neznámé"

                            results_embed.add_field(
                                name=f"🎬 {i}. {anime['title']}",
                                value=
                                f"📅 {aired_date} | ⭐ {anime.get('score', 'N/A')} | [MAL]({anime['url']})",
                                inline=False)

                        if len(mal_releases) > 10:
                            results_embed.add_field(
                                name="📝 Další anime",
                                value=
                                f"Zobrazeno 10 z {len(mal_releases)} anime",
                                inline=False)
                    else:
                        results_embed.add_field(
                            name="🔥 Nová anime z MAL",
                            value=
                            f"❌ Žádná nová anime za posledních {days} dní",
                            inline=True)

                if not found_any:
                    results_embed.add_field(
                        name="💤 Žádné novinky",
                        value=
                        "Bohužel nebylo nalezeno žádné nové anime v zadaném období.",
                        inline=False)

                results_embed.set_footer(
                    text=
                    f"Kontrola spuštěna administrátorem | Uživatel: {username}"
                )

                # Smazání průběhové zprávy a odeslání výsledků
                await progress_msg.delete()
                await interaction.followup.send(embed=results_embed)

        except asyncio.TimeoutError:
            # Pokud to trvá déle než 15 vteřin, pošleme chybu
            await progress_msg.delete()
            embed = discord.Embed(
                title="⏰ Timeout",
                description=
                "Kontrola trvala příliš dlouho. API pravděpodobně neodpovídá.",
                color=0xFF0000)
            embed.add_field(
                name="🔧 Řešení",
                value=
                "Zkus to prosím za pár minut nebo zkontroluj jestli MAL API funguje",
                inline=False)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            # Jakákoliv jiná chyba
            await progress_msg.delete()
            embed = discord.Embed(title="❌ Neočekávaná chyba",
                                  description="Během kontroly došlo k chybě.",
                                  color=0xFF0000)
            embed.add_field(name="Chyba", value=str(e), inline=False)
            await interaction.followup.send(embed=embed)

    # === KUROBOT PŘÍKAZY ===
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


# === NASTAVENÍ COG ===
async def setup(bot):
    await bot.add_cog(Functions(bot))
