/// <reference types="vitest/config" />
import { cpSync, existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { extname, join, normalize, relative, sep } from 'node:path';
import { defineConfig, type Plugin } from 'vite';
import preact from '@preact/preset-vite';
import { parse } from 'yaml';
import { validateContent } from './src/content/validate.ts';

const CONTENT_DIR = join(import.meta.dirname, 'content');
const SHOP_DIR = join(import.meta.dirname, 'practice', 'shop');

const yamlFiles = (dir: string): string[] =>
  readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory()
      ? yamlFiles(join(dir, entry.name))
      : entry.name.endsWith('.yaml')
        ? [join(dir, entry.name)]
        : [],
  );

/** Loads content/*.yaml as JS modules and refuses to start or build on invalid content. */
function learnerContent(): Plugin {
  const checkAll = () => {
    const read = (file: string): unknown => {
      try {
        return parse(readFileSync(file, 'utf8'));
      } catch (error) {
        throw new Error(`${relative(import.meta.dirname, file)}: ${(error as Error).message}`, {
          cause: error,
        });
      }
    };
    const lessons = Object.fromEntries(
      yamlFiles(join(CONTENT_DIR, 'lessons')).map((file) => [
        relative(import.meta.dirname, file),
        read(file),
      ]),
    );
    const interviewQuestions = Object.fromEntries(
      yamlFiles(join(CONTENT_DIR, 'interviews', 'questions')).map((file) => [
        relative(import.meta.dirname, file),
        read(file),
      ]),
    );
    const result = validateContent(read(join(CONTENT_DIR, 'curriculum.yaml')), lessons, {
      config: read(join(CONTENT_DIR, 'interviews', 'interviews.yaml')),
      questions: interviewQuestions,
    });
    if (!result.ok) throw new Error(`Invalid content:\n  ${result.errors.join('\n  ')}`);
  };
  return {
    name: 'learner-content',
    buildStart() {
      checkAll();
    },
    handleHotUpdate({ file }) {
      if (file.startsWith(CONTENT_DIR)) checkAll();
    },
    transform(code, id) {
      if (!id.endsWith('.yaml')) return null;
      try {
        return { code: `export default ${JSON.stringify(parse(code))};`, map: null };
      } catch (error) {
        throw new Error(`${relative(import.meta.dirname, id)}: ${(error as Error).message}`, {
          cause: error,
        });
      }
    },
  };
}

const SHOP_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
};

/**
 * The practice shop (practice/shop, a UI-automation target) is published with the app at ./shop/.
 * `npm run dev` serves it from the source folder; the build copies it into dist/shop.
 */
function practiceShop(): Plugin {
  return {
    name: 'practice-shop',
    configureServer(server) {
      server.middlewares.use('/shop', (req, res, next) => {
        const path = decodeURIComponent((req.url ?? '/').split('?')[0]!);
        if (req.originalUrl === '/shop') {
          res.writeHead(301, { Location: '/shop/' }).end();
          return;
        }
        const file = normalize(join(SHOP_DIR, path === '/' ? 'index.html' : path));
        if (!file.startsWith(SHOP_DIR + sep) || !existsSync(file) || statSync(file).isDirectory()) {
          next();
          return;
        }
        res.setHeader('Content-Type', SHOP_TYPES[extname(file)] ?? 'application/octet-stream');
        res.end(readFileSync(file));
      });
    },
    writeBundle(options) {
      cpSync(SHOP_DIR, join(options.dir ?? join(import.meta.dirname, 'dist'), 'shop'), { recursive: true });
    },
  };
}

export default defineConfig({
  // Relative asset paths + hash routing: the build works from any folder or sub-path
  // (GitHub Pages project site, a static server, or `npm run preview`).
  base: './',
  plugins: [preact(), learnerContent(), practiceShop()],
  build: {
    target: 'es2022',
    chunkSizeWarningLimit: 1500,
  },
  test: {
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
});
