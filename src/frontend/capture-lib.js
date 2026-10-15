/**
 * capture-lib.js
 *
 * Shared by the capture-*.js scripts: serves the already-built dist/ over a
 * local static server, loads one page in headless Chrome, and screenshots a
 * single element to a PNG.
 *
 * The output path defaults to public/<name>.png (the copy committed to the
 * repo and embedded in the README). Pass `--out <path>` to write elsewhere;
 * the CI build uses this to drop the image straight into dist/ so the
 * deployed og:image is always rendered from the data being deployed.
 */

import puppeteer from 'puppeteer';
import http from 'http';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

export const FRONTEND_DIR = path.dirname(fileURLToPath(import.meta.url));
const DIST_DIR = path.join(FRONTEND_DIR, 'dist');

const PREVIEW_PORT = 4321;
const BASE = '/WRFrontiers-Discount-Visualizer/';

const MIME_TYPES = {
  '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
  '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.gif': 'image/gif', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
  '.webp': 'image/webp', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf',
};

/** Start local HTTP server to serve dist/ and resolve when listening. */
function startPreviewServer(distDir) {
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
    res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] || 'application/octet-stream' });
    fs.createReadStream(filePath).pipe(res);
  });

  return new Promise((resolve, reject) => {
    server.on('error', reject);
    server.listen(PREVIEW_PORT, '127.0.0.1', () => resolve(server));
  });
}

/** `--out <path>` from argv, resolved against the cwd; else the default. */
function resolveOutPath(defaultPath) {
  const i = process.argv.indexOf('--out');
  if (i === -1) return defaultPath;
  const value = process.argv[i + 1];
  if (!value) throw new Error('--out needs a path');
  return path.resolve(value);
}

/**
 * Screenshot `selector` on `pagePath` (relative to the site base) to a PNG.
 *
 * @param {object} opts
 * @param {string} opts.name        Script name, for log/error prefixes.
 * @param {string} opts.pagePath    Page under the site base, e.g. 'predictions-og'.
 * @param {string} opts.selector    Element to screenshot.
 * @param {string} opts.defaultOut  Output path when no --out is given.
 * @param {object} opts.viewport    Puppeteer viewport.
 * @param {string} [opts.style]     Extra CSS injected before capture.
 * @param {object} [opts.launch]    Extra puppeteer.launch options.
 */
export async function captureElement({ name, pagePath, selector, defaultOut, viewport, style = '', launch = {} }) {
  const outPath = resolveOutPath(defaultOut);
  const url = `http://localhost:${PREVIEW_PORT}${BASE}${pagePath}`;

  if (!fs.existsSync(DIST_DIR)) {
    throw new Error(`dist/ not found at ${DIST_DIR}. Run "npm run build" first.`);
  }

  console.log(`[${name}] Starting preview server...`);
  const server = await startPreviewServer(DIST_DIR);

  let browser;
  try {
    browser = await puppeteer.launch({
      headless: true,
      // --disable-gpu forces CPU rasterization. Without it, newer headless Chrome
      // can stall painting at deviceScaleFactor 2 via SwiftShader, which hangs
      // the screenshot (and every CDP call that needs the main thread).
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
      ...launch,
    });

    const page = await browser.newPage();
    await page.setViewport(viewport);

    console.log(`[${name}] Navigating to ${url}...`);
    await page.goto(url, { waitUntil: 'networkidle0', timeout: 30_000 });
    await page.waitForSelector(selector, { visible: true, timeout: 15_000 });

    // Freeze animations, hide the Astro dev toolbar, plus any per-page tweaks.
    await page.addStyleTag({
      content: `*{animation:none!important;transition:none!important;} astro-dev-toolbar{display:none!important;} ${style}`,
    });

    // Extra settle time for icon images and fonts.
    await new Promise((r) => setTimeout(r, 1000));

    const element = await page.$(selector);
    if (!element) throw new Error(`Element "${selector}" not found after waiting`);

    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    await element.screenshot({ path: outPath });
    console.log(`[${name}] Screenshot saved -> ${outPath}`);
  } finally {
    if (browser) await browser.close();
    server.close();
  }
}

/** Run a capture as a script's entry point, exiting non-zero on failure. */
export function runCapture(opts) {
  captureElement(opts).catch((err) => {
    console.error(`${opts.name} failed:`, err.message);
    process.exit(1);
  });
}
