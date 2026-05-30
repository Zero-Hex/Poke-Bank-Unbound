#!/usr/bin/env python3
"""
Pokemon Unbound Box Organizer
Reads a .sav file, respects any named boxes, and sorts all mons from
unnamed boxes into tidy groups by evolutionary family.

Named boxes (anything other than the default "BoxN" name) are left
completely untouched. Everything else gets sorted and packed from Box 1.

IMPORTANT: Mons that straddle sector boundaries in the save file are pinned
in place — they cannot be moved or the emulator will reject the save.

Usage:
    python unbound_box_organizer.py <save_file.sav> [output.sav]

Requires the 'data/' folder from PUSE's backend/data/ next to this script.
"""

import struct
import sys
import json
import math
import re
from pathlib import Path

if getattr(sys, 'frozen', False):
    _BASE_DIR = Path(sys._MEIPASS)
else:
    _BASE_DIR = Path(__file__).parent

def _base_path(): return _BASE_DIR


# ---------------------------------------------------------------------------
# Save file constants
# ---------------------------------------------------------------------------
SECTION_SIZE          = 0x1000
SECTION_PAYLOAD_MAX   = 0xFF4
SECTION_13_VALID_LEN  = 0x450
PRESET_SECTOR_ID      = 0
PRESET_VALID_LEN      = 0xADC
OPAQUE_SECTION_IDS    = {4}
TRAINER_SECTION_ID    = 1
POKEMON_STREAM_SECTORS = [5, 6, 7, 8, 9, 10, 11, 12]
SECTOR_PAYLOAD        = 0xFF0
SECTOR_HEADER         = 4
MON_SIZE              = 58
SLOTS_PER_BOX         = 30
STREAM_BOXES          = 19
OFF_CHECKSUM          = 0xFF6
OFF_VALID_LEN         = 0xFF0
OFF_SECTION_ID        = 0xFF4
OFF_SAVE_IDX          = 0xFFC

BOX_NAMES_1_14_OFF    = 0x03C4
BOX_NAMES_15_25_OFF   = 0x0361
BOX_NAME_SIZE         = 9

CHARMAP = {
    0x00:" ",0xA1:"0",0xA2:"1",0xA3:"2",0xA4:"3",0xA5:"4",0xA6:"5",
    0xA7:"6",0xA8:"7",0xA9:"8",0xAA:"9",0xAB:"!",0xAC:"?",0xAD:".",
    0xAE:"-",0xBB:"A",0xBC:"B",0xBD:"C",0xBE:"D",0xBF:"E",0xC0:"F",
    0xC1:"G",0xC2:"H",0xC3:"I",0xC4:"J",0xC5:"K",0xC6:"L",0xC7:"M",
    0xC8:"N",0xC9:"O",0xCA:"P",0xCB:"Q",0xCC:"R",0xCD:"S",0xCE:"T",
    0xCF:"U",0xD0:"V",0xD1:"W",0xD2:"X",0xD3:"Y",0xD4:"Z",0xD5:"a",
    0xD6:"b",0xD7:"c",0xD8:"d",0xD9:"e",0xDA:"f",0xDB:"g",0xDC:"h",
    0xDD:"i",0xDE:"j",0xDF:"k",0xE0:"l",0xE1:"m",0xE2:"n",0xE3:"o",
    0xE4:"p",0xE5:"q",0xE6:"r",0xE7:"s",0xE8:"t",0xE9:"u",0xEA:"v",
    0xEB:"w",0xEC:"x",0xED:"y",0xEE:"z",0xFF:""
}

# ---------------------------------------------------------------------------
# Binary helpers
# ---------------------------------------------------------------------------
def ru16(b, o): return struct.unpack_from("<H", b, o)[0]
def ru32(b, o): return struct.unpack_from("<I", b, o)[0]
def wu16(b, o, v): struct.pack_into("<H", b, o, v & 0xFFFF)

def decode_name(raw):
    s = ""
    for b in raw:
        if b == 0xFF: break
        s += CHARMAP.get(b, "?")
    return s.strip()

# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------
def gba_checksum(data, offset, length):
    total = 0
    full = length - (length % 4)
    for i in range(0, full, 4):
        total = (total + ru32(data, offset + i)) & 0xFFFFFFFF
    if length % 4:
        tail = [0, 0, 0, 0]
        for i in range(length % 4):
            tail[i] = data[offset + full + i]
        word = tail[0] | (tail[1] << 8) | (tail[2] << 16) | (tail[3] << 24)
        total = (total + word) & 0xFFFFFFFF
    return ((total >> 16) + (total & 0xFFFF)) & 0xFFFF

