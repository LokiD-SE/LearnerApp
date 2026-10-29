// Renders the app icon (the favicon's "L" mark) to the PNG sizes the web app manifest and iOS need.
// Run with `node scripts/make-icons.mjs` after changing the design; the PNGs are committed in public/icons.
import { chromium } from '@playwright/test';

const ACCENT = '#2457d6';
const mark = (size, { padding = 0, radius = 7 } = {}) => {
  // The 32-unit favicon design, scaled; maskable icons keep the mark inside the 80% safe zone.
  const inner = 32 / (1 - 2 * padding);
  const offset = (inner - 32) / 2;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="${-offset} ${-offset} ${inner} ${inner}">
    <rect x="${-offset}" y="${-offset}" width="${inner}" height="${inner}" rx="${radius}" fill="${ACCENT}"/>
    <path d="M9 8v16h14" stroke="white" stroke-width="3.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;
};

const icons = [
  { file: 'icon-192.png', size: 192, svg: mark(192) },
  { file: 'icon-512.png', size: 512, svg: mark(512) },
  { file: 'maskable-512.png', size: 512, svg: mark(512, { padding: 0.1, radius: 0 }) },
  { file: 'apple-touch-icon.png', size: 180, svg: mark(180, { radius: 0 }) },
];

const browser = await chromium.launch({ channel: process.env.PW_CHANNEL ?? 'chrome' });
const page = await browser.newPage();
for (const { file, size, svg } of icons) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(`<style>html,body{margin:0;background:transparent}</style>${svg}`);
  await page.locator('svg').screenshot({ path: `public/icons/${file}`, omitBackground: true });
  console.log(`public/icons/${file}`);
}
await browser.close();
