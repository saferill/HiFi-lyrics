import os
import re
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LYRICS_DIR = os.path.join(BASE_DIR, "v1", "lyrics")
INDEX_FILE = os.path.join(BASE_DIR, "v1", "index.json")
CACHE_FILE = os.path.join(BASE_DIR, "scripts", "harvest_cache.json")

os.makedirs(LYRICS_DIR, exist_ok=True)

USER_AGENT = "HiFiLyricsHarvester/2.0 (https://github.com/saferill/HiFi-lyrics)"
HEADERS = {"User-Agent": USER_AGENT}

# High-priority curated Indonesian essentials
INDO_ESSENTIALS = [
    # Bernadya
    ("Bernadya", "Satu Bulan"), ("Bernadya", "Kata Mereka Ini Berlebihan"), ("Bernadya", "Kini Mereka Tahu"),
    ("Bernadya", "Untungnya, Hidup Harus Tetap Berjalan"), ("Bernadya", "Apa Mungkin"), ("Bernadya", "Masa Sepi"),
    # Hindia
    ("Hindia", "Cincin"), ("Hindia", "Evaluasi"), ("Hindia", "Rumah Ke Rumah"), ("Hindia", "Membasuh"),
    ("Hindia", "Secukupnya"), ("Hindia", "Berdansalah, Karir Ini Tak Ada Artinya"), ("Hindia", "Setengah Tahun Ini"),
    # Sal Priadi
    ("Sal Priadi", "Gala Bunga Matahari"), ("Sal Priadi", "Dari Planet Lain"), ("Sal Priadi", "Mesra-mesraannya kecil-kecilan dulu"),
    ("Sal Priadi", "Foto kita blur"), ("Sal Priadi", "Kita usahakan rumah itu"), ("Sal Priadi", "Ikat Aku Di Tulang Belikatmu"),
    # Nadin Amizah
    ("Nadin Amizah", "Rayuan Perempuan Gila"), ("Nadin Amizah", "Bertaut"), ("Nadin Amizah", "Semua Aku Dirayakan"),
    ("Nadin Amizah", "Sorai"), ("Nadin Amizah", "Taruh"), ("Nadin Amizah", "Rumpang"), ("Nadin Amizah", "Ah"),
    # Denny Caknan
    ("Denny Caknan", "Cundamani"), ("Denny Caknan", "Kartonyono Medot Janji"), ("Denny Caknan", "Los Dol"),
    ("Denny Caknan", "Sugeng Dalu"), ("Denny Caknan", "Sampek Tuwek"), ("Denny Caknan", "Kalih Welasku"),
    ("Denny Caknan", "Sigar"), ("Denny Caknan", "Wirang"), ("Denny Caknan", "Dumes"),
    # Guyon Waton & Happy Asmara & Gilga
    ("Guyon Waton", "Korban Janji"), ("Guyon Waton", "Perlahan"), ("Guyon Waton", "Sebatas Patok Tenda"),
    ("Guyon Waton", "Pelanggaran"), ("Guyon Waton", "Sanes"), ("Happy Asmara", "Rungkad"),
    ("Happy Asmara", "Kelebus"), ("Gilga Sahid", "Nemen"), ("Gilga Sahid", "Ginio"), ("Gilga Sahid", "Alum"),
    ("NDX AKA", "Nemen"), ("NDX AKA", "Ditinggal Rabi"), ("NDX AKA", "Kelingan Mantan"),
    ("Ndarboy Genk", "Mendung Tanpo Udan"), ("Ndarboy Genk", "Koyo Jogja Istimewa"),
    # Mahalini & Tiara & Lyodra & Ziva
    ("Mahalini", "Sial"), ("Mahalini", "Melawan Restu"), ("Mahalini", "Sisa Rasa"), ("Mahalini", "Kisah Sempurna"),
    ("Mahalini", "Bawa Dia Kembali"), ("Mahalini", "Mati-Matian"), ("Mahalini", "Ini Laguku"),
    ("Tiara Andini", "Usai"), ("Tiara Andini", "Janji Setia"), ("Tiara Andini", "Menjadi Dia"),
    ("Tiara Andini", "Merasa Indah"), ("Tiara Andini", "Kupu-Kupu"), ("Lyodra", "Pesan Terakhir"),
    ("Lyodra", "Sang Dewi"), ("Lyodra", "Dibanding Dia"), ("Lyodra", "Tak Dianggap"),
    ("Ziva Magnolya", "Pilihan yang Terbaik"), ("Ziva Magnolya", "Peri Cintaku"), ("Ziva Magnolya", "Menyesal"),
    # Tulus & Yura & Rizky Febian
    ("Tulus", "Hati-Hati di Jalan"), ("Tulus", "Monokrom"), ("Tulus", "Diri"), ("Tulus", "Interaksi"),
    ("Tulus", "Pamit"), ("Tulus", "Sepatu"), ("Tulus", "Gajah"), ("Tulus", "Labirin"),
    ("Yura Yunita", "Tutur Batin"), ("Yura Yunita", "Dunia Tipu-Tipu"), ("Yura Yunita", "Tenang"),
    ("Yura Yunita", "Lihatlah Lebih Dekat"), ("Rizky Febian", "Hingga Tua Bersama"),
    ("Rizky Febian", "Kesempurnaan Cinta"), ("Rizky Febian", "Cuek"), ("Rizky Febian", "Mantra Cinta"),
    ("Rizky Febian", "Makna Cinta"), ("Rizky Febian", "Bermuara"),
    # Dewa 19 & Sheila On 7 & Peterpan/Noah
    ("Dewa 19", "Kangen"), ("Dewa 19", "Pupus"), ("Dewa 19", "Risalah Hati"), ("Dewa 19", "Separuh Nafas"),
    ("Dewa 19", "Cinta Kan Membawamu Kembali"), ("Dewa 19", "Roman Picisan"), ("Dewa 19", "Kamulah Satu-Satunya"),
    ("Sheila On 7", "Dan"), ("Sheila On 7", "Sephia"), ("Sheila On 7", "Melompat Lebih Tinggi"),
    ("Sheila On 7", "Film Favorit"), ("Sheila On 7", "Mudah Saja"), ("Sheila On 7", "Hari Bersamanya"),
    ("Sheila On 7", "Sebuah Kisah Klasik"), ("Sheila On 7", "Anugerah Terindah Yang Pernah Kumiliki"),
    ("Noah", "Separuh Aku"), ("Noah", "Kisah Cintaku"), ("Noah", "Mungkin Nanti"), ("Noah", "Semua Tentang Kita"),
    ("Noah", "Yang Terdalam"), ("Noah", "Menghapus Jejakmu"), ("Noah", "Bintang Di Surga"), ("Noah", "Cobalah Mengerti"),
    # Padi & Chrisye & Glenn & Judika
    ("Padi", "Semua Tak Sama"), ("Padi", "Kasih Tak Sampai"), ("Padi", "Menanti Sebuah Jawaban"),
    ("Chrisye", "Kala Cinta Menggoda"), ("Chrisye", "Pergilah Kasih"), ("Chrisye", "Pelangi"), ("Chrisye", "Cintaku"),
    ("Glenn Fredly", "Januari"), ("Glenn Fredly", "Sekali Ini Saja"), ("Glenn Fredly", "Kasih Putih"), ("Glenn Fredly", "Sedih Tak Berujung"),
    ("Judika", "Mama Papa Larang"), ("Judika", "Jikalau Kau Cinta"), ("Judika", "Putus Atau Terus"), ("Judika", "Bagaimana Kalau Aku Tidak Baik-Baik Saja"),
    # Indie & Band Indo Populer
    ("Juicy Luicy", "Lantas"), ("Juicy Luicy", "Tanpa Tergesa"), ("Juicy Luicy", "Sayangnya"), ("Juicy Luicy", "Asing"),
    ("Juicy Luicy", "Tampar"), ("Juicy Luicy", "Lampu Kuning"), ("For Revenge", "Serana"), ("For Revenge", "Jakarta Hari Ini"),
    ("For Revenge", "Sadrah"), ("Batas Senja", "Nanti Kita Seperti Ini"), ("Feby Putri", "Runtuh"), ("Feby Putri", "Usik"),
    ("Fiersa Besari", "Celengan Rindu"), ("Fiersa Besari", "Waktu Yang Salah"), ("Fiersa Besari", "April"),
    ("Pamungkas", "To the Bone"), ("Pamungkas", "Kenangan Manis"), ("Pamungkas", "One Only"),
    ("Reality Club", "Anything You Want"), ("Reality Club", "Is It The Answer?"), ("Reality Club", "Am I Bothering You?"),
    ("D'Masiv", "Jangan Menyerah"), ("D'Masiv", "Cinta Ini Membunuhku"), ("Ungu", "Demi Waktu"), ("Ungu", "Kekasih Gelapku"),
    ("Armada", "Asal Kau Bahagia"), ("Armada", "Pergi Pagi Pulang Pagi"), ("Geisha", "Lumpuhkan Ingatanku"),
    ("Kotak", "Pelan-Pelan Saja"), ("Kerispatih", "Tertatih"), ("Kerispatih", "Mengenangmu"),
    ("Vierratale", "Seandainya"), ("Vierratale", "Dengarkan Curhatku"), ("Last Child", "Pedih"), ("Last Child", "Duka"),
    ("Payung Teduh", "Akad"), ("Payung Teduh", "Resah"), ("Fourtwnty", "Zona Nyaman"), ("Fourtwnty", "Fana Merah Jambu"),
    # Global Pop Staples
    ("Bruno Mars", "Die With A Smile"), ("Bruno Mars", "Just the Way You Are"), ("Bruno Mars", "That's What I Like"),
    ("Lady Gaga", "Die With A Smile"), ("Taylor Swift", "Cruel Summer"), ("Taylor Swift", "Fortnight"),
    ("Taylor Swift", "Anti-Hero"), ("Taylor Swift", "Blank Space"), ("Taylor Swift", "Love Story"),
    ("Billie Eilish", "Birds of a Feather"), ("Billie Eilish", "What Was I Made For?"), ("Billie Eilish", "Bad Guy"),
    ("Sabrina Carpenter", "Espresso"), ("Sabrina Carpenter", "Please Please Please"), ("Sabrina Carpenter", "Taste"),
    ("Olivia Rodrigo", "vampire"), ("Olivia Rodrigo", "drivers license"), ("Olivia Rodrigo", "good 4 u"),
    ("Coldplay", "Yellow"), ("Coldplay", "The Scientist"), ("Coldplay", "Fix You"), ("Coldplay", "Viva La Vida"),
    ("The Weeknd", "Blinding Lights"), ("The Weeknd", "Starboy"), ("The Weeknd", "Save Your Tears"),
    ("Ed Sheeran", "Shape of You"), ("Ed Sheeran", "Perfect"), ("Ed Sheeran", "Photograph"),
    ("Ariana Grande", "we can't be friends"), ("Ariana Grande", "7 rings"), ("Ariana Grande", "positions"),
    ("Dua Lipa", "Levitating"), ("Dua Lipa", "Don't Start Now"), ("Dua Lipa", "Houdini"),
    ("Queen", "Bohemian Rhapsody"), ("Queen", "Love of My Life"), ("Oasis", "Don't Look Back In Anger"),
    ("Oasis", "Wonderwall"), ("Linkin Park", "In the End"), ("Linkin Park", "Numb"),
    ("NewJeans", "Supernatural"), ("NewJeans", "Ditto"), ("NewJeans", "OMG"), ("NewJeans", "Hype Boy"),
    ("BLACKPINK", "How You Like That"), ("BLACKPINK", "Kill This Love"), ("BLACKPINK", "Shut Down"),
    ("BTS", "Dynamite"), ("BTS", "Butter"), ("BTS", "Spring Day"),
    ("YOASOBI", "Idol"), ("YOASOBI", "Yoru ni Kakeru"), ("Fujii Kaze", "Shinunoga E-Wa"), ("Fujii Kaze", "Matsuri")
]

