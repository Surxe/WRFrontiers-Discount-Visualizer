---
name: styling
description: Load before writing or editing ANY CSS or Astro `<style>` block in this repo. Shared visual language (colors, fonts, links, buttons, toggles, tooltips) comes from the WRFrontiersDB-Design submodule - use its `--wrf-*` tokens and `.wrf-*` element classes, never raw chrome hex. Covers scoped-vs-global styles and where to change shared vs local styling.
---

# Styling

This visualizer's visual language - palette, typography, and the reusable UI
elements (links, buttons, toggles, tooltips, form controls, focus, scrollbars,
selection) - is owned by the **WRFrontiersDB-Design** submodule, checked out at
`src/frontend/vendor/wrf-design/` and imported by the layout entry points
(`GenericPage.astro`, `DiscountPage.astro`, and other HTML entry files via
`import '../../vendor/wrf-design/index.css'`). WRFrontiersDB-Site consumes the
same submodule, so the two sites stay visually identical.

**Canonical reference:** `src/frontend/vendor/wrf-design/STYLE-GUIDE.md` (palette,
elements, do/don't) and `src/frontend/vendor/wrf-design/README.md` (consuming, the
local dev loop, and how a change propagates to the live sites). This skill is the
repo-specific how-to; the style guide is the source of truth.

## Rules

1. **Use tokens, never raw chrome hex.** Every chrome color, font, radius, and
   transition resolves through a `var(--wrf-*)` token. Do not write `#2a2a2a`,
   `#4fc3f7`, `#444`, etc. in component CSS - use `var(--wrf-surface)`,
   `var(--wrf-accent)`, `var(--wrf-border)`, and so on. See the token list in
   `design-tokens.css` / the style guide.
2. **Reuse the shared element classes.** Add `.wrf-btn` (`--primary` /
   `--secondary`), `.wrf-toggle` / `.wrf-toggle__btn`, `.wrf-tooltip` rather than
   restyling bare elements. Links (`a`), form controls, focus rings, scrollbars,
   and selection are styled globally by `elements.css` - don't re-declare them.
3. **Domain colors stay raw, on purpose.** Meaningful data-driven colors -
   savings / likelihood greens, Discord blurple, OG-card gradients - are NOT
   chrome and are intentionally left as raw hex. Don't tokenize them.
4. **Change shared looks in the submodule, not here.** If an element's canonical
   look needs to change, edit `src/frontend/vendor/wrf-design/` (see the dev loop
   below), not a per-component override. Local component CSS is for this repo's
   own layout.

## Scoped vs. global styles (Astro)

- **Default to a scoped `<style>` block** co-located in the `.astro` component.
  Astro scopes it (adds a `data-astro-cid-*` attribute), which is already the
  modular state - do NOT extract scoped styles to an external `.css` just to
  "modularize"; that would make them global and break scoping.
- **Use `:global(...)` only for DOM built in JavaScript** (via `innerHTML` /
  `document.createElement`), which the scoping attribute never reaches. Keep
  `:global` blocks next to the script that generates the markup. (The Cost
  Calculator's JS-built result rows are the main example.)
- An `@import` inside a scoped `<style>` IS scoped per-component by Astro, so a
  shared partial (e.g. `styles/tooltips.css`) imported into two components is
  scoped separately in each.

## Delivery specifics

- Layout entries bundle the shared CSS via the relative `import` above; the repo
  also serves `public/global.css` as a static `<link>` (its `* { font-family }`
  and base rules resolve against the submodule tokens).
- **Tooltips.** Two systems coexist: the shared `.wrf-tooltip` (`InfoTooltip.astro`,
  bubble positioned by `src/frontend/src/scripts/wrf-tooltip.js`) for standalone
  info icons, and the table/header tooltips in `styles/tooltips.css`
  (`.tooltip-icon` / `.custom-tooltip`) which keep a below-icon position and a
  tap-to-toggle on touch. The `.wrf-tooltip` JS is an **identical mirror** of the
  canonical source in `src/frontend/vendor/wrf-design/README.md`; WRFrontiersDB-Site
  keeps its own identical copy. Keep them in sync. (Fully unifying the table
  tooltips onto `.wrf-tooltip` is a known future cleanup.)

## Local dev loop for shared styling

To change a shared token/element and see it live here without any CI or submodule
bump: branch inside the submodule (`cd src/frontend/vendor/wrf-design && git
switch -c ...`), edit the CSS, and run this repo's dev server (`npm run dev` in
`src/frontend`) - it HMRs the change because the CSS is a relative import in the
Vite graph. Full loop, the independent-checkouts gotcha, and the 3-step
propagation-to-live model (this repo deploys via a manual `workflow_dispatch`) are
in `src/frontend/vendor/wrf-design/README.md`.
