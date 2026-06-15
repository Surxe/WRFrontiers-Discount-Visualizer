# Frontend Design Document

## Overview
The frontend is responsible for visualizing the discounted items based on the data provided by the backend. It is built as a static site using Astro, featuring a fully responsive CSS Grid layout and automated Discord embed screenshot generation.

## Structure
- `src/frontend/`
  - `src/`
    - `pages/`: Contains Astro views (e.g., `index.astro`).
    - `components/`: Contains UI components and the `DiscountGrid` layout.
    - `utils/`: Contains data fetchers and date validation logic.
  - `public/`
    - `data/`: Contains the generated JSON from the backend (e.g., `weeks.json`, `discount_data.json`, and `week_grids/grid_<slug>.json`). 
    - `discount-table.png`: The captured screenshot of the grid (generated dynamically).
    - `WRFrontiersDB-Data/`: A checked-out or symlinked copy of the game data repository for accessing textures and schemas.
  - `package.json`: Contains Astro and related dependencies, including Puppeteer for screenshots.
  - `astro.config.mjs`: Astro configuration file.
  - `capture-table.js`: Node.js script using Puppeteer and a native HTTP server to capture a screenshot of the discount grid.

## Data Workflow
1. **Data Ingestion**: The `dataFetcher.js` utility parses `weeks.json` to find the active discount data. It dynamically reads the raw game database files (`Module.json`, `VirtualBot.json`, etc.) to enrich the base discount data with rarities, categories, and texture paths.
2. **Validation**: The frontend enforces that Virtual Bot components (Chassis, Torso, Shoulder) share the exact same rarity, failing the build on mismatch.
3. **Rendering**: The `DiscountGrid.astro` component renders the enriched items into a 7-column responsive CSS grid, grouped by Virtual Bot and equipment type.

## Pipeline Operations
The typical workflow for running and deploying the frontend:

1. **Local Development**:
   - Run `npm run dev` in `src/frontend/` to start the Astro dev server at `http://localhost:4321`. This is used to confirm styling and layout changes locally.

2. **Local Build & Capture**:
   - Run `npm run build` to generate the production static HTML/CSS bundle into the `dist/` directory.
   - Run `npm run capture` to boot a native Node.js HTTP server pointing at `dist/` and launch a headless Puppeteer instance. It takes a crisp, scaled screenshot of the `#discount-grid` element and saves it to `public/discount-table.png`.

3. **Production Deployment**:
   - Changes are pushed to the repository.
   - The main **All** workflow (`all.yml`) or a standalone deployment workflow is dispatched via GitHub Actions.
   - The workflow executes the `screenshot` job (which installs Chrome/Puppeteer, builds the site, and captures the image) and uploads the PNG artifact.
   - The `build` job downloads the PNG artifact into `public/`, then runs the final Astro build.
   - The resulting static bundle is deployed to GitHub Pages, where the generated PNG is referenced by the `og:image` meta tags for automatic inline rendering in Discord embeds.
