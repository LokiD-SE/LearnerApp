# LearnerApp

A self-contained, hands-on technical training app. It teaches payments testing, API testing, mobile testing,
Java, Selenium/Appium and automation-framework design. The goal is that you can explain, implement, test, debug
and defend a solution in a real project or an interview, not just recognise the right answer.

Every lesson follows one template: plain-language idea, mechanics, diagrams, worked example, code, tests,
mistakes, trade-offs and summary. Practice is built around active recall, progressive hints, worked solutions,
spaced repetition and a mastery model that weighs practical work over multiple choice.

- **Static, installable and offline.** All content is bundled into the build; there is no server, account or
  paid API. Progress is stored in your browser. Install it on a phone or desktop like an app; after the first
  visit every lesson, diagram and exercise works without a network.
- **Skip what you already know.** A placement test per learning path (and "Test out" on each lesson) marks
  lessons you can already show you know as _tested out_; their recall cards still come back for review.
- **Practice that adapts.** A wrong answer points back to the sections that teach the concept and a similar
  exercise. The Practice page builds interleaved sessions from what you have studied, weakest concepts first,
  and says why each item was chosen.
- **Interview practice.** Generate a practice interview for any learning path or track in the style of Google,
  Meta, the Big 4, IT-services MNCs, mid-market product companies or startups - their reported rounds, with
  sources. Each round ends with a score, model answers, strengths and areas to improve; retake it as often as
  you like and compare your rounds over time.
- **Code you run yourself.** Coding exercises name a file in a practice project in this repository
  (`practice/`), the test class that checks it and the command to run. The tests are the judge; reference
  solutions are next to the exercises.
- **Know how long it takes.** Every course, chapter, lesson and lesson section shows its study time, and
  courses and paths show how much is left for you. Planned lessons are counted apart, as a rough figure.
- **Find your way.** Beside a course and a lesson, an outline lists every course with its chapters, lessons
  and the current lesson's sections; on a phone it folds into one panel. Every page has a way back home.
- **Desktop and mobile.** Responsive layout, touch-sized controls and pinch-zoom allowed everywhere. Diagrams
  have a full-size toggle.

## Status

The foundation and the **Payments QA core path** are complete, and the **Java automation engineer** path
has started. The full curriculum map is navigable (7 stages, foundations plus tracks A-H, 67 lessons). The
eight lessons of the core path are fully written:

1. Anatomy of an HTTP request and response
2. HTTP methods - safety and idempotency
3. Payment lifecycle - authorise, capture, settle, refund
4. Test cards, sandboxes and mock services
5. Idempotency keys and duplicate payment requests
6. Declines, timeouts and unknown outcomes
7. Webhooks, signatures and asynchronous status
8. Building a payment scenario matrix

**Track E (Java) is complete** - eight lessons, each with coding exercises you run locally:

1. Primitive and reference types
2. Strings, immutability and StringBuilder
3. Encapsulation, inheritance, polymorphism and abstraction
4. Exceptions and resource management
5. equals, hashCode and why HashMap needs both
6. Choosing the right collection
7. Lambdas, functional interfaces and streams
8. Concurrency basics for parallel test runs

Eight Selenium, Appium, Maven and framework lessons are written too:

1. Locator strategy - CSS, XPath and stable attributes
2. Explicit waits and synchronisation
3. Appium architecture, drivers and capabilities
4. Native, hybrid and WebView contexts
5. pom.xml, dependencies and scopes
6. The Maven lifecycle and running tests with Surefire
7. Page objects done right
8. A small reference framework, and why it is small

**Track H (Playwright with TypeScript and JavaScript)** has four lessons and a
**Playwright automation engineer** learning path:

1. JavaScript and TypeScript for testers: async, promises and types
2. Playwright locators, auto-waiting and web-first assertions
3. Fixtures and page objects in Playwright Test
4. Network mocking and API testing with Playwright

They use four practice projects - `practice/java`, `practice/framework` (a small Selenium + JUnit framework,
which also holds the Appium exercises - no device needed), `practice/maven` (broken builds to fix) and
`practice/playwright` (Playwright Test in TypeScript) - and the **SandPay Demo Shop** (`practice/shop`), a
fictional shop built to be awkward to automate, published with the app at `shop/`. See
[practice/README.md](practice/README.md).

**The Foundation course is complete** - eight lessons and a **Testing foundations** learning path, built
from the ISTQB Foundation Level syllabus v4.0.1, ISO/IEC/IEEE 29119, the RFCs, MDN, the Chrome DevTools
documentation, Pro Git and Andreas Zeller's work on systematic debugging (each lesson lists its sources):

1. Equivalence partitioning, boundaries and decision tables
2. State transition testing
3. Defect reports that get fixed
4. Risk-based testing
5. From a click to a response - the client-server request flow
6. Browser DevTools for testers
7. Git for testers and automation engineers
8. Scientific debugging - hypotheses, evidence and isolation

