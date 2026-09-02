# Style guide

The visual style guide for this visualizer - palette, typography, links, buttons,
toggles, tooltips, and the rest of the shared UI vocabulary - is the **canonical
WRFrontiersDB style guide** in the design system:

**[`src/frontend/vendor/wrf-design/STYLE-GUIDE.md`](../src/frontend/vendor/wrf-design/STYLE-GUIDE.md)**

That guide is shared with WRFrontiersDB-Site so the two sites look identical; both
consume the same WRFrontiersDB-Design submodule. Read it first for anything about
colors, fonts, or the reusable elements.

## Repo-specific notes

- **Delivery.** The shared CSS is bundled via a relative `import` from the layout
  entries (`src/frontend/src/components/GenericPage.astro`, `DiscountPage.astro`,
  and other HTML entry points do `import '../../vendor/wrf-design/index.css'`).
  The repo also serves `src/frontend/public/global.css` as a static `<link>`; its
  base rules resolve against the submodule tokens.
- **Where component CSS lives.** Component-specific styling stays in a scoped
  `<style>` block co-located in the `.astro` file. Do not extract scoped styles to
  an external `.css` (that makes them global). See the `styling` skill for the
  scoped-vs-`:global` rule and the token/element usage rules.
- **Tooltips.** Shared `.wrf-tooltip` (`InfoTooltip.astro`) is positioned by
  `src/frontend/src/scripts/wrf-tooltip.js`, an identical mirror of the canonical
  source in `src/frontend/vendor/wrf-design/README.md`. The table/header tooltips
  in `src/frontend/src/styles/tooltips.css` keep a below-icon position and touch
  tap-toggle.
- **Domain colors** (savings / likelihood greens, Discord blurple, OG gradients)
  are intentionally left as raw hex - they are data, not chrome. Don't tokenize
  them.

## For agents

- Load the **`styling`** skill before writing or editing any CSS or `<style>`
  block. Agent docs live in `.agents/` (mirrored into the tool dirs by
  `.agents/setup-symlinks.sh`); see `.agents/README.md`.
- For how a design-system change reaches this live site (this repo deploys via a
  manual `workflow_dispatch`), see the propagation model in
  `src/frontend/vendor/wrf-design/README.md`.
