import puppeteer from 'puppeteer';
import { preview } from 'astro';

const server = await preview({ root: process.cwd(), server: { port: 4331 } });
const base = 'http://localhost:4331/costs';
const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
const page = await browser.newPage();
await page.setViewport({ width: 1300, height: 1400, deviceScaleFactor: 1 });

await page.goto(base, { waitUntil: 'networkidle0' });
await new Promise(r => setTimeout(r, 400));
await page.screenshot({ path: '/tmp/claude-1001/-srv-dev/15940edc-f2ac-4c06-9318-4d51a27b2eee/scratchpad/costs-visual.png' });

// Switch to table view
await page.click('#btn-table');
await new Promise(r => setTimeout(r, 300));
await page.screenshot({ path: '/tmp/claude-1001/-srv-dev/15940edc-f2ac-4c06-9318-4d51a27b2eee/scratchpad/costs-table.png' });

// Mobile
await page.setViewport({ width: 390, height: 1600, deviceScaleFactor: 1 });
await page.click('#btn-visual');
await new Promise(r => setTimeout(r, 300));
await page.screenshot({ path: '/tmp/claude-1001/-srv-dev/15940edc-f2ac-4c06-9318-4d51a27b2eee/scratchpad/costs-mobile.png' });

await browser.close();
await server.stop();
console.log('done');
