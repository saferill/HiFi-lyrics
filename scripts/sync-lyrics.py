import json
import urllib.request
import urllib.parse
import os
import re

LYRICS_DIR = "v1/lyrics"
os.makedirs(LYRICS_DIR, exist_ok=True)

def clean_name(text):
    text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
    text = re.sub(r'(?i)official.*|video.*|audio.*|lyrics.*|mv.*', '', text)
    return text.strip()

def is_already_saved(video_id):
    path = os.path.join(LYRICS_DIR, f"{video_id}.json")
    return os.path.exists(path) and os.path.getsize(path) > 10

def parse_lrc_to_lines(lrc_text):
    lines = []
    for raw_line in lrc_text.splitlines():
        match = re.match(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)', raw_line)
        if match:
            mins = int(match.group(1))
            secs = float(match.group(2))
            start_ms = int((mins * 60 + secs) * 1000)
            words = match.group(3).strip()
            lines.append({"startTimeMs": str(start_ms), "words": words})
    return lines

def fetch_lrclib(title, artist):
    query = urllib.parse.urlencode({'track_name': clean_name(title), 'artist_name': clean_name(artist)})
    url = f"https://lrclib.net/api/get?{query}"
    req = urllib.request.Request(url, headers={'User-Agent': 'HiFiMusic/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            synced = data.get('syncedLyrics')
            plain = data.get('plainLyrics')
            if synced:
                return parse_lrc_to_lines(synced), "LINE_SYNCED"
            elif plain:
                lines = [{"startTimeMs": "0", "words": l.strip()} for l in plain.splitlines() if l.strip()]
                return lines, "UNSYNCED"
    except Exception:
        return None, None
    return None, None

def update_catalog():
    count = len([f for f in os.listdir(LYRICS_DIR) if f.endswith('.json')])
    index_data = {
        "service": "HiFi Lyrics Repository",
        "total": count,
        "status": "online"
    }
    with open("v1/index.json", "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)

print("Starting lyrics sync...")
update_catalog()
print("Catalog updated.")
