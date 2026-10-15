/**
 * capture-predictions-og.js
 *
 * Screenshots the dedicated /predictions-og card (#og-card, an exact 1200x630
 * box) from the already-built dist/; used as the /predictions og:image.
 * Writes public/predictions-og.png by default, or `--out <path>` (see
 * capture-lib.js).
 *
 * Prerequisites:
 *   1. Run `npm run build` first.
 *   2. Run `npm run capture:og` (or `node capture-predictions-og.js`).
 */

import path from 'path';
import { FRONTEND_DIR, runCapture } from './capture-lib.js';

runCapture({
  name: 'capture-predictions-og.js',
  pagePath: 'predictions-og',
  selector: '#og-card',
  defaultOut: path.join(FRONTEND_DIR, 'public', 'predictions-og.png'),
  viewport: { width: 1240, height: 700, deviceScaleFactor: 2 },
  // headless:'shell' avoids a compositor stall that hangs
  // Page.captureScreenshot under plain headless on some Linux hosts.
  launch: { headless: 'shell', protocolTimeout: 120_000 },
});
