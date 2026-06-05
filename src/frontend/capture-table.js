/**
 * capture-table.js
 *
 * Boots `astro preview` (serving the already-built dist/), waits for the
 * discount grid to render, screenshots just that element, and writes the PNG
 * to public/discount-table.png so the next `astro build` will deploy it as
 * a static asset.
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
    const safePath = path.normalize(relativePath).replace(/^(\.\.[\/\\])+/, '');
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

    // Wide viewport so the grid renders at full 1× scale (intrinsic width ~938px)
    await page.setViewport({ width: 1400, height: 900, deviceScaleFactor: 2 });

    console.log('Navigating to page...');
    await page.goto(PREVIEW_URL, { waitUntil: 'networkidle0', timeout: 30_000 });

    console.log(`Waiting for ${GRID_SELECTOR}...`);
    await page.waitForSelector(GRID_SELECTOR, { visible: true, timeout: 15_000 });

    // Force grid scale to 1 to bypass container query circular dependencies in headless Chrome
    await page.addStyleTag({ content: `${GRID_SELECTOR} { --grid-scale: 1 !important; }` });

    // Extra settle time for icon images, fonts, etc.
    await new Promise((r) => setTimeout(r, 1000));

    const element = await page.$(GRID_SELECTOR);
    if (!element) throw new Error(`Element "${GRID_SELECTOR}" not found after waiting`);

    console.log('Taking screenshot...');
    await element.screenshot({ path: OUT_PATH });

    console.log(`Screenshot saved -> ${OUT_PATH}`);
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
