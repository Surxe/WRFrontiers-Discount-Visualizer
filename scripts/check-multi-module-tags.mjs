#!/usr/bin/env node
/**
 * Quick check: torso/shoulder/chassis modules with more than one module_tags_refs.
 *
 * Usage (from repo root):
 *   node scripts/check-multi-module-tags.mjs
 *
 * Optional: DATA_DIR=/path/to/WRFrontiersDB-Data/current/Objects
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..');

function parseRef(ref) {
  if (!ref) return null;
  const parts = String(ref).split('::');
  return parts.length > 1 ? parts[1] : parts[0];
}

function resolveObjectsDir() {
  if (process.env.DATA_DIR) return process.env.DATA_DIR;

  const candidates = [
    path.join(repoRoot, 'WRFrontiersDB-Data', 'current', 'Objects'),
    path.join(repoRoot, '..', 'WRFrontiersDB-Data', 'current', 'Objects'),
    path.join(repoRoot, 'src', 'frontend', 'public', 'WRFrontiersDB-Data', 'current', 'Objects'),
  ];

  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, 'Module.json'))) return dir;
  }

  console.error('Module.json not found. Clone WRFrontiersDB-Data or set DATA_DIR.');
  process.exit(1);
}

function readJson(name, dir) {
  return JSON.parse(fs.readFileSync(path.join(dir, name), 'utf-8'));
}

function isBotPartCategory(categoryRef) {
  if (!categoryRef) return false;
  const c = categoryRef.toLowerCase();
  return c.includes('torso') || c.includes('shoulder') || c.includes('chassis');
}

const objectsDir = resolveObjectsDir();
const ModuleDB = readJson('Module.json', objectsDir);
const ModuleTypeDB = readJson('ModuleType.json', objectsDir);

const hits = [];

for (const [moduleId, module] of Object.entries(ModuleDB)) {
  const typeRef = parseRef(module.module_type_ref);
  const moduleType = typeRef ? ModuleTypeDB[typeRef] : null;
  const categoryRef = moduleType ? parseRef(moduleType.module_category_ref) : null;

  if (!isBotPartCategory(categoryRef)) continue;

  const tags = module.module_tags_refs;
  const tagCount = Array.isArray(tags) ? tags.length : 0;

  if (tagCount > 1) {
    hits.push({
      id: moduleId,
      category: categoryRef,
      tagCount,
      module_tags_refs: tags,
    });
  }
}

console.log(`Objects dir: ${objectsDir}`);
console.log(`Bot-part modules with >1 module_tags_refs: ${hits.length}\n`);

if (hits.length === 0) {
  console.log('None found.');
} else {
  for (const row of hits.sort((a, b) => a.id.localeCompare(b.id))) {
    console.log(`${row.id}  [${row.category}]  (${row.tagCount} tags)`);
    for (const tag of row.module_tags_refs) {
      console.log(`    - ${tag}`);
    }
  }
}
