"""
Unbound Save Manager - Flask backend
Run with: python app.py
Then open http://localhost:5000
"""

import struct, json, base64, math, re, sys
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="/static")

# ---------------------------------------------------------------------------
# Constants (mirrors save_core.py)
# ---------------------------------------------------------------------------
SECTION_SIZE          = 0x1000
SECTION_PAYLOAD_MAX   = 0xFF4
SECTION_13_VALID_LEN  = 0x450
PRESET_SECTOR_ID      = 0
PRESET_VALID_LEN      = 0xADC
OPAQUE_SECTION_IDS    = {4}
POKEMON_STREAM_SECTORS = [5,6,7,8,9,10,11,12]
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

FALLBACK_BOX_LAYOUTS = {
    20: [('absolute', 1, 21, 0x1EB0C)],
    21: [('absolute', 1, 30, 0x1F1E8)],
    22: [('absolute', 1, 30, 0x1F8B4)],
    23: [('section',  2, 1,  4,  0x0F18),
         ('section',  3, 5,  30, 0x0010)],
    24: [('section',  3, 1,  30, 0x05F4)],
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
        for abs_off in find_all_section_offsets(data, sec_id):
            data[abs_off + SECTOR_HEADER : abs_off + SECTOR_HEADER + SECTOR_PAYLOAD] = payload
            chk = gba_checksum(data, abs_off, 0xFF4)
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
    best = {}
    for i in range(0, len(data), SECTION_SIZE):
        if i + SECTION_SIZE > len(data): break
        sid  = ru16(data, i + OFF_SECTION_ID)
        sidx = ru32(data, i + OFF_SAVE_IDX)
        if sid in (2, 3):
            if sid not in best or sidx > best[sid][0]:
                best[sid] = (sidx, i)
    return {sid: off for sid, (_, off) in best.items()}

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
    return ((otid & 0xFFFF) ^ (otid >> 16) ^ (pid & 0xFFFF) ^ (pid >> 16)) < 8

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
    iv_raw = ru32(raw, 0x36)
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
        'hp':  raw[0x2C],
        'atk': raw[0x2D],
        'def': raw[0x2E],
        'spe': raw[0x2F],
        'spa': raw[0x30],
        'spd': raw[0x31],
    }

    # Moves (bitpacked at 0x27, 10 bits each)
    m0 = ru32(raw, 0x27)
    m1 = (ru32(raw, 0x27 + 2) >> 4)
    moves_raw = [
        m0 & 0x3FF,
        (m0 >> 10) & 0x3FF,
        (m0 >> 20) & 0x3FF,
        (m0 >> 30) | ((ru16(raw, 0x2B) & 0x3F) << 2),
    ]
    moves = [db['moves'].get(m, f"Move#{m}") if m else "" for m in moves_raw]

    # Nature
    nature = NATURES[pid % 25] if pid > 0 else "—"

    # Ability
    ability_idx = (iv_raw >> 31) & 1
    ability_name = "—"
    meta = db['ability_meta'].get(sp)
    if meta:
        ab_ids = meta.get("ability_ids", [])
        if ability_idx < len(ab_ids):
            ability_name = db['abilities'].get(ab_ids[ability_idx], "—")

    # Item
    item_id = ru16(raw, 0x1E)
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

    # EVs at 0x30
    evs = {
        'hp':  raw[0x30], 'atk': raw[0x31], 'def': raw[0x32],
        'spe': raw[0x33], 'spa': raw[0x34], 'spd': raw[0x35],
    }

    # IVs at 0x3A (bitpacked)
    iv_raw = ru32(raw, 0x3A)
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

    ability_idx  = (iv_raw >> 31) & 1
    ability_name = "—"
    meta = db['ability_meta'].get(sp)
    if meta:
        ab_ids = meta.get("ability_ids", [])
        if ability_idx < len(ab_ids):
            ability_name = db['abilities'].get(ab_ids[ability_idx], "—")

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

    return {
        "name":         name,
        "tid":          tid,
        "gender":       gender,
        "playtime":     f"{playtime_h}h {playtime_m}m",
        "money":        f"${money:,}",
        "badges":       badges,
        "national_dex": national_dex,
    }

