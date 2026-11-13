#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legacy entrypoint consolidated with scripts/sync-lyrics.py so all bug fixes
(match validation, rate-limiting, atomic per-videoId writes, index guard)
apply uniformly.
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("sync_lyrics_mod", os.path.join(SCRIPT_DIR, "sync-lyrics.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def main() -> int:
    return _mod.run_sync()


if __name__ == "__main__":
    sys.exit(main())
