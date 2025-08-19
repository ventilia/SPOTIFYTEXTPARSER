# Импортируем необходимые библиотеки
import sys  # Для аргументов командной строки
import time  # Для задержек в синхронизированном выводе
import requests  # Для HTTP-запросов (метаданные, API)
import base64  # Для кодирования client_id:secret
import spotipy  # Библиотека для Spotify API
from spotipy.oauth2 import SpotifyClientCredentials  # Для аутентификации в Spotify
import lyricsgenius  # Библиотека для Genius API
import re  # Для парсинга URL и LRC

# Хардкодим токены (в реальности лучше использовать .env или secrets manager)
SPOTIFY_CLIENT_ID = '3a9fe134095448b092e2c8dd95f209f0'
SPOTIFY_CLIENT_SECRET = 'e3dc93868af24f69b2a6efbe623814f6'
GENIUS_CLIENT_ID = '7e39MbC9H9y-G0sj-QcfvVrDo27_4So8FcILomWPVWzsXOgrsecL8oeX9iTiieNG'
GENIUS_CLIENT_SECRET = 'KItl2hbI7A0v1-_pSqf5LvS_daktJ9soWoyHcKPNsMJqJqui7_0kE3-CoBt7c4-u0mtHcWIhftpfdnJMx7hXew'

# ANSI escape-коды для цветов и стилей (bold)
COLORS = [
    '\033[31m',  # Красный
    '\033[32m',  # Зеленый
    '\033[33m',  # Желтый
    '\033[34m',  # Синий
    '\033[35m',  # Фиолетовый
    '\033[36m',  # Циан
]
BOLD = '\033[1m'  # Жирный текст
RESET = '\033[0m'  # Сброс стилей

