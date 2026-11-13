#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated synchronized lyrics harvester for HiFi-lyrics.
Fetches charts + curated seeds, queries LRCLIB and YouTube Innertube with
rate limiting, bounded retries, strict match validation, per-videoId locking,
and atomic writes that protect existing synced/curated lyrics.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
LYRICS_DIR = os.path.join(BASE_DIR, "v1", "lyrics")
INDEX_FILE = os.path.join(BASE_DIR, "v1", "index.json")

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from lyrics_common import (  # noqa: E402
    HEADERS,
    RateLimiter,
    VideoLockPool,
    extract_youtube_candidates,
    parse_kworb_chart_html,
    request_with_retry,
    save_lyric_if_better,
    select_best_lrclib,
    select_matching_youtube_videos,
    update_index_if_changed,
)
import re

os.makedirs(LYRICS_DIR, exist_ok=True)

INDO_ESSENTIALS = [
    ("Bernadya", "Satu Bulan"), ("Bernadya", "Kata Mereka Ini Berlebihan"), ("Bernadya", "Kini Mereka Tahu"),
    ("Bernadya", "Untungnya, Hidup Harus Tetap Berjalan"), ("Bernadya", "Apa Mungkin"), ("Bernadya", "Masa Sepi"),
    ("Hindia", "Cincin"), ("Hindia", "Evaluasi"), ("Hindia", "Rumah Ke Rumah"), ("Hindia", "Membasuh"),
    ("Hindia", "Secukupnya"), ("Hindia", "Berdansalah, Karir Ini Tak Ada Artinya"), ("Hindia", "Setengah Tahun Ini"),
    ("Sal Priadi", "Gala Bunga Matahari"), ("Sal Priadi", "Dari Planet Lain"), ("Sal Priadi", "Mesra-mesraannya kecil-kecilan dulu"),
    ("Sal Priadi", "Foto kita blur"), ("Sal Priadi", "Kita usahakan rumah itu"), ("Sal Priadi", "Ikat Aku Di Tulang Belikatmu"),
    ("Nadin Amizah", "Rayuan Perempuan Gila"), ("Nadin Amizah", "Bertaut"), ("Nadin Amizah", "Semua Aku Dirayakan"),
    ("Nadin Amizah", "Sorai"), ("Nadin Amizah", "Taruh"), ("Nadin Amizah", "Rumpang"), ("Nadin Amizah", "Ah"),
    ("Denny Caknan", "Cundamani"), ("Denny Caknan", "Kartonyono Medot Janji"), ("Denny Caknan", "Los Dol"),
    ("Denny Caknan", "Sugeng Dalu"), ("Denny Caknan", "Sampek Tuwek"), ("Denny Caknan", "Kalih Welasku"),
    ("Denny Caknan", "Sigar"), ("Denny Caknan", "Wirang"), ("Denny Caknan", "Dumes"),
    ("Mahalini", "Sial"), ("Mahalini", "Melawan Restu"), ("Mahalini", "Sisa Rasa"), ("Mahalini", "Kisah Sempurna"),
    ("Tiara Andini", "Usai"), ("Tiara Andini", "Janji Setia"), ("Lyodra", "Pesan Terakhir"), ("Lyodra", "Sang Dewi"),
    ("Tulus", "Hati-Hati di Jalan"), ("Tulus", "Monokrom"), ("Tulus", "Diri"), ("Tulus", "Interaksi"),
    ("Yura Yunita", "Tutur Batin"), ("Yura Yunita", "Dunia Tipu-Tipu"),
    ("Dewa 19", "Kangen"), ("Dewa 19", "Pupus"), ("Dewa 19", "Risalah Hati"), ("Dewa 19", "Separuh Nafas"),
    ("Sheila On 7", "Dan"), ("Sheila On 7", "Sephia"), ("Noah", "Separuh Aku"), ("Noah", "Yang Terdalam"),
    ("Juicy Luicy", "Lantas"), ("Juicy Luicy", "Tampar"), ("For Revenge", "Serana"), ("Feby Putri", "Runtuh"),
    ("Bruno Mars", "Die With A Smile"), ("Lady Gaga", "Die With A Smile"), ("Taylor Swift", "Cruel Summer"),
    ("Billie Eilish", "Birds of a Feather"), ("Sabrina Carpenter", "Espresso"), ("Coldplay", "Yellow"),
    ("The Weeknd", "Blinding Lights"), ("Ed Sheeran", "Shape of You"), ("Queen", "Bohemian Rhapsody"),
    ("NewJeans", "Supernatural"), ("BLACKPINK", "How You Like That"), ("BTS", "Dynamite"),
    ("YOASOBI", "Idol"), ("Fujii Kaze", "Shinunoga E-Wa"),
]

