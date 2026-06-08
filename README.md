<img width="368" height="561" alt="Snag_3b64e9c3" src="https://github.com/user-attachments/assets/141cc3b3-3f9a-4290-b84b-79c44c4b0c91" />
<img width="1918" height="918" alt="Snag_3b64dfe0" src="https://github.com/user-attachments/assets/c00436cf-c04a-4f07-a4b4-18621a65ecd7" />
<img width="1917" height="911" alt="Snag_3b64cf07" src="https://github.com/user-attachments/assets/833c8802-421c-49bd-a7e2-dd047cf34b24" />
# UnboundBank — Pokémon Unbound Save Manager

A local web app for managing your Pokémon Unbound save file. View and rearrange your PC boxes, inspect party and box Pokémon in detail, track your Pokédex progress across both the National and Borrius dexes, and export spreadsheets of your collection or pending evolutions.


This was specifically created to work with Unbounds offsets so it will not work with any other Rom Files (Sorry!)

Reasoning:

I got tired of trying to manage some organization within my PC for 250+ mons at any given time so I worked to develop this locally hosted app so that I could very easily with 1 click organize my mons and it grew from there. It now includes not only the sort functionality, evolution finder, an accurate PokeDex including a list of missing mons, as well as evolutions you are missing. There are some Excel type files that can be exported that contain data similiar to the website in-case you want them locally for some reason, one of them is an evolution helper so you can see all the evolutions you have in your boxes that you need to work on. This never touches your save, but its always recommended to back up before using. 

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
- Enable Move Mode to Select and Swap Pokémon between slots to rearrange
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
- Slots marked ⚠ are sector boundary slots and cannot be moved