**Interview practice** (`#/interview`) covers every path and track: six company profiles, 14 round types and
about 100 interview questions, alongside the exercises of the chosen course.

**Track G is complete** with four more lessons - the last of the curriculum map:

1. Parallel execution and thread safety
2. CI pipelines and quality gates
3. Capstone - an end-to-end payment journey
4. Mock interview - payments QA engineer

All 67 lessons are written. See [docs/PLAN.md](docs/PLAN.md) for the roadmap and what is deferred.

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

## Install and use offline

Open the site once while online. LearnerApp then downloads the whole app in the background (about 2.3 MB
compressed, 7.8 MB stored) and says **"LearnerApp is saved on this device and now works offline."**

- **Android (Chrome):** menu **⋮ → Add to Home screen → Install**.
- **iPhone and iPad (Safari):** **Share → Add to Home Screen**.
- **Desktop (Chrome or Edge):** the install icon in the address bar.

After a new version is published, the next visit downloads it in the background and shows **"A new version of
LearnerApp is ready."** Choose **Reload** to switch, or keep working - the new version starts the next time
the app is opened after every LearnerApp tab or window is closed. Progress is not affected: it stays in the
browser's storage, separate from the app's files.

The practice shop (`shop/`) is not saved for offline use. It is an automation target, so its requests always
go to the network, where your tests can see and mock them.

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
                          + interviews/ (company loops, round types, question bank)
src/content/              schema (zod), validation, loader, search
src/domain/               grading, spaced repetition, mastery model (pure functions)
src/store/                progress state, persistence, derived views, Preact context
src/ui/                   router, Markdown and diagram rendering, components, pages, styles
src/pwa/                  offline install: service worker template, build helpers, registration
public/                   web app manifest and icons (scripts/make-icons.mjs renders the icons)
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

Interview questions go in `content/interviews/questions/*.yaml` and company profiles in
`content/interviews/interviews.yaml`; see "Interview practice content" in the content guide.

## Troubleshooting

| Symptom                                                             | Cause and fix                                                                                                               |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `npm ci` or `vite` fails with an engine/syntax error                | Old Node. Run `nvm use` (or install Node 22.12+). `node -v` must show v22.12 or later.                                      |
| Build fails with `Invalid content:` and a list                      | A lesson or `curriculum.yaml` breaks the schema or a reference. Each line names the file and field to fix.                  |
| Blank page after opening `dist/index.html` directly                 | ES modules can't load from `file://`. Use `npm run preview` or any static web server.                                       |
| "Saved progress could not be loaded" banner                         | Stored progress was unreadable. It was kept aside under `learnerapp.progress.corrupt.<time>` and a fresh start was made.    |
| "This browser is not letting LearnerApp save data" banner           | Storage is disabled (some private modes) or full. Progress lasts only for the session; export it before closing.            |
| A diagram shows as text with "could not be rendered"                | The Mermaid source in that lesson is invalid. Check it at [mermaid.live](https://mermaid.live) and fix the lesson YAML.     |
| `test:e2e` fails with "Chromium distribution 'chrome' is not found" | Install Google Chrome, or `npx playwright install chromium` and run with `PW_CHANNEL=chromium`.                             |
| `test:e2e` fails at start with "port 4173 is already used"          | Something else is on 4173. Stop it, or let Playwright reuse a running `npm run preview` of the current build.               |
| The site still shows an old version after a deploy                  | The installed copy updates in the background. Choose **Reload** on the "new version" banner, or close every LearnerApp tab. |
| Offline, the app shows the browser's "no internet" page             | It was never opened online in this browser, or site data was cleared. Open it once online and wait for the offline message. |

## Known limitations

- **67 complete lessons.** New lessons are added as planned entries on the map first.
- **Free-text answers are self-assessed** against a model answer and rubric. They are not auto-graded, and
  the mastery model gives them slightly less weight (see [docs/MASTERY_MODEL.md](docs/MASTERY_MODEL.md)).
- **Progress is per browser.** Use export/import to move it; there is no sync.
- **Code runs on your computer, not in the browser.** Coding exercises name a practice project and a test
  command; the app links to the files and you self-assess against the rubric.
- **Interview profiles come from public reports** (checked 2026-10-12, sources listed with each). Real loops
  vary by team, level and year, and questions are written for practice, not taken from any company.
  Interview scores are practice signals, not predictions.
- **Bundle size.** Mermaid is large. Online it is a separate chunk fetched only on pages with diagrams; the
  offline install downloads all of it once, so every diagram also works offline.
- `npm audit` reports two low-severity advisories in `katex`, which Mermaid depends on. LearnerApp content does
  not use KaTeX math, and the suggested `--force` fix would change Mermaid's version, so it was not applied.

## Safety

All payment examples use **SandPay**, a fictional provider, and sandbox-style data. Never put real card numbers,
credentials or production tokens into lessons, notes or bug reports.
