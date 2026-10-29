/**
 * Build-time helpers for the service worker (src/pwa/service-worker.js): which built files it precaches,
 * and the generated worker source. Used by vite.config.ts and the unit tests.
 */

/** The worker itself, source maps and the practice shop are never precached. */
export function precachePaths(files: string[]): string[] {
  return files
    .filter((file) => file !== 'sw.js' && !file.endsWith('.map') && !file.startsWith('shop/'))
    .sort();
}

/** Fills the worker template's VERSION and PRECACHE placeholders. */
export function serviceWorkerSource(template: string, paths: string[], version: string): string {
  if (!template.includes("'__VERSION__'") || !template.includes('__PRECACHE__')) {
    throw new Error('service worker template: VERSION or PRECACHE placeholder missing');
  }
  return template
    .replace("'__VERSION__'", JSON.stringify(version))
    .replace('__PRECACHE__', JSON.stringify(paths));
}