# ---------------------------------------------------------------------------
# Section management
# ---------------------------------------------------------------------------
def find_active_sections(data):
    sections = {}
    for i in range(0, len(data), SECTION_SIZE):
        if i + SECTION_SIZE > len(data): break
        sec_id   = ru16(data, i + OFF_SECTION_ID)
        save_idx = ru32(data, i + OFF_SAVE_IDX)
        if sec_id not in sections or save_idx > sections[sec_id]['idx']:
            sections[sec_id] = {'offset': i, 'idx': save_idx}
    return sections

def find_all_section_offsets(data, target_id):
    result = []
    for i in range(0, len(data), SECTION_SIZE):
        if i + SECTION_SIZE > len(data): break
        if ru16(data, i + OFF_SECTION_ID) == target_id:
            result.append(i)
    return result

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def find_data_dir():
    for p in [_base_path() / "data", Path.cwd() / "data"]:
        if (p / "pokemon.txt").exists():
            return p
    return None

def load_id_name(path):
    out = {}
    if not path or not Path(path).exists(): return out
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        if ":" in line:
            l, r = line.split(":", 1)
            if l.strip().isdigit():
                out[int(l.strip())] = r.strip()
    return out

def load_json(path):
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except: return {}

def load_databases(data_dir):
    db_species = load_id_name(data_dir / "pokemon.txt")
    raw_growth = load_json(data_dir / "species_growth_rates.json")
    db_growth = {}
    for sid, meta in raw_growth.items():
        if str(sid).isdigit() and isinstance(meta, dict):
            rate = meta.get("growth_rate")
            if rate is not None:
                db_growth[int(sid)] = int(rate)
    print(f"  Loaded: {len(db_species)} species, {len(db_growth)} growth rates")
    return db_species, db_growth

# ---------------------------------------------------------------------------
# Level from EXP
# ---------------------------------------------------------------------------
def exp_at_level(rate, n):
    if n <= 1: return 0
    if n > 100: n = 100
    if rate == 0: return n ** 3
    if rate == 1:
        if n <= 50:  return int((n**3*(100-n))/50)
        if n <= 68:  return int((n**3*(150-n))/100)
        if n <= 98:  return int((n**3*((1911-10*n)/3))/500)
        return int((n**3*(160-n))/100)
    if rate == 2:
        if n <= 15:  return int(n**3*((math.floor((n+1)/3)+24)/50))
        if n <= 36:  return int(n**3*((n+14)/50))
        return int(n**3*((math.floor(n/2)+32)/50))
    if rate == 3: return int(1.2*(n**3)-15*(n**2)+100*n-140)
    if rate == 4: return int((4*(n**3))/5)
    if rate == 5: return int((5*(n**3))/4)
    return n**3

def calc_level(rate, exp):
    for lvl in range(1, 101):
        if exp < exp_at_level(rate, lvl+1): return lvl
    return 100

