#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validate and safely repair HiFi-lyrics v1/lyrics catalog and v1/index.json.
"""

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
LYRICS_DIR = os.path.join(BASE_DIR, "v1", "lyrics")
INDEX_FILE = os.path.join(BASE_DIR, "v1", "index.json")

from lyrics_common import (  # noqa: E402
    atomic_write_json,
    audit_catalog,
    parse_lrc_timestamps,
    update_index_if_changed,
)


def fix_safe_issues(lyrics_dir: str) -> dict:
    """
    Apply ONLY deterministic, non-fabricating repairs:
    1. Convert legacy non-BaseResponse jfKfPfyJRdk.json into BaseResponse schema
       without inventing timestamps or artist metadata.
    2. For files where syncedLyrics contains only plain text (zero timestamps),
       move text to plainLyric if empty and clear syncedLyrics so players fall back cleanly.
    """
    fixed = {"schema_migrated": [], "unsynced_cleared": []}
    if not os.path.isdir(lyrics_dir):
        return fixed

    for fn in sorted(os.listdir(lyrics_dir)):
        if not fn.endswith(".json"):
            continue
        vid = fn[:-5]
        path = os.path.join(lyrics_dir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            continue

        # 1. Legacy schema migration (e.g., jfKfPfyJRdk.json)
        if (
            isinstance(obj, dict)
            and "data" not in obj
            and isinstance(obj.get("lines"), list)
            and obj.get("videoId") == vid
        ):
            words = "\n".join(
                str(line.get("words") or "").strip()
                for line in obj.get("lines", [])
                if isinstance(line, dict) and str(line.get("words") or "").strip()
            )
            migrated = {
                "success": True,
                "error": None,
                "data": [
                    {
                        "id": vid,
                        "videoId": vid,
                        "songTitle": str(obj.get("title") or ""),
                        "artistName": "",
                        "albumName": "",
                        "durationSeconds": 0,
                        "plainLyric": words,
                        "syncedLyrics": "",
                        "richSyncLyrics": None,
                        "trackType": None,
                        "vote": 100,
                        "contributor": "HiFi Community",
                        "contributorEmail": "lyrics@hifi.org",
                    }
                ],
            }
            atomic_write_json(path, migrated)
            fixed["schema_migrated"].append(fn)
            continue

        # 2. syncedLyrics containing plain text without timestamps
        if (
            isinstance(obj, dict)
            and isinstance(obj.get("data"), list)
            and obj["data"]
            and isinstance(obj["data"][0], dict)
        ):
            entry = obj["data"][0]
            sl = str(entry.get("syncedLyrics") or "")
            pl = str(entry.get("plainLyric") or "")
            if sl.strip():
                ts_list, _, _ = parse_lrc_timestamps(sl)
                if not ts_list:
                    if not pl.strip():
                        entry["plainLyric"] = sl
                    entry["syncedLyrics"] = ""
                    atomic_write_json(path, obj)
                    fixed["unsynced_cleared"].append(fn)

    return fixed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate HiFi-lyrics catalog and index.")
    parser.add_argument("--lyrics-dir", default=LYRICS_DIR)
    parser.add_argument("--index-file", default=INDEX_FILE)
    parser.add_argument("--fix-safe", action="store_true", help="Apply deterministic non-fabricating schema/unsynced fixes")
    parser.add_argument("--update-index", action="store_true", help="Update v1/index.json if catalog metrics changed")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any schema/empty/synced_no_ts issues remain")
    args = parser.parse_args(argv)

    if args.fix_safe:
        fixed = fix_safe_issues(args.lyrics_dir)
        print(f"Safe fixes applied -> schema_migrated={fixed['schema_migrated']}, unsynced_cleared={fixed['unsynced_cleared']}")

    report = audit_catalog(args.lyrics_dir)
    print(f"Catalog audit summary ({args.lyrics_dir}):")
    print(f"  total_json_files  : {report['total_json_files']}")
    print(f"  valid_tracks      : {report['valid_tracks']}")
    print(f"  unique_songs      : {report['unique_songs']}")
    print(f"  synced_tracks     : {report['synced_tracks']} (3-digit ms files: {report['ts_3digit_files']})")
    print(f"  unsynced_tracks   : {report['unsynced_tracks']}")
    print(f"  non_json_files    : {report['non_json_files']}")
    print(f"  invalid_json      : {len(report['invalid_json'])}")
    print(f"  invalid_schema    : {report['invalid_schema']}")
    print(f"  vid_mismatch      : {report['vid_mismatch']}")
    print(f"  empty_both        : {report['empty_both']}")
    print(f"  synced_no_ts      : {report['synced_no_ts']}")
    print(f"  ts_out_of_order   : {report['ts_out_of_order']}")
    print(f"  duration_mismatch : {len(report['duration_mismatch'])} (flagged for review; sample: {report['duration_mismatch'][:5]})")

    if args.update_index:
        changed, idx = update_index_if_changed(args.index_file, args.lyrics_dir, status="online")
        print(f"Index {'updated' if changed else 'unchanged'}: total_tracks={idx['total_tracks']}, unique_songs={idx['unique_songs']}")

    if args.strict and (
        report["invalid_json"]
        or report["invalid_schema"]
        or report["vid_mismatch"]
        or report["synced_no_ts"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

