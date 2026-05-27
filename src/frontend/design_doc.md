# Frontend Design Document

## Overview
The frontend is responsible for visualizing the discounted items based on the data provided by the backend. It will be built as a completely static site using Astro.

## Structure
- `src/frontend/`
  - `src/`
    - `pages/`
      - `index.astro`: The main view containing the display logic.
  - `public/`
    - `data/`
      - `discounts.json`: The generated JSON from the backend (copied from `src/backend/prompt/output/discounts.json`).
    - `assets/`: Image assets copied from the data repository by the backend script. Files maintain the same directory structure as they exist in the source, e.g., `public/assets/content/x/y/z/file.png`.
  - `package.json`: Contains Astro and related dependencies.
  - `astro.config.mjs`: Astro configuration file.

## Workflow
1. **Data Consumption**: During the static build process, Astro will read `public/data/discounts.json`.
2. **Rendering**:
   - The page will iterate through the items in the exact order they were provided.
   - For each item, it uses the provided asset path inside `public/assets/` to display its respective image next to the others.
3. **Aesthetics**: No planned styling. Use the bare minimum for now.
4. **Static Output**: Running `npm run build` will produce a completely static HTML/CSS bundle that can be hosted on GitHub Pages.