# ---------------------------------------------------------------------------
# Full save parse
# ---------------------------------------------------------------------------
# Cache for growth rates so pc_to_party can use it without db access
_db_growth_cache = {}

def parse_save(data, db):
    global _db_growth_cache
    _db_growth_cache = db.get('growth', {})
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
    """Convert 100-byte party mon to 58-byte PC format."""
    if is_empty(party_raw[:6]):
        return bytes(MON_SIZE)
    pc = bytearray(MON_SIZE)
    # PID, OTID, Nickname (same offsets in both)
    pc[0x00:0x04] = party_raw[0x00:0x04]  # PID
    pc[0x04:0x08] = party_raw[0x04:0x08]  # OTID
    pc[0x08:0x12] = party_raw[0x08:0x12]  # Nickname
    pc[0x12:0x1B] = party_raw[0x12:0x1B]  # Language/misc/OT name/mark
    # Party-specific offsets → PC offsets
    pc[0x1C:0x1E] = party_raw[0x20:0x22]  # Species
    pc[0x1E:0x20] = party_raw[0x20:0x22]  # (also keep at 0x1C)
    struct.pack_into("<H", pc, 0x1C, ru16(party_raw, 0x20))  # Species
    struct.pack_into("<I", pc, 0x20, ru32(party_raw, 0x24))  # EXP
    struct.pack_into("<H", pc, 0x1E, ru16(party_raw, 0x22))  # Item (party@0x22 → pc@0x1E)
    # Moves: party has plain u16s at 0x2C, PC has bitpacked at 0x27
    moves = [ru16(party_raw, 0x2C + i*2) for i in range(4)]
    m = ((moves[0] & 0x3FF) | ((moves[1] & 0x3FF) << 10) |
         ((moves[2] & 0x3FF) << 20) | ((moves[3] & 0x3) << 30)) & 0xFFFFFFFF
    struct.pack_into("<I", pc, 0x27, m)
    pc[0x2B] = (moves[3] >> 2) & 0xFF
    # EVs: party 0x30 → PC 0x2C (same order: hp,atk,def,spe,spa,spd)
    pc[0x2C:0x32] = party_raw[0x30:0x36]
    # IVs: party 0x3A → PC 0x36 (same bitpacked format)
    pc[0x36:0x3A] = party_raw[0x3A:0x3E]
    return bytes(pc)


def pc_to_party(pc_raw, existing_party_raw=None):
    """Convert 58-byte PC mon to 100-byte party format."""
    if is_empty(pc_raw):
        return bytes(100)
    party = bytearray(100)
    # If there's an existing party mon there, preserve the battle stats
    # (current HP, level, etc.) from it as a base
    if existing_party_raw and not is_empty(existing_party_raw[:6]):
        party[:] = existing_party_raw[:100]
    # Overwrite the core data fields
    party[0x00:0x04] = pc_raw[0x00:0x04]  # PID
    party[0x04:0x08] = pc_raw[0x04:0x08]  # OTID
    party[0x08:0x12] = pc_raw[0x08:0x12]  # Nickname
    party[0x12:0x1B] = pc_raw[0x12:0x1B]  # Language/misc/OT/mark
    struct.pack_into("<H", party, 0x20, ru16(pc_raw, 0x1C))  # Species
    struct.pack_into("<I", party, 0x24, ru32(pc_raw, 0x20))  # EXP
    struct.pack_into("<H", party, 0x22, ru16(pc_raw, 0x1E))  # Item (pc@0x1E → party@0x22)
    # Moves: PC bitpacked at 0x27 → party plain u16s at 0x2C
    m0 = ru32(pc_raw, 0x27)
    m3_hi = pc_raw[0x2B]
    moves = [m0 & 0x3FF, (m0>>10) & 0x3FF, (m0>>20) & 0x3FF, ((m0>>30) | (m3_hi<<2)) & 0x3FF]
    for i, mv in enumerate(moves):
        struct.pack_into("<H", party, 0x2C + i*2, mv)
    # EVs: PC 0x2C → party 0x30
    party[0x30:0x36] = pc_raw[0x2C:0x32]
    # IVs: PC 0x36 → party 0x3A (same bitpacked format)
    party[0x3A:0x3E] = pc_raw[0x36:0x3A]
    # Set level from EXP — needed or the game shows level 0
    sp    = ru16(pc_raw, 0x1C)
    exp   = ru32(pc_raw, 0x20)
    # Look up growth rate from the global DB if available
    rate  = _db_growth_cache.get(sp, 0) if _db_growth_cache else 0
    level = calc_level(rate, exp)
    party[0x54] = level & 0xFF

    # Set current HP = max HP estimate (level * 2 as safe fallback if no base stats)
    # The game will recalculate on next battle; this just prevents 0/0 HP display
    if not existing_party_raw or is_empty(existing_party_raw[:6]):
        hp_estimate = max(1, level * 2)
        struct.pack_into("<H", party, 0x56, hp_estimate)   # current HP
        struct.pack_into("<H", party, 0x58, hp_estimate)   # max HP

    return bytes(party)


