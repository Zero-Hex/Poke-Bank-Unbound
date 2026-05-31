"""
vault_boxes.py (cloud_boxes.py) — Per-trainer vault storage for Pokémon outside any save file.

Each trainer gets their own cloud file: data/vault_{tid}_{name}.json
This ensures Zach's cloud is separate from Tont's cloud, etc.
"""

import json, re
from pathlib import Path

CLOUD_BOX_COUNT   = 10
SLOTS_PER_BOX     = 30
MON_SIZE          = 80   # PC struct size

# ── helpers ─────────────────────────────────────────────────────────────────

def _safe(s: str) -> str:
    """Sanitise a string for use in a filename."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(s))


def _vault_path(data_dir: Path, tid: int, trainer_name: str) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    filename = f"vault_{tid}_{_safe(trainer_name)}.json"
    return data_dir / filename


def _empty_box(index: int) -> dict:
    return {
        "box":   index,
        "name":  f"Vault {index}",
        "slots": [{"mon": None} for _ in range(SLOTS_PER_BOX)],
    }


def _default_cloud() -> list:
    return [_empty_box(i + 1) for i in range(CLOUD_BOX_COUNT)]


# ── public API ───────────────────────────────────────────────────────────────

def load_cloud(data_dir: Path, tid: int = 0, trainer_name: str = "default") -> list:
    """Return list of box dicts for this trainer. Creates file if missing."""
    p = _vault_path(data_dir, tid, trainer_name)
    if not p.exists():
        cloud = _default_cloud()
        save_cloud(data_dir, cloud, tid, trainer_name)
        return cloud
    try:
        cloud = json.loads(p.read_text(encoding="utf-8"))
        while len(cloud) < CLOUD_BOX_COUNT:
            cloud.append(_empty_box(len(cloud) + 1))
        return cloud
    except Exception:
        return _default_cloud()


def save_cloud(data_dir: Path, cloud: list, tid: int = 0, trainer_name: str = "default") -> None:
    p = _vault_path(data_dir, tid, trainer_name)
    p.write_text(json.dumps(cloud, ensure_ascii=False, indent=2), encoding="utf-8")


def deposit(data_dir: Path, box: int, slot: int,
            mon_dict: dict, raw: list,
            tid: int = 0, trainer_name: str = "default") -> dict:
    cloud = load_cloud(data_dir, tid, trainer_name)
    b = next((x for x in cloud if x["box"] == box), None)
    if b is None:
        raise ValueError(f"Cloud box {box} does not exist")
    if slot < 1 or slot > SLOTS_PER_BOX:
        raise ValueError(f"Slot {slot} out of range")
    b["slots"][slot - 1] = {"mon": {**mon_dict, "raw": raw}}
    save_cloud(data_dir, cloud, tid, trainer_name)
    return cloud


def withdraw(data_dir: Path, box: int, slot: int,
             tid: int = 0, trainer_name: str = "default") -> tuple:
    cloud = load_cloud(data_dir, tid, trainer_name)
    b = next((x for x in cloud if x["box"] == box), None)
    if b is None:
        raise ValueError(f"Cloud box {box} does not exist")
    if slot < 1 or slot > SLOTS_PER_BOX:
        raise ValueError(f"Slot {slot} out of range")
    entry = b["slots"][slot - 1]
    mon = entry.get("mon")
    if mon is None:
        return None, None, cloud
    raw = mon.get("raw")
    b["slots"][slot - 1] = {"mon": None}
    save_cloud(data_dir, cloud, tid, trainer_name)
    return mon, raw, cloud


def rename_box(data_dir: Path, box: int, name: str,
               tid: int = 0, trainer_name: str = "default") -> list:
    cloud = load_cloud(data_dir, tid, trainer_name)
    b = next((x for x in cloud if x["box"] == box), None)
    if b is None:
        raise ValueError(f"Cloud box {box} does not exist")
    b["name"] = name[:20]
    save_cloud(data_dir, cloud, tid, trainer_name)
    return cloud