KWORB_URLS = [
    'https://kworb.net/spotify/country/id_daily.html',
    'https://kworb.net/spotify/country/id_weekly.html',
    'https://kworb.net/spotify/country/global_daily.html',
    'https://kworb.net/spotify/country/global_weekly.html',
    'https://kworb.net/spotify/country/us_daily.html',
    'https://kworb.net/spotify/country/gb_daily.html',
    'https://kworb.net/spotify/country/jp_daily.html',
    'https://kworb.net/spotify/country/kr_daily.html',
    'https://kworb.net/spotify/country/my_daily.html',
    'https://kworb.net/spotify/country/ph_daily.html',
    'https://kworb.net/spotify/country/sg_daily.html',
    'https://kworb.net/spotify/country/th_daily.html',
    'https://kworb.net/spotify/country/br_daily.html',
    'https://kworb.net/spotify/country/mx_daily.html',
    'https://kworb.net/spotify/country/de_daily.html',
    'https://kworb.net/spotify/country/fr_daily.html',
    'https://kworb.net/spotify/country/es_daily.html',
    'https://kworb.net/spotify/country/it_daily.html',
    'https://kworb.net/spotify/country/au_daily.html',
    'https://kworb.net/spotify/country/ca_daily.html',
]

def clean_text(s):
    if not s:
        return ""
    s = re.sub(r'\(.*?(?:feat|ft\.|official|video|audio|remix|version|deluxe|bonus).*?\)', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\[.*?(?:feat|ft\.|official|video|audio|remix|version|deluxe|bonus).*?\]', '', s, flags=re.IGNORECASE)
    return s.strip()

def fetch_chart_tracks():
    tracks = set()
    for artist, title in INDO_ESSENTIALS:
        tracks.add((artist.strip(), title.strip()))

    pattern = re.compile(r'<td class="text mp"><div><a href="\.\./artist/[^"]+">([^<]+)</a>\s*-\s*<a href="\.\./track/[^"]+">([^<]+)</a>')
    for u in KWORB_URLS:
        try:
            req = urllib.request.Request(u, headers=HEADERS)
            html = urllib.request.urlopen(req, timeout=6).read().decode('utf-8', errors='ignore')
            matches = pattern.findall(html)
            for artist, title in matches:
                tracks.add((artist.strip(), title.strip()))
        except Exception:
            pass
    return list(tracks)

def search_lrclib(artist, title):
    q = urllib.parse.quote(f"{clean_text(title)} {clean_text(artist)}")
    url = f"https://lrclib.net/api/search?q={q}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if not isinstance(data, list):
                return None
            for item in data:
                if item.get("syncedLyrics"):
                    return item
            if data:
                return data[0]
    except Exception:
        pass
    return None

def resolve_youtube_videoids(artist, title):
    url = 'https://www.youtube.com/youtubei/v1/search?prettyPrint=false'
    query = f"{artist} - {title}"
    payload = {
        'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20240101.01.00'}},
        'query': query
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    )
    vids = []
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            resp = json.loads(r.read().decode('utf-8'))
            sections = resp.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [])
            for sec in sections:
                items = sec.get('itemSectionRenderer', {}).get('contents', [])
                for it in items:
                    vr = it.get('videoRenderer')
                    if vr and 'videoId' in vr:
                        vids.append(vr['videoId'])
                        if len(vids) >= 2:
                            break
                if len(vids) >= 2:
                    break
    except Exception:
        pass
    return vids