def apply_moves(data, moves):
    """
    moves: list of {from: {box, slot}, to: {box, slot}}
    box=0 = party, box=26 = preset
    Only stream boxes (1-19) supported for writing.
    Returns modified data bytes or raises ValueError.
    """
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

    # Update party count
    party_count = sum(
        1 for i in range(6)
        if not is_empty(data[sec1_off + 0x38 + i*100 : sec1_off + 0x38 + i*100 + 6])
    )
    struct.pack_into("<I", data, sec1_off + 0x34, party_count)

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
    }

    evo_c_text = evo_c.read_text(encoding="utf-8", errors="ignore")
    evo_table = {}  # species_id -> list of {method, param, target_id, target_name, description}

    section_re  = re.compile(r'(?=\[\w+\]\s*=\s*\{)')
    evo_tuple_re = re.compile(r'\{(EVO_\w+),\s*([^,]+),\s*(SPECIES_\w+),\s*[^}]+\}')

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
            tmpl = EVO_METHOD_TEMPLATES.get(method, method)
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
                'target_name': species_names.get(target, f'#{target}'),
                'description': desc,
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
    """Sort PC boxes using organizer logic. Returns modified data."""
    import organizer as org

    sections  = find_active_sections(data)
    db        = session.get("db") or load_databases()
    db_growth = db.get('growth', {})

    data_dir = find_data_dir()
    species_to_root = org.build_evo_chains(data_dir) if data_dir else {}

    db_species_simple = {}
    for k, v in (db.get('species') or {}).items():
        db_species_simple[k] = v

    box_names   = read_box_names(data, sections)
    named_boxes = {b for b in (
        {bn for bn, nm in box_names.items()
         if bn > 0 and nm.strip() and not nm.strip() in (f'Box{bn}', f'Box {bn}')}
    ) if b <= STREAM_BOXES}

    stream_buf = bytearray(build_stream_buffer(data, sections))

    # Collect all movable mons (same logic as organizer)
    SPLIT = find_split_slots()

    def slot_idx(box, slot): return (box-1)*SLOTS_PER_BOX + (slot-1)

    mons = []
    for box in range(1, STREAM_BOXES+1):
        if box in named_boxes: continue
        for slot in range(1, SLOTS_PER_BOX+1):
            idx = slot_idx(box, slot)
            raw = stream_buf[idx*MON_SIZE:(idx+1)*MON_SIZE]
            if all(b==0 for b in raw): continue
            sp  = ru16(raw, 0x1C)
            if not (1 <= sp <= 2500): continue
            exp   = ru32(raw, 0x20)
            rate  = db_growth.get(sp, 0)
            level = calc_level(rate, exp)
            root  = (species_to_root.get(sp, sp) if species_to_root else sp)
            mons.append({'raw': bytearray(raw), 'species': sp, 'level': level,
                         'root': root, 'name': db_species_simple.get(sp, f'#{sp}')})

    # Sort
    if sort_mode == 'level_asc':
        mons.sort(key=lambda m: (m['level'], m['root'], m['species']))
    elif sort_mode == 'level_desc':
        mons.sort(key=lambda m: (-m['level'], m['root'], m['species']))
    elif sort_mode == 'species':
        mons.sort(key=lambda m: (m['species'], m['level']))
    else:  # evo_family (default)
        mons.sort(key=lambda m: (m['root'], m['species'], m['level']))

    # Clear all unnamed, non-split slots
    for box in range(1, STREAM_BOXES+1):
        if box in named_boxes: continue
        for slot in range(1, SLOTS_PER_BOX+1):
            idx = slot_idx(box, slot)
            if idx not in SPLIT:
                stream_buf[idx*MON_SIZE:(idx+1)*MON_SIZE] = bytes(MON_SIZE)

    # Build destination slots (skip reserved boxes at start)
    dest_slots = []
    unnamed_count = 0
    for box in range(1, STREAM_BOXES+1):
        if box in named_boxes: continue
        unnamed_count += 1
        if unnamed_count <= reserve_boxes: continue
        for slot in range(1, SLOTS_PER_BOX+1):
            idx = slot_idx(box, slot)
            if idx not in SPLIT:
                dest_slots.append(idx)

    # Write sorted mons
    for i, m in enumerate(mons):
        if i >= len(dest_slots): break
        idx = dest_slots[i]
        stream_buf[idx*MON_SIZE:(idx+1)*MON_SIZE] = m['raw']

    # Write back
    write_stream_buffer(data, sections, stream_buf)
    return data