# ---------------------------------------------------------------------------
# Split slot detection
# ---------------------------------------------------------------------------
def find_split_slots():
    """
    Return the set of stream slot indices that straddle a sector boundary.
    These mons must never be moved — the emulator validates their position.
    """
    split = set()
    for i in range(len(POKEMON_STREAM_SECTORS)):
        boundary_byte = (i + 1) * SECTOR_PAYLOAD
        byte_in_slot  = boundary_byte % MON_SIZE
        if byte_in_slot != 0:
            split.add(boundary_byte // MON_SIZE)
    return split

SPLIT_SLOT_INDICES = find_split_slots()

def slot_index(box, slot):
    """0-based stream index for a given box (1-based) and slot (1-based)."""
    return (box - 1) * SLOTS_PER_BOX + (slot - 1)

def box_slot_from_index(idx):
    return idx // SLOTS_PER_BOX + 1, idx % SLOTS_PER_BOX + 1

# ---------------------------------------------------------------------------
# Box name reading
# ---------------------------------------------------------------------------
def read_box_names(data, sections):
    sec13_off = sections[13]['offset']
    names = {}
    for i in range(14):
        raw = data[sec13_off + BOX_NAMES_1_14_OFF + i*BOX_NAME_SIZE :
                   sec13_off + BOX_NAMES_1_14_OFF + i*BOX_NAME_SIZE + BOX_NAME_SIZE]
        names[i+1] = decode_name(raw)
    for slot in range(11):
        raw = data[sec13_off + BOX_NAMES_15_25_OFF + slot*BOX_NAME_SIZE :
                   sec13_off + BOX_NAMES_15_25_OFF + slot*BOX_NAME_SIZE + BOX_NAME_SIZE]
        name = decode_name(raw)
        if slot == 0:
            names[0] = name
        else:
            names[25 - slot] = name
    return names

def is_default_name(box_num, name):
    return name.strip() in (f"Box{box_num}", f"Box {box_num}", "")

def get_named_boxes(box_names):
    named = set()
    for box_num, name in box_names.items():
        if box_num == 0: continue
        if not is_default_name(box_num, name):
            named.add(box_num)
    return named

# ---------------------------------------------------------------------------
# PC stream read/write
# ---------------------------------------------------------------------------
def build_stream_buffer(data, sections):
    buf = bytearray()
    for sec_id in sorted(POKEMON_STREAM_SECTORS):
        off = sections[sec_id]['offset']
        buf += data[off + SECTOR_HEADER : off + SECTOR_HEADER + SECTOR_PAYLOAD]
    return buf

def stream_offset(box, slot):
    return ((box - 1) * SLOTS_PER_BOX + (slot - 1)) * MON_SIZE

def read_mon_from_stream(stream_buf, box, slot):
    off = stream_offset(box, slot)
    return bytearray(stream_buf[off : off + MON_SIZE])

def write_mon_to_stream(stream_buf, box, slot, mon_bytes):
    off = stream_offset(box, slot)
    stream_buf[off : off + MON_SIZE] = mon_bytes

def clear_slot_in_stream(stream_buf, box, slot):
    off = stream_offset(box, slot)
    stream_buf[off : off + MON_SIZE] = bytes(MON_SIZE)

def is_empty_slot(mon_bytes):
    return all(b == 0 for b in mon_bytes)

def get_species(mon_bytes):
    return ru16(mon_bytes, 0x1C)

def get_exp(mon_bytes):
    return ru32(mon_bytes, 0x20)

# ---------------------------------------------------------------------------
# Evolution family grouping
# ---------------------------------------------------------------------------
def build_evo_chains(data_dir):
    evo_c     = _base_path() / "Evolution Table.c"
    species_h = _base_path() / "species.h"
    if not evo_c.exists() or not species_h.exists():
        print("  WARNING: Evolution Table.c / species.h not found — sorting by species ID only.")
        return {}

    species_defs = {}
    for line in species_h.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r'#define\s+(\w+)\s+(0x[0-9a-fA-F]+|\d+)', line)
        if m:
            species_defs[m.group(1)] = int(m.group(2), 16) if m.group(2).startswith('0x') else int(m.group(2))

    evo_text = evo_c.read_text(encoding="utf-8", errors="ignore")
    evo_map = {}
    evo_tuple_re = re.compile(r'\{(EVO_\w+),\s*[^,]+,\s*(SPECIES_\w+),\s*[^}]+\}')
    sections_re  = re.compile(r'(?=\[\w+\]\s*=\s*\{)')

    for section in re.split(sections_re, evo_text):
        label_m = re.match(r'\[(\w+)\]\s*=\s*\{', section)
        if not label_m: continue
        species_id = species_defs.get(label_m.group(1))
        if species_id is None: continue
        targets = set()
        for e in evo_tuple_re.finditer(section):
            if e.group(1) in ('EVO_MEGA', 'EVO_GIGANTAMAX', '0xFE', '0xFD'): continue
            t = species_defs.get(e.group(2))
            if t and t != 0: targets.add(t)
        if targets:
            evo_map[species_id] = targets

    parent = {}
    def find(x):
        if x not in parent: parent[x] = x
        if parent[x] != x: parent[x] = find(parent[x])
        return parent[x]
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb: parent[rb] = ra
            else: parent[ra] = rb

    for sid, targets in evo_map.items():
        for t in targets: union(sid, t)

    all_species = set(evo_map.keys())
    for t in evo_map.values(): all_species |= t
    result = {s: find(s) for s in all_species}
    print(f"  Built {len(set(result.values()))} evolutionary families")
    return result

def get_sort_key(species_id, species_to_root):
    root = species_to_root.get(species_id, species_id)
    return (root, species_id)

