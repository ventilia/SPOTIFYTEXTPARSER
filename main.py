# Импортируем необходимые библиотеки
import sys  # Для аргументов командной строки
import time  # Для задержек в синхронизированном выводе
import requests  # Для HTTP-запросов (токены, API)
import base64  # Для кодирования client_id:secret
import json  # Для парсинга JSON
import spotipy  # Библиотека для Spotify API
from spotipy.oauth2 import SpotifyClientCredentials  # Для аутентификации в Spotify
import lyricsgenius  # Библиотека для Genius API
import re  # Для парсинга URL

# Хардкодим токены, как просил (в реальности лучше в .env)
SPOTIFY_CLIENT_ID = '3a9fe134095448b092e2c8dd95f209f0'
SPOTIFY_CLIENT_SECRET = 'e3dc93868af24f69b2a6efbe623814f6'
GENIUS_CLIENT_ID = '7e39MbC9H9y-G0sj-QcfvVrDo27_4So8FcILomWPVWzsXOgrsecL8oeX9iTiieNG'
GENIUS_CLIENT_SECRET = 'KItl2hbI7A0v1-_pSqf5LvS_daktJ9soWoyHcKPNsMJqJqui7_0kE3-CoBt7c4-u0mtHcWIhftpfdnJMx7hXew'


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
        response = requests.post(auth_url, headers=headers, data=data)
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
        response = requests.post(auth_url, data=data)
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
    """
    match = re.search(r'track/([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    else:
        raise ValueError("Неверный URL Spotify. Должен быть вида https://open.spotify.com/track/ID")


# Функция для получения метаданных трека из Spotify
def get_track_metadata(track_id, sp_token):
    """
    Получаем имя трека и артиста из Spotify API.
    Используем spotipy для удобства.
    """
    try:
        credentials = SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET)
        sp = spotipy.Spotify(auth_manager=credentials)
        track = sp.track(track_id)
        return track['name'], track['artists'][0]['name']  # Берем первого артиста
    except Exception as e:
        print(f"Ошибка при получении метаданных трека: {e}")
        return None, None


# Функция для получения synced lyrics из неофициального Spotify endpoint
def get_synced_lyrics(track_id, sp_token):
    """
    Пытаемся получить синхронизированные lyrics из internal Spotify API.
    Endpoint: https://spclient.wg.spotify.com/color-lyrics/v2/track/{id}
    Возвращает dict с 'lines' (каждая с 'startTimeMs' и 'words') или None.
    """
    lyrics_url = f"https://spclient.wg.spotify.com/color-lyrics/v2/track/{track_id}?format=json&market=from_token"
    headers = {
        'Authorization': f'Bearer {sp_token}',
        'Accept': 'application/json'
    }
    try:
        response = requests.get(lyrics_url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if 'lyrics' in data and 'lines' in data['lyrics']:
                return data['lyrics']['lines']  # Список строк с временем
        print("Synced lyrics не найдены или недоступны.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе synced lyrics: {e}")
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


# Функция для динамического вывода synced lyrics
def display_synced_lyrics(lines):
    """
    Выводим synced lyrics с задержками по времени.
    Используем time.sleep для имитации.
    Перезаписываем строку в консоли для "караоке-эффекта".
    """
    start_time = time.time() * 1000  # Текущее время в ms
    for line in lines:
        try:
            timestamp_ms = int(line['startTimeMs'])
            words = line['words']
        except KeyError:
            continue  # Пропускаем некорректные строки

        # Вычисляем задержку до следующей строки
        current_ms = (time.time() * 1000) - start_time
        delay_ms = timestamp_ms - current_ms
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        # Выводим строку с перезаписью
        sys.stdout.write(f"\r{words.ljust(80)}")  # ljust для очистки предыдущей
        sys.stdout.flush()

    print("\nКонец песни.")  # Финальный перевод строки


# Функция для вывода plain lyrics
def display_plain_lyrics(lyrics):
    """
    Просто печатаем весь текст.
    Добавляем атрибуцию Genius.
    """
    print(lyrics)
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

        sp_token = get_spotify_access_token()
        if not sp_token:
            sys.exit(1)

        title, artist = get_track_metadata(track_id, sp_token)
        if not title or not artist:
            print("Не удалось получить метаданные трека.")
            sys.exit(1)
        print(f"Трек: {title} by {artist}")

        # Сначала пробуем synced
        synced_lines = get_synced_lyrics(track_id, sp_token)
        if synced_lines:
            print("Нашли synced lyrics. Выводим с синхронизацией...")
            display_synced_lyrics(synced_lines)
        else:
            # Fallback на Genius
            genius_token = get_genius_access_token()
            if not genius_token:
                sys.exit(1)
            plain_lyrics = get_plain_lyrics(title, artist, genius_token)
            if plain_lyrics:
                print("Synced не найдены, выводим plain lyrics...")
                display_plain_lyrics(plain_lyrics)
            else:
                print("Lyrics не найдены нигде.")

    except Exception as e:
        print(f"Общая ошибка: {e}")


# Запуск главной функции
if __name__ == "__main__":
    main()