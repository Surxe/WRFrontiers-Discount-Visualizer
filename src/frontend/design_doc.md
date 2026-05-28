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
      - `discounts.json`: The generated JSON from the backend (written by step4). Contains full module objects with id, name, and image_path.
  - `package.json`: Contains Astro and related dependencies.
  - `astro.config.mjs`: Astro configuration file.

## Workflow
1. **Data Consumption**: During the static build process, Astro will read `public/data/discounts.json`.
2. **Rendering**:
   - The page will iterate through the items in the exact order they were provided.
   - For each item, it displays the module name and ID.
3. **Aesthetics**: No planned styling. Use the bare minimum for now.
4. **Static Output**: Running `npm run build` will produce a completely static HTML/CSS bundle that can be hosted on GitHub Pages.
