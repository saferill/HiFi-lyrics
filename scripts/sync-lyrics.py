import json
import urllib.request
import urllib.parse
import os
import re
import time

LYRICS_DIR = "v1/lyrics"
os.makedirs(LYRICS_DIR, exist_ok=True)

PLAYLIST_SOURCES = [
    "https://raw.githubusercontent.com/saferill/HiFi-charts/refs/heads/main/api/playlists.json",
    # Top Hits & Viral Indeks
]

SEEDS = [
    ("Hindia", "Cincin"), ("Bernadya", "Satu Bulan"), ("Nadin Amizah", "Rayuan Perempuan Gila"),
    ("Denny Caknan", "Cundamani"), ("Tulus", "Hati-Hati di Jalan"), ("Mahalini", "Sial"),
    ("Sheila On 7", "Dan"), ("Dewa 19", "Kangen"), ("Noah", "Separuh Aku"), ("Judika", "Mama Papa Larang"),
    ("Fabio Asher", "Rumah Singgah"), ("Sal Priadi", "Gala Bunga Matahari"), ("Ghea Indrawari", "Jiwa Yang Bersedih"),
    ("Tiara Andini", "Usai"), ("Lyodra", "Pesan Terakhir"), ("Ziva Magnolya", "Pilihan yang Terbaik"),
    ("Rizky Febian", "Hingga Tua Bersama"), ("Yura Yunita", "Tutur Batin"), ("Fiersa Besari", "Runtuh"),
    ("Taylor Swift", "Cruel Summer"), ("Billie Eilish", "Birds of a Feather"), ("Coldplay", "Yellow"),
    ("Ed Sheeran", "Shape of You"), ("Bruno Mars", "Die With A Smile"), ("The Weeknd", "Blinding Lights"),
    ("Ariana Grande", "we can't be friends"), ("Post Malone", "Circles"), ("Dua Lipa", "Levitating"),
    ("NewJeans", "Supernatural"), ("BTS", "Dynamite"), ("BLACKPINK", "How You Like That")
]

def clean_name(text):
    text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
    text = re.sub(r'(?i)official.*|video.*|audio.*|lyrics.*|mv.*', '', text)
    return text.strip()

def parse_lrc(lrc):
    lines = []
    for line in lrc.splitlines():
        m = re.match(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)', line)
        if m:
            ms = int((int(m.group(1)) * 60 + float(m.group(2))) * 1000)
            lines.append({"startTimeMs": str(ms), "words": m.group(3).strip()})
    return lines

print("Gathering massive lyrics from multi-sources...")
added = 0
for artist, title in SEEDS:
    q = urllib.parse.urlencode({'track_name': clean_name(title), 'artist_name': clean_name(artist)})
    url = f"https://lrclib.net/api/get?{q}"
    req = urllib.request.Request(url, headers={'User-Agent': 'HiFiMusic/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            synced = data.get('syncedLyrics')
            plain = data.get('plainLyrics')
            lines = parse_lrc(synced) if synced else ([{"startTimeMs": "0", "words": l.strip()} for l in plain.splitlines()] if plain else [])
            if lines:
                vid = f"seed_{abs(hash(artist + title))}"
                out_file = os.path.join(LYRICS_DIR, f"{vid}.json")
                if not os.path.exists(out_file):
                    with open(out_file, "w", encoding="utf-8") as f:
                        json.dump({"title": title, "artist": artist, "syncType": "LINE_SYNCED" if synced else "UNSYNCED", "lines": lines}, f, indent=2)
                    added += 1
        time.sleep(0.1)
    except Exception:
        pass

total = len([f for f in os.listdir(LYRICS_DIR) if f.endswith('.json')])
with open("v1/index.json", "w", encoding="utf-8") as f:
    json.dump({"service": "HiFi Lyrics Repository", "total": total, "status": "online"}, f, indent=2)
print(f"Finished. Added: {added}, Total: {total}")
