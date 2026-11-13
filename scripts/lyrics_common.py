#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared utilities for HiFi-lyrics harvesting, matching, validation, and atomic storage.
Uses only Python standard library.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
import json
import os
import random
import re
import socket
import tempfile
import threading
import time
from typing import Callable, Dict, Iterable, List, Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "HiFiLyricsHarvester/2.1 (https://github.com/saferill/HiFi-lyrics)"
HEADERS = {"User-Agent": USER_AGENT}

YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
LRC_TIMESTAMP_RE = re.compile(r"\[(\d{1,3}):(\d{2})(?:\.(\d{1,3}))?\]")

VERSION_MARKERS = (
    "live",
    "cover",
    "remix",
    "acoustic",
    "karaoke",
    "instrumental",
    "nightcore",
    "slowed",
    "reverb",
    "sped up",
    "8d",
    "concert",
    "tour",
    "tutorial",
    "lesson",
    "reaction",
    "parody",
    "mashup",
    "unplugged",
)

STOPWORDS = {"the", "a", "an", "and", "of", "ft", "feat", "featuring", "official", "audio", "video", "lyrics", "lyric", "mv", "hd", "4k"}


def is_valid_video_id(video_id) -> bool:
    return isinstance(video_id, str) and bool(YOUTUBE_VIDEO_ID_RE.fullmatch(video_id))


def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = unescape(str(s)).lower()
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", s)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokenize(s: str) -> set:
    norm = normalize_text(s)
    return {t for t in norm.split() if t and t not in STOPWORDS}


def extract_version_markers(s: str) -> set:
    low = unescape(str(s or "")).lower()
    found = set()
    for marker in VERSION_MARKERS:
        if re.search(rf"\b{re.escape(marker)}\b", low):
            found.add(marker)
    return found


def parse_duration_text(text: str) -> Optional[int]:
    """Parse YouTube duration strings like '3:14' or '1:02:05' into seconds."""
    if not text or not isinstance(text, str):
        return None
    parts = [p.strip() for p in text.strip().split(":")]
    if not all(p.isdigit() for p in parts):
        return None
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return None


def parse_lrc_timestamps(synced_lyrics: str) -> Tuple[List[int], bool, bool]:
    """
    Parse LRC timestamps supporting 1, 2, or 3 fractional digits.
    Returns (timestamps_ms, has_3digit_precision, out_of_order).
    """
    if not isinstance(synced_lyrics, str) or not synced_lyrics.strip():
        return [], False, False
    timestamps: List[int] = []
    has_3digit = False
    for line in synced_lyrics.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        cursor = 0
        while cursor < len(stripped) and stripped[cursor] == "[":
            m = LRC_TIMESTAMP_RE.match(stripped, cursor)
            if not m:
                break
            mins = int(m.group(1))
            secs = int(m.group(2))
            frac = m.group(3)
            if frac is None:
                ms = 0
            elif len(frac) == 1:
                ms = int(frac) * 100
            elif len(frac) == 2:
                ms = int(frac) * 10
            else:
                ms = int(frac)
                has_3digit = True
            timestamps.append(mins * 60_000 + secs * 1000 + ms)
            cursor = m.end()
    out_of_order = any(timestamps[i] < timestamps[i - 1] for i in range(1, len(timestamps)))
    return timestamps, has_3digit, out_of_order


