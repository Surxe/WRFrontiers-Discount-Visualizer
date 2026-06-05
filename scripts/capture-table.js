/**
 * capture-table.js
 *
 * Boots `astro preview` (serving the already-built dist/), waits for the
 * discount grid to render, screenshots just that element, and writes the PNG
 * to src/frontend/public/discount-table.png so the next `astro build` will
 * deploy it as a static asset.
 *
 * Prerequisites:
 *   1. Run `npm run build` inside src/frontend/ first.
 *   2. Run this script from the repo root: `node scripts/capture-table.js`
 *      or via npm: `cd src/frontend && npm run capture`
 */

import puppeteer from 'puppeteer';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..');
const FRONTEND_DIR = path.join(REPO_ROOT, 'src', 'frontend');
const OUT_PATH = path.join(FRONTEND_DIR, 'public', 'discount-table.png');

const PREVIEW_PORT = 4321;
const PREVIEW_URL = `http://localhost:${PREVIEW_PORT}/WRFrontiers-Discount-Visualizer/`;
const GRID_SELECTOR = '#discount-grid';

/** Start `astro preview` and resolve when the server is listening. */
function startPreviewServer() {
  return new Promise((resolve, reject) => {
    const server = spawn('node_modules/.bin/astro', ['preview', '--port', String(PREVIEW_PORT)], {
      cwd: FRONTEND_DIR,
      shell: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    const timeout = setTimeout(() => {
      server.kill();
      reject(new Error('Timed out waiting for astro preview to start'));
    }, 30_000);

    const onData = (chunk) => {
      const text = chunk.toString();
      // astro preview prints the URL once it's listening
      if (text.includes('localhost') || text.includes('Local')) {
        clearTimeout(timeout);
        resolve(server);
      }
    };

    server.stdout.on('data', onData);
    server.stderr.on('data', onData);
    server.on('error', (err) => { clearTimeout(timeout); reject(err); });
  });
}

async function main() {
  // Verify dist/ exists
  const distDir = path.join(FRONTEND_DIR, 'dist');
  if (!fs.existsSync(distDir)) {
    console.error(`❌ dist/ not found at ${distDir}`);
    console.error('   Run "npm run build" inside src/frontend/ first.');
    process.exit(1);
  }

  console.log('▶  Starting astro preview server…');
  const server = await startPreviewServer();
  console.log(`✅ Preview server ready at ${PREVIEW_URL}`);

  let browser;
  try {
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    const page = await browser.newPage();

    // Wide viewport so the grid renders at full 1× scale (intrinsic width ~938px)
    await page.setViewport({ width: 1400, height: 900, deviceScaleFactor: 2 });

    console.log('▶  Navigating to page…');
    await page.goto(PREVIEW_URL, { waitUntil: 'networkidle0', timeout: 30_000 });

    console.log(`▶  Waiting for ${GRID_SELECTOR}…`);
    await page.waitForSelector(GRID_SELECTOR, { visible: true, timeout: 15_000 });

    // Extra settle time for icon images, fonts, etc.
    await new Promise((r) => setTimeout(r, 1000));

    const element = await page.$(GRID_SELECTOR);
    if (!element) throw new Error(`Element "${GRID_SELECTOR}" not found after waiting`);

    console.log('▶  Taking screenshot…');
    await element.screenshot({ path: OUT_PATH });

    console.log(`✅ Screenshot saved → ${OUT_PATH}`);
  } finally {
    if (browser) await browser.close();
    server.kill();
    console.log('✅ Preview server stopped');
  }
}

main().catch((err) => {
  console.error('❌ capture-table.js failed:', err.message);
  process.exit(1);
});
