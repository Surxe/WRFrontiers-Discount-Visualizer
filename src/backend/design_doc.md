# Backend Design Document

## Overview
The backend is responsible for building game data from raw database objects, mapping items for a discount week using local fuzzy matching, generating layout grids, and registering discount weeks for the frontend.

## Structure
- `src/backend/`
  - `run.py`: The main orchestrator script that executes steps 1 through 3. Accepts `--items` (comma-separated names) and `--date-range` (e.g. "06-16 06-23").
  - `config.py`: Shared configuration, slug helper, and path definitions.
  - `step1_build_game_data.py`: Loads `Module.json` and `VirtualBot.json` from `WRFrontiersDB-Data/current/Objects/` and builds `src/backend/game_data/game_data.json`.
  - `step2_map_items.py`: Takes input items, checks for duplicates, maps them using fuzzy matching (via `difflib`) against `game_data.json` and `manual_mapping.json`. Expands VirtualBot refs to core module refs (filtering out titan weapons), and saves output to `temp/output/discounts.json`.
  - `step3_archive_gen_grid.py`: Reads the mapped discounts from `temp/output/discounts.json`, writes to `archive/discounts/discounts_<slug>.json`, generates the grid layout, and updates the manifest in `frontend/public/data/weeks.json`.
  - `manual_mapping.json`: Persistent mapping dictionary to save and reuse matched item names.

## Workflow
1. **Game Data Preparation**: `step1_build_game_data.py` extracts all ready virtual bots and standalone modules (weapons/gear) to `src/backend/game_data/game_data.json`.
2. **Local Fuzzy Mapping**: `step2_map_items.py` parses the target date range, fuzzy matches the item names, writes any new non-1:1 matches to `manual_mapping.json`, expands virtual bots, and writes the output JSON file.
3. **Archive & Grid Generation**: `step3_archive_gen_grid.py` saves the discount list under `archive/discounts/`, builds a visual grid layout for the frontend, and updates the weeks list in `weeks.json`.