# ---------------------------------------------------------------------------
# Main organizer logic
# ---------------------------------------------------------------------------
def organize(data, sections, named_boxes, species_to_root, db_species, db_growth):
    stream_buf = bytearray(build_stream_buffer(data, sections))

    # Build set of stream slot indices that are locked (named box or split slot)
    locked_indices = set(SPLIT_SLOT_INDICES)
    for box in range(1, STREAM_BOXES + 1):
        if box in named_boxes:
            for slot in range(1, SLOTS_PER_BOX + 1):
                locked_indices.add(slot_index(box, slot))

    # Report pinned split slots
    for idx in sorted(SPLIT_SLOT_INDICES):
        mon = stream_buf[idx*MON_SIZE:(idx+1)*MON_SIZE]
        box, slot = box_slot_from_index(idx)
        if not is_empty_slot(mon):
            sp   = get_species(mon)
            name = db_species.get(sp, f'#{sp}')
            print(f"  Pinned: Box{box} Slot{slot} ({name}) — straddles sector boundary, cannot move")
        else:
            print(f"  Pinned: Box{box} Slot{slot} (empty) — straddles sector boundary")

    # Collect mons from all movable, unnamed slots
    # Also collect from split slots so they get sorted into the right family group
    # (split slots are still locked for WRITING — they'll just be left empty)
    mons_to_sort = []
    collect_from = set()
    for box in range(1, STREAM_BOXES + 1):
        if box in named_boxes: continue
        for slot in range(1, SLOTS_PER_BOX + 1):
            collect_from.add(slot_index(box, slot))

    for idx in sorted(collect_from):
        box, slot = box_slot_from_index(idx)
        mon = read_mon_from_stream(stream_buf, box, slot)
        if not is_empty_slot(mon):
            sp = get_species(mon)
            if 1 <= sp <= 2500:
                rate  = db_growth.get(sp, 0)
                exp   = get_exp(mon)
                level = calc_level(rate, exp)
                mons_to_sort.append({
                    'raw':      mon,
                    'species':  sp,
                    'name':     db_species.get(sp, f'#{sp}'),
                    'level':    level,
                    'sort_key': get_sort_key(sp, species_to_root),
                })

    # Ask sort mode
    print()
    print("Sort options:")
    print("  1. Evolutionary family, then species ID (default)")
    print("  2. Level — lowest to highest")
    print("  3. Level — highest to lowest")
    print("  4. Species ID — lowest to highest")
    sort_choice = input("Choose sort mode [1-4, default=1]: ").strip()

    if sort_choice == "2":
        mons_to_sort.sort(key=lambda m: (m['level'], m['sort_key'][0], m['sort_key'][1]))
        print("  Sorting by: level ascending")
    elif sort_choice == "3":
        mons_to_sort.sort(key=lambda m: (-m['level'], m['sort_key'][0], m['sort_key'][1]))
        print("  Sorting by: level descending")
    elif sort_choice == "4":
        mons_to_sort.sort(key=lambda m: (m['species'], m['level']))
        print("  Sorting by: species ID ascending")
    else:
        mons_to_sort.sort(key=lambda m: (m['sort_key'][0], m['sort_key'][1], m['level']))
        print("  Sorting by: evolutionary family")
    print(f"  Collected {len(mons_to_sort)} movable mons")

    # Ask how many boxes to reserve empty at the start
    print()
    print("Reserve empty boxes at the start:")
    print("  0. None - fill from Box 1 (default)")
    print("  1. Leave Box 1 empty")
    print("  2. Leave Boxes 1 and 2 empty")
    reserve_choice = input("Reserve boxes [0-2, default=0]: ").strip()
    try:
        reserve_boxes = max(0, min(2, int(reserve_choice)))
    except ValueError:
        reserve_boxes = 0
    if reserve_boxes:
        print(f"  Reserving {reserve_boxes} empty box(es) at the start")

    # Clear all unnamed slots including split slots
    # (split slots are locked for writing so they'll stay empty after sort)
    for box in range(1, STREAM_BOXES + 1):
        if box in named_boxes: continue
        for slot in range(1, SLOTS_PER_BOX + 1):
            clear_slot_in_stream(stream_buf, box, slot)

    # Build list of available (unlocked, unnamed) destination slots in order
    # Skip the first N unnamed boxes if the user wants them kept empty
    unnamed_box_count = 0
    dest_slots = []
    for box in range(1, STREAM_BOXES + 1):
        if box in named_boxes: continue
        unnamed_box_count += 1
        if unnamed_box_count <= reserve_boxes: continue
        for slot in range(1, SLOTS_PER_BOX + 1):
            idx = slot_index(box, slot)
            if idx not in locked_indices:
                dest_slots.append((box, slot))

    if len(mons_to_sort) > len(dest_slots):
        print(f"  WARNING: {len(mons_to_sort)} mons but only {len(dest_slots)} slots — some mons won't fit!")

    # Write sorted mons into destination slots
    boxes_used = set()
    for i, m in enumerate(mons_to_sort):
        if i >= len(dest_slots): break
        box, slot = dest_slots[i]
        write_mon_to_stream(stream_buf, box, slot, m['raw'])
        boxes_used.add(box)

    print(f"  Sorted into {len(boxes_used)} boxes")
    if mons_to_sort:
        print(f"  First mon: {mons_to_sort[0]['name']} (lv{mons_to_sort[0]['level']})")
        print(f"  Last mon:  {mons_to_sort[-1]['name']} (lv{mons_to_sort[-1]['level']})")

    return stream_buf

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("Drag and drop your .sav file onto this script, or run:")
        print("  python unbound_box_organizer.py MySave.sav")
        input("\nPress Enter to close...")
        sys.exit(1)

    save_path = sys.argv[1]
    if not Path(save_path).exists():
        print(f"ERROR: Save file not found: {save_path}")
        input("\nPress Enter to close...")
        sys.exit(1)

    stem   = Path(save_path).stem
    suffix = Path(save_path).suffix or ".sav"
    output_path = sys.argv[2] if len(sys.argv) > 2 else \
                  str(Path(save_path).parent / f"{stem}_organized{suffix}")

    print(f"Reading: {save_path}")
    data = bytearray(Path(save_path).read_bytes())
    print(f"  File size: {len(data):,} bytes")

    data_dir = find_data_dir()
    if data_dir is None:
        print("ERROR: data/ directory not found. Copy it from PUSE's backend/data/ folder.")
        input("\nPress Enter to close...")
        sys.exit(1)
    print(f"  Data dir: {data_dir}")

    print("\nLoading databases...")
    db_species, db_growth = load_databases(data_dir)
    species_to_root = build_evo_chains(data_dir)

    sections = find_active_sections(data)
    for r in [1, 5, 6, 7, 8, 9, 10, 11, 12, 13]:
        if r not in sections:
            print(f"ERROR: Could not find section {r} in save file.")
            input("\nPress Enter to close...")
            sys.exit(1)

    print("\nReading box names...")
    box_names   = read_box_names(data, sections)
    named_boxes = get_named_boxes(box_names)

    print(f"  All box names:")
    for box_num in range(1, 26):
        name = box_names.get(box_num, "")
        if box_num in named_boxes:
            flag = " ← NAMED (will be skipped)"
        elif box_num > STREAM_BOXES:
            flag = " (fallback sector — skipped)"
        else:
            flag = ""
        print(f"    Box {box_num:2d}: '{name}'{flag}")

    stream_named = {b for b in named_boxes if b <= STREAM_BOXES}
    if stream_named:
        names_str = ", ".join(f"Box {b} ('{box_names[b]}')" for b in sorted(stream_named))
        print(f"\n  Skipping named boxes: {names_str}")
    else:
        print(f"\n  No named boxes in stream range — all unnamed boxes 1-{STREAM_BOXES} will be sorted")

    print(f"\nThis will reorganize all unnamed boxes (1-{STREAM_BOXES}).")
    print(f"Output: {output_path}")
    print("Your original save will NOT be modified.")
    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        input("\nPress Enter to close...")
        sys.exit(0)

    print("\nOrganizing boxes...")
    new_stream = organize(data, sections, stream_named, species_to_root, db_species, db_growth)

    print("\nWriting to save...")
    pos = 0
    for sec_id in sorted(POKEMON_STREAM_SECTORS):
        payload = new_stream[pos : pos + SECTOR_PAYLOAD]
        pos += SECTOR_PAYLOAD
        for abs_off in find_all_section_offsets(data, sec_id):
            data[abs_off + SECTOR_HEADER : abs_off + SECTOR_HEADER + SECTOR_PAYLOAD] = payload
            chk = gba_checksum(data, abs_off, 0xFF4)
            wu16(data, abs_off + OFF_CHECKSUM, chk)

    Path(output_path).write_bytes(data)
    print(f"\nSaved: {output_path}")
    print("Done! Load this save file in your emulator.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print("\n--- ERROR ---")
        traceback.print_exc()
    finally:
        input("\nPress Enter to close...")