def write_lyric_file(vid, lrc_obj, fallback_title, fallback_artist):
    song_title = lrc_obj.get("trackName") or fallback_title
    artist_name = lrc_obj.get("artistName") or fallback_artist
    album_name = lrc_obj.get("albumName") or ""
    duration = int(lrc_obj.get("duration") or 0)
    plain_lyrics = lrc_obj.get("plainLyrics") or ""
    synced_lyrics = lrc_obj.get("syncedLyrics") or ""

    payload = {
        "success": True,
        "error": None,
        "data": [
            {
                "id": vid,
                "videoId": vid,
                "songTitle": song_title,
                "artistName": artist_name,
                "albumName": album_name,
                "durationSeconds": duration,
                "plainLyric": plain_lyrics,
                "syncedLyrics": synced_lyrics,
                "richSyncLyrics": None,
                "trackType": None,
                "vote": 100,
                "contributor": "LRCLIB / HiFi Community",
                "contributorEmail": "lyrics@hifi.org"
            }
        ]
    }
    filepath = os.path.join(LYRICS_DIR, f"{vid}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def process_track(track):
    artist, title = track
    lrc = search_lrclib(artist, title)
    if not lrc:
        return 0
    vids = resolve_youtube_videoids(artist, title)
    if not vids:
        return 0
    saved = 0
    for vid in vids:
        write_lyric_file(vid, lrc, title, artist)
        saved += 1
    return saved

def main():
    print("Step 1: Gathering chart and seed tracks...")
    all_tracks = fetch_chart_tracks()
    print(f"Total track candidates: {len(all_tracks)}")

    # Clean legacy dummy seed_*.json files
    cleaned = 0
    for f in os.listdir(LYRICS_DIR):
        if f.startswith("seed_") and f.endswith(".json"):
            try:
                os.remove(os.path.join(LYRICS_DIR, f))
                cleaned += 1
            except Exception:
                pass
    if cleaned > 0:
        print(f"Cleaned {cleaned} legacy dummy seed files.")

    print("Step 2: Harvesting lyrics from LRCLIB & mapping YouTube video IDs...")
    total_saved = 0
    completed = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(process_track, t): t for t in all_tracks}
        for future in as_completed(futures):
            completed += 1
            try:
                saved = future.result()
                total_saved += saved
            except Exception:
                pass
            if completed % 50 == 0 or completed == len(all_tracks):
                elapsed = time.time() - start_time
                print(f"Progress: {completed}/{len(all_tracks)} tracks processed. Saved lyric files: {total_saved}. ({elapsed:.1f}s)")

    print("Step 3: Building catalog index...")
    lyrics_files = [f for f in os.listdir(LYRICS_DIR) if f.endswith(".json") and len(f) == 16] # 11 char vid + .json
    index_data = {
        "service": "HiFi Lyrics Repository",
        "version": "2.0.0",
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_tracks": len(lyrics_files),
        "status": "online"
    }
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)

    print(f"DONE! Total lyrics in database: {len(lyrics_files)} files.")

if __name__ == "__main__":
    main()

