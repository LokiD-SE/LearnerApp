# Architecture

## Decisions

| Decision    | Choice                                                            | Why                                                                                                          | Revisit if                                                                |
| ----------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------- |
| App shape   | Static single-page app, hash routing                              | The original requirement: everything bundled, works on desktop and mobile, hostable on GitHub Pages for free | Accounts or sync are needed                                               |
| Stack       | Vite + TypeScript (strict) + Preact                               | Small runtime (~4 KB UI library), fast builds, typed content                                                 | The UI outgrows simple components                                         |
| Content     | YAML files, validated with zod at dev/build/test time             | Readable to author (Markdown blocks), separate from UI, every reference checked                              | Authoring needs a CMS                                                     |
| Persistence | `localStorage`, versioned and validated, export/import            | No backend or account; survives reloads and restarts                                                         | Multi-device sync is required                                             |
| Markdown    | marked + DOMPurify + highlight.js (selected languages)            | Small, safe (raw HTML escaped, output sanitised)                                                             | Rich interactive content is needed                                        |
| Diagrams    | Mermaid, lazy-loaded chunk, `securityLevel: 'strict'`             | Diagrams as text in content; only pages that use them pay the cost                                           | Bundle size matters more than live rendering - pre-render to SVG at build |
| Tests       | Vitest (+ jsdom, Testing Library), Playwright on installed Chrome | Unit, integration and journey coverage without downloading browsers                                          | CI needs Playwright's bundled browsers                                    |
| Offline     | Hand-written service worker, generated at build time, no library  | Precaches the exact build (every lazy chunk), small enough to read in one sitting, no new dependencies       | Caching rules grow (runtime caches, background sync) - consider Workbox   |
| Node        | 24 LTS via `.nvmrc` (≥ 22.12 required)                            | Current tool versions need it; the system Node 18 is end-of-life                                             | -                                                                         |

## Layers

```
content/*.yaml ──(Vite plugin: YAML → JS, validate all)──► src/content (schema, validate, index, search)
                                                              │
src/domain (pure: grading, mastery, srs) ◄────────────────────┤
                                                              ▼
src/store (profiles.ts → ProfilesContext: who is signed in, one progress key per profile;
           state.ts pure updates → ProgressContext → localStorage via storage.ts; selectors.ts derived views;
           adaptive.ts remediation and practice sessions; interviews.ts interview generation, scoring, reports)
                                                              │
src/ui (router, Markdown/Mermaid, components, pages) ◄────────┘
```

- **Content never contains UI** and the UI hard-codes no content. A new lesson is a new YAML file.
- **Practice projects** (`practice/`) are separate builds (Maven for Java, npm for Playwright) that the app
  only links to. Coding
  exercises name a project from `practice:` in the curriculum; a content test checks the named files exist,
  and `practice/verify.sh` checks the reference solutions pass and the unsolved exercises fail.
- **The practice shop** (`practice/shop`, static files, no build) is a UI-automation target. A small Vite
  plugin serves it at `/shop/` in `npm run dev` and copies it to `dist/shop/`, so it is published with the
  app; lessons link to it relatively (`shop/index.html`).
- **Interview practice** is content too: company loops, round types and a question bank in
  `content/interviews/`. A generated interview stores only question keys (`bank:<id>`,
  `lesson:<lesson>/<exercise>`), its seed and the learner's attempts, and is resolved against the current
  content when shown - a question removed from the content is left out rather than breaking old interviews.
- **Study times are derived, not stored.** `src/content/time.ts` (pure) shares each lesson's
  `estimatedMinutes` between its parts by their size, so section times always add up to the lesson, and sums
  lessons for chapters, courses, paths and stages. Planned lessons are counted apart with the median published
  lesson as a rough figure. The time left for a learner is a selector (`minutesLeft`).
- **All progress changes are pure functions** in `src/store/state.ts`: `(state, input, now) → state`. The
  Preact context only holds the state and saves it after each change. That makes the rules testable without a
  browser and keeps time injectable (tests and Playwright fix the clock).
- **Offline install** (`src/pwa/`, `public/`). A Vite plugin (`offlineApp` in `vite.config.ts`) writes
  `dist/sw.js` from `src/pwa/service-worker.js`, filling in the list of this build's files (the bundle and
  `public/`, never the practice shop) and a version hashed from their contents. The worker precaches that list
  into a cache named after the version (copying unchanged hashed files from the previous cache), answers the
  app's requests from it - page loads get `index.html`, as the app routes with the URL hash - and leaves
  `shop/` to the network. A new version waits until the learner chooses **Reload** (`src/pwa/register.ts`
  posts `SKIP_WAITING` and reloads on `controllerchange`), so a page never mixes files from two builds; the
  activated version deletes older caches. The worker is registered only in production builds. Playwright
  blocks service workers except in `tests/e2e/offline.spec.ts`, so `page.route` mocking keeps working.
- **Validation happens three times.** The Vite plugin fails `dev`/`build` on invalid content, the content tests
  fail CI, and the app shows a readable error page instead of crashing if content is somehow invalid at runtime.
- **Persistence is defensive.** Unavailable storage, corrupt JSON, unknown versions and quota errors all
  become visible warnings. Corrupt data is kept aside, never silently overwritten.
- **Profiles share a device, not data.** Each profile's progress has its own localStorage key, and the
  ProgressProvider is remounted per profile, so a profile only ever loads and saves its own progress. The
  profile list holds a summary for the profile screen, recomputed from progress whenever it changes.

## Security and privacy

- No network calls at runtime apart from loading the app's own files (and the service worker checking for a
  new `sw.js`). No analytics, no CDN.
- Lesson Markdown cannot inject HTML: raw HTML is escaped and the output passes through DOMPurify. User notes
  and answers are rendered as text only.
- Mermaid runs in strict mode. Diagram source travels as escaped text, never as an attribute (sanitisers strip
  attribute values containing `-->`, which Mermaid arrows use).
- Examples use a fictional provider and sandbox data. The content guide forbids real card data and secrets.

## Accessibility and responsiveness

- Semantic landmarks, a skip link, and focus moved to the page heading on navigation.
- `aria-live` feedback, `aria-pressed` toggles and labelled controls; exercise inputs are native form controls.
- 44 px minimum touch targets; layouts collapse to one column; tables and code scroll inside their own box.
- Pinch-zoom is never disabled. Diagrams fit the width by default and have a full-size toggle.
- `prefers-color-scheme` (light/dark) and `prefers-reduced-motion` are respected.
