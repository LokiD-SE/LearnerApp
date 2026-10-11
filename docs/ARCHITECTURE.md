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
| Node        | 24 LTS via `.nvmrc` (≥ 22.12 required)                            | Current tool versions need it; the system Node 18 is end-of-life                                             | -                                                                         |

## Layers

```
content/*.yaml ──(Vite plugin: YAML → JS, validate all)──► src/content (schema, validate, index, search)
                                                              │
src/domain (pure: grading, mastery, srs) ◄────────────────────┤
                                                              ▼
src/store (state.ts pure updates → ProgressContext → localStorage via storage.ts; selectors.ts derived views)
                                                              │
src/ui (router, Markdown/Mermaid, components, pages) ◄────────┘
```

- **Content never contains UI** and the UI hard-codes no content. A new lesson is a new YAML file.
- **All progress changes are pure functions** in `src/store/state.ts`: `(state, input, now) → state`. The
  Preact context only holds the state and saves it after each change. That makes the rules testable without a
  browser and keeps time injectable (tests and Playwright fix the clock).
- **Validation happens three times.** The Vite plugin fails `dev`/`build` on invalid content, the content tests
  fail CI, and the app shows a readable error page instead of crashing if content is somehow invalid at runtime.
- **Persistence is defensive.** Unavailable storage, corrupt JSON, unknown versions and quota errors all
  become visible warnings. Corrupt data is kept aside, never silently overwritten.

## Security and privacy

- No network calls at runtime apart from loading the app's own files. No analytics, no CDN.
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
