# UnboundBank User Guide

**UnboundBank** is a save editor and Pokémon manager for Pokémon Unbound. It lets you view, edit, and organize your team and boxes directly from your save file.

## Getting Started

### Installation

1. Download `UnboundBank-v2.0.0-windows.zip` from the [releases page](https://github.com/Zero-Hex/Poke-Bank-Unbound/releases)
2. Extract the zip anywhere on your computer (Desktop, Documents, etc.)
3. Double-click `UnboundBank.exe`

A small launcher window will appear with three buttons.

### First Launch

The launcher window shows:
- **Start PokeBANK** — Opens the app in your browser
- **Check for Updates** — Checks GitHub for newer releases (no data sent)
- **Exit** — Closes the app

Click **Start PokeBANK** and your browser will open automatically to the app. If the browser doesn't open, manually visit `http://localhost:5000`.

## Loading Your Save

When UnboundBank starts, you'll see the upload screen with a large drop zone.

**To load your save:**
1. Drag your `.sav` file from your emulator folder and drop it on the grey box, OR
2. Click the box to browse for your save file

Supported formats: `.sav`, `.sa1`, `.sa2`, `.sa3`, `.sa4`, `.srm`, `.SaveRAM`

Once loaded, your trainer info appears in the header (name, ID, money, badges, playtime).

## Bank Tab

The **Bank** is your main interface. It shows all 10 boxes with 30 slots each.

### Viewing Pokémon

- Each Pokémon shows its sprite, nickname (or name if unnamed), and level
- **Gold shimmer + ★** indicates a shiny Pokémon
- **"evo"** badge means the Pokémon can evolve
- **⚠** warning mark indicates a sector boundary (don't move that Pokémon — it can corrupt your save)

### Selecting & Moving Pokémon

**Single selection:**
- Click a Pokémon to select it
- Details appear in the right panel (stats, moves, items, etc.)

**Multi-select (move or release):**
- Click multiple Pokémon to select them
- Use the action buttons at the bottom:
  - **Send to Vault** — Move them to permanent storage
  - **Move to Box** — Move them to a different box
  - **Release** — Remove them from your save (cannot be undone)

### Downloading Your Save

When you make changes:
1. An orange **Unsaved** badge appears in the header
2. Click **Download Save** to save your changes
3. A file named `save_modified.sav` downloads
4. Load this file in your emulator to play with the changes

> **Important:** Always back up your original save file before editing!

### Editing Pokémon

Click a Pokémon to open the detail panel on the right. You can edit:
- Nickname
- Level
- Experience
- Individual Values (IVs)
- Effort Values (EVs)
- Moves (up to 4)
- Held item
- Ability
- Nature
- Gender
- Shiny status

Changes apply instantly.

## Vault Tab

The **Vault** is permanent storage for Pokémon you want to keep but don't need on your team or in boxes.

### Sending to Vault

1. Select one or more Pokémon in the Bank
2. Click **Send to Vault**
3. They move out of your boxes and into the Vault

The Vault stores them in your save file, so they're always with you when you download.

### Retrieving from Vault

1. Go to the **Vault** tab
2. Click a Pokémon to view details
3. Click **Send to Box** to move it back to your boxes

## Pokédex Tab

View your Pokédex progress and browse all available Pokémon.

### Filter & Search

- **All / Caught / Seen / Missing / Can Evolve** — Filter by completion status
- **Type dropdown** — Filter by Pokémon type
- **Search box** — Search by name
- **Spoilers: ON/OFF** — Hide names and sprites for Pokémon you haven't seen yet (useful for avoiding spoilers)
- **★ Shiny** — Toggle to view all sprites as their shiny variants at once

The header shows:
- **Caught** — How many you've caught
- **Seen** — How many you've encountered
- **Completion** — Your Pokédex completion percentage

### Viewing Details

Click a Pokémon card to see more info (if spoilers are off for unseen Pokémon, only the ID shows until you catch/see it).

## Trade Tab

The **Trade** feature lets you view and manage Pokémon trades with other players.

*(Details depend on your specific trade setup)*

## Update Checker

Click **Check for Updates** in the launcher window to check if a newer version is available.

- **Up to date** — You're running the latest version
- **Update available** — A newer version exists; click the link to visit the release page
- **Could not reach GitHub** — Internet connection issue; check your connection and try again

> **Privacy:** The update checker only connects to GitHub's public API. No data about your save or system is sent.

## Launcher & System Tray

### Minimizing to Tray

Close the launcher window by clicking the X button. Instead of closing, it minimizes to your system tray (bottom-right corner of your screen, next to the clock).

### Restoring the Launcher

Right-click the PokeBANK icon in the system tray and click **Show** to bring the launcher back.

### Exiting Completely

Either:
- Click the **Exit** button in the launcher window, OR
- Right-click the tray icon and click **Exit**

This closes the entire app and stops the background server.

## Data & Privacy

**Everything is local.** UnboundBank:
- Runs entirely on your computer
- Does not upload your save or any data to the internet
- Does not collect usage statistics or telemetry
- Only connects to GitHub's API to check for updates

Your save file is only modified when you click **Download Save**. All changes are made to the copy you download — your original save on disk is never touched.

## Troubleshooting

### The launcher window won't appear

- Make sure Python 3.11+ is installed if running from source
- On fresh Windows installs, you may need the [Visual C++ Redistributable](https://support.microsoft.com/en-us/help/2977003/)
- Check that all dependencies installed correctly by looking at the console output when you run the app

### The browser won't open automatically

- The app is still running. Manually visit `http://localhost:5000` in your browser

### "Cannot load save" error

- Make sure the file is a valid Pokémon Unbound `.sav` file
- The file must be exactly 131,072 or 131,088 bytes
- Try a different save file to rule out corruption

### Pokémon won't move between boxes

- The Pokémon may be at a sector boundary (marked with ⚠). Don't move those.
- Refresh the page and try again

### My changes didn't save in the game

- You must download the save file and load it in your emulator
- Changes in UnboundBank only affect the downloaded copy — the original file never changes

### The sprite won't load for a Pokémon

- This is rare. Try refreshing the page
- Some forms may not have sprites available

## FAQ

**Q: Is this safe to use?**  
A: Yes. UnboundBank is read-only for your original save. Changes only apply to the downloaded copy, which you then load in your emulator. Always keep a backup of your original save just in case.

**Q: Can I edit my trainer name or ID?**  
A: The trainer info in the header (name, ID, money, badges, playtime) is displayed but not editable in the current version. Focus is on Pokémon management.

**Q: Can I transfer Pokémon between saves?**  
A: Yes, with the trade tool. 

**Q: Does it work on Mac/Linux?**  
A: The pre-built executable is Windows-only. If you have Python installed, you can run it from source on Mac/Linux — just clone the repo and run `python launcher.py`.

**Q: Why does it take 20-30 seconds to start?**  
A: The first launch extracts bundled resources. Subsequent launches are faster.

## Support

For issues, questions, or feature requests, visit the [GitHub repository](https://github.com/Zero-Hex/Poke-Bank-Unbound).

---

**Version:** 2.0.0  
**Last Updated:** 2026-06-04

*UnboundBank is not affiliated with Nintendo, The Pokémon Company, or Pokémon Unbound. This is a fan-made tool.*
