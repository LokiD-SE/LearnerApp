// Serves the SandPay Demo Shop (practice/shop) on 127.0.0.1 for the tests - no dependencies.
// Usage: node scripts/serve-shop.mjs [port]   (SHOP_DIR overrides the folder)
import { createReadStream, existsSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, extname, join, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(process.env.SHOP_DIR ?? join(here, '..', '..', 'shop'));
const port = Number(process.argv[2] ?? process.env.SHOP_PORT ?? 4310);
const types = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
};

createServer((request, response) => {
  const path = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
  // a deliberately wrong "API" response, for the API exercise's validation test
  if (path === '/broken/products.json') {
    response.writeHead(200, { 'Content-Type': types['.json'] }).end('[{"sku": 1, "name": null}]');
    return;
  }
  const file = normalize(join(root, path === '/' ? 'index.html' : path));
  if (
    request.method !== 'GET' ||
    !file.startsWith(root + sep) ||
    !existsSync(file) ||
    statSync(file).isDirectory()
  ) {
    response.writeHead(404).end('not found');
    return;
  }
  response.writeHead(200, {
    'Content-Type': types[extname(file)] ?? 'application/octet-stream',
    'Cache-Control': 'no-store',
  });
  createReadStream(file).pipe(response);
}).listen(port, '127.0.0.1', () => console.log(`SandPay shop on http://127.0.0.1:${port}/ (from ${root})`));
