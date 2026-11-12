# HiFi Synced Lyrics Repository (`HiFi-lyrics`)

Community-curated and automated synchronized lyrics database for **[HiFi Music](https://github.com/saferill/HiFi)**.

Provides millisecond-accurate, time-synced (`LINE_SYNCED`) lyrics formatted for seamless real-time scrolling and lyric highlighting directly inside the HiFi mobile and desktop players.

---

## Architecture & Endpoints

All files are hosted statically via GitHub raw storage, acting as a high-performance, zero-latency serverless lyrics CDN:

* **Single Track Lookup Endpoint**:
  ```
  https://raw.githubusercontent.com/saferill/HiFi-lyrics/refs/heads/main/v1/lyrics/{videoId}.json
  ```
  where `{videoId}` is the 11-character YouTube video ID (e.g. `7Jm2Il2U-c0.json`).

* **Catalog Index & Health Status**:
  ```
  https://raw.githubusercontent.com/saferill/HiFi-lyrics/refs/heads/main/v1/index.json
  ```

* **Translated Lyrics Endpoint (Optional)**:
  ```
  https://raw.githubusercontent.com/saferill/HiFi-lyrics/refs/heads/main/v1/translated/{videoId}/{language}.json
  ```

---

## Lyric File Specification

Each lyric file follows the exact `BaseResponse<List<LyricsResponse>>` schema expected by `SimpMusicLyricsClient`:

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
│   ├── index.json                 # Repository health, catalog statistics, and index status
│   ├── lyrics/
│   │   └── <videoId>.json         # Synced lyrics keyed by YouTube videoId (e.g., 7Jm2Il2U-c0.json)
│   └── translated/
│       └── <videoId>/<lang>.json  # Localized line-by-line translated lyrics (id, en, ja, etc.)
├── scripts/
│   ├── sync-lyrics.py             # Multi-source harvesting script with rate-limiting & deduplication
│   └── sync-lyrics.sh             # Shell runner for CI/CD
└── .github/workflows/
    └── sync-lyrics.yml            # Scheduled daily automation (02:00 UTC)
```

---

## Automated Daily Sync (Bot Pipeline)

A scheduled GitHub Actions workflow (`.github/workflows/sync-lyrics.yml`) runs daily to:
1. Fetch latest daily & weekly music charts (Indonesia, Global, Billboard, K-Pop, J-Pop).
2. Harvest high-precision timestamped `.lrc` lyrics from [LRCLIB](https://lrclib.net/).
3. Query YouTube Innertube to resolve official audio & video IDs.
4. Auto-commit and push updates back to `main`.
