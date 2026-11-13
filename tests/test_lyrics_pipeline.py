#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Offline unit tests for HiFi-lyrics pipeline (mocked HTTP, temp directories).
"""

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(TESTS_DIR)
SCRIPTS_DIR = os.path.join(REPO_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import lyrics_common  # noqa: E402


def _load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS_DIR, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sync_lyrics = _load_script("sync_lyrics_mod", "sync-lyrics.py")
validate_lyrics = _load_script("validate_lyrics_mod", "validate-lyrics.py")


class FakeResp:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestChartParserAndTimestamps(unittest.TestCase):
    def test_kworb_html_variations_and_html_entities(self):
        html = """
        <table><tbody>
          <tr>
            <td class="text mp"><div><a href="../artist/abc">Guns N&#39; Roses</a> - <a href="../track/xyz">Sweet Child O&#39; Mine</a></div></td>
          </tr>
          <tr>
            <td class="other"><a href="/artist/123">Maliq &amp; D&#39;Essentials</a> - <a href="/track/456">Kita Bikin Romantis</a></td>
          </tr>
        </tbody></table>
        """
        tracks = lyrics_common.parse_kworb_chart_html(html)
        self.assertEqual(
            tracks,
            [
                ("Guns N' Roses", "Sweet Child O' Mine"),
                ("Maliq & D'Essentials", "Kita Bikin Romantis"),
            ],
        )

    def test_parse_lrc_timestamps_1_2_3_digits_and_order(self):
        lrc = "[00:21.2]A\n[00:27.89]B\n[00:21.252]C"
        ts, has_3d, out_of_order = lyrics_common.parse_lrc_timestamps(lrc)
        self.assertEqual(ts, [21200, 27890, 21252])
        self.assertTrue(has_3d)
        self.assertTrue(out_of_order)

        ts_ok, has_3d_ok, out_ok = lyrics_common.parse_lrc_timestamps("[00:21.2]A\n[00:21.252]B\n[00:27.89]C")
        self.assertEqual(ts_ok, [21200, 21252, 27890])
        self.assertTrue(has_3d_ok)
        self.assertFalse(out_ok)


class TestMatchingAndProtection(unittest.TestCase):
    def test_rejects_wrong_version_artist_duration_and_invalid_videoid(self):
        lrc_items = [
            {
                "trackName": "Satu Bulan",
                "artistName": "Bernadya",
                "duration": 194,
                "syncedLyrics": "[00:13.40]Sudah satu bulan\n[00:17.15]Banyak malam",
            },
            {
                "trackName": "Satu Bulan (Live)",
                "artistName": "Bernadya",
                "duration": 194,
                "syncedLyrics": "[00:13.40]Live version",
            },
        ]
        best, _ = lyrics_common.select_best_lrclib(lrc_items, "Bernadya", "Satu Bulan")
        self.assertIsNotNone(best)
        self.assertEqual(best["trackName"], "Satu Bulan")

        yt_candidates = [
            {"videoId": "badid", "title": "Bernadya - Satu Bulan", "channel": "Bernadya", "durationSeconds": 194},
            {"videoId": "vidLive1234", "title": "Bernadya - Satu Bulan (Live Acoustic)", "channel": "Bernadya", "durationSeconds": 194},
            {"videoId": "vidCover123", "title": "Satu Bulan - Cover by Someone", "channel": "CoverGuy", "durationSeconds": 194},
            {"videoId": "vidWrongDur", "title": "Bernadya - Satu Bulan", "channel": "Bernadya", "durationSeconds": 320},
            {"videoId": "vidNoDur123", "title": "Bernadya - Satu Bulan", "channel": "Bernadya", "durationSeconds": None},
            {"videoId": "7Jm2Il2U-c0", "title": "Bernadya - Satu Bulan (Official Audio)", "channel": "Bernadya - Topic", "durationSeconds": 195},
        ]
        matched, rejected = lyrics_common.select_matching_youtube_videos(yt_candidates, "Bernadya", "Satu Bulan", 194)
        self.assertEqual(matched, ["7Jm2Il2U-c0"])
        self.assertEqual(len(rejected), 5)

    def test_protects_curated_and_synced_lyrics_from_worse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 1. Existing synced file must not be overwritten by unsynced lyrics
            vid = "7Jm2Il2U-c0"
            synced_lrc = {
                "trackName": "Satu Bulan",
                "artistName": "Bernadya",
                "duration": 194,
                "syncedLyrics": "[00:13.40]Sudah satu bulan",
                "plainLyrics": "Sudah satu bulan",
            }
            self.assertEqual(lyrics_common.save_lyric_if_better(tmp, vid, synced_lrc, "Satu Bulan", "Bernadya"), "saved")

            unsynced_lrc = {
                "trackName": "Satu Bulan",
                "artistName": "Bernadya",
                "duration": 194,
                "syncedLyrics": "",
                "plainLyrics": "Sudah satu bulan",
            }
            self.assertEqual(
                lyrics_common.save_lyric_if_better(tmp, vid, unsynced_lrc, "Satu Bulan", "Bernadya"),
                "skipped_synced_preserved",
            )

            # 2. Curated file (custom contributor or vote > 100) must never be overwritten
            vid2 = "abCdeFg1234"
            curated_payload = {
                "success": True,
                "error": None,
                "data": [
                    {
                        "id": vid2,
                        "videoId": vid2,
                        "songTitle": "Test",
                        "artistName": "Artist",
                        "albumName": "",
                        "durationSeconds": 180,
                        "plainLyric": "Custom",
                        "syncedLyrics": "[00:01.00]Custom",
                        "richSyncLyrics": None,
                        "trackType": None,
                        "vote": 150,
                        "contributor": "Manual Curator",
                        "contributorEmail": "lyrics@hifi.org",
                    }
                ],
            }
            lyrics_common.atomic_write_json(os.path.join(tmp, f"{vid2}.json"), curated_payload)
            self.assertEqual(
                lyrics_common.save_lyric_if_better(tmp, vid2, synced_lrc, "Test", "Artist"),
                "skipped_curated",
            )

    def test_concurrent_writes_to_same_videoid_stay_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool = lyrics_common.VideoLockPool()
            vid = "conCurR3nt1"

            def writer(i):
                lrc = {
                    "trackName": f"Song {i}",
                    "artistName": "Artist",
                    "duration": 180,
                    "syncedLyrics": f"[00:01.00]Line {i}",
                    "plainLyrics": f"Line {i}",
                }
                return lyrics_common.save_lyric_if_better(tmp, vid, lrc, f"Song {i}", "Artist", lock_pool=pool)

            with ThreadPoolExecutor(max_workers=8) as ex:
                results = list(ex.map(writer, range(20)))

            self.assertTrue(all(r in ("saved", "skipped_unchanged") for r in results))
            with open(os.path.join(tmp, f"{vid}.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertTrue(data["success"])
            self.assertEqual(data["data"][0]["videoId"], vid)


class TestNetworkRetryAndSyncFailure(unittest.TestCase):
    def test_retry_on_429_and_total_service_failure_returns_nonzero(self):
        calls = {"n": 0}
        sleeps = []

        def flaky_opener(req, timeout=8):
            calls["n"] += 1
            if calls["n"] < 3:
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {"Retry-After": "1"}, io.BytesIO(b""))
            return FakeResp(b'[{"trackName":"Satu Bulan","artistName":"Bernadya","duration":194,"syncedLyrics":"[00:13.40]Hi"}]')

        req = urllib.request.Request("https://lrclib.net/api/search?q=test")
        res = lyrics_common.request_with_retry(req, max_attempts=3, opener=flaky_opener, sleep_fn=sleeps.append)
        self.assertTrue(res.ok)
        self.assertEqual(calls["n"], 3)
        self.assertEqual(sleeps, [1.0, 1.0])

        # Total failure must exit non-zero and must NOT create a misleading index.json
        with tempfile.TemporaryDirectory() as tmp:
            lyrics_dir = os.path.join(tmp, "lyrics")
            index_file = os.path.join(tmp, "index.json")
            os.makedirs(lyrics_dir, exist_ok=True)

            def failing_opener(req, timeout=8):
                raise TimeoutError("Network down")

            rc = sync_lyrics.run_sync(
                tracks=[("Bernadya", "Satu Bulan")],
                lyrics_dir=lyrics_dir,
                index_file=index_file,
                opener=failing_opener,
                sleep_fn=lambda _: None,
            )
            self.assertEqual(rc, 1)
            self.assertFalse(os.path.exists(index_file))


class TestValidationFixAndIndexNoOp(unittest.TestCase):
    def test_fix_safe_migrates_legacy_schema_clears_plain_synced_and_preserves_3digit(self):
        with tempfile.TemporaryDirectory() as tmp:
            lyrics_dir = os.path.join(tmp, "lyrics")
            index_file = os.path.join(tmp, "index.json")
            os.makedirs(lyrics_dir, exist_ok=True)

            # 1. Legacy non-BaseResponse file (like jfKfPfyJRdk.json)
            with open(os.path.join(lyrics_dir, "jfKfPfyJRdk.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "videoId": "jfKfPfyJRdk",
                        "title": "Lofi Hip Hop Radio",
                        "syncType": "LINE_SYNCED",
                        "lines": [{"startTimeMs": "0", "words": "Lofi beats"}],
                    },
                    f,
                )

            # 2. syncedLyrics containing plain text without timestamps
            with open(os.path.join(lyrics_dir, "plainInSyn1.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "success": True,
                        "error": None,
                        "data": [
                            {
                                "id": "plainInSyn1",
                                "videoId": "plainInSyn1",
                                "songTitle": "Song A",
                                "artistName": "Artist A",
                                "durationSeconds": 180,
                                "plainLyric": "Hello world",
                                "syncedLyrics": "Hello world",
                            }
                        ],
                    },
                    f,
                )

            # 3. Valid 3-digit millisecond file must be preserved untouched
            lrc_3d = "[00:21.252]Three digit line"
            with open(os.path.join(lyrics_dir, "threeDigit1.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "success": True,
                        "error": None,
                        "data": [
                            {
                                "id": "threeDigit1",
                                "videoId": "threeDigit1",
                                "songTitle": "Song B",
                                "artistName": "Artist B",
                                "durationSeconds": 180,
                                "plainLyric": "Three digit line",
                                "syncedLyrics": lrc_3d,
                            }
                        ],
                    },
                    f,
                )

            rc = validate_lyrics.main(["--lyrics-dir", lyrics_dir, "--index-file", index_file, "--fix-safe", "--update-index", "--strict"])
            self.assertEqual(rc, 0)

            with open(os.path.join(lyrics_dir, "jfKfPfyJRdk.json"), "r", encoding="utf-8") as f:
                migrated = json.load(f)
            self.assertTrue(migrated["success"])
            self.assertEqual(migrated["data"][0]["plainLyric"], "Lofi beats")

            with open(os.path.join(lyrics_dir, "plainInSyn1.json"), "r", encoding="utf-8") as f:
                fixed_plain = json.load(f)
            self.assertEqual(fixed_plain["data"][0]["syncedLyrics"], "")
            self.assertEqual(fixed_plain["data"][0]["plainLyric"], "Hello world")

            with open(os.path.join(lyrics_dir, "threeDigit1.json"), "r", encoding="utf-8") as f:
                preserved_3d = json.load(f)
            self.assertEqual(preserved_3d["data"][0]["syncedLyrics"], lrc_3d)

            # Index update must be a no-op on second run when catalog didn't change
            changed_again, idx = lyrics_common.update_index_if_changed(index_file, lyrics_dir)
            self.assertFalse(changed_again)
            self.assertEqual(idx["total_tracks"], 3)
            self.assertEqual(idx["unique_songs"], 3)


if __name__ == "__main__":
    unittest.main()

