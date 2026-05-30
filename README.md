# UnboundBank — Pokémon Unbound Save Manager

A local web app for managing your Pokémon Unbound save file. View and rearrange your PC boxes, inspect party and box Pokémon in detail, track your Pokédex progress across both the National and Borrius dexes, and export spreadsheets of your collection or pending evolutions.

---

## Usage

### Releases (recommended — no installs needed)

1. Download `UnboundBank-vX.X-windows.zip` from the [Releases](../../releases) page
2. Extract it anywhere
3. Double-click `UnboundBank.exe`
4. Open **http://localhost:5000** in your browser and drag in your `.sav` file

Everything is bundled — Python, all dependencies, and all game data files.

### Running from source

**Requirements:** Python 3.9+, then `pip install -r requirements.txt`

**Windows:** Double-click `run.bat`

**Mac / Linux:**
```
python app.py
```

Your save file is exported from your emulator — in mGBA use *File → Export Save*.

---

## Features

### Bank Tab
- View all 24 PC boxes and your party
- Click any Pokémon to see full details: stats, EVs, IVs, moves, ability, nature, item
- Drag Pokémon between slots to rearrange (move mode)
- Search across all boxes by name
- Pokémon that can still evolve show a purple **evo** badge
  - Only shown when the evolution result isn't already in your Pokédex
- **Export Excel** — exports every Pokémon in your boxes and party to a spreadsheet
- **Evo Report** — exports a spreadsheet of every Pokémon that has a pending evolution you don't own yet, colour-coded by how to evolve them
- **Download Save** — saves your box changes back to a `.sav` file

### Pokédex Tab
- **National Pokédex** and **Borrius Pokédex** tabs
- Filter by: All / Caught / Seen / Missing / Can Evolve
- Filter by type, generation, or search by name
- Can Evolve filter only shows Pokémon whose evolution you haven't caught yet

---

## Credits & Licenses

- Game data (`data/` folder) sourced from [PUSE](https://github.com/Zannael/PUSE) by Zannael — [MIT License](https://github.com/Zannael/PUSE/blob/master/LICENSE)
- Game source files (`Evolution Table.c`, `species.h`, `items.h`, `moves.h`) from [Dynamic-Pokemon-Expansion](https://github.com/Skeli789/Dynamic-Pokemon-Expansion) by Skeli789 — [WTFPL](https://github.com/Skeli789/Dynamic-Pokemon-Expansion/blob/master/LICENSE)

---

## Notes

- The app runs entirely locally — no data leaves your machine
- The original `.sav` file is never modified; use **Download Save** to get your changes
- Boxes 20–24 are read-only (they use a fallback sector layout that doesn't support moves yet)
- Slots marked ⚠ are sector boundary slots and cannot be moved
