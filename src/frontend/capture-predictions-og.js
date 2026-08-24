/**
 * capture-predictions-og.js
 *
 * Boots a static server over the already-built dist/, loads the dedicated
 * /predictions-og card, screenshots the #og-card element (an exact 1200x630
 * box), and writes the PNG to public/predictions-og.png so the next
 * `astro build` deploys it as a static asset (used as the /predictions
 * og:image).
 *
 * Prerequisites:
 *   1. Run `npm run build` first.
 *   2. Run `npm run capture:og` (or `node capture-predictions-og.js`).
 */

import puppeteer from 'puppeteer';
import http from 'http';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const FRONTEND_DIR = __dirname;
const OUT_PATH = path.join(FRONTEND_DIR, 'public', 'predictions-og.png');

const PREVIEW_PORT = 4321;
const BASE = '/WRFrontiers-Discount-Visualizer/';
const PREVIEW_URL = `http://localhost:${PREVIEW_PORT}${BASE}predictions-og`;
const CARD_SELECTOR = '#og-card';

/** Start local HTTP server to serve dist/ and resolve when listening. */
function startPreviewServer(distDir) {
  const mimeTypes = {
    '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
    '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
    '.gif': 'image/gif', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
    '.webp': 'image/webp', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf',
  };
  const server = http.createServer((req, res) => {
    const urlPath = (req.url || '/').split('?')[0].split('#')[0];
    let relativePath = urlPath;
    if (urlPath.startsWith(BASE)) {
      relativePath = urlPath.substring(BASE.length);
    } else if (urlPath === '/' || urlPath === '') {
      res.writeHead(302, { Location: BASE });
      res.end();
      return;
    }
    const safePath = path.normalize(relativePath).replace(/^(\.\.[\/\\])+/, '');
    let filePath = path.join(distDir, safePath);
    if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
      filePath = path.join(filePath, 'index.html');
    }
    if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('404 Not Found');
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream' });
    fs.createReadStream(filePath).pipe(res);
  });

  return new Promise((resolve, reject) => {
    server.on('error', reject);
    server.listen(PREVIEW_PORT, '127.0.0.1', () => resolve(server));
  });
}

async function main() {
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
    // headless:'shell' + --disable-gpu avoids a compositor stall that hangs
    // Page.captureScreenshot under plain headless on some Linux hosts.
    browser = await puppeteer.launch({
      headless: 'shell',
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
      protocolTimeout: 120_000,
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1240, height: 700, deviceScaleFactor: 2 });

    console.log('Navigating to page...');
    await page.goto(PREVIEW_URL, { waitUntil: 'networkidle0', timeout: 30_000 });

    console.log(`Waiting for ${CARD_SELECTOR}...`);
    await page.waitForSelector(CARD_SELECTOR, { visible: true, timeout: 15_000 });

    // Freeze animations/transitions and hide the Astro dev toolbar if injected.
    await page.addStyleTag({ content: `*{animation:none!important;transition:none!important;} astro-dev-toolbar{display:none!important;}` });

    // Extra settle time for icon images and fonts.
    await new Promise((r) => setTimeout(r, 1000));

    const element = await page.$(CARD_SELECTOR);
    if (!element) throw new Error(`Element "${CARD_SELECTOR}" not found after waiting`);

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
  console.error('capture-predictions-og.js failed:', err.message);
  process.exit(1);
});