# Функция для получения access token Spotify (Client Credentials Flow)
def get_spotify_access_token():
    """
    Получаем access token для Spotify API.
    Используем client_id и client_secret для аутентификации.
    Возвращает token или None при ошибке.
    """
    auth_url = 'https://accounts.spotify.com/api/token'
    auth_header = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode('utf-8')).decode('utf-8')
    headers = {
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {'grant_type': 'client_credentials'}
    try:
        response = requests.post(auth_url, headers=headers, data=data, timeout=10)
        response.raise_for_status()  # Проверяем на ошибки HTTP
        return response.json()['access_token']
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении Spotify token: {e}")
        return None

# Функция для получения access token Genius (Client Credentials)
def get_genius_access_token():
    """
    Получаем access token для Genius API.
    Используем client_id и client_secret.
    Возвращает token или None при ошибке.
    """
    auth_url = 'https://api.genius.com/oauth/token'
    data = {
        'grant_type': 'client_credentials',
        'client_id': GENIUS_CLIENT_ID,
        'client_secret': GENIUS_CLIENT_SECRET
    }
    try:
        response = requests.post(auth_url, data=data, timeout=10)
        response.raise_for_status()
        return response.json()['access_token']
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении Genius token: {e}")
        return None

# Функция для парсинга track_id из Spotify URL
def parse_track_id(url):
    """
    Извлекаем track_id из URL Spotify.
    Пример: https://open.spotify.com/track/2HRqTpkrJO5ggZyyK6NPWz?si=... -> '2HRqTpkrJO5ggZyyK6NPWz'
    Поддерживает параметры после ID.
    """
    match = re.search(r'track/([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    else:
        raise ValueError("Неверный URL Spotify. Должен быть вида https://open.spotify.com/track/ID")

# Функция для получения метаданных трека из Spotify
def get_track_metadata(track_id):
    """
    Получаем имя трека и артиста из Spotify API.
    Используем spotipy для удобства.
    Возвращает (title, artist) или (None, None) при ошибке.
    """
    try:
        credentials = SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET)
        sp = spotipy.Spotify(auth_manager=credentials)
        track = sp.track(track_id)
        return track['name'], track['artists'][0]['name']  # Берем первого артиста (основного)
    except Exception as e:
        print(f"Ошибка при получении метаданных трека: {e}")
        return None, None

# Функция для получения synced lyrics из LRCLIB.net в формате LRC
def get_lrc_lyrics(title, artist):
    """
    Запрашиваем synced lyrics из LRCLIB.net.
    Endpoint: https://lrclib.net/api/get?artist_name={artist}&track_name={title}
    Возвращает список dict {'startTimeMs': int, 'words': str} или None, если не найдено.
    Если syncedLyrics пусто, возвращаем None.
    """
    api_url = f"https://lrclib.net/api/get?artist_name={artist}&track_name={title}"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'syncedLyrics' in data and data['syncedLyrics']:
            # Парсим LRC: строки вида [mm:ss.xx] words
            lines = []
            lrc_lines = data['syncedLyrics'].splitlines()
            for lrc_line in lrc_lines:
                match = re.match(r'\[(\d+):(\d+\.\d+)\]\s*(.*)', lrc_line.strip())
                if match:
                    minutes, seconds, words = match.groups()
                    timestamp_ms = (int(minutes) * 60 * 1000) + (float(seconds) * 1000)
                    if words:  # Пропускаем пустые строки
                        lines.append({'startTimeMs': str(int(timestamp_ms)), 'words': words})
            if lines:
                return lines
        print("Synced lyrics не найдены в LRCLIB.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе LRCLIB: {e}")
        return None

# Функция для получения plain lyrics из Genius
def get_plain_lyrics(title, artist, genius_token):
    """
    Получаем обычный текст песни из Genius API.
    Используем lyricsgenius библиотеку.
    Возвращает текст или None.
    """
    try:
        genius = lyricsgenius.Genius(genius_token, timeout=10, retries=3)
        song = genius.search_song(title, artist)
        if song:
            return song.lyrics
        else:
            print("Lyrics не найдены в Genius.")
            return None
    except Exception as e:
        print(f"Ошибка при запросе Genius: {e}")
        return None

# Функция для динамического вывода synced lyrics с цветами и bold
def display_synced_lyrics(lines):
    """
    Выводим synced lyrics с задержками по времени.
    Используем time.sleep для имитации реального времени.
    Перезаписываем строку в консоли для "караоке-эффекта".
    Каждая строка — bold и другого цвета (чередование).
    Добавляем обработку для плавности и пустых строк.
    """
    start_time = time.time() * 1000  # Текущее время в ms
    num_colors = len(COLORS)
    for idx, line in enumerate(lines):
        try:
            timestamp_ms = int(line['startTimeMs'])
            words = line['words'].strip()
            if not words:
                continue  # Пропускаем пустые
        except (KeyError, ValueError):
            continue  # Пропускаем некорректные строки

        # Вычисляем задержку до следующей строки
        current_ms = (time.time() * 1000) - start_time
        delay_ms = timestamp_ms - current_ms
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        # Выбираем цвет по индексу (цикл)
        color = COLORS[idx % num_colors]
        styled_words = f"{color}{BOLD}{words}{RESET}"

        # Выводим строку с перезаписью (ljust для очистки остатков предыдущей строки)
        sys.stdout.write(f"\r{styled_words.ljust(100)}")
        sys.stdout.flush()

    print("\nКонец песни.")  # Финальный перевод строки

# Функция для вывода plain lyrics с цветами и bold
def display_plain_lyrics(lyrics):
    """
    Печатаем весь текст с чередованием цветов по строкам.
    Каждая строка — bold и другого цвета.
    Добавляем атрибуцию Genius.
    """
    lines = lyrics.splitlines()  # Разбиваем на строки
    num_colors = len(COLORS)
    for idx, line in enumerate(lines):
        stripped_line = line.strip()
        if not stripped_line:  # Пропускаем пустые строки
            print()  # Просто новая строка
            continue
        color = COLORS[idx % num_colors]
        styled_line = f"{color}{BOLD}{stripped_line}{RESET}"
        print(styled_line)
    print("\nLyrics from Genius.")

# Главная функция
def main():
    if len(sys.argv) != 2:
        print("Использование: python spotify_lyrics.py <Spotify URL>")
        sys.exit(1)

    url = sys.argv[1]
    try:
        track_id = parse_track_id(url)
        print(f"Извлечен track_id: {track_id}")

        title, artist = get_track_metadata(track_id)
        if not title or not artist:
            print("Не удалось получить метаданные трека.")
            sys.exit(1)
        print(f"Трек: {title} by {artist}")

        # Сначала пробуем synced из LRCLIB
        synced_lines = get_lrc_lyrics(title, artist)
        if synced_lines:
            print("Нашли synced lyrics в LRCLIB. Выводим с синхронизацией...")
            display_synced_lyrics(synced_lines)
        else:
            # Fallback на Genius plain
            genius_token = get_genius_access_token()
            if not genius_token:
                sys.exit(1)
            plain_lyrics = get_plain_lyrics(title, artist, genius_token)
            if plain_lyrics:
                print("Synced не найдены, выводим plain lyrics из Genius...")
                display_plain_lyrics(plain_lyrics)
            else:
                print("Lyrics не найдены нигде.")

    except ValueError as ve:
        print(f"Ошибка валидации: {ve}")
        sys.exit(1)
    except Exception as e:
        print(f"Общая ошибка: {e}")
        sys.exit(1)

# Запуск главной функции
if __name__ == "__main__":
    main()