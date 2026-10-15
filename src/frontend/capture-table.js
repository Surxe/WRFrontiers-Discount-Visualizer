/**
 * capture-table.js
 *
 * Screenshots the discount grid (#discount-grid) on the home page of the
 * already-built dist/. Writes public/discount-table.png by default, or
 * `--out <path>` (see capture-lib.js).
 *
 * Prerequisites:
 *   1. Run `npm run build` first.
 *   2. Run `npm run capture` (or `node capture-table.js` from src/frontend/).
 */

import path from 'path';
import { FRONTEND_DIR, runCapture } from './capture-lib.js';

const GRID_SELECTOR = '#discount-grid';

runCapture({
  name: 'capture-table.js',
  pagePath: '',
  selector: GRID_SELECTOR,
  defaultOut: path.join(FRONTEND_DIR, 'public', 'discount-table.png'),
  // Wide viewport so the grid renders at full 1x scale (intrinsic width ~938px).
  viewport: { width: 1400, height: 900, deviceScaleFactor: 2 },
  // Force grid scale to 1 to bypass container query circular dependencies in
  // headless Chrome, and hide the "add to calculator" controls, which have no
  // place in the static og:image.
  style: `${GRID_SELECTOR} { --grid-scale: 1 !important; } .add-to-calc-btn, .mobile-calc-hint { display: none !important; }`,
});
