/**
 * capture-table.js
 *
 * Boots a local HTTP server serving the already-built dist/, waits for the
 * discount grid to render, then screenshots it padded to a 1.91:1 (OG standard)
 * aspect ratio and writes the PNG to public/discount-table.png so the next
 * `astro build` will deploy it as a static asset.
 *
 * Prerequisites:
 *   1. Run `npm run build` first.
 *   2. Run `npm run capture` (or `node capture-table.js` from src/frontend/).
 */

import puppeteer from 'puppeteer';
import http from 'http';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// This script lives in src/frontend/, so __dirname IS the frontend dir.
const FRONTEND_DIR = __dirname;
const OUT_PATH = path.join(FRONTEND_DIR, 'public', 'discount-table.png');

const PREVIEW_PORT = 4321;
const PREVIEW_URL = `http://localhost:${PREVIEW_PORT}/WRFrontiers-Discount-Visualizer/`;
const GRID_SELECTOR = '#discount-grid';

/** Start local HTTP server to serve dist/ and resolve when listening. */
function startPreviewServer(distDir) {
  const server = http.createServer((req, res) => {
    let reqUrl = req.url || '/';
    // Strip query strings and hashes
    const urlPath = reqUrl.split('?')[0].split('#')[0];

    const base = '/WRFrontiers-Discount-Visualizer/';
    let relativePath = urlPath;

    if (urlPath.startsWith(base)) {
      relativePath = urlPath.substring(base.length);
    } else if (urlPath === '/' || urlPath === '') {
      res.writeHead(302, { Location: base });
      res.end();
      return;
    }

    // Resolve file path in dist/
    const safePath = path.normalize(relativePath).replace(/^(\.\.[\\/])+/, '');
    let filePath = path.join(distDir, safePath);

    // If filePath is a directory, look for index.html
    if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
      filePath = path.join(filePath, 'index.html');
    }

    if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('404 Not Found');
      return;
    }

    // Determine content type
    const ext = path.extname(filePath).toLowerCase();
    const mimeTypes = {
      '.html': 'text/html',
      '.css': 'text/css',
      '.js': 'application/javascript',
      '.json': 'application/json',
      '.png': 'image/png',
      '.jpg': 'image/jpeg',
      '.gif': 'image/gif',
      '.svg': 'image/svg+xml',
      '.ico': 'image/x-icon',
      '.webp': 'image/webp',
      '.woff': 'font/woff',
      '.woff2': 'font/woff2',
      '.ttf': 'font/ttf',
    };
    const contentType = mimeTypes[ext] || 'application/octet-stream';

    res.writeHead(200, { 'Content-Type': contentType });
    fs.createReadStream(filePath).pipe(res);
  });

  return new Promise((resolve, reject) => {
    server.on('error', (err) => {
      reject(err);
    });
    server.listen(PREVIEW_PORT, '127.0.0.1', () => {
      resolve(server);
    });
  });
}

async function main() {
  // Verify dist/ exists
  const distDir = path.join(FRONTEND_DIR, 'dist');
  if (!fs.existsSync(distDir)) {
    console.error(`dist/ not found at ${distDir}`);
    console.error('Run "npm run build" first.');
    process.exit(1);
  }

  console.log('Starting preview server...');
  const server = await startPreviewServer(distDir);
  console.log(`Preview server ready at ${PREVIEW_URL}`);

  let browser;
  try {
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    const page = await browser.newPage();

    // Use a large CSS viewport at deviceScaleFactor:1.
    // This means the PNG file dimensions will exactly equal the CSS pixel dimensions —
    // no DPR mismatch — so Discord mobile's lightbox displays the image at the correct scale.
    // We compensate for the lower DPR by rendering the grid at 2× its normal CSS size
    // (by overriding --grid-scale-unit to 2px below), giving a high-res output.
    await page.setViewport({ width: 2800, height: 1800, deviceScaleFactor: 1 });

    console.log('Navigating to page...');
    await page.goto(PREVIEW_URL, { waitUntil: 'networkidle0', timeout: 30_000 });

    console.log(`Waiting for ${GRID_SELECTOR}...`);
    await page.waitForSelector(GRID_SELECTOR, { visible: true, timeout: 15_000 });

    // Force grid scale to 1 to bypass container query circular dependencies in headless Chrome.
    // Also hide the Astro dev toolbar, sidebar, and navbar — they must not appear in the OG image.
    await page.addStyleTag({
      content: `
        ${GRID_SELECTOR} { --grid-scale-unit: 1.2px !important; }
        astro-dev-toolbar { display: none !important; }
        #sidebar, .sidebar-toggle, nav, .navbar { display: none !important; }
      `,
    });

    // Extra settle time for icon images, fonts, etc.
    await new Promise((r) => setTimeout(r, 1000));

    const element = await page.$(GRID_SELECTOR);
    if (!element) throw new Error(`Element "${GRID_SELECTOR}" not found after waiting`);

    // -------------------------------------------------------------------------
    // Option 1: Letterbox to 1.91:1 (standard OG / Discord-mobile-safe ratio)
    // -------------------------------------------------------------------------
    // Strategy: leave the grid exactly where it is in the DOM. Just expand the
    // screenshot clip rect outward from the grid's natural bounding box until
    // the result satisfies the 1.91:1 ratio. The page background fills the bars.

    const gridBox = await element.boundingBox();
    if (!gridBox) throw new Error('Could not get bounding box for grid element');

    const TARGET_RATIO = 1200 / 630; // ≈ 1.905 — the OG standard
    const gridW = Math.ceil(gridBox.width);
    const gridH = Math.ceil(gridBox.height);

    // Compute a canvas that contains the grid and matches TARGET_RATIO.
    let canvasW, canvasH;
    if (gridW / gridH >= TARGET_RATIO) {
      canvasW = gridW;
      canvasH = Math.ceil(gridW / TARGET_RATIO);
    } else {
      canvasH = gridH;
      canvasW = Math.ceil(gridH * TARGET_RATIO);
    }

    // Centre the clip rect symmetrically around the grid.
    // The sidebar is hidden above, so the dark background fills the left bar cleanly.
    const padX = Math.floor((canvasW - gridW) / 2);
    const padY = Math.floor((canvasH - gridH) / 2);
    const clipX = Math.max(0, Math.floor(gridBox.x) - padX);
    const clipY = Math.max(0, Math.floor(gridBox.y) - padY);

    console.log(`Grid: ${gridW}×${gridH} at (${Math.floor(gridBox.x)}, ${Math.floor(gridBox.y)})  →  Canvas: ${canvasW}×${canvasH}  clip: (${clipX}, ${clipY})`);

    // The initial 2800×1800 viewport is already large enough for any clip region.
    // Just allow a brief settle after style injection.
    await new Promise((r) => setTimeout(r, 200));

    console.log('Taking screenshot...');
    await page.screenshot({
      path: OUT_PATH,
      clip: { x: clipX, y: clipY, width: canvasW, height: canvasH },
    });

    console.log(
      `Screenshot saved -> ${OUT_PATH}  (${canvasW}×${canvasH}, ratio ${(canvasW / canvasH).toFixed(3)})`
    );
  } finally {
    if (browser) await browser.close();
    server.close();
    console.log('Preview server stopped');
  }
}

main().catch((err) => {
  console.error('capture-table.js failed:', err.message);
  process.exit(1);
});
