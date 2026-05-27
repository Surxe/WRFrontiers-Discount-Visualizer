# WRFrontiers Discount Visualizer - Design Overview

## Overview
The WRFrontiers Discount Visualizer is a project designed to parse news articles from the War Robots Frontiers website regarding discount events and display them in a visually appealing, static web page. It is composed of a Python-based backend processor and an Astro-based static frontend.

## Components

The project is split into two distinct components:

1. **[Backend Documentation](./backend/design_doc.md)**: Details the Python and npm-based pipeline for scraping news articles, setting up prompt files, calling the Gemini CLI to perform mapping, and outputting the structured data.
2. **[Frontend Documentation](./frontend/design_doc.md)**: Details the Astro-based static site generator that consumes the processed backend data and renders the final visual presentation of the discounted items.

## End-to-End Workflow

1. A news URL is provided to the backend tool.
2. The backend scrapes the URL and saves the body text into `src/backend/prompt/scraped_news_page.txt`.
3. The backend extracts production-ready English module names, IDs, and image paths from `WRFrontiersDB-Data` and writes them into `src/backend/prompt/game_data.json`.
4. The prompt instructions are stored in `src/backend/prompt/prompt.md`.
5. The backend calls the Gemini CLI, giving it access only to the files in `src/backend/prompt/`. It is tasked with reading the inputs and writing the mapped output to `src/backend/prompt/output/discounts.json` (or similar output file).
6. The backend script copies the mapped image files from `WRFrontiersDB-Data/` to the frontend's `public/assets/` directory while keeping their original folder structure.
7. The static Astro site uses the mapped output to build a static page showing the images sequentially.
