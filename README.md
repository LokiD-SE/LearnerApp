# LearnerApp

A self-contained, hands-on technical training app. It teaches payments testing, API testing, mobile testing,
Java, Selenium/Appium and automation-framework design. The goal is that you can explain, implement, test, debug
and defend a solution in a real project or an interview, not just recognise the right answer.

Every lesson follows one template: plain-language idea, mechanics, diagrams, worked example, code, tests,
mistakes, trade-offs and summary. Practice is built around active recall, progressive hints, worked solutions,
spaced repetition and a mastery model that weighs practical work over multiple choice.

- **Static and offline-friendly.** All content is bundled into the build; there is no server, account or paid
  API. Progress is stored in your browser.
- **Skip what you already know.** A placement test per learning path (and "Test out" on each lesson) marks
  lessons you can already show you know as _tested out_; their recall cards still come back for review.
- **Practice that adapts.** A wrong answer points back to the sections that teach the concept and a similar
  exercise. The Practice page builds interleaved sessions from what you have studied, weakest concepts first,
  and says why each item was chosen.
- **Code you run yourself.** Coding exercises name a file in a practice project in this repository
  (`practice/`), the test class that checks it and the command to run. The tests are the judge; reference
  solutions are next to the exercises.
- **Desktop and mobile.** Responsive layout, touch-sized controls and pinch-zoom allowed everywhere. Diagrams
  have a full-size toggle.

## Status

The foundation and the **Payments QA core path** are complete, and the **Java automation engineer** path
has started. The full curriculum map is navigable (7 stages, foundations plus tracks A-G, 63 lessons). The
eight lessons of the core path are fully written:

1. Anatomy of an HTTP request and response
2. HTTP methods - safety and idempotency
3. Payment lifecycle - authorise, capture, settle, refund
4. Test cards, sandboxes and mock services
5. Idempotency keys and duplicate payment requests
6. Declines, timeouts and unknown outcomes
7. Webhooks, signatures and asynchronous status
8. Building a payment scenario matrix

Six lessons of the automation path are written, each with coding exercises you run locally:

1. Primitive and reference types (Java)
2. equals, hashCode and why HashMap needs both (Java)
3. Locator strategy - CSS, XPath and stable attributes (Selenium)
4. Explicit waits and synchronisation (Selenium)
5. Page objects done right
6. A small reference framework, and why it is small

They use two practice projects - `practice/java` and `practice/framework`, a small Selenium + JUnit
framework - and the **SandPay Demo Shop** (`practice/shop`), a fictional shop built to be awkward to
automate, published with the app at `shop/`. See [practice/README.md](practice/README.md).

The other 49 lessons are listed as _planned_. See [docs/PLAN.md](docs/PLAN.md) for the roadmap and what is
deferred.

## Requirements