KWORB_URLS = [
    "https://kworb.net/spotify/country/id_daily.html",
    "https://kworb.net/spotify/country/id_weekly.html",
    "https://kworb.net/spotify/country/global_daily.html",
    "https://kworb.net/spotify/country/global_weekly.html",
    "https://kworb.net/spotify/country/us_daily.html",
    "https://kworb.net/spotify/country/gb_daily.html",
    "https://kworb.net/spotify/country/jp_daily.html",
    "https://kworb.net/spotify/country/kr_daily.html",
    "https://kworb.net/spotify/country/my_daily.html",
    "https://kworb.net/spotify/country/ph_daily.html",
    "https://kworb.net/spotify/country/sg_daily.html",
    "https://kworb.net/spotify/country/th_daily.html",
    "https://kworb.net/spotify/country/br_daily.html",
    "https://kworb.net/spotify/country/mx_daily.html",
    "https://kworb.net/spotify/country/de_daily.html",
    "https://kworb.net/spotify/country/fr_daily.html",
    "https://kworb.net/spotify/country/es_daily.html",
    "https://kworb.net/spotify/country/it_daily.html",
    "https://kworb.net/spotify/country/au_daily.html",
    "https://kworb.net/spotify/country/ca_daily.html",
]


def _clean_query_part(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"\(.*?(?:feat|ft\.|official|video|audio|remix|version|deluxe|bonus).*?\)", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\[.*?(?:feat|ft\.|official|video|audio|remix|version|deluxe|bonus).*?\]", "", s, flags=re.IGNORECASE)
    return " ".join(s.split())


class SourceStats:
    def __init__(self):
        self._lock = threading.Lock()
        self.counts: Dict[str, Dict[str, int]] = {
            "charts": {"ok": 0, "empty": 0, "failed": 0},
            "lrclib": {"ok": 0, "empty": 0, "failed": 0},
            "youtube": {"ok": 0, "empty": 0, "failed": 0},
        }
        self.skipped_reasons: Dict[str, int] = {}

    def inc(self, source: str, outcome: str):
        with self._lock:
            self.counts[source][outcome] = self.counts[source].get(outcome, 0) + 1

    def inc_skip(self, reason: str):
        with self._lock:
            self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + 1


def fetch_chart_tracks(
    chart_urls: Optional[List[str]] = None,
    seeds: Optional[List[Tuple[str, str]]] = None,
    stats: Optional[SourceStats] = None,
    rate_limiter: Optional[RateLimiter] = None,
    opener=urllib.request.urlopen,
    sleep_fn=time.sleep,
) -> List[Tuple[str, str]]:
    tracks = set()
    for artist, title in (seeds if seeds is not None else INDO_ESSENTIALS):
        tracks.add((artist.strip(), title.strip()))

    urls = chart_urls if chart_urls is not None else KWORB_URLS
    for url in urls:
        req = urllib.request.Request(url, headers=HEADERS)
        res = request_with_retry(req, timeout=8.0, max_attempts=2, rate_limiter=rate_limiter, opener=opener, sleep_fn=sleep_fn)
        if not res.ok:
            if stats:
                stats.inc("charts", "failed")
            print(f"[WARN] Chart fetch failed ({url}): {res.error_msg}", flush=True)
            continue
        html_text = res.body_bytes.decode("utf-8", errors="ignore")
        parsed = parse_kworb_chart_html(html_text)
        if not parsed:
            if stats:
                stats.inc("charts", "empty")
            print(f"[WARN] Chart parsed 0 tracks ({url})", flush=True)
            continue
        if stats:
            stats.inc("charts", "ok")
        for artist, title in parsed:
            tracks.add((artist, title))
    return sorted(tracks)


def search_lrclib(
    artist: str,
    title: str,
    *,
    stats: Optional[SourceStats] = None,
    rate_limiter: Optional[RateLimiter] = None,
    opener=urllib.request.urlopen,
    sleep_fn=time.sleep,
) -> Tuple[bool, Optional[dict], str]:
    q = urllib.parse.quote(f"{_clean_query_part(title)} {_clean_query_part(artist)}")
    url = f"https://lrclib.net/api/search?q={q}"
    req = urllib.request.Request(url, headers=HEADERS)
    res = request_with_retry(req, timeout=8.0, max_attempts=3, rate_limiter=rate_limiter, opener=opener, sleep_fn=sleep_fn)
    if not res.ok:
        if stats:
            stats.inc("lrclib", "failed")
        return False, None, f"LRCLIB error: {res.error_msg}"
    try:
        data = json.loads(res.body_bytes.decode("utf-8"))
    except Exception as e:
        if stats:
            stats.inc("lrclib", "failed")
        return False, None, f"LRCLIB invalid JSON: {e}"

    if not isinstance(data, list) or not data:
        if stats:
            stats.inc("lrclib", "empty")
        return True, None, "LRCLIB returned no results"

    best, reason = select_best_lrclib(data, artist, title)
    if best is None:
        if stats:
            stats.inc("lrclib", "empty")
        return True, None, reason
    if stats:
        stats.inc("lrclib", "ok")
    return True, best, "OK"


def resolve_youtube_videoids(
    artist: str,
    title: str,
    expected_duration_sec: Optional[int],
    *,
    stats: Optional[SourceStats] = None,
    rate_limiter: Optional[RateLimiter] = None,
    opener=urllib.request.urlopen,
    sleep_fn=time.sleep,
) -> Tuple[bool, List[str], List[str]]:
    url = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"
    payload = {
        "context": {"client": {"clientName": "WEB", "clientVersion": "2.20240101.01.00"}},
        "query": f"{artist} - {title}",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": HEADERS["User-Agent"]},
    )
    res = request_with_retry(req, timeout=8.0, max_attempts=3, rate_limiter=rate_limiter, opener=opener, sleep_fn=sleep_fn)
    if not res.ok:
        if stats:
            stats.inc("youtube", "failed")
        return False, [], [f"YouTube error: {res.error_msg}"]
    try:
        resp_json = json.loads(res.body_bytes.decode("utf-8"))
    except Exception as e:
        if stats:
            stats.inc("youtube", "failed")
        return False, [], [f"YouTube invalid JSON: {e}"]

    candidates = extract_youtube_candidates(resp_json)
    matched, rejected = select_matching_youtube_videos(candidates, artist, title, expected_duration_sec, max_results=2)
    if not matched:
        if stats:
            stats.inc("youtube", "empty")
        return True, [], rejected
    if stats:
        stats.inc("youtube", "ok")
    return True, matched, rejected


def process_track(
    track: Tuple[str, str],
    *,
    lyrics_dir: str = LYRICS_DIR,
    lock_pool: Optional[VideoLockPool] = None,
    stats: Optional[SourceStats] = None,
    lrclib_limiter: Optional[RateLimiter] = None,
    yt_limiter: Optional[RateLimiter] = None,
    opener=urllib.request.urlopen,
    sleep_fn=time.sleep,
) -> int:
    artist, title = track
    ok_lrc, lrc, lrc_reason = search_lrclib(
        artist, title, stats=stats, rate_limiter=lrclib_limiter, opener=opener, sleep_fn=sleep_fn
    )
    if not ok_lrc or not lrc:
        if stats:
            stats.inc_skip(lrc_reason)
        return 0

    expected_dur = int(lrc.get("duration") or 0) or None
    ok_yt, vids, yt_rejected = resolve_youtube_videoids(
        artist, title, expected_dur, stats=stats, rate_limiter=yt_limiter, opener=opener, sleep_fn=sleep_fn
    )
    if not ok_yt or not vids:
        if stats:
            stats.inc_skip(yt_rejected[0] if yt_rejected else "No matching YouTube video")
        return 0

    saved = 0
    for vid in vids:
        outcome = save_lyric_if_better(lyrics_dir, vid, lrc, title, artist, lock_pool=lock_pool)
        if outcome == "saved":
            saved += 1
        elif stats:
            stats.inc_skip(outcome)
    return saved


def run_sync(
    *,
    tracks: Optional[List[Tuple[str, str]]] = None,
    chart_urls: Optional[List[str]] = None,
    lyrics_dir: str = LYRICS_DIR,
    index_file: str = INDEX_FILE,
    max_workers: int = 8,
    opener=urllib.request.urlopen,
    sleep_fn=time.sleep,
) -> int:
    stats = SourceStats()
    lock_pool = VideoLockPool()
    chart_limiter = RateLimiter(0.1, sleep_fn=sleep_fn)
    lrclib_limiter = RateLimiter(0.15, sleep_fn=sleep_fn)
    yt_limiter = RateLimiter(0.15, sleep_fn=sleep_fn)

    print("Step 1: Gathering chart and seed tracks...", flush=True)
    all_tracks = (
        list(tracks)
        if tracks is not None
        else fetch_chart_tracks(chart_urls=chart_urls, stats=stats, rate_limiter=chart_limiter, opener=opener, sleep_fn=sleep_fn)
    )
    print(f"Total track candidates: {len(all_tracks)}", flush=True)

    print("Step 2: Harvesting lyrics from LRCLIB & matching YouTube videos...", flush=True)
    total_saved = 0
    worker_errors = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                process_track,
                t,
                lyrics_dir=lyrics_dir,
                lock_pool=lock_pool,
                stats=stats,
                lrclib_limiter=lrclib_limiter,
                yt_limiter=yt_limiter,
                opener=opener,
                sleep_fn=sleep_fn,
            ): t
            for t in all_tracks
        }
        for i, future in enumerate(as_completed(futures), 1):
            try:
                total_saved += future.result()
            except Exception as e:
                worker_errors += 1
                print(f"[ERROR] Worker failed for {futures[future]}: {e}", flush=True)
            if i % 50 == 0 or i == len(all_tracks):
                print(f"Progress: {i}/{len(all_tracks)} | Saved: {total_saved}", flush=True)

    print(f"Source stats: {json.dumps(stats.counts)}", flush=True)
    if stats.skipped_reasons:
        top_skips = sorted(stats.skipped_reasons.items(), key=lambda x: -x[1])[:8]
        print(f"Top skip reasons: {top_skips}", flush=True)

    # Detect total external service failure (never fake success!)
    lrc_ok_or_empty = stats.counts["lrclib"]["ok"] + stats.counts["lrclib"]["empty"]
    yt_ok_or_empty = stats.counts["youtube"]["ok"] + stats.counts["youtube"]["empty"]
    all_services_failed = len(all_tracks) > 0 and (
        (stats.counts["lrclib"]["failed"] > 0 and lrc_ok_or_empty == 0)
        or (stats.counts["youtube"]["failed"] > 0 and yt_ok_or_empty == 0 and stats.counts["lrclib"]["ok"] > 0)
    )
    if all_services_failed or worker_errors == len(all_tracks) > 0:
        print("[ERROR] External services failed across all requests; not marking sync healthy.", flush=True)
        return 1

    print("Step 3: Validating catalog & updating index if changed...", flush=True)
    changed, idx = update_index_if_changed(index_file, lyrics_dir, status="online")
    print(f"Index {'updated' if changed else 'unchanged'}: total_tracks={idx['total_tracks']}, unique_songs={idx['unique_songs']}", flush=True)
    return 0


def main() -> int:
    return run_sync()


if __name__ == "__main__":
    sys.exit(main())
