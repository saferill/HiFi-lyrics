# HiFi Synced Lyrics Repository (`HiFi-lyrics`)

Community-curated and automated synchronized lyrics cache for **[HiFi Music](https://github.com/saferill/HiFi)**.

Provides millisecond-accurate, time-synced (`LINE_SYNCED`) lyrics formatted for smooth scrolling and real-time word highlighting, with multi-provider fallbacks.

---

## Directory Structure

```
.
├── v1/
│   ├── index.json                 # Repository health, catalog statistics, and index status
│   ├── lyrics/
│   │   ├── <videoId>.json         # Synced lyrics keyed by YouTube videoId (e.g., jfKfPfyJRdk.json)
│   │   └── seed_<hash>.json       # Pre-harvested lyrics for popular charts and viral hits
│   └── translated/
│       └── <videoId>/<lang>.json  # Localized line-by-line translated lyrics (id, en, ja, etc.)
├── scripts/
│   ├── sync-lyrics.py             # Multi-source harvesting script with rate-limiting & deduplication
│   └── sync-lyrics.sh             # Shell runner
└── .github/workflows/
    └── sync-lyrics.yml            # Automated scheduled harvester
```

---

## Lyric File Specification

Each lyric file is stored in pure JSON format:

```json
{
  "title": "Dan",
  "artist": "Sheila On 7",
  "syncType": "LINE_SYNCED",
  "lines": [
    {
      "startTimeMs": "16540",
      "words": "Dan..."
    },
    {
      "startTimeMs": "19040",
      "words": "Dan bila esok datang kembali"
    },
    {
      "startTimeMs": "26790",
      "words": "Seperti sedia kala"
    }
  ]
}
```

### Fields
* **`syncType`**: `"LINE_SYNCED"` for time-aligned karaoke playback, or `"UNSYNCED"` for plain text.
* **`startTimeMs`**: Playback timestamp in milliseconds from track start. HiFi uses a binary search lookup to highlight the active line with sub-frame precision.

---

## Client Resolution Strategy

When a song begins playing in HiFi, the lyric engine checks providers in this order:

```
1. HiFi-lyrics Repository (Local Cache & Raw GitHub)
         ↓ (if missing)
2. LRCLIB Public API (Search by Title + Artist + Duration)
         ↓ (if missing)
3. Spotify Canvas & Synced Lyrics
         ↓ (if missing)
4. YouTube Timed Captions (Embedded CC)
```

This multi-tier fallback ensures over 95% lyric coverage across both mainstream pop hits and niche indie music.

---

## License

Open-source under the [GPL-3.0 License](https://www.gnu.org/licenses/gpl-3.0.html). Lyric contents belong to their respective authors and copyright holders.
