import json
import urllib.request
import os
import re

def clean_title(title):
    title = re.sub(r'\(.*?\)|\[.*?\]', '', title)
    title = re.sub(r'(?i)official.*|video.*|audio.*|lyrics.*', '', title)
    return title.strip()

print("Fetching chart tracks...")
try:
    req = urllib.request.Request(
        "https://raw.githubusercontent.com/saferill/HiFi-charts/refs/heads/main/api/playlists.json",
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req) as resp:
        chart_data = json.loads(resp.read().decode('utf-8'))
except Exception as e:
    print(f"Error fetching chart: {e}")