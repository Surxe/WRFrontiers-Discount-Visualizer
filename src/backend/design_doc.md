# Backend Design Document

## Overview
The backend is responsible for fetching discount information from the War Robots Frontiers news URL, preparing structured input files, invoking the Gemini CLI to perform item mapping, and producing a structured JSON file that the frontend can consume.

## Structure
- `src/backend/`
  - `fetch_discounts.py`: The main orchestrator script.
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
1. **Scraping**: `fetch_discounts.py` downloads the HTML from the provided URL and extracts the main text body of the news article. The text is saved to `prompt/scraped_news_page.txt`.
2. **Game Data Preparation**: The script reads `current/Module.json` from the `WRFrontiersDB-Data` repository, extracts all production-ready English module names, their IDs, and their image file paths, and writes them to `prompt/game_data.json`.
3. **LLM Invocation**: The script invokes the Gemini CLI via subprocess. The CLI is configured to:
   - Only read files in `prompt/` (including `prompt.md`, `game_data.json`, and `scraped_news_page.txt`).
   - Only edit files in `prompt/output/`.
   - Follow the instructions in `prompt.md` to map the items mentioned in `scraped_news_page.txt` to the modules listed in `game_data.json`.
   - Output the result to `prompt/output/discounts.json`, containing module IDs, English names, and image paths in the order they appear in the news article.
4. **Image Copying**: After the LLM produces its output, the script reads `prompt/output/discounts.json` and copies the referenced image files from `WRFrontiersDB-Data/` to `src/frontend/public/assets/`, preserving the original folder structure.
5. **Frontend Data Delivery**: The script copies `prompt/output/discounts.json` to `src/frontend/public/data/discounts.json` for the Astro build to consume.
