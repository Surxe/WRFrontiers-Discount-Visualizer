# WRFrontiers Discount Visualizer - Design Overview

## Overview
The WRFrontiers Discount Visualizer is a project designed to parse item lists for discount events and display them in a visually appealing, static web page. It is composed of a Python-based backend processor and an Astro-based static frontend.

## Components

The project is split into two distinct components:

1. **[Backend Documentation](./backend/design_doc.md)**: Details the Python pipeline for compiling game data, mapping items using local fuzzy matching, storing mappings in a persistent manual override file, and generating visual grid outputs.
2. **[Frontend Documentation](./frontend/design_doc.md)**: Details the Astro-based static site generator that consumes the processed backend data and renders the final visual presentation of the discounted items.

## End-to-End Workflow

1. A list of items (comma-separated string) and a date range are provided to the backend orchestrator `run.py`.
2. **Step 1**: The backend extracts production-ready English module names and Virtual Bot names from raw data in `WRFrontiersDB-Data` and writes them into `src/backend/game_data/game_data.json`.
3. **Step 2**: The backend maps the input item names against `game_data.json` and a persistent `manual_mapping.json` using Python's `difflib` fuzzy matching. Non-1:1 fuzzy matches are saved to `manual_mapping.json` to respect future overrides. Virtual Bots are expanded to their core modules, filtering out titan weapons. Mapped IDs are output to `temp/output/discounts.json`.
4. **Step 3**: The backend reads `temp/output/discounts.json`, writes a date-keyed item list to `archive/discounts/discounts_<slug>.json`, generates a layout grid file in `src/frontend/public/data/week_grids/grid_<slug>.json`, updates the reverse lookup index `discount_data.json`, and registers the week in `src/frontend/public/data/weeks.json`.
5. The static Astro site uses the grid layout output to build a static page showing the images sequentially.


