import fs from 'fs';
import path from 'path';

export function fetchWeeksManifest() {
  const manifestPath = path.resolve('public/data/weeks.json');
  try {
    const content = fs.readFileSync(manifestPath, 'utf-8');
    const manifest = JSON.parse(content);
    return manifest.weeks || [];
  } catch (e) {
    console.error(`Error reading weeks.json:`, e);
    return [];
  }
}
