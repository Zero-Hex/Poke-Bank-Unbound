UNBOUND BANK - Pokemon Save Manager
=====================================

REQUIREMENTS:
  pip install flask

SETUP:
  1. Place this folder anywhere on your PC
  2. Copy the 'data' folder (from PUSE's backend/data/) into this folder
  3. Place Evolution Table.c and species.h next to app.py (optional, not needed for bank)

RUN:
  python app.py

Then open http://localhost:5000 in your browser.

USAGE:
  - Drag and drop your .sav file onto the upload screen
  - Click any Pokemon to see its details in the right panel
  - Drag Pokemon between box slots or party slots to move them
  - Grey slots with ⚠ are sector boundary slots and cannot be moved
  - Boxes 20-24 are read-only (fallback sector storage — moves not supported yet)
  - Click "Download Save" to save your changes

NOTES:
  - All changes are applied immediately when you drop a Pokemon
  - The original save file is never modified — always download to save
  - Run the organizer scripts separately for bulk sorting
