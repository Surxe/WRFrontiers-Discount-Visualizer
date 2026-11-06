/**
 * set-og-size.js
 *
 * Writes a captured og:image's real pixel size into the built pages that use it.
 *
 * The pages are built before their og:images are captured, so they can only
 * guess og:image:width/height. The discount table's height changes with the
 * number of rows each week, and Discord sizes the embed from the declared
 * aspect ratio and crops the image to fill it, so a wrong guess cuts off the
 * edges. Run this after capturing: for every dist/**\/*.html whose og:image
 * names the given PNG, it sets og:image:width/height to the PNG's actual size.
 *
 * Usage (from src/frontend/):
 *   node set-og-size.js dist/discount-table-<sha>.png [more.png ...]
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const FRONTEND_DIR = path.dirname(fileURLToPath(import.meta.url));
const DIST_DIR = path.join(FRONTEND_DIR, 'dist');
const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

/** Width and height from a PNG's IHDR chunk (always the first chunk). */
export function pngSize(file) {
  const fd = fs.openSync(file, 'r');
  const head = Buffer.alloc(24);
  try {
    fs.readSync(fd, head, 0, 24, 0);
  } finally {
    fs.closeSync(fd);
  }
  if (!head.subarray(0, 8).equals(PNG_SIGNATURE) || head.toString('ascii', 12, 16) !== 'IHDR') {
    throw new Error(`${file} is not a PNG`);
  }
  return { width: head.readUInt32BE(16), height: head.readUInt32BE(20) };
}

function htmlFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return htmlFiles(full);
    return entry.name.endsWith('.html') ? [full] : [];
  });
}

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * Set og:image:width/height in `html` if its og:image names `imageName`.
 * Returns the updated html, or null when the page doesn't use that image.
 */
export function setOgSize(html, imageName, { width, height }) {
  const usesImage = new RegExp(
    `<meta[^>]+property="og:image"[^>]+content="[^"]*/${escapeRe(imageName)}"`
  );
  if (!usesImage.test(html)) return null;
  let out = html;
  for (const [prop, value] of [['og:image:width', width], ['og:image:height', height]]) {
    const tag = new RegExp(`(<meta[^>]+property="${prop}"[^>]+content=")\\d+(")`);
    if (!tag.test(out)) throw new Error(`no ${prop} tag next to og:image ${imageName}`);
    out = out.replace(tag, `$1${value}$2`);
  }
  return out;
}

function main(pngPaths) {
  if (pngPaths.length === 0) {
    console.error('Usage: node set-og-size.js <dist/image.png> [...]');
    process.exit(1);
  }
  const pages = htmlFiles(DIST_DIR);
  for (const pngPath of pngPaths) {
    const size = pngSize(pngPath);
    const imageName = path.basename(pngPath);
    let updated = 0;
    for (const page of pages) {
      const html = fs.readFileSync(page, 'utf8');
      const out = setOgSize(html, imageName, size);
      if (out === null) continue;
      if (out !== html) fs.writeFileSync(page, out);
      updated += 1;
    }
    if (updated === 0) throw new Error(`no built page uses og:image ${imageName}`);
    console.log(`[set-og-size.js] ${imageName}: ${size.width}x${size.height} on ${updated} page(s)`);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2));
}