# ---------------------------------------------------------------------------
# Excel export (reuses save_reader.py)
# ---------------------------------------------------------------------------
def run_excel_export(data):
    """Generate xlsx and return as bytes."""
    import save_reader as sr
    import io, tempfile, os

    db = session.get("db") or load_databases()

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

    db = session.get("db") or load_databases()
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
    db = session.get("db") or load_databases()
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
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR / "static" / "dist"), "index.html")

@app.route("/species_types.json")
def species_types():
    return send_from_directory(str(BASE_DIR / "static"), "species_types.json")

@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(str(BASE_DIR / "static" / "dist" / "assets"), filename)

@app.route("/api/load", methods=["POST"])
def api_load():
    if 'save' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files['save']
    raw = f.read()
    if len(raw) not in (131072, 131088):
        return jsonify({"error": f"Unexpected file size {len(raw)} — expected 131072 or 131088 bytes"}), 400

    db = session.get("db") or load_databases()
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
    if session.get("data") is None:
        return jsonify({"error": "No save loaded"}), 400
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

@app.route("/api/download")
def api_download():
    if session.get("data") is None:
        return jsonify({"error": "No save loaded"}), 400
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
    if session.get("data") is None:
        return jsonify({"error": "No save loaded"}), 400
    try:
        table = load_evo_table()
        # Return as {species_id: [{target_name, description}, ...]}
        result = {}
        for sid, evos in table.items():
            result[str(sid)] = [{"target": e["target_name"], "target_id": e["target_id"], "desc": e["description"]} for e in evos]
        return jsonify({"ok": True, "evo_table": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sort", methods=["POST"])
def api_sort():
    if session.get("data") is None:
        return jsonify({"error": "No save loaded"}), 400
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
    if session.get("data") is None:
        return jsonify({"error": "No save loaded"}), 400
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
    if session.get("data") is None:
        return jsonify({"error": "No save loaded"}), 400
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

@app.route("/dex_species.json")
def dex_species_route():
    return send_from_directory(str(BASE_DIR / "static"), "dex_species.json")

@app.route("/species_to_national.json")
def species_to_national_route():
    return send_from_directory(str(BASE_DIR / "static"), "species_to_national.json")


@app.route("/api/dex_flags")
def api_dex_flags():
    """Return seen and caught dex flags decoded from the active save.
    Flags live directly in active section 1 at fixed offsets — no
    SaveBlock1 reconstruction needed.
    """
    if session.get("data") is None:
        return jsonify({"error": "No save loaded"}), 400

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
    db = session.get("db") or load_databases()
    species = db.get("species", {})
    return jsonify({str(k): v for k, v in species.items()})


if __name__ == "__main__":
    print("Pokemon Unbound Save Manager")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=False, port=5000)
