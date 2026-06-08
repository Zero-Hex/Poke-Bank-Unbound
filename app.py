"""
Unbound Save Manager - Flask backend
Run with: python app.py
Then open http://localhost:5000
"""

import struct, json, base64, math, re, sys, urllib.request
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
import vault_boxes as cb
import trade_session as ts

VERSION = "2.0.0"
GITHUB_RELEASES_API = "https://api.github.com/repos/Zero-Hex/Poke-Bank-Unbound/releases/latest"

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
    print(f"[UnboundBank] Running as exe, BASE_DIR={BASE_DIR}")
    print(f"[UnboundBank] static/dist/index.html exists: {(BASE_DIR / 'static' / 'dist' / 'index.html').exists()}")
    # List top-level and static/ contents to aid debugging
    print("[UnboundBank] _MEIPASS contents:", [p.name for p in BASE_DIR.iterdir()])
    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        print("[UnboundBank] static/ contents:", [p.name for p in static_dir.iterdir()])
else:
    BASE_DIR = Path(__file__).parent

app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="/static")

# User data folder (persists across updates)
DO_NOT_DELETE_DIR = BASE_DIR / "DoNotDelete"
DO_NOT_DELETE_DIR.mkdir(exist_ok=True)
(DO_NOT_DELETE_DIR / "data").mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Constants (mirrors save_core.py)
# ---------------------------------------------------------------------------
SECTION_SIZE          = 0x1000
SECTION_PAYLOAD_MAX   = 0xFF0   # = SECTOR_PAYLOAD; checksum covers payload only, not footer
SECTION_13_VALID_LEN  = 0x450
PRESET_SECTOR_ID      = 0
PRESET_VALID_LEN      = 0xADC
SECTION_3_VALID_LEN   = 0xFEC   # Fallback box storage section 3
SECTION_4_VALID_LEN   = 0xD94   # SaveBlock1 tail — valid payload is shorter than max
OPAQUE_SECTION_IDS    = {4}
POKEMON_STREAM_SECTORS = [5,6,7,8,9,10,11,12,13]
SECTOR_PAYLOAD        = 0xFF0
SECTOR_HEADER         = 4
MON_SIZE              = 58
SLOTS_PER_BOX         = 30
STREAM_BOXES          = 19   # Boxes stored in stream sectors 5-13
STREAM_BOXES_WRITABLE = 19   # Same — all stream boxes are writable
OFF_CHECKSUM          = 0xFF6
OFF_VALID_LEN         = 0xFF0
OFF_SECTION_ID        = 0xFF4
OFF_SAVE_IDX          = 0xFFC
BOX_NAMES_1_14_OFF    = 0x03C4
BOX_NAMES_15_25_OFF   = 0x0361
BOX_NAME_SIZE         = 9

# Fallback box layouts: (type, slot_start, slot_end, offset)
# type 'absolute' = offset from save file start
# type 'section'  = (section_id, slot_start, slot_end, rel_offset_within_section_payload)
# Box 20 has a 16-byte internal gap after slot 21 — handled by read/write_fallback_slot
FALLBACK_BOX_LAYOUTS = {
    20: [('absolute', 1,  21, 0x1EB0C),           # slots 1-21 sequential
         ('absolute', 22, 30, 0x1EB0C + 16 + 21*58)],  # slots 22-30 after 16-byte gap
    21: [('absolute', 1,  30, 0x1F1E8)],
    22: [('absolute', 1,  30, 0x1F8B4)],
    23: [('section',  2,  1,   4,  0x0F18),        # sec2 payload slots 1-4
         ('section',  3,  5,  30,  0x0010)],       # sec3 payload slots 5-30
    24: [('section',  3,  1,  30,  0x05F4)],
}

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

NATURES = ["Hardy","Lonely","Brave","Adamant","Naughty","Bold","Docile",
           "Relaxed","Impish","Lax","Timid","Hasty","Serious","Jolly",
           "Naive","Modest","Mild","Quiet","Bashful","Rash","Calm",
           "Gentle","Sassy","Careful","Quirky"]

# ---------------------------------------------------------------------------
# In-memory session state
# ---------------------------------------------------------------------------
session = {"data": None, "sections": None, "db": None}

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
        tail = [0,0,0,0]
        for i in range(length % 4):
            tail[i] = data[offset + full + i]
        word = tail[0] | (tail[1]<<8) | (tail[2]<<16) | (tail[3]<<24)
        total = (total + word) & 0xFFFFFFFF
    return ((total >> 16) + (total & 0xFFFF)) & 0xFFFF

