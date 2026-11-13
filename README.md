# HiFi Synced Lyrics Repository (`HiFi-lyrics`)

Community-curated and automated lyrics database for **[HiFi Music](https://github.com/saferill/HiFi)**.

Provides both time-synced (`LINE_SYNCED`, supporting 1-, 2-, and 3-digit fractional timestamps) and plain-text (`UNSYNCED`) lyrics via static GitHub Raw JSON endpoints.

---

## Architecture & Endpoints

Static catalog reads use GitHub Raw storage (read-only):

* **Single Track Lookup Endpoint**:
  ```
  https://raw.githubusercontent.com/saferill/HiFi-lyrics/refs/heads/main/v1/lyrics/{videoId}.json
  ```
  where `{videoId}` is a valid 11-character YouTube video ID (`[A-Za-z0-9_-]{11}`, e.g. `7Jm2Il2U-c0.json`).

* **Catalog Index & Health Status**:
  ```
  https://raw.githubusercontent.com/saferill/HiFi-lyrics/refs/heads/main/v1/index.json
  ```
  - `total_tracks`: count of `.json` lyric files (`index_basis: "video_id_files"`).
  - `unique_songs`: count of unique normalized `(artistName, songTitle)` pairs.
  - `synced_tracks` / `unsynced_tracks` / `flagged_tracks`: catalog breakdown from `scripts/validate-lyrics.py`.

* **Translated Lyrics Endpoint (Optional / Community-Contributed)**:
  ```
  https://raw.githubusercontent.com/saferill/HiFi-lyrics/refs/heads/main/v1/translated/{videoId}/{language}.json
  ```
  *Note:* `v1/translated/` is optional and only populated when community-contributed files are committed; GitHub Raw is read-only and does not serve dynamic insert, vote, or AI translation mutations.

---

## Lyric File Specification

Each lyric file follows the `BaseResponse<List<LyricsResponse>>` schema expected by `HiFiLyricsClient`:

```json
{
  "success": true,
  "error": null,
  "data": [
    {
      "id": "7Jm2Il2U-c0",
      "videoId": "7Jm2Il2U-c0",
      "songTitle": "Satu Bulan",
      "artistName": "Bernadya",
      "albumName": "Sialnya, Hidup Harus Tetap Berjalan",
      "durationSeconds": 194,
      "plainLyric": "Sudah satu bulan kau tinggal kelana...",
      "syncedLyrics": "[00:13.40]Sudah satu bulan kau tinggal kelana\n[00:17.15]Banyak malam ku lalui tanpa cerita\n...",
      "richSyncLyrics": null,
      "trackType": null,
      "vote": 100,
      "contributor": "LRCLIB / HiFi Community",
      "contributorEmail": "lyrics@hifi.org"
    }
  ]
}
```

---

## Directory Structure

```
.
├── v1/
│   ├── index.json                 # Catalog statistics & validation summary
│   ├── lyrics/
│   │   └── <videoId>.json         # Synced or unsynced lyrics keyed by YouTube videoId
│   └── translated/                # Optional community-contributed translations
├── scripts/
│   ├── lyrics_common.py           # Shared HTML parser, matcher, retry/rate-limit, atomic writer & validator
│   ├── sync-lyrics.py             # Main harvesting script
│   ├── harvest-lyrics.py          # Consolidated legacy entrypoint -> sync-lyrics.py
│   ├── validate-lyrics.py         # Catalog auditor, safe fixer, and index updater
│   └── sync-lyrics.sh             # Shell runner for CI/CD (pushes to current branch)
├── tests/
│   └── test_lyrics_pipeline.py    # Offline unit tests (mocked HTTP, temp dirs)
└── .github/workflows/
    └── sync-lyrics.yml            # Scheduled every 2 hours (0 */2 * * *) with concurrency guard
```

---

## Automated Sync (Bot Pipeline)

`.github/workflows/sync-lyrics.yml` is scheduled every 2 hours (`0 */2 * * *`, best-effort on GitHub Actions) and supports `workflow_dispatch`:
1. Fetches Spotify chart HTML from Kworb using `HTMLParser` + entity decoding and combines with curated seed tracks.
2. Queries [LRCLIB](https://lrclib.net/) and YouTube Innertube with rate-limiting, timeouts, and bounded retries (`429` / `5xx`).
3. Validates title, artist, version markers (rejecting mismatched live/cover/remix/karaoke videos), and duration before saving.
4. Protects existing curated or synced lyrics via per-`videoId` locks and atomic file writes.
5. Validates the catalog and updates `v1/index.json` only when catalog metrics change.
