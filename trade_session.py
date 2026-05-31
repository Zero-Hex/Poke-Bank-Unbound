"""
trade_session.py — Manages a secondary save loaded alongside the primary.

The primary save lives in Flask's session as usual.
The secondary save is held in a module-level dict keyed by Flask session ID
so it survives across requests without bloating the cookie.

Key design decisions:
  - Secondary save is READ + WRITE; changes are written to its file on disk.
  - We never cross-contaminate the two save's trainer data. A transferred mon
    keeps its original OT name/TID (authentic traded-mon behaviour).
  - Before any write we backup both saves (up to MAX_BACKUPS retained).
  - Transfer is atomic: write to destination first, clear source only after
    destination write succeeds.
"""

import os
import shutil
import time
from pathlib import Path

MAX_BACKUPS = 3

# Module-level store: flask_session_id -> {data, path, trainer, sections_cache}
_secondary: dict = {}


# ── backup ──────────────────────────────────────────────────────────────────

def _backup(save_path: str, label: str = "") -> str:
    """Write a timestamped backup. Prune old backups beyond MAX_BACKUPS."""
    p      = Path(save_path)
    suffix = f"_{label}" if label else ""
    ts     = int(time.time())
    bak    = p.parent / f"{p.stem}_bak{suffix}_{ts}{p.suffix}"
    shutil.copy2(p, bak)

    # Prune — keep only the newest MAX_BACKUPS backups for this stem
    pattern = f"{p.stem}_bak"
    all_baks = sorted(
        [f for f in p.parent.iterdir()
         if f.name.startswith(pattern) and f.suffix == p.suffix],
        key=lambda f: f.stat().st_mtime,
    )
    for old in all_baks[:-MAX_BACKUPS]:
        try:
            old.unlink()
        except OSError:
            pass
    return str(bak)


# ── secondary save lifecycle ─────────────────────────────────────────────────

def load_secondary(session_id: str, data: bytearray, path: str,
                   trainer: dict, sections: dict) -> None:
    """Store the secondary save in memory."""
    _secondary[session_id] = {
        "data":     data,
        "path":     path,
        "trainer":  trainer,
        "sections": sections,
    }


def get_secondary(session_id: str) -> dict | None:
    return _secondary.get(session_id)


def clear_secondary(session_id: str) -> None:
    _secondary.pop(session_id, None)


def has_secondary(session_id: str) -> bool:
    return session_id in _secondary


# ── persistence ──────────────────────────────────────────────────────────────

def flush_secondary(session_id: str) -> str:
    """Write secondary save back to disk. Returns backup path."""
    sec = _secondary.get(session_id)
    if sec is None:
        raise RuntimeError("No secondary save loaded")
    bak = _backup(sec["path"], "pre_transfer")
    Path(sec["path"]).write_bytes(sec["data"])
    return bak


def flush_primary(primary_data: bytearray, primary_path: str) -> str:
    """Write primary save back to disk. Returns backup path."""
    bak = _backup(primary_path, "pre_transfer")
    Path(primary_path).write_bytes(primary_data)
    return bak
