# Backend Design Document

## Overview
The backend is responsible for fetching discount information from the War Robots Frontiers news URL, preparing structured input files, invoking the Gemini CLI to perform item mapping, and producing a structured JSON file that the frontend can consume.

## Structure
- `src/backend/`
  - `run.py`: The main orchestrator script that executes steps 1 through 5.
  - `config.py`: Shared configuration and path definitions for all step scripts.
  - `step1_scrape.py`: Scrapes the news URL and saves body text to `prompt/scraped_news_page.txt`.
  - `step2_build_game_data.py`: Loads `WRFrontiersDB-Data/current/Objects/Module.json` and builds `game_data.json`.
  - `step3_call_gemini.py`: Calls the Gemini CLI with access to the `prompt/` directory.
  - `step4_read_output.py`: Reads and validates LLM output from `prompt/output/discounts.json`.
  - `step5_copy_assets.py`: Copies referenced images and the output JSON to the frontend.
  - `package.json`: Contains the npm dependencies, specifically the `@google/gemini-cli` package used for LLM interaction.
  - `requirements.txt`: Python dependencies (`requests`, `beautifulsoup4`).
  - `prompt/`
    - `prompt.md`: The instructions telling the LLM what to do (read inputs, map items, write output).
    - `game_data.json`: A summarized JSON file of all production-ready English module names, their IDs, and their image file paths, extracted from `WRFrontiersDB-Data`.
    - `scraped_news_page.txt`: The raw text content scraped from the provided news URL.
    - `output/`
      - `discounts.json`: The LLM's output file containing matched module IDs, English names, and image paths in the order they appear in the news article.
        Example format:
        ```json
        [
          {
            "id": "module_robot_destrier",
            "name": "Destrier",
            "image_path": "content/modules/destrier.png"
          },
          {
            "id": "module_weapon_punisher",
            "name": "Punisher",
            "image_path": "content/modules/punisher.png"
          }
        ]
        ```

## Workflow
1. **Scraping**: `step1_scrape.py` downloads the HTML from the provided URL and extracts the main text body of the news article. The text is saved to `prompt/scraped_news_page.txt`.
2. **Game Data Preparation**: `step2_build_game_data.py` reads `current/Module.json` from the `WRFrontiersDB-Data` repository, extracts all production-ready English module names, their IDs, and their image file paths, and writes them to `prompt/game_data.json`.
3. **LLM Invocation**: `step3_call_gemini.py` invokes the Gemini CLI via subprocess. The CLI is configured to:
   - Only read files in `prompt/` (including `prompt.md`, `game_data.json`, and `scraped_news_page.txt`).
   - Only edit files in `prompt/output/`.
   - Follow the instructions in `prompt.md` to map the items mentioned in `scraped_news_page.txt` to the modules listed in `game_data.json`.
   - Output the result to `prompt/output/discounts.json`, containing module IDs, English names, and image paths in the order they appear in the news article.
4. **Image Copying & Frontend Data Delivery**:
   - `step4_read_output.py` reads and parses `prompt/output/discounts.json` to validate the output.
   - `step5_copy_assets.py` copies the referenced image files from `WRFrontiersDB-Data/` to `src/frontend/public/assets/` (preserving original folder structure) and copies the JSON output to `src/frontend/public/data/discounts.json` for the frontend build.