def recalculate_checksum(data, section_offset):
    sec_id    = ru16(data, section_offset + OFF_SECTION_ID)
    valid_raw = ru32(data, section_offset + OFF_VALID_LEN)
    if sec_id in OPAQUE_SECTION_IDS:
        return
    if sec_id == PRESET_SECTOR_ID:
        valid_len = PRESET_VALID_LEN
    elif sec_id == 3:
        valid_len = SECTION_3_VALID_LEN
    elif sec_id == 4:
        valid_len = SECTION_4_VALID_LEN
    elif sec_id == 13:
        valid_len = SECTION_13_VALID_LEN
    else:
        valid_len = min(valid_raw, SECTION_PAYLOAD_MAX) if valid_raw else SECTION_PAYLOAD_MAX
    chk = gba_checksum(data, section_offset, valid_len)
    wu16(data, section_offset + OFF_CHECKSUM, chk)

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
# Split slot detection
# ---------------------------------------------------------------------------
def find_split_slots():
    split = set()
    for i in range(len(POKEMON_STREAM_SECTORS)):
        boundary = (i + 1) * SECTOR_PAYLOAD
        if boundary % MON_SIZE != 0:
            split.add(boundary // MON_SIZE)
    return split

SPLIT_SLOT_INDICES = find_split_slots()

def slot_index(box, slot):
    return (box - 1) * SLOTS_PER_BOX + (slot - 1)

def is_split_slot(box, slot):
    return slot_index(box, slot) in SPLIT_SLOT_INDICES

# ---------------------------------------------------------------------------
# PC stream
# ---------------------------------------------------------------------------
def build_stream_buffer(data, sections):
    buf = bytearray()
    for sec_id in sorted(POKEMON_STREAM_SECTORS):
        off = sections[sec_id]['offset']
        buf += data[off + SECTOR_HEADER : off + SECTOR_HEADER + SECTOR_PAYLOAD]
    return buf

def write_stream_buffer(data, sections, stream):
    pos = 0
    for sec_id in sorted(POKEMON_STREAM_SECTORS):
        payload = stream[pos : pos + SECTOR_PAYLOAD]
        pos += SECTOR_PAYLOAD
        # Section 13 has a shorter valid payload (bag data only)
        chk_len = SECTION_13_VALID_LEN if sec_id == 13 else SECTOR_PAYLOAD
        for abs_off in find_all_section_offsets(data, sec_id):
            data[abs_off + SECTOR_HEADER : abs_off + SECTOR_HEADER + SECTOR_PAYLOAD] = payload
            chk = gba_checksum(data, abs_off, chk_len)
            wu16(data, abs_off + OFF_CHECKSUM, chk)

def read_stream_slot(stream, box, slot):
    off = ((box-1)*SLOTS_PER_BOX + (slot-1)) * MON_SIZE
    if off + MON_SIZE > len(stream): return None
    return bytearray(stream[off : off + MON_SIZE])

def write_stream_slot(stream, box, slot, mon):
    off = ((box-1)*SLOTS_PER_BOX + (slot-1)) * MON_SIZE
    stream[off : off + MON_SIZE] = mon

def is_empty(mon): return all(b == 0 for b in mon)

# ---------------------------------------------------------------------------
# Fallback boxes (20-24) — read only for now
# ---------------------------------------------------------------------------
def get_fallback_section_offsets(data):
    """
    Find the best copies of sections 2 and 3 (fallback box storage).
    Prefer: (1) valid checksum + highest save_idx, (2) any valid checksum, (3) highest save_idx.
    """
    candidates = {2: [], 3: []}
    for i in range(0, len(data), SECTION_SIZE):
        if i + SECTION_SIZE > len(data): break
        sid  = ru16(data, i + OFF_SECTION_ID)
        sidx = ru32(data, i + OFF_SAVE_IDX)
        if sid in (2, 3):
            stored = ru16(data, i + OFF_CHECKSUM)
            vl_chk = SECTION_3_VALID_LEN if sid == 3 else SECTION_PAYLOAD_MAX
            calc   = gba_checksum(data, i, vl_chk)
            valid  = stored == calc
            candidates[sid].append((sidx, valid, i))

    result = {}
    for sid, copies in candidates.items():
        if not copies: continue
        # Prefer valid checksum with highest save_idx
        valid_copies = [c for c in copies if c[1]]
        if valid_copies:
            best = max(valid_copies, key=lambda x: x[0])
        else:
            best = max(copies, key=lambda x: x[0])
        result[sid] = best[2]
    return result

def read_fallback_slot(data, fb_secs, box, slot):
    for seg in FALLBACK_BOX_LAYOUTS.get(box, []):
        if seg[0] == 'absolute':
            _, s, e, base = seg
            if s <= slot <= e:
                off = base + (slot - s) * MON_SIZE
                return bytearray(data[off:off+MON_SIZE]) if off+MON_SIZE <= len(data) else None
        elif seg[0] == 'section':
            _, sec_id, s, e, rel = seg
            if s <= slot <= e:
                sec_off = fb_secs.get(sec_id)
                if sec_off is None: return None
                off = sec_off + rel + (slot - s) * MON_SIZE
                return bytearray(data[off:off+MON_SIZE]) if off+MON_SIZE <= len(data) else None
    return None


def write_fallback_slot(data, fb_secs, box, slot, mon_bytes):
    """
    Write a mon to a fallback box slot.
    Boxes 20-22: raw absolute file offsets — no checksums needed.
    Boxes 23-24: section-relative offsets — checksums recalculated after.
    Returns set of section IDs that were modified (need checksum update).
    """
    dirty_sections = set()
    mon = mon_bytes[:MON_SIZE] if mon_bytes else bytes(MON_SIZE)
    if len(mon) < MON_SIZE:
        mon = bytes(mon) + bytes(MON_SIZE - len(mon))

    for seg in FALLBACK_BOX_LAYOUTS.get(box, []):
        if seg[0] == 'absolute':
            _, s, e, base = seg
            if s <= slot <= e:
                off = base + (slot - s) * MON_SIZE
                if off + MON_SIZE <= len(data):
                    data[off:off+MON_SIZE] = mon
                return dirty_sections  # no checksums for absolute area

        elif seg[0] == 'section':
            _, sec_id, s, e, rel = seg
            if s <= slot <= e:
                sec_off = fb_secs.get(sec_id)
                if sec_off is None:
                    raise ValueError(f"Section {sec_id} not found in save")
                off = sec_off + rel + (slot - s) * MON_SIZE
                if off + MON_SIZE <= len(data):
                    # Preserve footer bytes if the write overlaps the section footer
                    footer_start = sec_off + 0xFF4
                    write_end    = off + MON_SIZE
                    if write_end > footer_start:
                        # Save the section footer (12 bytes: valid_len + sec_id + chk + save_idx + pad)
                        footer = bytearray(data[footer_start:sec_off + 0x1000])
                        data[off:off+MON_SIZE] = mon
                        # Restore footer
                        data[footer_start:sec_off + 0x1000] = footer
                    else:
                        data[off:off+MON_SIZE] = mon
                    dirty_sections.add(sec_id)
                return dirty_sections

    raise ValueError(f"Box {box} Slot {slot} not found in fallback layout")

# ---------------------------------------------------------------------------
# Box names
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

# ---------------------------------------------------------------------------
# Database loading
# ---------------------------------------------------------------------------
def find_data_dir():
    for p in [BASE_DIR / "data",
              BASE_DIR.parent / "data"]:
        if (p / "pokemon.txt").exists():
            return p
    return None

def load_databases():
    data_dir = find_data_dir()
    if not data_dir:
        return None

    db = {}

    # Species
    db['species'] = {}
    for line in (data_dir / "pokemon.txt").read_text(encoding="utf-8", errors="ignore").splitlines():
        if ":" in line:
            l, r = line.split(":", 1)
            if l.strip().isdigit():
                db['species'][int(l.strip())] = r.strip()

    # Growth rates
    raw_gr = json.loads((data_dir / "species_growth_rates.json").read_text())
    db['growth'] = {}
    for sid, meta in raw_gr.items():
        if str(sid).isdigit() and isinstance(meta, dict):
            r = meta.get("growth_rate")
            if r is not None:
                db['growth'][int(sid)] = int(r)

    # Abilities
    db['abilities'] = {}
    if (data_dir / "abilities.txt").exists():
        for line in (data_dir / "abilities.txt").read_text(encoding="utf-8", errors="ignore").splitlines():
            if ":" in line:
                l, r = line.split(":", 1)
                if l.strip().isdigit():
                    db['abilities'][int(l.strip())] = r.strip()

    # Species ability meta
    db['ability_meta'] = {}
    if (data_dir / "species_abilities_meta.json").exists():
        raw = json.loads((data_dir / "species_abilities_meta.json").read_text())
        for sid, meta in raw.items():
            if str(sid).isdigit():
                db['ability_meta'][int(sid)] = meta

    # Items
    db['items'] = {}
    if (data_dir / "items.txt").exists():
        for line in (data_dir / "items.txt").read_text(encoding="utf-8", errors="ignore").splitlines():
            if ":" in line:
                l, r = line.split(":", 1)
                if l.strip().isdigit():
                    db['items'][int(l.strip())] = r.strip()

    # Moves
    db['moves'] = {}
    if (data_dir / "moves.txt").exists():
        for line in (data_dir / "moves.txt").read_text(encoding="utf-8", errors="ignore").splitlines():
            if ":" in line:
                l, r = line.split(":", 1)
                if l.strip().isdigit():
                    db['moves'][int(l.strip())] = r.strip()

    # Gender thresholds
    db['gender'] = {}
    if (data_dir / "species_identity_meta.json").exists():
        raw = json.loads((data_dir / "species_identity_meta.json").read_text())
        for sid, meta in raw.items():
            if str(sid).isdigit() and isinstance(meta, dict):
                t = meta.get("gender_threshold")
                if t is not None:
                    db['gender'][int(sid)] = int(t) & 0xFF

    # Base stats (hp, atk, def, spe, spa, spd)
    db['base_stats'] = {}
    if (data_dir / "species_base_stats.json").exists():
        raw = json.loads((data_dir / "species_base_stats.json").read_text())
        for sid, stats in raw.items():
            if str(sid).isdigit() and isinstance(stats, dict):
                db['base_stats'][int(sid)] = stats

    return db

# ---------------------------------------------------------------------------
# Level calculation
# ---------------------------------------------------------------------------
def calc_level(rate, exp):
    def exp_at(n):
        if n <= 1: return 0
        if n > 100: n = 100
        if rate == 0: return n**3
        if rate == 1:
            if n<=50: return int(n**3*(100-n)/50)
            if n<=68: return int(n**3*(150-n)/100)
            if n<=98: return int(n**3*((1911-10*n)/3)/500)
            return int(n**3*(160-n)/100)
        if rate == 2:
            if n<=15: return int(n**3*((math.floor((n+1)/3)+24)/50))
            if n<=36: return int(n**3*((n+14)/50))
            return int(n**3*((math.floor(n/2)+32)/50))
        if rate == 3: return int(1.2*n**3-15*n**2+100*n-140)
        if rate == 4: return int(4*n**3/5)
        if rate == 5: return int(5*n**3/4)
        return n**3
    for lvl in range(1, 101):
        if exp < exp_at(lvl+1): return lvl
    return 100

# ---------------------------------------------------------------------------
# Mon parsing
# ---------------------------------------------------------------------------
def is_shiny(otid, pid):
    return ((otid & 0xFFFF) ^ (otid >> 16) ^ (pid & 0xFFFF) ^ (pid >> 16)) < 16

def gender_from_pid(pid, threshold):
    if threshold is None: return "?"
    if threshold == 0:    return "♂"
    if threshold == 254:  return "♀"
    if threshold == 255:  return "—"
    return "♀" if (pid & 0xFF) < threshold else "♂"

def parse_pc_mon(raw, box, slot, db):
    if is_empty(raw): return None
    pid  = ru32(raw, 0x00)
    otid = ru32(raw, 0x04)
    sp   = ru16(raw, 0x1C)
    exp  = ru32(raw, 0x20)
    if sp == 0 or sp > 2500: return None

    nick_raw = raw[0x08:0x12]
    nick = decode_name(nick_raw)
    species_name = db['species'].get(sp, f"#{sp}")
    if not nick or nick == species_name[:len(nick)]:
        nick = species_name

    rate  = db['growth'].get(sp, 0)
    level = calc_level(rate, exp)

    # IVs (bitpacked at 0x36, 5 bits each)
    iv_raw = ru32(raw, 0x36) if len(raw) >= 0x3A else 0
    ivs = {
        'hp':  iv_raw & 0x1F,
        'atk': (iv_raw >> 5) & 0x1F,
        'def': (iv_raw >> 10) & 0x1F,
        'spe': (iv_raw >> 15) & 0x1F,
        'spa': (iv_raw >> 20) & 0x1F,
        'spd': (iv_raw >> 25) & 0x1F,
    }

    # EVs at 0x2C, 1 byte each
    evs = {
        'hp':  raw[0x2C] if len(raw) > 0x2C else 0,
        'atk': raw[0x2D] if len(raw) > 0x2D else 0,
        'def': raw[0x2E] if len(raw) > 0x2E else 0,
        'spe': raw[0x2F] if len(raw) > 0x2F else 0,
        'spa': raw[0x30] if len(raw) > 0x30 else 0,
        'spd': raw[0x31] if len(raw) > 0x31 else 0,
    }

    # Moves: 4 x 10-bit values bitpacked at 0x27 (5 bytes = 40 bits)
    if len(raw) >= 0x2C:
        bits40 = int.from_bytes(raw[0x27:0x2C], 'little')
        moves_raw = [(bits40 >> (10*i)) & 0x3FF for i in range(4)]
    else:
        moves_raw = [0, 0, 0, 0]
    moves = [db['moves'].get(m, f"Move#{m}") if m else "" for m in moves_raw]

    # Nature
    nature = NATURES[pid % 25] if pid > 0 else "—"

    # Ability — CFRU: bit 31 of IV word is the hidden-ability flag; regular
    # ability slot (1 or 2) is determined by pid & 1, same as vanilla Gen III.
    hidden = (iv_raw >> 31) & 1
    ability_slot = 2 if hidden else (pid & 1)
    ability_name = "—"
    meta = db['ability_meta'].get(sp)
    if meta:
        if ability_slot == 2:
            ab_id = meta.get("hidden_ability_id") or meta.get("ability_1_id")
        elif ability_slot == 1:
            ab_id = meta.get("ability_2_id") or meta.get("ability_1_id")
        else:
            ab_id = meta.get("ability_1_id")
        if ab_id:
            ability_name = db['abilities'].get(ab_id, "—")

    # Item
    item_id = ru16(raw, 0x1E) if len(raw) >= 0x20 else 0
    item_name = db['items'].get(item_id, "") if item_id else ""

    # Shiny
    shiny = is_shiny(otid, pid)

    # Gender
    gender = gender_from_pid(pid, db['gender'].get(sp))

    return {
        "pid":     pid,
        "species": sp,
        "name":    species_name,
        "nick":    nick,
        "level":   level,
        "nature":  nature,
        "gender":  gender,
        "shiny":   shiny,
        "ability": ability_name,
        "item":    item_name,
        "moves":   moves,
        "ivs":     ivs,
        "evs":     evs,
        "box":     box,
        "slot":    slot,
        "raw":     list(raw),
    }

def parse_party_mon(raw, slot, db):
    """Party mons use a different offset layout."""
    if is_empty(raw): return None
    pid  = ru32(raw, 0x00)
    otid = ru32(raw, 0x04)
    sp   = ru16(raw, 0x20)
    exp  = ru32(raw, 0x24)
    if sp == 0 or sp > 2500: return None

    nick_raw = raw[0x08:0x12]
    nick = decode_name(nick_raw)
    species_name = db['species'].get(sp, f"#{sp}")
    if not nick: nick = species_name

    rate  = db['growth'].get(sp, 0)
    level = calc_level(rate, exp)

    # Party moves at 0x2C (plain u16s)
    moves = []
    for i in range(4):
        mid = ru16(raw, 0x2C + i*2)
        moves.append(db['moves'].get(mid, f"Move#{mid}") if mid else "")

    # EVs at 0x38 (confirmed from CFRU party mon format: hp,atk,def,spe,spa,spd)
    evs = {
        'hp':  raw[0x38] if len(raw) > 0x38 else 0,
        'atk': raw[0x39] if len(raw) > 0x39 else 0,
        'def': raw[0x3A] if len(raw) > 0x3A else 0,
        'spe': raw[0x3B] if len(raw) > 0x3B else 0,
        'spa': raw[0x3C] if len(raw) > 0x3C else 0,
        'spd': raw[0x3D] if len(raw) > 0x3D else 0,
    }

    # IVs at 0x48 (confirmed from CFRU party mon format)
    iv_raw = ru32(raw, 0x48) if len(raw) >= 0x4C else 0
    ivs = {
        'hp':  iv_raw & 0x1F,
        'atk': (iv_raw >> 5) & 0x1F,
        'def': (iv_raw >> 10) & 0x1F,
        'spe': (iv_raw >> 15) & 0x1F,
        'spa': (iv_raw >> 20) & 0x1F,
        'spd': (iv_raw >> 25) & 0x1F,
    }

    nature = NATURES[pid % 25]
    shiny  = is_shiny(otid, pid)
    gender = gender_from_pid(pid, db['gender'].get(sp))

    hidden = (iv_raw >> 31) & 1
    ability_slot = 2 if hidden else (pid & 1)
    ability_name = "—"
    meta = db['ability_meta'].get(sp)
    if meta:
        if ability_slot == 2:
            ab_id = meta.get("hidden_ability_id") or meta.get("ability_1_id")
        elif ability_slot == 1:
            ab_id = meta.get("ability_2_id") or meta.get("ability_1_id")
        else:
            ab_id = meta.get("ability_1_id")
        if ab_id:
            ability_name = db['abilities'].get(ab_id, "—")

    item_id   = ru16(raw, 0x22)
    item_name = db['items'].get(item_id, "") if item_id else ""

    return {
        "pid":     pid,
        "species": sp,
        "name":    db['species'].get(sp, f"#{sp}"),
        "nick":    nick,
        "level":   level,
        "nature":  nature,
        "gender":  gender,
        "shiny":   shiny,
        "ability": ability_name,
        "item":    item_name,
        "moves":   moves,
        "ivs":     ivs,
        "evs":     evs,
        "box":     "party",
        "slot":    slot,
        "raw":     list(raw),
    }

# ---------------------------------------------------------------------------
# Trainer info
# ---------------------------------------------------------------------------
def read_trainer_info(data, sections):
    # Section 0 = vanilla SaveBlock2 (trainer identity, untouched by CFRU)
    # Section 1 = CFRU SaveBlock1 (money, badges, dex flags)
    sec0 = sections[0]['offset']
    sec1 = sections[1]['offset']

    name      = decode_name(data[sec0 + 0x00 : sec0 + 0x07]) or "???"
    gender    = "♀" if data[sec0 + 0x08] else "♂"
    tid       = ru16(data, sec0 + 0x0A)
    sid       = ru16(data, sec0 + 0x0C)

    # In-game playtime from section 0 (only advances during normal-speed play)
    playtime_h = ru16(data, sec0 + 0x0E)
    playtime_m = data[sec0 + 0x10]

    # Money at sec1+0x290 (plain u32, no encryption in CFRU)
    money = ru32(data, sec1 + 0x290)

    # Badge mask at sec1+0xFE4 — bit N = badge N+1
    badge_mask = data[sec1 + 0xFE4]
    badges     = bin(badge_mask).count('1')

    # National dex unlocked if sec0+0x1A == 0xDA
    national_dex = data[sec0 + 0x1A] == 0xDA

    sid = ru16(data, sec0 + 0x0C)

    return {
        "name":         name,
        "tid":          tid,
        "sid":          sid,
        "sid":          sid,
        "gender":       gender,
        "playtime":     f"{playtime_h}h {playtime_m}m",
        "money":        f"${money:,}",
        "badges":       badges,
        "national_dex": national_dex,
    }

# ---------------------------------------------------------------------------
# Full save parse
# ---------------------------------------------------------------------------
# Cache for growth rates and base stats so pc_to_party can use them without db access
_db_growth_cache = {}
_db_base_stats_cache = {}

PORTA_PC_ITEM_ID = 368

def has_porta_pc(data: bytearray) -> bool:
    """
    Return True if the Porta-PC (item 368) is in the save's key items pocket.
    Uses dynamic scanning to find the key items pocket — CFRU stores it in the
    extra save data area rather than at a fixed section/offset like vanilla FireRed.
    """
    # Load key item IDs to identify the pocket by its contents
    try:
        import json
        from pathlib import Path
        dd = find_data_dir()
        km = json.loads((dd / "item_pocket_map.json").read_text())
        key_ids = set(km["pockets"]["key"]["ids"])
    except Exception:
        # Fallback: just scan the whole save for item 368 with qty>0
        i = 0
        while i < len(data) - 3:
            if ru16(data, i) == PORTA_PC_ITEM_ID and ru16(data, i+2) > 0:
                return True
            i += 4
        return False

    # Scan save for a contiguous run of key item IDs (pocket) that contains item 368
    i = 0
    while i < len(data) - 3:
        iid = ru16(data, i)
        if iid in key_ids:
            # Possible pocket start — walk forward while items are all key items
            start = i; count = 0; found = False
            j = i
            while j < len(data) - 3:
                iid2 = ru16(data, j)
                if iid2 == 0: break
                if iid2 not in key_ids: break
                if iid2 == PORTA_PC_ITEM_ID and ru16(data, j+2) > 0:
                    found = True
                count += 1; j += 4
            if count >= 5 and found:
                return True
            i = j + 4
        else:
            i += 4
    return False


def parse_save(data, db):
    global _db_growth_cache, _db_base_stats_cache
    _db_growth_cache    = db.get('growth', {})
    _db_base_stats_cache = db.get('base_stats', {})
    sections  = find_active_sections(data)
    stream    = bytearray(build_stream_buffer(data, sections))
    fb_secs   = get_fallback_section_offsets(data)
    box_names = read_box_names(data, sections)
    trainer   = read_trainer_info(data, sections)

    # Party
    sec1_off = sections[1]['offset']
    party_count = min(ru32(data, sec1_off + 0x34), 6)
    party = []
    for i in range(6):
        raw = bytearray(data[sec1_off + 0x38 + i*100 : sec1_off + 0x38 + i*100 + 100])
        if i < party_count and not is_empty(raw):
            mon = parse_party_mon(raw, i+1, db)
            if mon: party.append(mon)
        else:
            party.append(None)

    # PC boxes
    boxes = []
    for box in range(1, 25):
        box_slots = 21 if box == 20 else 30
        slots = []
        for slot in range(1, box_slots + 1):
            split = is_split_slot(box, slot) if box <= STREAM_BOXES else False
            if split:
                slots.append({"split": True, "mon": None})
                continue
            if box <= STREAM_BOXES:
                raw = read_stream_slot(stream, box, slot)
            else:
                raw = read_fallback_slot(data, fb_secs, box, slot)
            if raw is None or is_empty(raw):
                slots.append({"split": False, "mon": None})
            else:
                mon = parse_pc_mon(raw, box, slot, db)
                slots.append({"split": False, "mon": mon})
        name = box_names.get(box, f"Box{box}")
        if not name or name == f"Box{box}":
            name = f"Box {box}"
        boxes.append({"box": box, "name": name, "slots": slots})

    # Preset box (box 26)
    sec0_off = sections[0]['offset']
    preset_slots = []
    for slot in range(1, 31):
        off = sec0_off + 0xB0 + (slot-1)*MON_SIZE
        raw = bytearray(data[off:off+MON_SIZE]) if off+MON_SIZE <= len(data) else None
        if raw is None or is_empty(raw):
            preset_slots.append({"split": False, "mon": None})
        else:
            mon = parse_pc_mon(raw, 26, slot, db)
            preset_slots.append({"split": False, "mon": mon})
    preset_name = box_names.get(0, "Preset")
    if not preset_name: preset_name = "Preset"
    boxes.append({"box": 26, "name": preset_name, "slots": preset_slots})

    return {
        "trainer": trainer,
        "party":   party,
        "boxes":   boxes,
    }

# ---------------------------------------------------------------------------
# Apply moves and write save
# ---------------------------------------------------------------------------
def party_to_pc(party_raw):
    """Convert 100-byte party mon to 58-byte PC format.
    Offsets verified from CFRU empirical format map.
    Party: 0x20=Species, 0x22=Item, 0x24=EXP, 0x28=PP_ups(3)
           0x2C=Moves 4xu16, 0x38=EVs(6), 0x44=IVs/misc(8)
    PC:    0x1C=Species, 0x1E=Item, 0x20=EXP, 0x24=PP_ups(3)
           0x27=Moves bitpacked(5), 0x2C=EVs(6), 0x32=IVs(4)
    """
    if is_empty(party_raw[:6]):
        return bytes(MON_SIZE)
    pc = bytearray(MON_SIZE)
    pc[0x00:0x04] = party_raw[0x00:0x04]  # PID
    pc[0x04:0x08] = party_raw[0x04:0x08]  # OTID
    pc[0x08:0x12] = party_raw[0x08:0x12]  # Nickname
    pc[0x12:0x1B] = party_raw[0x12:0x1B]  # Language/misc/OT/mark
    struct.pack_into("<H", pc, 0x1C, ru16(party_raw, 0x20))  # Species
    struct.pack_into("<H", pc, 0x1E, ru16(party_raw, 0x22))  # Item
    struct.pack_into("<I", pc, 0x20, ru32(party_raw, 0x24))  # EXP
    pc[0x24:0x27] = party_raw[0x28:0x2B]                    # PP_ups
    # Moves: party plain u16s at 0x2C → PC bitpacked 4x10-bit at 0x27
    moves = [ru16(party_raw, 0x2C + i*2) for i in range(4)]
    bits  = ((moves[0] & 0x3FF) | ((moves[1] & 0x3FF) << 10) |
             ((moves[2] & 0x3FF) << 20) | ((moves[3] & 0x3) << 30)) & 0xFFFFFFFF
    struct.pack_into("<I", pc, 0x27, bits)
    pc[0x2B] = (moves[3] >> 2) & 0xFF
    pc[0x2C:0x32] = party_raw[0x38:0x3E]  # EVs  party@0x38 → pc@0x2C
    pc[0x36:0x3A] = party_raw[0x48:0x4C]  # IVs  party@0x48 → pc@0x36  (confirmed working offsets)
    return bytes(pc)


def _calc_stat(base, ev, iv, level, nature_mult):
    """Standard Gen III stat formula."""
    val = int((2 * base + iv + ev // 4) * level / 100) + 5
    return max(1, int(val * nature_mult))

def _calc_hp(base, ev, iv, level):
    """Standard Gen III HP formula."""
    return int((2 * base + iv + ev // 4) * level / 100) + level + 10

# Nature stat multipliers: [atk, def, spe, spa, spd] index by nature
_NATURE_MODS = [
    (1.0,1.0,1.0,1.0,1.0),  # Hardy
    (1.1,0.9,1.0,1.0,1.0),  # Lonely
    (1.1,1.0,0.9,1.0,1.0),  # Brave
    (1.1,1.0,1.0,0.9,1.0),  # Adamant
    (1.1,1.0,1.0,1.0,0.9),  # Naughty
    (0.9,1.1,1.0,1.0,1.0),  # Bold
    (1.0,1.0,1.0,1.0,1.0),  # Docile
    (1.0,1.1,0.9,1.0,1.0),  # Relaxed
    (1.0,1.1,1.0,0.9,1.0),  # Impish
    (1.0,1.1,1.0,1.0,0.9),  # Lax
    (0.9,1.0,1.1,1.0,1.0),  # Timid
    (1.0,0.9,1.1,1.0,1.0),  # Hasty
    (1.0,1.0,1.0,1.0,1.0),  # Serious
    (1.0,1.0,1.1,0.9,1.0),  # Jolly
    (1.0,1.0,1.1,1.0,0.9),  # Naive
    (0.9,1.0,1.0,1.1,1.0),  # Modest
    (1.0,0.9,1.0,1.1,1.0),  # Mild
    (1.0,1.0,0.9,1.1,1.0),  # Quiet
    (1.0,1.0,1.0,1.0,1.0),  # Bashful
    (1.0,1.0,1.0,1.1,0.9),  # Rash
    (0.9,1.0,1.0,1.0,1.1),  # Calm
    (1.0,0.9,1.0,1.0,1.1),  # Gentle
    (1.0,1.0,0.9,1.0,1.1),  # Sassy
    (1.0,1.0,1.0,0.9,1.1),  # Careful
    (1.0,1.0,1.0,1.0,1.0),  # Quirky
]

def pc_to_party(pc_raw, existing_party_raw=None):
    """Convert 58-byte PC mon to 100-byte party format with full stat calculation."""
    if is_empty(pc_raw):
        return bytes(100)
    party = bytearray(100)
    # If there's an existing party mon there, start from it to preserve
    # any fields we don't explicitly set (status, etc.)
    if existing_party_raw and not is_empty(existing_party_raw[:6]):
        party[:] = existing_party_raw[:100]
    # Core identity fields
    party[0x00:0x04] = pc_raw[0x00:0x04]  # PID
    party[0x04:0x08] = pc_raw[0x04:0x08]  # OTID
    party[0x08:0x12] = pc_raw[0x08:0x12]  # Nickname
    party[0x12:0x1B] = pc_raw[0x12:0x1B]  # Language/misc/OT/mark
    sp  = ru16(pc_raw, 0x1C)
    exp = ru32(pc_raw, 0x20)
    struct.pack_into("<H", party, 0x20, sp)   # Species
    struct.pack_into("<I", party, 0x24, exp)  # EXP
    struct.pack_into("<H", party, 0x22, ru16(pc_raw, 0x1E))  # Held item
    # Moves: PC bitpacked at 0x27 → party plain u16s at 0x2C
    m0    = ru32(pc_raw, 0x27)
    m3_hi = pc_raw[0x2B]
    moves = [m0 & 0x3FF, (m0>>10) & 0x3FF, (m0>>20) & 0x3FF, ((m0>>30) | (m3_hi<<2)) & 0x3FF]
    for i, mv in enumerate(moves):
        struct.pack_into("<H", party, 0x2C + i*2, mv)
    # PP_ups: PC 0x24 (3 bytes) → party 0x28 (3 bytes)
    party[0x28:0x2B] = pc_raw[0x24:0x27]
    # EVs: PC 0x2C → party 0x38 (hp,atk,def,spe,spa,spd)
    party[0x38:0x3E] = pc_raw[0x2C:0x32]
    # IVs: PC 0x36 (4 bytes) → party 0x48 (matching parse_party_mon confirmed offset)
    party[0x48:0x4C] = pc_raw[0x36:0x3A]
    # PP values at party 0x34 (4 bytes) — set to max PP (base PP, ignoring PP_ups for safety)
    # We just zero them here; the game will restore on next use
    # (leaving existing if swapping same slot)

    # --- Level and stats ---
    rate  = _db_growth_cache.get(sp, 0) if _db_growth_cache else 0
    level = calc_level(rate, exp)
    party[0x54] = level & 0xFF

    # IVs unpacked for stat calc (PC IVs at 0x36, matching parse_pc_mon)
    iv_raw = ru32(pc_raw, 0x36)
    iv = {
        'hp':  iv_raw & 0x1F,
        'atk': (iv_raw >> 5)  & 0x1F,
        'def': (iv_raw >> 10) & 0x1F,
        'spe': (iv_raw >> 15) & 0x1F,
        'spa': (iv_raw >> 20) & 0x1F,
        'spd': (iv_raw >> 25) & 0x1F,
    }
    # EVs
    ev = {
        'hp':  pc_raw[0x2C] if len(pc_raw) > 0x2C else 0,
        'atk': pc_raw[0x2D] if len(pc_raw) > 0x2D else 0,
        'def': pc_raw[0x2E] if len(pc_raw) > 0x2E else 0,
        'spe': pc_raw[0x2F] if len(pc_raw) > 0x2F else 0,
        'spa': pc_raw[0x30] if len(pc_raw) > 0x30 else 0,
        'spd': pc_raw[0x31] if len(pc_raw) > 0x31 else 0,
    }
    # Nature multipliers
    pid    = ru32(pc_raw, 0x00)
    nature = pid % 25
    nm     = _NATURE_MODS[nature]  # (atk, def, spe, spa, spd)

    bs = (_db_base_stats_cache.get(sp) or {}) if _db_base_stats_cache else {}
    if bs:
        max_hp  = _calc_hp(bs.get('hp',45),  ev['hp'],  iv['hp'],  level)
        max_atk = _calc_stat(bs.get('atk',45), ev['atk'], iv['atk'], level, nm[0])
        max_def = _calc_stat(bs.get('def',45), ev['def'], iv['def'], level, nm[1])
        max_spe = _calc_stat(bs.get('spe',45), ev['spe'], iv['spe'], level, nm[2])
        max_spa = _calc_stat(bs.get('spa',45), ev['spa'], iv['spa'], level, nm[3])
        max_spd = _calc_stat(bs.get('spd',45), ev['spd'], iv['spd'], level, nm[4])
    else:
        # Fallback if base stats not available
        max_hp  = max(1, level * 2)
        max_atk = max_def = max_spe = max_spa = max_spd = max(1, level)

    # Write stats to party offsets
    # Current HP = max HP (full health on withdraw)
    struct.pack_into("<H", party, 0x56, max_hp)   # current HP
    struct.pack_into("<H", party, 0x58, max_hp)   # max HP
    struct.pack_into("<H", party, 0x5A, max_atk)
    struct.pack_into("<H", party, 0x5C, max_def)
    struct.pack_into("<H", party, 0x5E, max_spe)
    struct.pack_into("<H", party, 0x60, max_spa)
    struct.pack_into("<H", party, 0x62, max_spd)

    return bytes(party)


def apply_moves(data, moves):
    """
    moves: list of {from: {box, slot}, to: {box, slot}}
    box=0 or "party" = party, box=26 = preset
    Only stream boxes (1-19) supported for writing.
    Returns modified data bytes or raises ValueError.
    """
    def _norm_box(b):
        if b == "party": return 0
        return int(b)

    moves = [
        {"from": {"box": _norm_box(m["from"]["box"]), "slot": m["from"]["slot"]},
         "to":   {"box": _norm_box(m["to"]["box"]),   "slot": m["to"]["slot"]}}
        for m in moves
    ]
    sections = find_active_sections(data)
    stream   = bytearray(build_stream_buffer(data, sections))
    sec1_off = sections[1]['offset']

    def get_party_raw(slot):
        off = sec1_off + 0x38 + (slot-1)*100
        return bytearray(data[off:off+100])

    def get_pc_raw(box, slot):
        return read_stream_slot(stream, box, slot)

    def get_mon_as_pc(box, slot):
        """Get a mon in PC (58-byte) format regardless of source."""
        if box == 0:
            return party_to_pc(get_party_raw(slot))
        elif 1 <= box <= STREAM_BOXES:
            return get_pc_raw(box, slot) or bytes(MON_SIZE)
        elif box in FALLBACK_BOX_LAYOUTS:
            raw = read_fallback_slot(data, get_fallback_section_offsets(data), box, slot)
            return raw or bytes(MON_SIZE)
        return bytes(MON_SIZE)

    fb_secs = get_fallback_section_offsets(data)

    def set_mon_from_pc(box, slot, pc_raw, original_dst_pc=None):
        """Write a PC-format mon to any destination, converting if needed."""
        if box == 0:
            existing = get_party_raw(slot) if not is_empty(get_party_raw(slot)) else None
            party_bytes = pc_to_party(pc_raw, existing)
            off = sec1_off + 0x38 + (slot-1)*100
            data[off:off+100] = party_bytes
        elif 1 <= box <= STREAM_BOXES:
            if is_split_slot(box, slot):
                raise ValueError(f"Box {box} Slot {slot} is a split slot and cannot be written")
            write_stream_slot(stream, box, slot, pc_raw[:MON_SIZE])
        elif box in FALLBACK_BOX_LAYOUTS:
            dirty = write_fallback_slot(data, fb_secs, box, slot, pc_raw)
            # Recalculate checksums for modified sections
            for sec_id in dirty:
                for abs_off in find_all_section_offsets(data, sec_id):
                    recalculate_checksum(data, abs_off)
        else:
            raise ValueError(f"Box {box} is not writable")

    # Read all sources first (atomically), then write
    move_ops = []
    for move in moves:
        fb, fs = move['from']['box'], move['from']['slot']
        tb, ts = move['to']['box'], move['to']['slot']
        src_pc = get_mon_as_pc(fb, fs)
        dst_pc = get_mon_as_pc(tb, ts)
        move_ops.append((fb, fs, tb, ts, src_pc, dst_pc))

    for fb, fs, tb, ts, src_pc, dst_pc in move_ops:
        set_mon_from_pc(tb, ts, src_pc)
        set_mon_from_pc(fb, fs, dst_pc)

    # Write stream back
    write_stream_buffer(data, sections, stream)

    # Compact party — GBA reads party sequentially and stops at the first empty slot,
    # so any gap makes mons after it invisible. Shift filled slots to the front.
    party_slots = [bytearray(data[sec1_off + 0x38 + i*100 : sec1_off + 0x38 + i*100 + 100]) for i in range(6)]
    filled   = [s for s in party_slots if not is_empty(s[:6])]
    compacted = filled + [bytearray(100)] * (6 - len(filled))
    for i, slot_raw in enumerate(compacted):
        data[sec1_off + 0x38 + i*100 : sec1_off + 0x38 + i*100 + 100] = slot_raw

    party_count = len(filled)
    struct.pack_into("<I", data, sec1_off + 0x34, party_count)

    # Recalculate checksum for section 1 (party + SaveBlock1 data lives here)
    # Without this the game flags the save as corrupted and reverts to backup.
    for abs_off in find_all_section_offsets(data, 1):
        recalculate_checksum(data, abs_off)

    return data

# ---------------------------------------------------------------------------
# Evolution table loader
# ---------------------------------------------------------------------------
_evo_table_cache = None

def load_evo_table():
    global _evo_table_cache
    if _evo_table_cache is not None:
        return _evo_table_cache

    base = BASE_DIR
    evo_c     = base / "Evolution Table.c"
    species_h = base / "species.h"

    if not evo_c.exists() or not species_h.exists():
        _evo_table_cache = {}
        return _evo_table_cache

    # Parse species defines
    species_defs = {}
    for line in species_h.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r'#define\s+(\w+)\s+(0x[0-9a-fA-F]+|\d+)', line)
        if m:
            species_defs[m.group(1)] = int(m.group(2), 16) if m.group(2).startswith('0x') else int(m.group(2))

    # Parse items defines
    items_h = base / "items.h"
    item_defs = {}
    if items_h.exists():
        for line in items_h.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r'#define\s+(\w+)\s+(0x[0-9a-fA-F]+|\d+)', line)
            if m:
                item_defs[m.group(1)] = int(m.group(2), 16) if m.group(2).startswith('0x') else int(m.group(2))

    # Parse moves defines (for EVO_MOVE param names)
    moves_h = base / "moves.h"
    move_defs = {}
    if moves_h.exists():
        for line in moves_h.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r'#define\s+(\w+)\s+(0x[0-9a-fA-F]+|\d+)', line)
            if m:
                move_defs[m.group(1)] = int(m.group(2), 16) if m.group(2).startswith('0x') else int(m.group(2))

    EVO_METHOD_TEMPLATES = {
        "EVO_LEVEL": "Level {param}",
        "EVO_LEVEL_DAY": "Level {param} (day)",
        "EVO_LEVEL_NIGHT": "Level {param} (night)",
        "EVO_LEVEL_ATK_GT_DEF": "Level {param} (ATK>DEF)",
        "EVO_LEVEL_ATK_EQ_DEF": "Level {param} (ATK=DEF)",
        "EVO_LEVEL_ATK_LT_DEF": "Level {param} (DEF>ATK)",
        "EVO_LEVEL_HOLD_ITEM": "Level {param} holding {item}",
        "EVO_MALE_LEVEL": "Level {param} (male)",
        "EVO_FEMALE_LEVEL": "Level {param} (female)",
        "EVO_ITEM": "Use {item}",
        "EVO_ITEM_NIGHT": "Use {item} (night)",
        "EVO_ITEM_HOLD_ITEM": "Use item holding {item}",
        "EVO_HOLD_ITEM_NIGHT": "Level up holding {item} (night)",
        "EVO_HOLD_ITEM_DAY": "Level up holding {item} (day)",
        "EVO_TRADE": "Trade",
        "EVO_TRADE_ITEM": "Trade holding {item}",
        "EVO_FRIENDSHIP": "High friendship",
        "EVO_FRIENDSHIP_DAY": "High friendship (day)",
        "EVO_FRIENDSHIP_NIGHT": "High friendship (night)",
        "EVO_MOVE": "Know move: {param_name}",
        "EVO_MOVE_TYPE": "Know {param_name}-type move",
        "EVO_SPECIFIC_MON_IN_PARTY": "With {param_name} in party",
        "EVO_TYPE_IN_PARTY": "Level with {param_name}-type in party",
        "EVO_OTHER_PARTY_MON": "Level with {param_name} in party",
        "EVO_BEAUTY": "High beauty",
        "EVO_ITEM_LOCATION": "Use {item} (specific location)",
        "EVO_DAMAGE_LOCATION": "Level up (specific location)",
        "EVO_MAP": "Level up on specific map",
        "EVO_LEVEL_SPECIFIC_TIME_RANGE": "Level {param} (specific time)",
        "EVO_LEVEL_CASCOON": "Level {param}",
        "EVO_LEVEL_SILCOON": "Level {param}",
        "EVO_LEVEL_NINJASK": "Level {param}",
        "EVO_LEVEL_SHEDINJA": "Level {param} (shed)",
        "EVO_MOVE_MALE": "Know move: {param_name} (male)",
        "EVO_MOVE_FEMALE": "Know move: {param_name} (female)",
        "EVO_NATURE_HIGH": "Level {param} (nature↑)",
        "EVO_NATURE_LOW": "Level {param} (nature↓)",
        "EVO_RAINY_FOGGY_OW": "Level up in rain/fog",
        "EVO_CRITICAL_HIT": "Land a critical hit",
    }

    evo_c_text = evo_c.read_text(encoding="utf-8", errors="ignore")
    evo_table = {}  # species_id -> list of {method, param, target_id, target_name, description}

    section_re  = re.compile(r'(?=\[\w+\]\s*=\s*\{)')
    evo_tuple_re = re.compile(r'\{(EVO_\w+),\s*([^,]+),\s*(SPECIES_\w+),\s*([^}]*)\}')

    db = session.get("db") or {}
    species_names = db.get('species', {})
    item_names    = db.get('items', {})

    for sec in re.split(section_re, evo_c_text):
        label_m = re.match(r'\[(\w+)\]\s*=\s*\{', sec)
        if not label_m: continue
        sid = species_defs.get(label_m.group(1))
        if sid is None: continue

        evos = []
        for e in evo_tuple_re.finditer(sec):
            method    = e.group(1).strip()
            param_raw = e.group(2).strip()
            target    = species_defs.get(e.group(3).strip())
            if not target or method in ('EVO_MEGA', 'EVO_GIGANTAMAX'): continue

            # Resolve param
            param = 0
            try:
                param = int(param_raw, 16) if param_raw.startswith('0x') else int(param_raw)
            except ValueError:
                param = species_defs.get(param_raw) or item_defs.get(param_raw) or 0

            # Build description
            tmpl = EVO_METHOD_TEMPLATES.get(method, method.replace("EVO_","").replace("_"," ").title())
            # The 4th field (e.group(4)) is the item for HOLD_ITEM methods
            item_raw = e.group(4).strip() if e.lastindex >= 4 else ''
            if item_raw and item_raw != '0' and 'ITEM_' in item_raw:
                item_id = item_defs.get(item_raw, 0)
                item_name_str = item_names.get(item_id, item_raw.replace('ITEM_','').replace('_',' ').title())
            else:
                item_name_str = item_names.get(
                    item_defs.get(param_raw, param), param_raw.replace('ITEM_','').replace('_',' ').title()
                )
            # param_name depends on method: moves for EVO_MOVE*, types for TYPE, species otherwise
            if 'MOVE' in method:
                move_id = move_defs.get(param_raw, param)
                move_names = db.get('moves', {})
                param_name_str = move_names.get(move_id,
                    param_raw.replace('MOVE_','').replace('_',' ').title())
            elif 'TYPE' in method:
                param_name_str = param_raw.replace('TYPE_','').replace('_',' ').title()
            else:
                param_name_str = species_names.get(param,
                    param_raw.replace('SPECIES_','').replace('_',' ').title())
            desc = (tmpl
                .replace('{param}', str(param))
                .replace('{item}', item_name_str)
                .replace('{param_name}', param_name_str))

            evos.append({
                'method':      method,
                'param':       param,
                'target_id':   target,
                'target':      species_names.get(target, f'#{target}'),
                'desc':        desc,
            })

        if evos:
            evo_table[sid] = evos

    _evo_table_cache = evo_table
    print(f"  Evo table loaded: {len(evo_table)} species with evolutions")
    return evo_table


# ---------------------------------------------------------------------------
# Sort logic (reuses organizer.py)
# ---------------------------------------------------------------------------
def run_sort(data, sort_mode, reserve_boxes):
    """Sort all PC boxes (stream 1-18 + fallback 19-24). Returns modified data."""
    import organizer as org

    sections  = find_active_sections(data)
    fb_secs   = get_fallback_section_offsets(data)
    db = session['db']
    db_growth = db.get('growth', {})

    data_dir = find_data_dir()
    species_to_root = org.build_evo_chains(data_dir) if data_dir else {}

    db_species_simple = {}
    for k, v in (db.get('species') or {}).items():
        db_species_simple[k] = v

    box_names   = read_box_names(data, sections)
    named_boxes = {bn for bn, nm in box_names.items()
                   if bn > 0 and nm.strip() and nm.strip() not in (f'Box{bn}', f'Box {bn}')}

    stream_buf = bytearray(build_stream_buffer(data, sections))
    SPLIT = find_split_slots()

    def slot_idx(box, slot): return (box-1)*SLOTS_PER_BOX + (slot-1)

    # ── Collect mons from ALL boxes (stream 1-18 + fallback 19-24) ──────────
    mons = []

    for box in range(1, STREAM_BOXES_WRITABLE+1):
        if box in named_boxes: continue
        for slot in range(1, SLOTS_PER_BOX+1):
            idx = slot_idx(box, slot)
            if idx in SPLIT: continue
            raw = stream_buf[idx*MON_SIZE:(idx+1)*MON_SIZE]
            if all(b==0 for b in raw): continue
            sp = ru16(raw, 0x1C)
            if not (1 <= sp <= 2500): continue
            exp  = ru32(raw, 0x20)
            rate = db_growth.get(sp, 0)
            level = calc_level(rate, exp)
            root  = (species_to_root.get(sp, sp) if species_to_root else sp)
            mons.append({'raw': bytearray(raw), 'species': sp, 'level': level,
                         'root': root, 'name': db_species_simple.get(sp, f'#{sp}')})

    for box in sorted(FALLBACK_BOX_LAYOUTS.keys()):
        if box in named_boxes: continue
        for slot in range(1, SLOTS_PER_BOX+1):
            raw = read_fallback_slot(data, fb_secs, box, slot)
            if not raw or is_empty(raw): continue
            sp = ru16(raw, 0x1C)
            if not (1 <= sp <= 2500): continue
            exp  = ru32(raw, 0x20)
            rate = db_growth.get(sp, 0)
            level = calc_level(rate, exp)
            root  = (species_to_root.get(sp, sp) if species_to_root else sp)
            mons.append({'raw': bytearray(raw), 'species': sp, 'level': level,
                         'root': root, 'name': db_species_simple.get(sp, f'#{sp}')})

    # ── Sort ────────────────────────────────────────────────────────────────
    if sort_mode == 'level_asc':
        mons.sort(key=lambda m: (m['level'], m['root'], m['species']))
    elif sort_mode == 'level_desc':
        mons.sort(key=lambda m: (-m['level'], m['root'], m['species']))
    elif sort_mode == 'species':
        mons.sort(key=lambda m: (m['species'], m['level']))
    else:
        mons.sort(key=lambda m: (m['root'], m['species'], m['level']))

    # ── Clear all unnamed non-split slots in stream + fallback ──────────────
    for box in range(1, STREAM_BOXES_WRITABLE+1):
        if box in named_boxes: continue
        for slot in range(1, SLOTS_PER_BOX+1):
            idx = slot_idx(box, slot)
            if idx not in SPLIT:
                stream_buf[idx*MON_SIZE:(idx+1)*MON_SIZE] = bytes(MON_SIZE)

    dirty_clear = set()
    for box in sorted(FALLBACK_BOX_LAYOUTS.keys()):
        if box in named_boxes: continue
        for slot in range(1, SLOTS_PER_BOX+1):
            dirty_clear |= write_fallback_slot(data, fb_secs, box, slot, bytes(MON_SIZE))

    # ── Build dest slots: stream 1-18 first, then fallback 19-24 ────────────
    dest_stream = []   # list of stream buffer indices
    dest_fallback = [] # list of (box, slot) for fallback boxes
    unnamed_count = 0

    for box in range(1, STREAM_BOXES_WRITABLE+1):
        if box in named_boxes: continue
        unnamed_count += 1
        if unnamed_count <= reserve_boxes: continue
        for slot in range(1, SLOTS_PER_BOX+1):
            idx = slot_idx(box, slot)
            if idx not in SPLIT:
                dest_stream.append(idx)

    for box in sorted(FALLBACK_BOX_LAYOUTS.keys()):
        if box in named_boxes: continue
        for slot in range(1, SLOTS_PER_BOX+1):
            dest_fallback.append((box, slot))

    # ── Write sorted mons ────────────────────────────────────────────────────
    mon_idx = 0
    for idx in dest_stream:
        if mon_idx >= len(mons): break
        stream_buf[idx*MON_SIZE:(idx+1)*MON_SIZE] = mons[mon_idx]['raw']
        mon_idx += 1

    dirty = set(dirty_clear)  # include sections dirtied during clear
    for box, slot in dest_fallback:
        if mon_idx >= len(mons): break
        dirty |= write_fallback_slot(data, fb_secs, box, slot, mons[mon_idx]['raw'])
        mon_idx += 1

    # ── Write stream back ────────────────────────────────────────────────────
    write_stream_buffer(data, sections, stream_buf)

    # Recalculate checksums for any modified fallback sections (2, 3)
    for sec_id in dirty:
        for abs_off in find_all_section_offsets(data, sec_id):
            recalculate_checksum(data, abs_off)

    return data


# ---------------------------------------------------------------------------
# Excel export (reuses save_reader.py)
# ---------------------------------------------------------------------------
def run_excel_export(data):
    """Generate xlsx and return as bytes."""
    import save_reader as sr
    import io, tempfile, os

    db = session['db']

    db_species   = db.get('species', {})
    db_items     = db.get('items', {})
    db_moves     = db.get('moves', {})
    db_abilities = db.get('abilities', {})
    db_ability_m = db.get('ability_meta', {})
    db_gender    = db.get('gender', {})
    db_move_pp   = {}
    db_growth    = db.get('growth', {})

    party_mons = sr.read_party(data, db_species, db_items, db_moves,
                                db_abilities, db_ability_m, db_gender, db_move_pp, db_growth)
    pc_mons    = sr.read_pc(data, db_species, db_items, db_moves,
                             db_abilities, db_ability_m, db_gender, db_move_pp, db_growth)
    all_mons   = party_mons + pc_mons

    # write_xlsx writes to a file path, so use a temp file
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        tmp_path = f.name
    try:
        sr.write_xlsx(all_mons, tmp_path, 'save_export')
        with open(tmp_path, 'rb') as f:
            return f.read()
    finally:
        try: os.unlink(tmp_path)
        except: pass


def run_evo_export(data):
    """Generate evolution checker xlsx and return as bytes."""
    import sys, io, tempfile, os
    # Temporarily add app dir to path so evo checker can find its siblings
    app_dir = str(BASE_DIR)
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import unbound_evo_checker as ec

    db = session['db']
    db_species = db.get('species', {})
    db_items   = db.get('items', {})
    db_moves   = db.get('moves', {})
    db_growth  = db.get('growth', {})
    db_gender  = db.get('gender', {})

    base = BASE_DIR
    evo_c     = base / "Evolution Table.c"
    species_h = base / "species.h"
    items_h   = base / "items.h"
    moves_h   = base / "moves.h"

    evo_table, item_by_id, species_defs = ec.load_evolution_table(
        str(evo_c), str(species_h), str(items_h), str(moves_h)
    )

    party = ec.read_party(data, db_species, db_growth, db_gender)
    pc    = ec.read_pc(data, db_species, db_growth, db_gender)
    rows  = ec.build_evo_rows(party + pc, evo_table, db_species, db_moves)

    # Filter to only evolutions we don't already have caught in the dex
    try:
        dex_species = json.load(open(BASE_DIR / "static" / "dex_species.json"))
        sid_to_national = {int(k): v["national"] for k, v in dex_species.items()}

        sections = find_active_sections(data)
        sec1 = sections[1]["offset"]
        DEX_CAUGHT_OFF, DEX_FLAG_SIZE = 0x38D, 0x7D
        caught_bytes = data[sec1 + DEX_CAUGHT_OFF : sec1 + DEX_CAUGHT_OFF + DEX_FLAG_SIZE]
        caught_nationals = set()
        for bi, byte in enumerate(caught_bytes):
            if byte == 0: continue
            for bit in range(8):
                if byte & (1 << bit):
                    caught_nationals.add(bi * 8 + bit + 1)

        def any_target_uncaught(row_species_id):
            for evo in evo_table.get(row_species_id, []):
                nat = sid_to_national.get(evo["target_id"])
                if nat and nat not in caught_nationals:
                    return True
            return False

        # Rebuild rows keeping only entries whose evolution target isn't caught
        filtered = []
        for row in rows:
            # Find species_id from the mon's species name
            sid = next((s for s, evos in evo_table.items()
                        if db_species.get(s) == row["species"]), None)
            if sid is None:
                filtered.append(row)
                continue
            # Find target_id for this specific evo row
            target_nat = None
            for evo in evo_table.get(sid, []):
                if db_species.get(evo["target_id"]) == row["evolves_to"]:
                    target_nat = sid_to_national.get(evo["target_id"])
                    break
            if target_nat is None or target_nat not in caught_nationals:
                filtered.append(row)
        rows = filtered
    except Exception as e:
        import traceback; traceback.print_exc()
        # If filtering fails, fall back to all rows

    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        tmp_path = f.name
    try:
        ec.write_xlsx(rows, tmp_path, 'save_export')
        with open(tmp_path, 'rb') as f:
            return f.read()
    finally:
        try: os.unlink(tmp_path)
        except: pass


def run_sort_single_box(data, box_num, sort_mode):
    """Sort a single box in-place."""
    sections = find_active_sections(data)
    db = session['db']
    db_growth = db.get('growth', {})
    db_species_simple = db.get('species', {})

    data_dir = find_data_dir()
    import organizer as org
    species_to_root = org.build_evo_chains(data_dir) if data_dir else {}

    SPLIT = find_split_slots()
    stream_buf = bytearray(build_stream_buffer(data, sections))

    def slot_idx(box, slot): return (box-1)*SLOTS_PER_BOX + (slot-1)

    # Only works on stream boxes
    if box_num > STREAM_BOXES:
        return data  # fallback boxes not sortable in-place for now

    mons = []
    for slot in range(1, SLOTS_PER_BOX+1):
        idx = slot_idx(box_num, slot)
        if idx in SPLIT: continue
        raw = stream_buf[idx*MON_SIZE:(idx+1)*MON_SIZE]
        if all(b==0 for b in raw): continue
        sp = ru16(raw, 0x1C)
        if not (1 <= sp <= 2500): continue
        exp   = ru32(raw, 0x20)
        rate  = db_growth.get(sp, 0)
        level = calc_level(rate, exp)
        root  = species_to_root.get(sp, sp) if species_to_root else sp
        mons.append({'raw': bytearray(raw), 'species': sp, 'level': level, 'root': root})

    if sort_mode == 'level_asc':
        mons.sort(key=lambda m: (m['level'], m['root'], m['species']))
    elif sort_mode == 'level_desc':
        mons.sort(key=lambda m: (-m['level'], m['root'], m['species']))
    elif sort_mode == 'species':
        mons.sort(key=lambda m: (m['species'], m['level']))
    else:
        mons.sort(key=lambda m: (m['root'], m['species'], m['level']))

    # Clear non-split slots in this box
    for slot in range(1, SLOTS_PER_BOX+1):
        idx = slot_idx(box_num, slot)
        if idx not in SPLIT:
            stream_buf[idx*MON_SIZE:(idx+1)*MON_SIZE] = bytes(MON_SIZE)

    # Write sorted mons back
    dest = [slot_idx(box_num, s) for s in range(1, SLOTS_PER_BOX+1)
            if slot_idx(box_num, s) not in SPLIT]
    for i, m in enumerate(mons):
        if i >= len(dest): break
        idx = dest[i]
        stream_buf[idx*MON_SIZE:(idx+1)*MON_SIZE] = m['raw']

    write_stream_buffer(data, sections, stream_buf)
    return data


# ---------------------------------------------------------------------------
# Preferences (user settings that persist across updates)
# ---------------------------------------------------------------------------
def load_preferences():
    prefs = DEFAULT_PREFS.copy()
    if PREFERENCES_FILE.exists():
        try:
            loaded = json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
            prefs.update({k: v for k, v in loaded.items() if k in prefs})
        except Exception:
            pass
    return prefs

def save_preferences(prefs):
    PREFERENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PREFERENCES_FILE.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    index_path = BASE_DIR / "static" / "dist" / "index.html"
    print(f"[UnboundBank] Serving index from: {index_path} (exists={index_path.exists()})")
    from flask import Response
    return Response(index_path.read_bytes(), mimetype="text/html")

@app.route("/icons/<path:filename>")
def serve_icons(filename):
    return send_from_directory(str(BASE_DIR / "static" / "icons"), filename)

@app.route("/sprites/<path:filename>")
def serve_sprites(filename):
    return send_from_directory(str(BASE_DIR / "static" / "sprites"), filename)


@app.route("/species_types.json")
def species_types():
    return send_from_directory(str(BASE_DIR / "static"), "species_types.json")

@app.route("/pokemon-icon-manifest.json")
def pokemon_icon_manifest():
    return send_from_directory(str(BASE_DIR / "static"), "pokemon-icon-manifest.json")

@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(str(BASE_DIR / "static" / "dist" / "assets"), filename)

# ── Before-request hooks ───────────────────────────────────────────────────────

# Paths under /api/ that work without a save being loaded (load the save,
# work on vault/trade alone, or handle the missing-save case themselves).
_SKIP_SAVE_CHECK = {
    '/api/load', '/api/load_recent',
    '/api/undo',             # owns its own "no save" logic
    '/api/status',           # reports whether a save is loaded
    '/api/has_porta_pc',     # returns False gracefully when no save
    '/api/recent_saves',
    '/api/check_update',
    '/api/preferences',
    '/api/vault/boxes',      # vault-only; works with default trainer key
    '/api/vault/move',
    '/api/vault/batch_move',
    '/api/vault/sort',
    '/api/vault/rename',
    '/api/vault/release',
    '/api/trade/vault',
    '/api/trade/load_secondary',
    '/api/trade/unload_secondary',
    '/api/trade/secondary_status',
    '/api/trade/transfer',   # checks primary/secondary internally
    '/api/trade/swap',
    '/api/trade/save_primary',
    '/api/trade/save_secondary',
}

@app.before_request
def require_save_loaded():
    """Return 400 for any /api/ route that needs a save when none is loaded."""
    if request.path.startswith('/api/') and request.path not in _SKIP_SAVE_CHECK:
        if session.get('data') is None:
            return jsonify({'error': 'No save loaded'}), 400

@app.before_request
def ensure_db():
    """Keep the lookup-table dict in session whenever a save is present."""
    if session.get('data') is not None and not session.get('db'):
        session['db'] = load_databases() or {}

# ── Undo Management ────────────────────────────────────────────────────────────

# POST paths that must NOT trigger an undo snapshot (non-mutating or
# administrative operations where restoring old state would be wrong).
_SKIP_UNDO_PATHS = {
    '/api/load',
    '/api/load_recent',
    '/api/undo',
    '/api/current_save',
    '/api/download',
    '/api/preferences',
    '/api/has_porta_pc',
    '/api/trade/load_secondary',
    '/api/trade/unload_secondary',
    '/api/trade/save_primary',
    '/api/trade/save_secondary',
    '/api/trade/transfer',
    '/api/trade/swap',
    '/api/check_update',
    '/api/export_excel',
    '/api/export_evolutions',
}

def save_undo_state():
    """Save current save state (save + vault) as undo checkpoint before mutation."""
    if "data" in session:
        session["prev_data"] = bytearray(session["data"])
        try:
            vault_snapshot = cb.load_cloud(_get_data_dir(), *_get_trainer_key())
            session["prev_vault"] = json.dumps(vault_snapshot)
        except Exception:
            session["prev_vault"] = None

@app.before_request
def auto_save_undo():
    """Automatically snapshot state before any mutating POST request."""
    if request.method == 'POST' and request.path not in _SKIP_UNDO_PATHS:
        save_undo_state()

@app.route("/api/undo", methods=["POST"])
def api_undo():
    """Restore previous save state (save + vault)"""
    prev_data = session.get("prev_data")
    if not prev_data:
        return jsonify({"error": "No undo state available"}), 400
    if "data" not in session:
        return jsonify({"error": "No save loaded"}), 400

    try:
        session["data"] = prev_data
        session["prev_data"] = None
        session["sections"] = find_active_sections(session["data"])

        # Restore vault state if we have a snapshot
        prev_vault_json = session.pop("prev_vault", None)
        if prev_vault_json:
            try:
                vault_snapshot = json.loads(prev_vault_json)
                cb.save_cloud(_get_data_dir(), vault_snapshot, *_get_trainer_key())
            except Exception:
                pass  # Best-effort; save data restore still completes

        db = session.get("db", {})
        result = parse_save(bytearray(session["data"]), db)
        return jsonify({"ok": True, "save": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/load", methods=["POST"])
def api_load():
    if 'save' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files['save']
    raw = f.read()
    if len(raw) not in (131072, 131088):
        return jsonify({"error": f"Unexpected file size {len(raw)} — expected 131072 or 131088 bytes"}), 400

    db = session.get('db') or load_databases()
    if not db:
        return jsonify({"error": "data/ directory not found. Place PUSE's backend/data/ folder next to app.py"}), 500
    session["db"] = db

    data = bytearray(raw)
    try:
        result = parse_save(data, db)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    session["data"] = data
    session["sections"] = find_active_sections(data)

    return jsonify({"ok": True, "save": result, "filename": f.filename})

@app.route("/api/move", methods=["POST"])
def api_move():
    body = request.get_json()
    moves = body.get("moves", [])
    if not moves:
        return jsonify({"error": "No moves provided"}), 400

    data = bytearray(session["data"])
    try:
        data = apply_moves(data, moves)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    session["data"] = data
    db = session["db"]
    result = parse_save(data, db)
    return jsonify({"ok": True, "save": result})

@app.route("/api/has_porta_pc")
def api_has_porta_pc():
    data=session.get("data")
    if data is None:return jsonify({"ok":False,"has_porta_pc":False})
    return jsonify({"ok":True,"has_porta_pc":has_porta_pc(bytearray(data))})


@app.route("/api/move_to_box", methods=["POST"])
def api_move_to_box():
    """Move multiple selected mons into the first available empty slots of a target box."""
    body = request.get_json()
    items = body.get("items", [])   # [{box, slot}, ...]
    target_box = body.get("target_box")
    if not items or target_box is None:
        return jsonify({"error": "Missing items or target_box"}), 400

    data = bytearray(session["data"])
    db   = session["db"]

    # Parse current save to find empty slots in target box
    current = parse_save(data, db)
    target_box_data = next((b for b in current["boxes"] if b["box"] == target_box), None)
    if target_box_data is None:
        return jsonify({"error": f"Box {target_box} not found"}), 400

    # Collect empty slots in order, excluding split slots (sector boundary artifacts)
    empty_slots = [
        i + 1
        for i, sl in enumerate(target_box_data["slots"])
        if not sl.get("mon") and not sl.get("split")
    ]

    if not empty_slots:
        return jsonify({"error": f"Box {target_box} is full"}), 400

    # Build move list: each selected mon → next empty slot in target box
    moves = []
    for item, dest_slot in zip(items, empty_slots):
        # Skip if source is already in target box (would be a no-op)
        if item["box"] == target_box and item["slot"] == dest_slot:
            continue
        moves.append({
            "from": {"box": item["box"], "slot": item["slot"]},
            "to":   {"box": target_box,  "slot": dest_slot}
        })

    if not moves:
        return jsonify({"error": "Nothing to move"}), 400

    try:
        data = apply_moves(data, moves)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    session["data"] = data
    result = parse_save(data, db)
    return jsonify({"ok": True, "save": result, "moved": len(moves)})


@app.route("/api/release", methods=["POST"])
def api_release():
    body=request.get_json();items=body.get("items",[])
    if not items:return jsonify({"error":"Nothing to release"}),400
    data=bytearray(session["data"]);db=session["db"]
    tid,tname=_get_trainer_key();data_dir=_get_data_dir()
    pc_items=[i for i in items if not i.get("vault")]
    vault_items=[i for i in items if i.get("vault")]
    if pc_items:
        try:
            empty=bytes(MON_SIZE);sections=find_active_sections(data)
            stream=bytearray(build_stream_buffer(data,sections))
            fb_secs=get_fallback_section_offsets(data)
            for item in pc_items:
                b=item["box"];s=item["slot"]
                if str(b)=="party":continue
                b=int(b)
                if 1<=b<=STREAM_BOXES:write_stream_slot(stream,b,s,empty)
                elif b in FALLBACK_BOX_LAYOUTS:write_fallback_slot(data,fb_secs,b,s,empty)
            write_stream_buffer(data,sections,stream)
            for abs_off in find_all_section_offsets(data,5):recalculate_checksum(data,abs_off)
        except Exception as e:return jsonify({"error":str(e)}),400
    if vault_items:
        cloud=cb.load_cloud(data_dir,tid,tname)
        for item in vault_items:
            bx=next((b for b in cloud if b["box"]==item["box"]),None)
            if bx:bx["slots"][item["slot"]-1]={"mon":None}
        cb.save_cloud(data_dir,cloud,tid,tname)
    session["data"]=data;result=parse_save(data,db)
    return jsonify({"ok":True,"save":result})


@app.route("/api/download")
def api_download():
    from flask import Response
    return Response(
        bytes(session["data"]),
        mimetype="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=save_modified.sav"}
    )

@app.route("/api/status")
def api_status():
    return jsonify({"loaded": session.get("data") is not None})


@app.route("/api/evo_table")
def api_evo_table():
    try:
        table = load_evo_table()
        # Return as {species_id: [{target_name, description}, ...]}
        result = {}
        for sid, evos in table.items():
            result[str(sid)] = [{"target": e["target"], "target_id": e["target_id"], "desc": e["desc"]} for e in evos]
        return jsonify({"ok": True, "evo_table": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sort", methods=["POST"])
def api_sort():
    body         = request.get_json()
    sort_mode    = body.get("sort_mode", "evo_family")   # evo_family|level_asc|level_desc|species
    scope        = body.get("scope", "all")              # all|current
    current_box  = body.get("current_box", 1)
    reserve      = int(body.get("reserve_boxes", 0))

    data = bytearray(session["data"])
    try:
        if scope == "current":
            # Sort only the current box (simple in-place sort, ignore named/split rules)
            data = run_sort_single_box(data, current_box, sort_mode)
        else:
            data = run_sort(data, sort_mode, reserve)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    session["data"] = data
    db = session["db"]
    result = parse_save(data, db)
    return jsonify({"ok": True, "save": result})


@app.route("/api/export_excel")
def api_export_excel():
    try:
        xlsx_bytes = run_excel_export(bytearray(session["data"]))
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    from flask import Response
    return Response(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=pokemon_save.xlsx"}
    )

@app.route("/api/export_evolutions")
def api_export_evolutions():
    try:
        xlsx_bytes = run_evo_export(bytearray(session["data"]))
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    from flask import Response
    return Response(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=pending_evolutions.xlsx"}
    )

@app.route("/borrius_locations.json")
def borrius_locations_route():
    return send_from_directory(str(BASE_DIR / "static"), "borrius_locations.json")

@app.route("/dex_species.json")
def dex_species_route():
    return send_from_directory(str(BASE_DIR / "static"), "dex_species.json")

@app.route("/species_to_national.json")
def species_to_national_route():
    return send_from_directory(str(BASE_DIR / "static"), "species_to_national.json")

@app.route("/species_base_stats.json")
def species_base_stats_route():
    return send_from_directory(str(BASE_DIR / "static"), "species_base_stats.json")


@app.route("/api/dex_flags")
def api_dex_flags():
    """Return seen and caught dex flags decoded from the active save.
    Flags live directly in active section 1 at fixed offsets — no
    SaveBlock1 reconstruction needed.
    """

    data = session["data"]
    sections  = find_active_sections(data)
    sec1      = sections[1]['offset']

    DEX_SEEN_OFF   = 0x310
    DEX_CAUGHT_OFF = 0x38D
    DEX_FLAG_SIZE  = 0x7D   # 125 bytes = 1000 bits

    seen_bytes   = data[sec1 + DEX_SEEN_OFF   : sec1 + DEX_SEEN_OFF   + DEX_FLAG_SIZE]
    caught_bytes = data[sec1 + DEX_CAUGHT_OFF : sec1 + DEX_CAUGHT_OFF + DEX_FLAG_SIZE]

    def decode(b):
        result = []
        for bi, byte in enumerate(b):
            if byte == 0: continue
            for bit in range(8):
                if byte & (1 << bit):
                    result.append(bi * 8 + bit + 1)
        return result

    return jsonify({
        "ok":     True,
        "seen":   decode(seen_bytes),
        "caught": decode(caught_bytes),
    })


@app.route("/api/species_list")
def api_species_list():
    """Return all species as {id: name} for the dex view."""
    db = session['db']
    species = db.get("species", {})
    return jsonify({str(k): v for k, v in species.items()})


# ===========================================================================
# CLOUD BOXES
# ===========================================================================

def _get_trainer_key():
    """Return (tid, trainer_name) for the currently loaded save, used to scope cloud files."""
    data = session.get("data")
    if data is None:
        return 0, "default"
    try:
        sections = session.get("sections") or find_active_sections(bytearray(data))
        t = read_trainer_info(bytearray(data), sections)
        return t["tid"], t["name"]
    except Exception:
        return 0, "default"


def _get_data_dir() -> Path:
    dd = find_data_dir()
    if dd:
        return dd
    # Fallback: create data/ next to app.py
    p = BASE_DIR / "data"
    p.mkdir(exist_ok=True)
    return p



@app.route("/api/current_save")
def api_current_save():
    """Return the current parsed save state (for Trade view to display primary boxes)."""
    db = session['db']
    data = bytearray(session["data"])
    result = parse_save(data, db)
    sections = find_active_sections(data)
    trainer = read_trainer_info(data, sections)
    return jsonify({"ok": True, "save": result, "trainer": trainer})

@app.route("/api/vault/boxes")
def api_vault_boxes():
    """Return all cloud boxes."""
    cloud = cb.load_cloud(_get_data_dir(), *_get_trainer_key())
    return jsonify({"ok": True, "cloud": cloud})


@app.route("/api/vault/deposit", methods=["POST"])
def api_vault_deposit():
    """
    Move a mon FROM the primary save INTO a cloud box slot.
    Body: {from_box, from_slot, to_vault_box, to_vault_slot}
    from_box 0 = party
    """
    body = request.get_json()
    from_box   = body["from_box"]
    from_slot  = body["from_slot"]
    to_cb      = body["to_vault_box"]
    to_cs      = body["to_vault_slot"]

    data     = bytearray(session["data"])
    sections = find_active_sections(data)
    db = session['db']

    # Read the mon raw bytes from the save
    if from_box == 0:
        # Party slot
        sec1_off = sections[1]["offset"]
        raw = bytearray(data[sec1_off + 0x38 + (from_slot-1)*100 :
                             sec1_off + 0x38 + (from_slot-1)*100 + 100])
        mon = parse_party_mon(raw, from_slot, db)
    elif from_box <= STREAM_BOXES:
        stream = bytearray(build_stream_buffer(data, sections))
        raw = read_stream_slot(stream, from_box, from_slot)
        mon = parse_pc_mon(raw, from_box, from_slot, db)
    else:
        fb_secs = get_fallback_section_offsets(data)
        raw = read_fallback_slot(data, fb_secs, from_box, from_slot)
        mon = parse_pc_mon(raw, from_box, from_slot, db)

    if raw is None or is_empty(raw) or mon is None:
        return jsonify({"error": "No Pokémon in that slot"}), 400

    # Duplicate check: reject if this mon's PID already exists in the cloud
    mon_pid = mon.get("pid")
    if mon_pid:
        vault_check = cb.load_cloud(_get_data_dir(), *_get_trainer_key())
        all_vault_pids = [s["mon"]["pid"] for box in vault_check for s in box["slots"] if s.get("mon") and s["mon"].get("pid")]
        if mon_pid in all_vault_pids:
            return jsonify({"error": "This Pokémon is already in the cloud. Reload your save to sync."}), 400

    # Add provenance from current trainer
    trainer = read_trainer_info(data, sections)
    mon["vault_from_trainer"] = trainer["name"]
    mon["vault_from_tid"]     = trainer["tid"]

    # If to_vault_slot == 0, find first empty slot starting from to_vault_box
    # and falling through to subsequent boxes if needed
    if to_cs == 0:
        vault_current = cb.load_cloud(_get_data_dir(), *_get_trainer_key())
        found = False
        for bx in vault_current:
            if bx["box"] < to_cb:
                continue
            empty_slot = next((i+1 for i,s in enumerate(bx["slots"]) if s["mon"] is None), None)
            if empty_slot is not None:
                to_cb = bx["box"]
                to_cs = empty_slot
                found = True
                break
        if not found:
            return jsonify({"error": "Vault is full — no empty slots available"}), 400

    # Write to cloud FIRST (atomic: cloud before clearing save)
    cloud = cb.deposit(_get_data_dir(), to_cb, to_cs, mon, list(raw[:MON_SIZE]), *_get_trainer_key())

    # Now clear the slot in the save
    empty = bytearray(MON_SIZE)
    if from_box == 0:
        sec1_off = sections[1]["offset"]
        data[sec1_off + 0x38 + (from_slot-1)*100 :
             sec1_off + 0x38 + (from_slot-1)*100 + MON_SIZE] = empty
    elif from_box <= STREAM_BOXES:
        stream = bytearray(build_stream_buffer(data, sections))
        write_stream_slot(stream, from_box, from_slot, empty)
        write_stream_buffer(data, sections, stream)
    else:
        fb_secs = get_fallback_section_offsets(data)
        write_fallback_slot(data, fb_secs, from_box, from_slot, empty)

    session["data"] = data
    session["sections"] = find_active_sections(data)

    # Re-parse save to return updated state
    result = parse_save(data, db)
    return jsonify({"ok": True, "save": result, "cloud": cloud})


@app.route("/api/vault/batch_deposit", methods=["POST"])
def api_vault_batch_deposit():
    """
    Move multiple mons FROM the primary save INTO cloud slots in one atomic operation.
    Saves undo state once before any mutation.
    Body: {items: [{from_box, from_slot, to_vault_box, to_vault_slot}]}
    """

    try:
        body = request.get_json()
        items = body.get("items", [])
        if not items:
            return jsonify({"error": "No items provided"}), 400


        data     = bytearray(session["data"])
        sections = find_active_sections(data)
        db = session['db']
        trainer  = read_trainer_info(data, sections)

        # Load vault once and track occupied slots
        vault_current = cb.load_cloud(_get_data_dir(), *_get_trainer_key())
        vault_boxes = [bx["box"] for bx in vault_current]
        max_vault_box = max(vault_boxes) if vault_boxes else 0
        occupied = set()
        all_vault_pids = set()
        for bx in vault_current:
            for i, s in enumerate(bx["slots"]):
                if s.get("mon"):
                    occupied.add((bx["box"], i + 1))
                    if s["mon"].get("pid"):
                        all_vault_pids.add(s["mon"]["pid"])

        cloud = None
        for idx, item in enumerate(items):
            from_box = item["from_box"]
            from_slot = item["from_slot"]
            to_cb = item["to_vault_box"]
            to_cs = item["to_vault_slot"]

            if from_box == 0:
                sec1_off = sections[1]["offset"]
                raw = bytearray(data[sec1_off + 0x38 + (from_slot-1)*100 :
                                     sec1_off + 0x38 + (from_slot-1)*100 + 100])
                mon = parse_party_mon(raw, from_slot, db)
            elif from_box <= STREAM_BOXES:
                stream = bytearray(build_stream_buffer(data, sections))
                raw = read_stream_slot(stream, from_box, from_slot)
                mon = parse_pc_mon(raw, from_box, from_slot, db)
            else:
                fb_secs = get_fallback_section_offsets(data)
                raw = read_fallback_slot(data, fb_secs, from_box, from_slot)
                mon = parse_pc_mon(raw, from_box, from_slot, db)

            if raw is None or is_empty(raw) or mon is None:
                return jsonify({"error": f"No Pokémon in item {idx+1}: box={from_box} slot={from_slot}"}), 400

            mon_pid = mon.get("pid")
            if mon_pid and mon_pid in all_vault_pids:
                return jsonify({"error": f"Item {idx+1}: Pokémon already in vault. Reload to sync."}), 400

            mon["vault_from_trainer"] = trainer["name"]
            mon["vault_from_tid"]     = trainer["tid"]

            # Find empty vault slot if not specified
            if to_cs == 0:
                found = False
                for bx in vault_current:
                    if bx["box"] < to_cb:
                        continue
                    for i, s in enumerate(bx["slots"]):
                        slot_key = (bx["box"], i + 1)
                        if s["mon"] is None and slot_key not in occupied:
                            to_cb = bx["box"]
                            to_cs = i + 1
                            found = True
                            break
                    if found:
                        break
                if not found:
                    return jsonify({"error": "Vault is full — no empty slots available"}), 400

            # Safeguard: if target slot somehow occupied, find next available
            # (This shouldn't happen with proper frontend logic, but protects against edge cases)
            attempts = 0
            while (to_cb, to_cs) in occupied and attempts < 600:
                to_cs += 1
                if to_cs > 30:
                    to_cs = 1
                    to_cb += 1
                attempts += 1

            if attempts >= 600:
                return jsonify({"error": "Item {}: could not find available vault slot (vault possibly full)".format(idx+1)}), 400

            if to_cb > max_vault_box:
                return jsonify({"error": "Item {}: target vault box {} out of range".format(idx+1, to_cb)}), 400

            occupied.add((to_cb, to_cs))
            if mon_pid:
                all_vault_pids.add(mon_pid)

            cloud = cb.deposit(_get_data_dir(), to_cb, to_cs, mon, list(raw[:MON_SIZE]), *_get_trainer_key())

            # Clear the slot in the save
            empty = bytearray(MON_SIZE)
            if from_box == 0:
                sec1_off = sections[1]["offset"]
                data[sec1_off + 0x38 + (from_slot-1)*100 :
                     sec1_off + 0x38 + (from_slot-1)*100 + MON_SIZE] = empty
            elif from_box <= STREAM_BOXES:
                stream = bytearray(build_stream_buffer(data, sections))
                write_stream_slot(stream, from_box, from_slot, empty)
                write_stream_buffer(data, sections, stream)
            else:
                fb_secs = get_fallback_section_offsets(data)
                write_fallback_slot(data, fb_secs, from_box, from_slot, empty)

            sections = find_active_sections(data)

        session["data"] = data
        session["sections"] = find_active_sections(data)

        result = parse_save(data, db)
        final_cloud = cloud if cloud is not None else cb.load_cloud(_get_data_dir(), *_get_trainer_key())
        return jsonify({"ok": True, "save": result, "cloud": final_cloud})

    except Exception as e:
        return jsonify({"error": f"Batch deposit failed: {str(e)}"}), 500


@app.route("/api/vault/withdraw", methods=["POST"])
def api_vault_withdraw():
    """
    Move a mon FROM cloud INTO the primary save (game box slot).
    Body: {from_vault_box, from_vault_slot, to_box, to_slot}
    """
    try:
        body     = request.get_json()
        from_cb  = body["from_vault_box"]
        from_cs  = body["from_vault_slot"]
        to_box   = body["to_box"]
        to_slot  = body["to_slot"]

        mon, raw, cloud = cb.withdraw(_get_data_dir(), from_cb, from_cs, *_get_trainer_key())
        if mon is None:
            return jsonify({"error": "Cloud slot is empty"}), 400

        data     = bytearray(session["data"])
        sections = find_active_sections(data)

        raw_bytes = bytearray(raw[:MON_SIZE])
        if len(raw_bytes) < MON_SIZE:
            raw_bytes += bytes(MON_SIZE - len(raw_bytes))

        # Auto-find first empty slot if to_slot == 0
        if to_slot == 0:
            found = False
            for try_box in range(1, 19):
                if try_box <= STREAM_BOXES:
                    stream = bytearray(build_stream_buffer(data, sections))
                    for try_slot in range(1, 31):
                        existing = read_stream_slot(stream, try_box, try_slot)
                        if not existing or is_empty(existing):
                            to_box, to_slot = try_box, try_slot
                            found = True
                            break
                else:
                    fb_secs = get_fallback_section_offsets(data)
                    for try_slot in range(1, 31):
                        existing = read_fallback_slot(data, fb_secs, try_box, try_slot)
                        if not existing or is_empty(existing):
                            to_box, to_slot = try_box, try_slot
                            found = True
                            break
                if found:
                    break
            if not found:
                cb.deposit(_get_data_dir(), from_cb, from_cs, mon, raw, *_get_trainer_key())
                return jsonify({"error": "No empty slots in PC"}), 400

        if to_box <= STREAM_BOXES:
            stream = bytearray(build_stream_buffer(data, sections))
            existing = read_stream_slot(stream, to_box, to_slot)
            if existing and not is_empty(existing):
                cb.deposit(_get_data_dir(), from_cb, from_cs, mon, raw, *_get_trainer_key())
                return jsonify({"error": "Destination slot is occupied"}), 400
            write_stream_slot(stream, to_box, to_slot, raw_bytes)
            write_stream_buffer(data, sections, stream)
        else:
            fb_secs  = get_fallback_section_offsets(data)
            existing = read_fallback_slot(data, fb_secs, to_box, to_slot)
            if existing and not is_empty(existing):
                cb.deposit(_get_data_dir(), from_cb, from_cs, mon, raw, *_get_trainer_key())
                return jsonify({"error": "Destination slot is occupied"}), 400
            write_fallback_slot(data, fb_secs, to_box, to_slot, raw_bytes)

        session["data"] = data
        session["sections"] = find_active_sections(data)

        db = session['db']
        result = parse_save(data, db)
        return jsonify({"ok": True, "save": result, "cloud": cloud})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/vault/rename", methods=["POST"])
def api_vault_rename():
    body  = request.get_json()
    cloud = cb.rename_box(_get_data_dir(), body["box"], body["name"], *_get_trainer_key())
    return jsonify({"ok": True, "cloud": cloud})


# ===========================================================================
# TRADE (two saves side-by-side)
# ===========================================================================

# Simple per-process secondary store (single-user desktop app)
_secondary_save = {"data": None, "path": None, "trainer": None, "sections": None}



@app.route("/api/trade/vault")
def api_trade_vault():
    """Return vault boxes for both primary and secondary trainers."""
    data_dir = _get_data_dir()
    pri_cloud = cb.load_cloud(data_dir, *_get_trainer_key())
    sec_cloud = None
    if _secondary_save["data"] is not None:
        t = _secondary_save.get("trainer") or {}
        sec_tid  = t.get("tid", 0)
        sec_name = t.get("name", "default")
        sec_cloud = cb.load_cloud(data_dir, sec_tid, sec_name)
    return jsonify({"ok": True, "primary": pri_cloud, "secondary": sec_cloud})

@app.route("/api/trade/load_secondary", methods=["POST"])
def api_trade_load_secondary():
    """Load a second save file for trading."""
    if 'save' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f   = request.files['save']
    raw = f.read()
    if len(raw) not in (131072, 131088):
        return jsonify({"error": f"Unexpected size {len(raw)}"}), 400

    db = session['db']
    if not db:
        return jsonify({"error": "data/ not found"}), 500

    data     = bytearray(raw)
    sections = find_active_sections(data)
    trainer  = read_trainer_info(data, sections)
    result   = parse_save(data, db)

    _secondary_save["data"]     = data
    _secondary_save["path"]     = f.filename
    _secondary_save["trainer"]  = trainer
    _secondary_save["sections"] = sections

    return jsonify({"ok": True, "save": result, "trainer": trainer,
                    "filename": f.filename})


@app.route("/api/trade/secondary_status")
def api_trade_secondary_status():
    loaded = _secondary_save["data"] is not None
    if not loaded:
        return jsonify({"loaded": False, "trainer": None, "save": None})
    db = session['db']
    parsed = parse_save(_secondary_save["data"], db)
    return jsonify({"loaded": True,
                    "trainer": _secondary_save.get("trainer"),
                    "filename": _secondary_save.get("filename", "secondary.sav"),
                    "save": parsed})


@app.route("/api/trade/unload_secondary", methods=["POST"])
def api_trade_unload_secondary():
    _secondary_save["data"]     = None
    _secondary_save["path"]     = None
    _secondary_save["trainer"]  = None
    _secondary_save["sections"] = None
    return jsonify({"ok": True})


@app.route("/api/trade/transfer", methods=["POST"])
def api_trade_transfer():
    """
    Transfer a mon between primary <-> secondary save.
    Body: {
      direction: "primary_to_secondary" | "secondary_to_primary",
      from_box, from_slot,   -- source location (1-indexed, box 0 = party)
      to_box,   to_slot      -- destination (must be empty)
    }
    The mon keeps its original OT / TID (authentic traded-mon behaviour).
    Both saves are backed up before any write.
    """
    if session.get("data") is None:
        return jsonify({"error": "No primary save loaded"}), 400
    if _secondary_save["data"] is None:
        return jsonify({"error": "No secondary save loaded"}), 400

    body      = request.get_json()
    direction = body["direction"]
    from_box  = body["from_box"]
    from_slot = body["from_slot"]
    to_box    = body["to_box"]
    to_slot   = body["to_slot"]

    db = session['db']

    # direction variants: 
    #   primary_to_secondary / primary_to_secondary_vault  
    #   secondary_to_primary / secondary_to_primary_vault
    to_vault = direction.endswith("_vault")
    base_dir = direction.replace("_vault", "")

    if base_dir == "primary_to_secondary":
        src_data  = bytearray(session["data"])
        dst_data  = _secondary_save["data"]
    else:
        src_data  = _secondary_save["data"]
        dst_data  = bytearray(session["data"])

    src_secs = find_active_sections(src_data)
    dst_secs = find_active_sections(dst_data)

    from_vault = body.get("from_vault", False)

    # ── Read mon from source ─────────────────────────────────────────────────
    vault_raw = None
    if from_vault:
        if direction == "primary_to_secondary":
            src_tid, src_name = _get_trainer_key()
        else:
            t = _secondary_save.get("trainer") or {}
            src_tid, src_name = t.get("tid", 0), t.get("name", "default")
        src_vault = cb.load_cloud(_get_data_dir(), src_tid, src_name)
        src_vbox  = next((b for b in src_vault if b["box"] == from_box), None)
        if src_vbox is None:
            return jsonify({"error": f"Vault box {from_box} not found"}), 400
        entry = src_vbox["slots"][from_slot - 1]
        mon_dict = entry.get("mon")
        if not mon_dict:
            return jsonify({"error": "Source vault slot is empty"}), 400
        raw_list = mon_dict.get("raw")
        if not raw_list:
            return jsonify({"error": "Vault entry has no raw data"}), 400
        raw = bytes(raw_list[:MON_SIZE])
        vault_raw = (src_vault, src_vbox, from_slot, src_tid, src_name)
    elif from_box <= STREAM_BOXES:
        src_stream = bytearray(build_stream_buffer(src_data, src_secs))
        raw = read_stream_slot(src_stream, from_box, from_slot)
    else:
        fb_secs = get_fallback_section_offsets(src_data)
        raw = read_fallback_slot(src_data, fb_secs, from_box, from_slot)

    if raw is None or is_empty(raw):
        return jsonify({"error": "Source slot is empty"}), 400

    # ── Resolve destination trainer key ─────────────────────────────────────
    if base_dir == "primary_to_secondary":
        dst_t    = _secondary_save.get("trainer") or {}
        dst_tid, dst_name = dst_t.get("tid", 0), dst_t.get("name", "default")
    else:
        dst_tid, dst_name = _get_trainer_key()

    # ── Write to destination ─────────────────────────────────────────────────
    if to_vault:
        dst_vault = cb.load_cloud(_get_data_dir(), dst_tid, dst_name)
        # Find first empty slot across vault boxes
        found = False
        for bx in dst_vault:
            for i, sl in enumerate(bx["slots"]):
                if not sl.get("mon"):
                    mon_dict = parse_pc_mon(raw, bx["box"], i+1, db) or {}
                    bx["slots"][i] = {"mon": {**mon_dict, "raw": list(raw)}}
                    found = True
                    break
            if found: break
        if not found:
            return jsonify({"error": "Destination vault is full"}), 400
        cb.save_cloud(_get_data_dir(), dst_vault, dst_tid, dst_name)
    else:
        # ── Auto-find first empty PC slot if to_slot==0 ──────────────────────
        if to_slot == 0:
            found = False
            for try_box in range(1, 19):
                if try_box <= STREAM_BOXES:
                    try_stream = bytearray(build_stream_buffer(dst_data, dst_secs))
                    for try_slot in range(1, 31):
                        ex = read_stream_slot(try_stream, try_box, try_slot)
                        if not ex or is_empty(ex):
                            to_box, to_slot = try_box, try_slot
                            found = True; break
                else:
                    fb_secs_dst = get_fallback_section_offsets(dst_data)
                    for try_slot in range(1, 31):
                        ex = read_fallback_slot(dst_data, fb_secs_dst, try_box, try_slot)
                        if not ex or is_empty(ex):
                            to_box, to_slot = try_box, try_slot
                            found = True; break
                if found: break
            if not found:
                return jsonify({"error": "No empty slots in destination save"}), 400

        if to_box <= STREAM_BOXES:
            dst_stream = bytearray(build_stream_buffer(dst_data, dst_secs))
            existing   = read_stream_slot(dst_stream, to_box, to_slot)
        else:
            fb_secs_dst = get_fallback_section_offsets(dst_data)
            existing    = read_fallback_slot(dst_data, fb_secs_dst, to_box, to_slot)

        if existing and not is_empty(existing):
            return jsonify({"error": "Destination slot is occupied"}), 400

        if to_box <= STREAM_BOXES:
            write_stream_slot(dst_stream, to_box, to_slot, raw)
            write_stream_buffer(dst_data, dst_secs, dst_stream)
        else:
            write_fallback_slot(dst_data, fb_secs_dst, to_box, to_slot, raw)

    # ── Clear source ─────────────────────────────────────────────────────────
    if vault_raw:
        src_vault_obj, _, vs, v_tid, v_name = vault_raw
        src_vbox2 = next((b for b in src_vault_obj if b["box"] == from_box), None)
        if src_vbox2:
            src_vbox2["slots"][vs - 1] = {"mon": None}
        cb.save_cloud(_get_data_dir(), src_vault_obj, v_tid, v_name)
    else:
        empty = bytearray(MON_SIZE)
        if from_box <= STREAM_BOXES:
            write_stream_slot(src_stream, from_box, from_slot, empty)
            write_stream_buffer(src_data, src_secs, src_stream)
        else:
            write_fallback_slot(src_data, fb_secs, from_box, from_slot, empty)

    # ── Commit ───────────────────────────────────────────────────────────────
    if base_dir == "primary_to_secondary":
        session["data"]              = src_data
        session["sections"]          = find_active_sections(src_data)
        _secondary_save["data"]      = dst_data
        _secondary_save["sections"]  = find_active_sections(dst_data)
    else:
        _secondary_save["data"]      = src_data
        _secondary_save["sections"]  = find_active_sections(src_data)
        session["data"]              = dst_data
        session["sections"]          = find_active_sections(dst_data)

    primary_result   = parse_save(bytearray(session["data"]), db)
    secondary_result = parse_save(_secondary_save["data"], db)

    return jsonify({"ok": True,
                    "primary":   primary_result,
                    "secondary": secondary_result})


@app.route("/api/trade/save_secondary", methods=["POST"])
def api_trade_save_secondary():
    """Write secondary save to a new file (user chooses name via download)."""
    if _secondary_save["data"] is None:
        return jsonify({"error": "No secondary save loaded"}), 400
    from flask import Response
    data = bytes(_secondary_save["data"])
    fname = _secondary_save.get("path") or "secondary.sav"
    # Return just the filename stem for the UI to show
    return Response(
        data,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{Path(fname).name}"'}
    )


@app.route("/api/trade/save_primary", methods=["POST"])
def api_trade_save_primary():
    """Download current primary save after trade operations."""
    if session.get("data") is None:
        return jsonify({"error": "No primary save loaded"}), 400
    from flask import Response
    return Response(
        bytes(session["data"]),
        mimetype="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="primary.sav"'}
    )


@app.route("/api/trade/swap", methods=["POST"])
def api_trade_swap():
    """
    Atomic 1-for-1 swap between primary and secondary save.
    Body: {pri_box, pri_slot, sec_box, sec_slot}
    """
    if session.get("data") is None:
        return jsonify({"error": "No primary save loaded"}), 400
    if _secondary_save["data"] is None:
        return jsonify({"error": "No secondary save loaded"}), 400

    body      = request.get_json()
    pri_box   = body["pri_box"]
    pri_slot  = body["pri_slot"]
    sec_box   = body["sec_box"]
    sec_slot  = body["sec_slot"]
    pri_vault = body.get("pri_vault", False)
    sec_vault = body.get("sec_vault", False)

    db = session['db']
    data_dir  = _get_data_dir()

    pri_data = bytearray(session["data"])
    sec_data = bytearray(_secondary_save["data"])
    pri_secs = find_active_sections(pri_data)
    sec_secs = find_active_sections(sec_data)

    pri_tid, pri_name = _get_trainer_key()
    sec_t    = _secondary_save.get("trainer") or {}
    sec_tid, sec_name = sec_t.get("tid", 0), sec_t.get("name", "default")

    # Read primary mon
    if pri_vault:
        pv_cloud = cb.load_cloud(data_dir, pri_tid, pri_name)
        pv_box   = next((b for b in pv_cloud if b["box"] == pri_box), None)
        if not pv_box:
            return jsonify({"error": f"Primary vault box {pri_box} not found"}), 400
        pv_entry = pv_box["slots"][pri_slot - 1].get("mon")
        if not pv_entry:
            return jsonify({"error": "Primary vault slot is empty"}), 400
        pri_raw = bytes(pv_entry["raw"][:MON_SIZE])
    elif pri_box <= STREAM_BOXES:
        pri_stream = bytearray(build_stream_buffer(pri_data, pri_secs))
        pri_raw = read_stream_slot(pri_stream, pri_box, pri_slot)
    else:
        pri_fb  = get_fallback_section_offsets(pri_data)
        pri_raw = read_fallback_slot(pri_data, pri_fb, pri_box, pri_slot)

    # Read secondary mon
    if sec_vault:
        sv_cloud = cb.load_cloud(data_dir, sec_tid, sec_name)
        sv_box   = next((b for b in sv_cloud if b["box"] == sec_box), None)
        if not sv_box:
            return jsonify({"error": f"Secondary vault box {sec_box} not found"}), 400
        sv_entry = sv_box["slots"][sec_slot - 1].get("mon")
        if not sv_entry:
            return jsonify({"error": "Secondary vault slot is empty"}), 400
        sec_raw = bytes(sv_entry["raw"][:MON_SIZE])
    elif sec_box <= STREAM_BOXES:
        sec_stream = bytearray(build_stream_buffer(sec_data, sec_secs))
        sec_raw = read_stream_slot(sec_stream, sec_box, sec_slot)
    else:
        sec_fb  = get_fallback_section_offsets(sec_data)
        sec_raw = read_fallback_slot(sec_data, sec_fb, sec_box, sec_slot)

    if pri_raw is None or is_empty(pri_raw):
        return jsonify({"error": "Primary source slot is empty"}), 400
    if sec_raw is None or is_empty(sec_raw):
        return jsonify({"error": "Secondary source slot is empty"}), 400

    # Write pri_raw -> secondary destination
    if sec_vault:
        sv_box["slots"][sec_slot - 1] = {"mon": {**parse_pc_mon(pri_raw, sec_box, sec_slot, db), "raw": list(pri_raw)}}
        cb.save_cloud(data_dir, sv_cloud, sec_tid, sec_name)
    elif sec_box <= STREAM_BOXES:
        write_stream_slot(sec_stream, sec_box, sec_slot, pri_raw)
        write_stream_buffer(sec_data, sec_secs, sec_stream)
    else:
        write_fallback_slot(sec_data, sec_fb, sec_box, sec_slot, pri_raw)

    # Write sec_raw -> primary destination
    if pri_vault:
        pv_box["slots"][pri_slot - 1] = {"mon": {**parse_pc_mon(sec_raw, pri_box, pri_slot, db), "raw": list(sec_raw)}}
        cb.save_cloud(data_dir, pv_cloud, pri_tid, pri_name)
    elif pri_box <= STREAM_BOXES:
        write_stream_slot(pri_stream, pri_box, pri_slot, sec_raw)
        write_stream_buffer(pri_data, pri_secs, pri_stream)
    else:
        write_fallback_slot(pri_data, pri_fb, pri_box, pri_slot, sec_raw)

    session["data"]             = pri_data
    session["sections"]         = find_active_sections(pri_data)
    _secondary_save["data"]     = sec_data
    _secondary_save["sections"] = find_active_sections(sec_data)

    primary_result   = parse_save(pri_data, db)
    secondary_result = parse_save(sec_data, db)
    return jsonify({"ok": True, "primary": primary_result, "secondary": secondary_result})


@app.route("/api/vault/move", methods=["POST"])
def api_vault_move():
    """Move a mon from one vault slot to another (within the vault)."""
    body = request.get_json()
    from_box  = body["from_box"]
    from_slot = body["from_slot"]
    to_box    = body["to_box"]
    to_slot   = body["to_slot"]

    tid, tname = _get_trainer_key()
    data_dir = _get_data_dir()
    cloud = cb.load_cloud(data_dir, tid, tname)

    def get_slot(bx, sl):
        b = next((x for x in cloud if x["box"] == bx), None)
        return b["slots"][sl-1] if b else None

    def set_slot(bx, sl, val):
        b = next((x for x in cloud if x["box"] == bx), None)
        if b: b["slots"][sl-1] = val

    src = get_slot(from_box, from_slot)
    dst = get_slot(to_box, to_slot)

    if src is None or src.get("mon") is None:
        return jsonify({"error": "Source slot is empty"}), 400

    # Swap src and dst (dst may be empty)
    set_slot(to_box, to_slot, src)
    set_slot(from_box, from_slot, dst if dst else {"mon": None})

    cb.save_cloud(data_dir, cloud, tid, tname)
    return jsonify({"ok": True, "cloud": cloud})


@app.route("/api/vault/batch_move", methods=["POST"])
def api_vault_batch_move():
    """Batch move multiple Pokémon within the vault in a single operation."""
    body = request.get_json()
    moves = body.get("moves", [])  # List of {from_box, from_slot, to_box, to_slot}

    if not moves:
        return jsonify({"error": "No moves specified"}), 400

    tid, tname = _get_trainer_key()
    data_dir = _get_data_dir()
    cloud = cb.load_cloud(data_dir, tid, tname)

    def get_slot(bx, sl):
        b = next((x for x in cloud if x["box"] == bx), None)
        return b["slots"][sl-1] if b else None

    def set_slot(bx, sl, val):
        b = next((x for x in cloud if x["box"] == bx), None)
        if b: b["slots"][sl-1] = val

    # Apply all moves in order
    for move in moves:
        from_box  = move["from_box"]
        from_slot = move["from_slot"]
        to_box    = move["to_box"]
        to_slot   = move["to_slot"]

        src = get_slot(from_box, from_slot)
        dst = get_slot(to_box, to_slot)

        if src is None or src.get("mon") is None:
            continue

        # Swap src and dst (dst may be empty)
        set_slot(to_box, to_slot, src)
        set_slot(from_box, from_slot, dst if dst else {"mon": None})

    cb.save_cloud(data_dir, cloud, tid, tname)
    return jsonify({"ok": True, "cloud": cloud})


@app.route("/api/vault/sort", methods=["POST"])
def api_vault_sort():
    """Sort vault boxes by national dex, name, or level."""
    body = request.get_json() or {}
    mode  = body.get("mode", "national")   # national | name | level
    scope = body.get("scope", "all")       # all | box
    box   = body.get("box")               # required when scope=box
    if mode not in ("national", "name", "level"):
        return jsonify({"error": "Invalid sort mode"}), 400
    try:
        cloud = cb.sort_vault(_get_data_dir(), mode, scope, box, *_get_trainer_key())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "cloud": cloud})


@app.route("/api/debug/party_raw", methods=["GET"])
def api_debug_party_raw():
    """Dump raw bytes for party mons to find correct IV offsets."""
    try:
        data = bytearray(session["data"])
        sections = find_active_sections(data)
        sec1_off = sections[1]["offset"]
        party_count = min(ru32(data, sec1_off + 0x34), 6)
        result = []
        for i in range(6):
            raw = bytearray(data[sec1_off + 0x38 + i*100 : sec1_off + 0x38 + i*100 + 100])
            if is_empty(raw): continue
            pid  = ru32(raw, 0x00)
            otid = ru32(raw, 0x04)
            nick = decode_name(raw[0x08:0x12])
            # Scan every possible u32 offset for the 31/31/31/31/31/31 pattern
            # 31 in all 6 IVs = 0x7FFF_FFFF in the standard bitpacked format
            # but could also be split differently
            iv_candidates = {}
            for off in range(0x20, min(len(raw)-3, 0x70)):
                val = ru32(raw, off)
                # Extract 5-bit fields
                fields = [(val >> (5*j)) & 0x1F for j in range(6)]
                if any(f == 31 for f in fields):
                    iv_candidates[f"0x{off:02X}"] = {
                        "raw_hex": f"0x{val:08X}",
                        "fields_5bit": fields
                    }
            result.append({
                "slot": i+1,
                "nick": nick,
                "len":  len(raw),
                "pid_otid": f"pid=0x{pid:08X} otid=0x{otid:08X}",
                "iv_candidates": iv_candidates,
                "full_hex": raw.hex()
            })
        # Also check first few PC box mons
        stream = bytearray(build_stream_buffer(data, sections))
        pc_result = []
        for slot_idx in range(6):  # first 6 slots of box 1
            pc_raw = read_stream_slot(stream, 1, slot_idx+1)
            if pc_raw is None or is_empty(pc_raw): continue
            pc_pid = ru32(pc_raw, 0x00)
            pc_nick = decode_name(pc_raw[0x08:0x12])
            sp = ru16(pc_raw, 0x1C)
            moves_24 = [ru16(pc_raw, 0x24+i*2) if len(pc_raw)>=0x24+i*2+2 else 0 for i in range(4)]
            moves_2c = [ru16(pc_raw, 0x2C+i*2) if len(pc_raw)>=0x2C+i*2+2 else 0 for i in range(4)]
            iv_36 = struct.unpack_from("<I", pc_raw, 0x36)[0] if len(pc_raw)>=0x3A else 0
            iv_32 = struct.unpack_from("<I", pc_raw, 0x32)[0] if len(pc_raw)>=0x36 else 0
            pc_result.append({
                "slot": slot_idx+1, "nick": pc_nick, "species": sp,
                "len": len(pc_raw), "hex": pc_raw.hex(),
                "moves@0x24": moves_24, "moves@0x2C": moves_2c,
                "ivs@0x36": [(iv_36>>(5*j))&0x1F for j in range(6)],
                "ivs@0x32": [(iv_32>>(5*j))&0x1F for j in range(6)],
            })
        return jsonify({"party": result, "pc_box1": pc_result})
    except Exception as e:
        return jsonify({"error": str(e), "trace": __import__("traceback").format_exc()})


# ---------------------------------------------------------------------------
# Recent saves tracking
# ---------------------------------------------------------------------------
RECENT_SAVES_FILE = DO_NOT_DELETE_DIR / "data" / "recent_saves.json"
PREFERENCES_FILE = DO_NOT_DELETE_DIR / "preferences.json"

# Default preferences
DEFAULT_PREFS = {
    "list_view": False,
    "spoilers_on": True,
    "shiny_toggle": False,
    "show_preset_box": False,
    "confirm_move": False,
    "confirm_release": True,
}
MAX_RECENT = 5

def load_recent_saves():
    try:
        if RECENT_SAVES_FILE.exists():
            return json.loads(RECENT_SAVES_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []

def save_recent_saves(entries):
    try:
        RECENT_SAVES_FILE.parent.mkdir(parents=True, exist_ok=True)
        RECENT_SAVES_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def record_recent_save(filepath, filename, trainer_name, trainer_tid):
    entries = load_recent_saves()
    # Remove duplicate path
    entries = [e for e in entries if e.get("path") != filepath]
    entries.insert(0, {
        "path":    filepath,
        "name":    filename,
        "trainer": trainer_name,
        "tid":     trainer_tid,
    })
    save_recent_saves(entries[:MAX_RECENT])

@app.route("/api/recent_saves", methods=["GET"])
def api_recent_saves():
    entries = load_recent_saves()
    # Filter to only entries where the file still exists
    valid = [e for e in entries if Path(e.get("path","")).exists()]
    if len(valid) != len(entries):
        save_recent_saves(valid)
    return jsonify({"ok": True, "saves": valid})

@app.route("/api/check_update", methods=["GET"])
def api_check_update():
    def parse_ver(v):
        try:
            return tuple(int(x) for x in v.lstrip("v").split("."))
        except Exception:
            return (0, 0, 0)
    try:
        req = urllib.request.Request(
            GITHUB_RELEASES_API,
            headers={"User-Agent": "UnboundBank", "Accept": "application/vnd.github+json"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read())
        if data.get("prerelease"):
            return jsonify({"current": VERSION, "up_to_date": True, "latest": VERSION})
        latest_tag  = data.get("tag_name", "").lstrip("v")
        release_url = data.get("html_url", "")
        up_to_date  = parse_ver(VERSION) >= parse_ver(latest_tag)
        return jsonify({
            "current":     VERSION,
            "latest":      latest_tag,
            "up_to_date":  up_to_date,
            "release_url": release_url,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/preferences", methods=["GET"])
def api_get_preferences():
    return jsonify(load_preferences())


@app.route("/api/preferences", methods=["POST"])
def api_set_preferences():
    prefs = load_preferences()
    updates = request.get_json() or {}
    prefs.update({k: v for k, v in updates.items() if k in prefs})
    save_preferences(prefs)
    return jsonify(prefs)


@app.route("/api/load_recent", methods=["POST"])
def api_load_recent():
    body = request.get_json()
    filepath = body.get("path", "").strip()
    p = Path(filepath)
    if not p.exists():
        return jsonify({"error": f"File not found: {filepath}"}), 404
    raw = p.read_bytes()
    if len(raw) not in (131072, 131088):
        return jsonify({"error": f"Unexpected file size {len(raw)}"}), 400
    db = session.get('db') or load_databases()
    session["db"] = db
    session["data"] = list(raw)
    parsed = parse_save(bytearray(raw), db)
    session["sections"] = None
    trainer = parsed.get("trainer", {})
    record_recent_save(str(p.resolve()), p.name, trainer.get("name",""), trainer.get("tid", 0))
    return jsonify({"ok": True, "save": parsed, "filename": p.name})


if __name__ == "__main__":
    try:
        from waitress import serve
        serve(app, host="127.0.0.1", port=5000, threads=8)
    except ImportError:
        print("Starting Flask dev server (install waitress for production)")
        app.run(debug=False, port=5000, threaded=True)
