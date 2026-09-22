# Backend Design Document

## Overview
The backend is responsible for building game data from raw database objects, mapping the announced item names for a discount week to game ids, generating layout grids, and registering discount weeks for the frontend.

## Structure
- `src/backend/`
  - `run.py`: The main orchestrator script that executes steps 1 through 3. Accepts `--items` (comma-separated names) and `--date-range` (e.g. "06-16 06-23").
  - `config.py`: Shared configuration, slug helper, and path definitions.
  - `step1_build_game_data.py`: Loads `Module.json` and `VirtualBot.json` from `WRFrontiersDB-Data/current/Objects/` and builds `src/backend/game_data/game_data.json`.
  - `step2_map_items.py`: Takes input items, checks for duplicates, and maps each announced name to a `game_data.json` ref via the resolution order `manual_mapping.json` -> exact vocab match -> Jev (see `jev_mapper.py`). Records new hits back into `manual_mapping.json`, expands VirtualBot refs to core module refs (filtering out titan weapons), and saves output to `temp/output/discounts.json`. Jev is the mapper: without a `JEV_API_KEY` the step fails fast rather than guessing.
  - `jev_mapper.py`: The name->id classifier. Wraps TypeSafe AI's Jev "System One" model (`Choice` over the closed `game_data` vocabulary) to resolve typos, plurals, and mis-split announcement tokens with calibrated confidence. Re-adds, reworked around Jev, the mapping intelligence removed with the Gemini step in commit 9779159. Reports itself unavailable when `JEV_API_KEY` is unset, in which case only manual pins and exact matches resolve (the CLI step fails fast).
  - `step3_archive_gen_grid.py`: Reads the mapped discounts from `temp/output/discounts.json`, writes to `archive/discounts/discounts_<slug>.json`, generates the grid layout, and updates the manifest in `frontend/public/data/weeks.json`.
  - `manual_mapping.json`: Persistent mapping dictionary to save and reuse matched item names.

## Workflow
1. **Game Data Preparation**: `step1_build_game_data.py` extracts all ready virtual bots and standalone modules (weapons/gear) to `src/backend/game_data/game_data.json`.
2. **Name -> Id Mapping**: `step2_map_items.py` parses the target date range, resolves each announced name to a ref (manual pin -> exact match -> Jev), writes any new matches to `manual_mapping.json`, expands virtual bots, and writes the output JSON file. In CI, `JEV_API_KEY` is supplied as a repo secret; without it the step fails fast, since Jev is the mapper.
3. **Archive & Grid Generation**: `step3_archive_gen_grid.py` saves the discount list under `archive/discounts/`, builds a visual grid layout for the frontend, and updates the weeks list in `weeks.json`.



