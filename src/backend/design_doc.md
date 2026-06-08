# Backend Design Document

## Overview
The backend is responsible for fetching discount information from the War Robots Frontiers news URL, preparing structured input files, invoking the Gemini CLI to perform item mapping, and producing a structured JSON file that the frontend can consume.

## Structure
- `src/backend/`
- `run.py`: The main orchestrator script that executes steps 1 through 4. Optionally accepts a `target_date_range` CLI parameter.
- `config.py`: Shared configuration, slug helper, and path definitions.
- `step1_scrape.py`: Scrapes the news URL and saves body text to `prompt/scraped_news_page.txt`.
- `step2_build_game_data.py`: Loads `WRFrontiersDB-Data/current/Objects/Module.json` and builds `game_data.json`.
- `step3_call_gemini.py`: Calls the Gemini CLI with access to the `prompt/` directory, optionally passing `target_date_range` parameter.
- `step4_archive_gen_grid.py`: Reads and validates LLM output from `prompt/output/discounts.json`, writes the result to `archive/discounts/discounts_<slug>.json`, generates the grid layout, and registers the week in `frontend/public/data/weeks.json`.
- `package.json`: Contains the npm dependencies, specifically the `@google/gemini-cli` package used for LLM interaction.
- `requirements.txt`: Python dependencies (`requests`, `beautifulsoup4`, `python-dotenv`).
- `prompt/`
  - `prompt.md`: The instructions telling the LLM what to do (read inputs, map items, write output).
  - `game_data.json`: A summarized JSON file of all production-ready English module names, their IDs, and their image file paths, extracted from `WRFrontiersDB-Data`.
  - `scraped_news_page.txt`: The raw text content scraped from the provided news URL.
  - `output/`
    - `discounts.json`: The LLM's output file containing matched module IDs and the standardized date range.
      Example format:
      ```json
      {
        "date_range": "May 26 - June 2",
        "items": [
          "OBJID_VirtualBot::varangian",
          "OBJID_Module::DA_Module_Weapon_Zeus.0"
        ]
      }
      ```

## Workflow
1. **Scraping**: `step1_scrape.py` downloads the HTML from the provided URL and extracts the main text body of the news article. The text is saved to `prompt/scraped_news_page.txt`.
2. **Game Data Preparation**: `step2_build_game_data.py` reads `current/Module.json` from the `WRFrontiersDB-Data` repository, extracts all production-ready English module names, their IDs, and their image file paths, and writes them to `prompt/game_data.json`.
3. **LLM Invocation**: `step3_call_gemini.py` invokes the Gemini CLI via subprocess. The CLI is configured to:
   - Only read files in `prompt/` (including `prompt.md`, `game_data.json`, and `scraped_news_page.txt`).
   - Only edit files in `prompt/output/`.
   - Follow the instructions in `prompt.md` to map the items mentioned in `scraped_news_page.txt` to the modules listed in `game_data.json`.
   - Optionally target a specific `target_date_range` if provided. Otherwise, it targets the latest/most recent section.
   - Output the result to `prompt/output/discounts.json`, containing mapped references and a standardized `date_range`.
4. **Archive & Grid Generation**: `step4_archive_gen_grid.py` reads and parses `prompt/output/discounts.json`, writes the result to `archive/discounts/discounts_<slug>.json`, generates the grid layout to `frontend/public/data/week_grids/grid_<slug>.json`, and registers the week in `frontend/public/data/weeks.json`.


