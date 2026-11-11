# HiFi Lyrics (`HiFi-lyrics`)

Community synced lyrics & translation repository for **[HiFi Music](https://github.com/saferill/HiFi)**.

## Structure
- `v1/lyrics/<videoId>.json`: Time-synced lyrics keyed by YouTube `videoId`.
- `v1/translated/<videoId>/<lang>.json`: Translated synced lyrics keyed by `videoId` and ISO-639-1 language code (`id`, `en`, etc.).
- Automatic multi-provider fallback (`BetterLyrics`, `LRCLIB`, `Spotify`, and crowdsourced index).