- **Node.js 22.12 or later** (developed on Node 24 LTS). The repository has an `.nvmrc`; with
  [nvm](https://github.com/nvm-sh/nvm) run `nvm install` once, then `nvm use` in each new shell.
- npm 10+ (bundled with Node).
- For the end-to-end tests: Google Chrome, or Playwright's own Chromium (see below).
- For the practice projects only: a **JDK 17+** and **Maven 3.8+** - see [practice/README.md](practice/README.md).

## Quick start

```bash
nvm use            # Node 24 from .nvmrc
npm ci             # install exact versions from package-lock.json
npm run dev        # http://localhost:5173 - edits to code and content reload live
```

Production build and a local preview of it:

```bash
npm run build      # validates all content, then writes dist/
npm run preview    # http://localhost:4173
```

`dist/` is a static site with relative paths and hash routing (`#/lesson/<id>`), so it can be served from any
folder or sub-path, for example GitHub Pages. Open it through a web server (`npm run preview` or any static
server), not by double-clicking `index.html`. Browsers block ES modules loaded from `file://`.

## Deployment (GitHub Pages)

`.github/workflows/pages.yml` runs `npm run check` on every push and pull request. On `main` it also publishes
`dist/` to GitHub Pages: **https://lokid-se.github.io/LearnerApp/**

One-time repository setting: **Settings → Pages → Build and deployment → Source: GitHub Actions**. A failed
check blocks the deployment, so the live site is always a build that passed every test.

## Scripts

| Command                     | What it does                                                                             |
| --------------------------- | ---------------------------------------------------------------------------------------- |
| `npm run dev`               | Development server with live reload                                                      |
| `npm run build`             | Validates content, then builds `dist/`                                                   |
| `npm run preview`           | Serves `dist/` on port 4173                                                              |
| `npm run typecheck`         | TypeScript, strict mode                                                                  |
| `npm run lint`              | ESLint                                                                                   |
| `npm run format` / `:check` | Prettier                                                                                 |
| `npm test`                  | Unit, integration and component tests (Vitest + jsdom)                                   |
| `npm run validate:content`  | Only the content tests: schemas and cross-references                                     |
| `npm run test:e2e`          | End-to-end tests (Playwright) against the production build, desktop and mobile viewports |
| `npm run check`             | Everything above, in order - run before committing                                       |

`npm run test:e2e` needs a build first (`npm run build`); `npm run check` does that for you.

## Configuration

There is nothing to configure for normal use: no environment variables, keys or services.

- **End-to-end browser:** the tests use the installed Google Chrome (`channel: 'chrome'`). Without Chrome, run
  `npx playwright install chromium` once and then `PW_CHANNEL=chromium npm run test:e2e`.
- **Progress data:** stored in `localStorage` under `learnerapp.progress.v1`. Use **Progress → Export
  progress** to back it up or move it to another device, and **Import progress** to restore it.

## Project layout

```
content/                  the course: curriculum.yaml + lessons/<subject>/<lesson-id>.yaml
src/content/              schema (zod), validation, loader, search
src/domain/               grading, spaced repetition, mastery model (pure functions)
src/store/                progress state, persistence, derived views, Preact context
src/ui/                   router, Markdown and diagram rendering, components, pages, styles
tests/unit/               Vitest: domain, state, storage, content, search, router, components
tests/e2e/                Playwright: the learning journey end to end
docs/                     architecture, mastery model, content guide, plan
```

## Adding content

Lessons are YAML files. The UI never needs to change to add one. Read
[docs/CONTENT_GUIDE.md](docs/CONTENT_GUIDE.md) for the template, exercise types and accuracy rules. Then:

1. Create `content/lessons/<subject-id>/<lesson-id>.yaml`.
2. In `content/curriculum.yaml`, replace the planned entry's title, level and summary with just `- id: <lesson-id>`.
3. Run `npm run validate:content`, or keep `npm run dev` running: invalid content stops the dev server with a
   list of every problem, by file and field.

## Troubleshooting

| Symptom                                                             | Cause and fix                                                                                                            |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `npm ci` or `vite` fails with an engine/syntax error                | Old Node. Run `nvm use` (or install Node 22.12+). `node -v` must show v22.12 or later.                                   |
| Build fails with `Invalid content:` and a list                      | A lesson or `curriculum.yaml` breaks the schema or a reference. Each line names the file and field to fix.               |
| Blank page after opening `dist/index.html` directly                 | ES modules can't load from `file://`. Use `npm run preview` or any static web server.                                    |
| "Saved progress could not be loaded" banner                         | Stored progress was unreadable. It was kept aside under `learnerapp.progress.corrupt.<time>` and a fresh start was made. |
| "This browser is not letting LearnerApp save data" banner           | Storage is disabled (some private modes) or full. Progress lasts only for the session; export it before closing.         |
| A diagram shows as text with "could not be rendered"                | The Mermaid source in that lesson is invalid. Check it at [mermaid.live](https://mermaid.live) and fix the lesson YAML.  |
| `test:e2e` fails with "Chromium distribution 'chrome' is not found" | Install Google Chrome, or `npx playwright install chromium` and run with `PW_CHANNEL=chromium`.                          |
| `test:e2e` fails at start with "port 4173 is already used"          | Something else is on 4173. Stop it, or let Playwright reuse a running `npm run preview` of the current build.            |

## Known limitations

- **Eight complete lessons** (the Payments QA core path). The other 55 are planned entries on the map.
- **Free-text answers are self-assessed** against a model answer and rubric. They are not auto-graded, and
  the mastery model gives them slightly less weight (see [docs/MASTERY_MODEL.md](docs/MASTERY_MODEL.md)).
- **Progress is per browser.** Use export/import to move it; there is no sync.
- **Placement covers lessons that have placement questions** - currently the eight core-path lessons.
- **Java code is shown, not run.** There is no in-browser JVM; exercises check understanding of the code.
- **Bundle size.** Mermaid is large, but it is a separate lazily loaded chunk fetched only on pages with
  diagrams.
- `npm audit` reports two low-severity advisories in `katex`, which Mermaid depends on. LearnerApp content does
  not use KaTeX math, and the suggested `--force` fix would change Mermaid's version, so it was not applied.

## Safety

All payment examples use **SandPay**, a fictional provider, and sandbox-style data. Never put real card numbers,
credentials or production tokens into lessons, notes or bug reports.