class _KworbChartParser(HTMLParser):
    """Resilient HTMLParser for Kworb Spotify chart tables (decodes HTML entities)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._in_tr = False
        self._in_td = False
        self._in_a = False
        self._current_href = ""
        self._current_text: List[str] = []
        self._row_links: List[Tuple[str, str]] = []
        self._cell_text: List[str] = []
        self.tracks: List[Tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attr_map = dict(attrs)
        if tag == "tr":
            self._in_tr = True
            self._row_links = []
        elif tag == "td" and self._in_tr:
            self._in_td = True
            self._cell_text = []
        elif tag == "a" and self._in_td:
            self._in_a = True
            self._current_href = attr_map.get("href", "") or ""
            self._current_text = []

    def handle_data(self, data):
        if self._in_a:
            self._current_text.append(data)
        if self._in_td:
            self._cell_text.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "a" and self._in_a:
            text = unescape("".join(self._current_text)).strip()
            self._row_links.append((self._current_href, text))
            self._in_a = False
            self._current_href = ""
            self._current_text = []
        elif tag == "td" and self._in_td:
            # Check if this cell contains artist/track links or "Artist - Title"
            artist_links = [txt for href, txt in self._row_links if "/artist/" in href and txt]
            track_links = [txt for href, txt in self._row_links if "/track/" in href and txt]
            if artist_links and track_links:
                self.tracks.append((artist_links[0], track_links[0]))
                self._row_links = []
            elif len(self._row_links) >= 2 and all(t for _, t in self._row_links[:2]):
                raw_cell = unescape("".join(self._cell_text)).strip()
                if " - " in raw_cell:
                    self.tracks.append((self._row_links[0][1], self._row_links[1][1]))
                    self._row_links = []
            self._in_td = False
        elif tag == "tr" and self._in_tr:
            self._in_tr = False
            self._row_links = []


def parse_kworb_chart_html(html_text: str) -> List[Tuple[str, str]]:
    """Extract unique (artist, title) pairs from Kworb chart HTML using HTMLParser."""
    if not html_text:
        return []
    parser = _KworbChartParser()
    parser.feed(html_text)
    parser.close()
    seen = set()
    unique: List[Tuple[str, str]] = []
    for artist, title in parser.tracks:
        a = " ".join(artist.split())
        t = " ".join(title.split())
        if a and t and (a, t) not in seen:
            seen.add((a, t))
            unique.append((a, t))
    return unique


class RateLimiter:
    """Thread-safe minimum-interval rate limiter."""

    def __init__(self, min_interval_sec: float = 0.25, clock_fn: Callable[[], float] = time.monotonic, sleep_fn: Callable[[float], None] = time.sleep):
        self._min_interval = max(0.0, min_interval_sec)
        self._clock = clock_fn
        self._sleep = sleep_fn
        self._lock = threading.Lock()
        self._last_ts = 0.0

    def wait(self):
        if self._min_interval <= 0:
            return
        with self._lock:
            now = self._clock()
            wait_for = self._min_interval - (now - self._last_ts)
            if wait_for > 0:
                self._sleep(wait_for)
            self._last_ts = self._clock()


@dataclass
class HttpResult:
    ok: bool
    status_code: Optional[int] = None
    body_bytes: bytes = b""
    error_kind: str = ""  # "" | "TRANSIENT" | "HTTP_ERROR"
    error_msg: str = ""


def _parse_retry_after(headers) -> Optional[float]:
    if not headers or not hasattr(headers, "get"):
        return None
    val = headers.get("Retry-After")
    if not val:
        return None
    try:
        secs = float(str(val).strip())
        if secs > 0:
            return min(secs, 15.0)
    except ValueError:
        pass
    return None


def request_with_retry(
    req,
    *,
    timeout: float = 8.0,
    max_attempts: int = 3,
    base_delay: float = 0.6,
    rate_limiter: Optional[RateLimiter] = None,
    opener: Callable = urllib.request.urlopen,
    sleep_fn: Callable[[float], None] = time.sleep,
    rand_fn: Callable[[float, float], float] = random.uniform,
) -> HttpResult:
    last_err = ""
    for attempt in range(1, max_attempts + 1):
        if rate_limiter is not None:
            rate_limiter.wait()
        retry_after = None
        try:
            with opener(req, timeout=timeout) as resp:
                code = getattr(resp, "status", 200)
                return HttpResult(ok=True, status_code=code, body_bytes=resp.read())
        except urllib.error.HTTPError as e:
            code = getattr(e, "code", None)
            if code in (400, 404, 410):
                return HttpResult(ok=False, status_code=code, error_kind="HTTP_ERROR", error_msg=f"HTTP {code}")
            last_err = f"HTTP {code}"
            if code == 429:
                retry_after = _parse_retry_after(getattr(e, "headers", None))
        except (TimeoutError, socket.timeout) as e:
            last_err = f"Timeout: {e}"
        except urllib.error.URLError as e:
            last_err = f"Network error: {e.reason}"
        except Exception as e:
            last_err = str(e)

        if attempt < max_attempts:
            delay = retry_after if retry_after is not None else base_delay * (2 ** (attempt - 1)) + rand_fn(0.05, 0.25)
            sleep_fn(delay)

    return HttpResult(ok=False, error_kind="TRANSIENT", error_msg=last_err or "Request failed")


def score_lrclib_candidate(item: dict, expected_artist: str, expected_title: str) -> Tuple[bool, float, str]:
    """Validate an LRCLIB result against expected artist, title, version, and lyric validity."""
    if not isinstance(item, dict):
        return False, 0.0, "Non-dict candidate"
    if item.get("instrumental") is True:
        return False, 0.0, "Instrumental track"

    cand_title = str(item.get("trackName") or item.get("name") or "")
    cand_artist = str(item.get("artistName") or "")
    exp_title_toks = tokenize(expected_title)
    exp_artist_toks = tokenize(expected_artist)
    cand_title_toks = tokenize(cand_title)
    cand_artist_toks = tokenize(cand_artist)

    if not exp_title_toks or not cand_title_toks:
        return False, 0.0, "Empty title tokens"

    title_overlap = len(exp_title_toks & cand_title_toks) / max(len(exp_title_toks), 1)
    if title_overlap < 0.6:
        return False, 0.0, f"Title mismatch ({cand_title!r} vs {expected_title!r})"

    if exp_artist_toks:
        artist_overlap = len(exp_artist_toks & cand_artist_toks) / max(len(exp_artist_toks), 1)
        if artist_overlap < 0.5:
            return False, 0.0, f"Artist mismatch ({cand_artist!r} vs {expected_artist!r})"
    else:
        artist_overlap = 1.0

    exp_versions = extract_version_markers(expected_title)
    cand_versions = extract_version_markers(cand_title)
    if cand_versions - exp_versions:
        return False, 0.0, f"Version mismatch ({cand_versions - exp_versions})"

    synced = str(item.get("syncedLyrics") or "").strip()
    plain = str(item.get("plainLyrics") or "").strip()
    if not synced and not plain:
        return False, 0.0, "Empty lyrics"

    ts_list, _, out_of_order = parse_lrc_timestamps(synced)
    if synced and not ts_list:
        return False, 0.0, "syncedLyrics lacks valid timestamps"
    if out_of_order:
        return False, 0.0, "syncedLyrics timestamps out of order"

    dur = float(item.get("duration") or 0)
    if ts_list and dur > 0 and (ts_list[-1] / 1000.0) > dur + 30:
        return False, 0.0, "LRCLIB duration inconsistent with last timestamp"

    score = title_overlap * 2.0 + artist_overlap * 2.0 + (1.0 if ts_list else 0.0)
    return True, score, "OK"


def select_best_lrclib(items: Iterable[dict], expected_artist: str, expected_title: str) -> Tuple[Optional[dict], str]:
    best = None
    best_score = -1.0
    reasons = []
    for item in items:
        ok, score, reason = score_lrclib_candidate(item, expected_artist, expected_title)
        if ok and score > best_score:
            best = item
            best_score = score
        elif not ok:
            reasons.append(reason)
    if best is not None:
        return best, "OK"
    return None, (reasons[0] if reasons else "No matching LRCLIB candidate")


def extract_youtube_candidates(resp_json: dict) -> List[dict]:
    """Extract structured candidate metadata from YouTube search response."""
    candidates: List[dict] = []
    if not isinstance(resp_json, dict):
        return candidates
    sections = (
        resp_json.get("contents", {})
        .get("twoColumnSearchResultsRenderer", {})
        .get("primaryContents", {})
        .get("sectionListRenderer", {})
        .get("contents", [])
    )
    for sec in sections:
        items = sec.get("itemSectionRenderer", {}).get("contents", [])
        for it in items:
            vr = it.get("videoRenderer")
            if not isinstance(vr, dict):
                continue
            vid = vr.get("videoId")
            if not is_valid_video_id(vid):
                continue
            title_runs = vr.get("title", {}).get("runs") or []
            title = "".join(r.get("text", "") for r in title_runs if isinstance(r, dict)) or str(vr.get("title", {}).get("simpleText") or "")
            owner_runs = (
                vr.get("ownerText", {}).get("runs")
                or vr.get("longBylineText", {}).get("runs")
                or vr.get("shortBylineText", {}).get("runs")
                or []
            )
            channel = "".join(r.get("text", "") for r in owner_runs if isinstance(r, dict))
            dur_text = str(vr.get("lengthText", {}).get("simpleText") or "")
            duration_sec = parse_duration_text(dur_text)
            candidates.append(
                {
                    "videoId": vid,
                    "title": title,
                    "channel": channel,
                    "durationSeconds": duration_sec,
                }
            )
    return candidates


def validate_youtube_match(
    cand: dict,
    expected_artist: str,
    expected_title: str,
    expected_duration_sec: Optional[int],
) -> Tuple[bool, float, str]:
    vid = cand.get("videoId")
    if not is_valid_video_id(vid):
        return False, 0.0, "Invalid videoId"

    yt_title = str(cand.get("title") or "")
    yt_channel = str(cand.get("channel") or "")
    yt_dur = cand.get("durationSeconds")

    if yt_dur is None:
        return False, 0.0, "Missing duration (possible livestream or ambiguous video)"

    exp_versions = extract_version_markers(expected_title)
    yt_versions = extract_version_markers(yt_title)
    if yt_versions - exp_versions:
        return False, 0.0, f"Rejected version marker(s) {sorted(yt_versions - exp_versions)} in {yt_title!r}"

    exp_title_toks = tokenize(expected_title)
    yt_title_toks = tokenize(yt_title)
    if not exp_title_toks or not yt_title_toks:
        return False, 0.0, "Empty title tokens"

    title_overlap = len(exp_title_toks & yt_title_toks) / max(len(exp_title_toks), 1)
    if title_overlap < 0.6:
        return False, 0.0, f"Title mismatch ({yt_title!r})"

    exp_artist_toks = tokenize(expected_artist)
    combined_yt_toks = tokenize(yt_title) | tokenize(yt_channel)
    if exp_artist_toks:
        artist_overlap = len(exp_artist_toks & combined_yt_toks) / max(len(exp_artist_toks), 1)
        if artist_overlap < 0.5:
            return False, 0.0, f"Artist mismatch ({yt_channel!r} / {yt_title!r})"
    else:
        artist_overlap = 1.0

    if expected_duration_sec and expected_duration_sec > 0:
        diff = abs(int(yt_dur) - int(expected_duration_sec))
        max_diff = max(8, int(expected_duration_sec * 0.05))
        if diff > max_diff:
            return False, 0.0, f"Duration mismatch (yt={yt_dur}s vs lrc={expected_duration_sec}s)"

    # Prefer official audio / topic / VEVO channels
    bonus = 0.5 if any(k in yt_channel.lower() for k in ("topic", "vevo", "official")) or "official audio" in yt_title.lower() else 0.0
    score = title_overlap * 2.0 + artist_overlap * 2.0 + bonus
    return True, score, "OK"


def select_matching_youtube_videos(
    candidates: Iterable[dict],
    expected_artist: str,
    expected_title: str,
    expected_duration_sec: Optional[int],
    max_results: int = 2,
) -> Tuple[List[str], List[str]]:
    scored: List[Tuple[float, str]] = []
    rejected: List[str] = []
    seen = set()
    for cand in candidates:
        vid = cand.get("videoId")
        if not vid or vid in seen:
            continue
        ok, score, reason = validate_youtube_match(cand, expected_artist, expected_title, expected_duration_sec)
        if ok:
            seen.add(vid)
            scored.append((score, vid))
        else:
            rejected.append(f"{vid}: {reason}")
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [vid for _, vid in scored[:max_results]], rejected


class VideoLockPool:
    """Per-videoId lock pool to prevent concurrent writes to the same lyric file."""

    def __init__(self):
        self._guard = threading.Lock()
        self._locks: Dict[str, threading.Lock] = {}

    def for_video(self, video_id: str) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(video_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[video_id] = lock
            return lock


def atomic_write_json(filepath: str, data: dict):
    parent = os.path.dirname(os.path.abspath(filepath))
    os.makedirs(parent, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=f".{os.path.basename(filepath)}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = tmp.name
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, filepath)
        tmp_path = None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def build_lyric_payload(vid: str, lrc_obj: dict, fallback_title: str, fallback_artist: str) -> dict:
    song_title = str(lrc_obj.get("trackName") or fallback_title or "").strip()
    artist_name = str(lrc_obj.get("artistName") or fallback_artist or "").strip()
    album_name = str(lrc_obj.get("albumName") or "").strip()
    duration = int(lrc_obj.get("duration") or 0)
    plain_lyrics = str(lrc_obj.get("plainLyrics") or "")
    synced_lyrics = str(lrc_obj.get("syncedLyrics") or "")
    ts_list, _, out_of_order = parse_lrc_timestamps(synced_lyrics)
    if synced_lyrics.strip() and (not ts_list or out_of_order):
        if not plain_lyrics.strip():
            plain_lyrics = synced_lyrics
        synced_lyrics = ""

    return {
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
                "contributorEmail": "lyrics@hifi.org",
            }
        ],
    }


def _is_curated_entry(entry: dict) -> bool:
    contributor = str(entry.get("contributor") or "")
    vote = int(entry.get("vote") or 0)
    return (contributor and contributor != "LRCLIB / HiFi Community") or vote > 100


def save_lyric_if_better(
    lyrics_dir: str,
    vid: str,
    lrc_obj: dict,
    fallback_title: str,
    fallback_artist: str,
    lock_pool: Optional[VideoLockPool] = None,
) -> str:
    """
    Protect curated/synced data and write atomically under a per-videoId lock.
    Returns: "saved" | "skipped_curated" | "skipped_synced_preserved" | "skipped_unchanged" | "skipped_invalid"
    """
    if not is_valid_video_id(vid):
        return "skipped_invalid"
    new_payload = build_lyric_payload(vid, lrc_obj, fallback_title, fallback_artist)
    new_entry = new_payload["data"][0]
    new_has_sync = bool(parse_lrc_timestamps(new_entry["syncedLyrics"])[0])
    new_has_plain = bool(new_entry["plainLyric"].strip())
    if not new_has_sync and not new_has_plain:
        return "skipped_invalid"

    filepath = os.path.join(lyrics_dir, f"{vid}.json")
    lock = lock_pool.for_video(vid) if lock_pool else threading.Lock()
    with lock:
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                ex_data = existing.get("data") if isinstance(existing, dict) else None
                if isinstance(ex_data, list) and ex_data and isinstance(ex_data[0], dict):
                    ex_entry = ex_data[0]
                    if _is_curated_entry(ex_entry):
                        return "skipped_curated"
                    ex_has_sync = bool(parse_lrc_timestamps(str(ex_entry.get("syncedLyrics") or ""))[0])
                    if ex_has_sync and not new_has_sync:
                        return "skipped_synced_preserved"
                    if existing == new_payload:
                        return "skipped_unchanged"
            except Exception:
                # Corrupted existing file can be replaced if new payload is valid
                pass

        atomic_write_json(filepath, new_payload)
        return "saved"


def audit_catalog(lyrics_dir: str) -> dict:
    """Audit all files in v1/lyrics and return structured report."""
    report = {
        "total_json_files": 0,
        "valid_tracks": 0,
        "unique_songs": 0,
        "synced_tracks": 0,
        "unsynced_tracks": 0,
        "ts_3digit_files": 0,
        "non_json_files": [],
        "invalid_json": [],
        "invalid_schema": [],
        "vid_mismatch": [],
        "empty_both": [],
        "synced_no_ts": [],
        "ts_out_of_order": [],
        "duration_mismatch": [],
    }
    if not os.path.isdir(lyrics_dir):
        return report

    unique_songs = set()
    for fn in sorted(os.listdir(lyrics_dir)):
        path = os.path.join(lyrics_dir, fn)
        if not os.path.isfile(path):
            continue
        if not fn.endswith(".json"):
            report["non_json_files"].append(fn)
            continue
        report["total_json_files"] += 1
        vid = fn[:-5]
        if not is_valid_video_id(vid):
            report["invalid_schema"].append(f"{fn}: invalid videoId filename")
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception as e:
            report["invalid_json"].append(f"{fn}: {e}")
            continue

        if (
            not isinstance(obj, dict)
            or obj.get("success") is not True
            or not isinstance(obj.get("data"), list)
            or not obj["data"]
            or not isinstance(obj["data"][0], dict)
        ):
            report["invalid_schema"].append(fn)
            continue

        entry = obj["data"][0]
        if entry.get("videoId") != vid or entry.get("id") != vid:
            report["vid_mismatch"].append(fn)
            continue

        sl = str(entry.get("syncedLyrics") or "")
        pl = str(entry.get("plainLyric") or "")
        dur = entry.get("durationSeconds") or 0

        if not sl.strip() and not pl.strip():
            report["empty_both"].append(fn)
            continue

        song_key = (normalize_text(str(entry.get("artistName") or "")), normalize_text(str(entry.get("songTitle") or "")))
        if any(song_key):
            unique_songs.add(song_key)

        if sl.strip():
            ts_list, has_3d, out_of_order = parse_lrc_timestamps(sl)
            if not ts_list:
                report["synced_no_ts"].append(fn)
                continue
            if has_3d:
                report["ts_3digit_files"] += 1
            if out_of_order:
                report["ts_out_of_order"].append(fn)
            last_sec = ts_list[-1] / 1000.0
            if isinstance(dur, (int, float)) and dur > 0 and last_sec > dur + 30:
                report["duration_mismatch"].append((fn, dur, round(last_sec, 1)))
            report["synced_tracks"] += 1
        else:
            report["unsynced_tracks"] += 1

        report["valid_tracks"] += 1

    report["unique_songs"] = len(unique_songs)
    return report


def update_index_if_changed(index_path: str, lyrics_dir: str, status: str = "online") -> Tuple[bool, dict]:
    """
    Update v1/index.json only if catalog counts or status actually changed.
    Returns (changed, index_data).
    """
    audit = audit_catalog(lyrics_dir)
    flagged = (
        len(audit["invalid_json"])
        + len(audit["invalid_schema"])
        + len(audit["vid_mismatch"])
        + len(audit["empty_both"])
        + len(audit["synced_no_ts"])
    )
    candidate = {
        "service": "HiFi Lyrics Repository",
        "version": "2.0.0",
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_tracks": audit["total_json_files"],
        "index_basis": "video_id_files",
        "valid_tracks": audit["valid_tracks"],
        "unique_songs": audit["unique_songs"],
        "synced_tracks": audit["synced_tracks"],
        "unsynced_tracks": audit["unsynced_tracks"],
        "flagged_tracks": flagged,
        "status": status,
    }

    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, dict):
                comparable_keys = (
                    "service",
                    "version",
                    "total_tracks",
                    "index_basis",
                    "valid_tracks",
                    "unique_songs",
                    "synced_tracks",
                    "unsynced_tracks",
                    "flagged_tracks",
                    "status",
                )
                if all(existing.get(k) == candidate.get(k) for k in comparable_keys):
                    return False, existing
        except Exception:
            pass

    atomic_write_json(index_path, candidate)
    return True, candidate

