# Plan

## Increment 1 - foundation and first vertical slice (done)

Goal: a learner can open the curriculum, study a lesson, attempt exercises, get feedback, have progress saved,
reload and resume.

Acceptance criteria - all met and covered by automated tests:

- [x] The app starts locally with documented commands (`npm ci`, `npm run dev` / `build` + `preview`).
- [x] The curriculum is navigable: 7 stages, foundations + tracks A-G, 63 lessons (1 published, 62 planned),
      learning paths, search and filters.
- [x] A representative lesson (idempotency keys) has every template section, two diagrams, code, eight
      exercises of six types, and six recall cards.
- [x] Feedback works without giving answers away: misconception feedback, progressive hints, solution after an
      attempt or an explicit give-up, follow-up challenge.
- [x] Progress persists across reloads and restarts (localStorage, validated, versioned), with export/import.
- [x] Mastery per concept (documented model), weak areas, review queue with spaced repetition and interleaving.
- [x] Error and empty states: invalid content, corrupt or unavailable storage, planned / unknown lessons,
      unknown routes, empty search, filters, review queue.
- [x] Checks: typecheck, lint, format, 68 unit/integration/component tests, 8 end-to-end runs (4 journeys ×
      desktop and mobile viewports).

## Increment 2 - Payments QA core path (done)

Goal: the eight lessons of the "Payments QA - core path", written to the lesson template and checked.

- [x] Seven new lessons: HTTP anatomy, methods and idempotency, payment lifecycle, sandboxes and test data,
      declines/timeouts/unknown outcomes, webhooks and signatures, payment scenario matrix (plus the existing
      idempotency-keys lesson).
- [x] Home page follows the path: "Start here" opens the first unfinished lesson of the core path; path
      progress is shown for every learning path.
- [x] Content-quality tests for every published lesson (environment, core template sections, a diagram,
      varied practice with hints, distinct feedback per option, recall cards, no card-number-like digits).
- [x] End-to-end test that opens every lesson at desktop and mobile size and requires every diagram to render
      with no page errors.

## Increment 3 - diagnostic placement (done)

Goal: learners skip what they can already show they know (prompt section 14).

- [x] Placement questions per lesson (auto-graded, at least one per concept): 20 across the core path.
- [x] Placement test for a learning path (offered on the home page) and "Test out" on each lesson page: no
      hints or feedback until the end, "I don't know this yet", results with a question review.
- [x] New lesson status **Tested out**: paths skip it, prerequisites show it, recall cards join the review
      queue; "Study it anyway" undoes it. Not mastery evidence (documented in the mastery model).
- [x] Placement results on the Progress page; Learn filter for tested-out lessons.
- [x] Unit tests (rules, status precedence, path progress, routing, loading older saved progress), content
      rules (placement per concept), end-to-end tests of the path test, the lesson test-out and empty states.

## Increment 4 - adaptive practice (done)

- [x] "To fix this" after wrong answers: sections teaching the concept and a similar exercise.
- [x] Sections declare the concepts they teach (validated; every concept has a teaching section).
- [x] Practice page: adaptive, interleaved sessions across studied lessons or one lesson, with reasons.
- [x] Practice answers count as retention evidence after 24 hours; unit and end-to-end tests.

## Increment 5 - Java track with runnable code (done)

Goal: Java practice that is judged by real tests, not by multiple choice.

- [x] New exercise type `coding`: the lesson names a practice project, the files to change, the test class and
      the command; links go to the files on GitHub; self-assessed against a rubric whose first point is "the
      tests pass" (documented in the mastery model and content guide).
- [x] `practice/java`: Maven, Java 17+, JUnit 6. Exercises in `src/exercises/java`, reference solutions in
      `src/solutions/java` (`-Psolutions`), exercise test classes tagged `@Tag("exercise")`.
- [x] `practice/verify.sh`: reference solutions pass every test, every exercise test class fails against the
      unsolved exercise; runs in CI (`practice` job), and the deployment waits for it.
- [x] Content test: every file, solution and test class a coding exercise names exists.
- [x] Lessons: **Primitive and reference types** (`==` vs `equals`, the `Integer` cache, money types; coding
      exercises `PaymentChecks`, `MinorUnits`) and **equals, hashCode and HashMap** (coding exercises `Money`,
      `Payment`).
- [x] The rest of Track E, each with two coding exercises: **Strings and StringBuilder** (`ReportLine`,
      `Receipt`), **OOP pillars** (`CapturedPayment`, `FeePolicies`), **Exceptions** (`PaymentSubmitter`,
      `Transfers`), **Choosing collections** (`Reconciliation`, `RetryQueue`), **Streams and lambdas**
      (`PaymentStats`, `LatestAttempts`), **Concurrency basics** (`IdempotencyGuard`, `ParallelChecks`).
      Performance and concurrency tests use wide margins (each solution runs in under a quarter of its time
      limit) and latches rather than luck, so they stay stable in CI.

## Increment 6 - Selenium and framework tracks (first slice done)

Goal: UI automation practised against a real (fictional) shop, with a framework small enough to understand.

- [x] `practice/shop`: the SandPay Demo Shop - static HTML, CSS and JavaScript with deliberate automation
      traps (asynchronous loading, re-sorting, generated ids and classes, an iframe, a processing overlay,
      PENDING orders that settle later) and test cards instead of card numbers. Published with the app at
      `shop/`; `npm run dev` serves it; Playwright smoke tests cover the published copy.
- [x] `practice/framework`: Selenium 4.51 + JUnit 6 reference framework - `Config`, `ShopServer` (JDK HTTP
      server), `Browser`, a JUnit extension (shop per class, browser per test, evidence on failure), page
      objects and components, and journey tests. Each part's Javadoc names the need that justified it.
- [x] Coding exercises with tests: `ShopLocators` (stable locators, checked across reloads and re-sorts),
      `OrderWaits` (explicit waits, checked for timeouts and hidden sleeps), `CartPage` (a page object,
      checked for waiting and for keeping Selenium inside). CI runs `practice/verify.sh framework` with
      headless Chrome and keeps evidence on failure.
- [x] Lessons: **Locator strategy**, **Explicit waits and synchronisation**, **Page objects done right**,
      **A small reference framework, and why it is small**.
- [x] Appium lessons: **Appium architecture, drivers and capabilities** and **Native, hybrid and WebView
      contexts**. Their coding exercises need no device: `AndroidSessions` (Appium 1 capabilities migrated
      to `UiAutomator2Options`, checked capability by capability) and `Contexts` (waiting for and choosing a
      webview context, with simulated context lists). `practice/framework` now uses `io.appium:java-client`
      10.1.1 and imports the Selenium BOM, because java-client asks for Selenium with a version range.
      Running against a real emulator is shown as optional, illustrative code.
- [x] Maven lessons: **pom.xml, dependencies and scopes** and **The Maven lifecycle and Surefire**, with
      `practice/maven`: broken exercise projects (`receipt-tool`, `checkout-suite`) whose test classes run
      Maven on the learner's project and check the outcome - build success, the real test count, the
      Failsafe phase, a failing integration test failing the build. CI runs `practice/verify.sh maven`.
- [x] Parallel runs and thread safety, CI quality gates and the capstone.

## Increment 7 - Playwright track and interview practice (done)

Goal: the same hands-on depth for Playwright in TypeScript and JavaScript, and interview rehearsal for any
course.

- [x] `practice/playwright`: Playwright Test 1.64 with TypeScript (one JavaScript exercise, type-checked with
      `checkJs`). Exercises in `exercises/`, solutions in `solutions/`, specs tagged `@exercise`;
      `npm run verify` (CI: `practice/verify.sh playwright`) type-checks, runs the solutions and checks every
      exercise spec fails on the stubs. Eight exercises: `checkAll`, `pollUntil`, shop locators, order-status
      waits, a cart page object, fixtures, network mocks, an API client.
- [x] The shop's catalog now loads `products.json` (with an error state and Try again), so there is a real
      request to mock and an API to test.
- [x] Lessons (Track H): **JavaScript and TypeScript for testers**, **Playwright locators, auto-waiting and
      web-first assertions**, **Fixtures and page objects in Playwright Test**, **Network mocking and API
      testing with Playwright**; a **Playwright automation engineer** learning path.
- [x] Interview practice (`#/interview`): company profiles for Google, Meta, the Big 4, IT-services MNCs,
      mid-market product companies and startups, each with its reported loop and sources (checked
      2026-10-12); 14 round types; a question bank of about 100 original questions with model answers,
      rubrics and follow-ups, plus exercises from the chosen course's lessons.
- [x] Generate an interview for any path or track: a company's loop with its optional stages, a different
      company and set of rounds each time, unseen questions first. Rounds are timed against the real round's
      length; hints cost credit; every round ends with a report - score and band, strengths, areas to improve
      with links to lessons, missed rubric points, tips, and the change since the previous attempt. Retake an
      interview or a round any number of times; the interview page compares every attempt round by round.
- [x] Rules in [MASTERY_MODEL.md](MASTERY_MODEL.md) (interview answers are not mastery evidence); unit tests
      for generation, scoring, feedback and state; an end-to-end journey on desktop and mobile.

## Increment 7b - study times and navigation (done)

- [x] Study time for every course (subject), chapter (module), lesson and lesson section, and for learning
      paths and stages; "time left" for courses and paths once a learner has made progress. Section times are
      shares of the lesson's figure, so they add up to it; planned lessons are shown apart as a rough figure.
- [x] A course outline beside the course page and every lesson page: all courses with their times, the current
      course open with its chapters and lessons, and the current lesson's sections (with times) under it.
      Collapsed into one panel on narrow screens. It replaces the lesson's separate Contents panel.
- [x] "Back to home" on every page except the home page.
- [x] Unit tests (sharing, totals, formatting, time left) and an end-to-end spec on desktop and mobile.

## Increment 7c - the Foundation course (done)

- [x] All eight Foundation lessons written to the template, each with its sources in `environment:`:
      **Equivalence partitioning, boundaries and decision tables** and **State transition testing** (ISTQB
      CTFL v4.0.1 4.2, ISO/IEC/IEEE 29119-4), **Risk-based testing** (ISTQB 5.2, ISO 31000, ISO/IEC 25010),
      **Defect reports that get fixed** (ISTQB 5.5 and 1.2.3, ISO/IEC/IEEE 29119-3, Mozilla's Bug Writing
      Guidelines), **From a click to a response** (RFC 1034/1035, 9293, 8446, 9110-9114, 9000, MDN),
      **Browser DevTools for testers** (Chrome DevTools documentation), **Git for testers** (Pro Git,
      git-scm.com), **Scientific debugging** (Zeller, _Why Programs Fail_ chapter 6, The Debugging Book,
      git-bisect documentation).
- [x] Command output in the lessons (curl 8.5, Git 2.43) was captured from real runs; exercises use the
      SandPay Demo Shop's real behaviour (test cards, `products.json`, session storage keys).
- [x] A **Testing foundations** learning path (added after the existing paths, so the home page still starts
      with the Payments QA core path).

## Increment 7d - completing the courses (done)

- [x] Track A (payments): ecosystem roles; void, reversal, refund and chargeback; card payments and tokenisation; 3-D
      Secure and redirects; wallets and bank payments (UPI, SEPA); amounts, currency and rounding; refresh, back and
      interruptions; partial refunds and invariants; reconciliation; PCI DSS awareness. Sources: Visa Core Rules (18 April
      2026), EMVCo, PCI DSS v4.0.1, PSD2 RTS (EU) 2018/389, NPCI circulars, EPC rulebooks, ISO 4217, ISO 20022.
- [x] Track C (API testing): status codes and Problem Details (RFC 9110, 9457, 6585); authentication and authorization
      (RFC 6749, 6750, 7519, 8725, 9700, OWASP API Top 10 2023); Postman and the Postman CLI; JSON Schema 2020-12, OpenAPI
      and Pact; pagination, filtering and rate limits (RFC 8288); the payment API negative matrix.
- [x] Track B (architecture and RCA): tracing (W3C Trace Context, OpenTelemetry); sync versus async; logs, metrics and
      traces (Google SRE book); defect isolation decision trees; inconsistent status incidents and postmortems.
- [x] Track D (mobile): test planning; interruptions and lifecycle; Android lifecycle and process death; adb and logcat;
      iOS lifecycle and universal links; mobile payment interruptions. Kotlin and Swift code highlighting added.
- [x] Practice project `practice/java`: `parallel/TestDataFactory` and `parallel/PerThread` exercises with tests and
      solutions (verified with `practice/verify.sh java`), for the coming parallel-runs lesson.
- [x] Track G: parallel runs and thread safety (JUnit parallel execution, Surefire forks, ThreadLocal, unique data,
      honest retries); CI pipelines and quality gates (GitHub Actions, secrets, required checks); the end-to-end
      payment capstone; the payments QA mock interview.
- [x] Review of the 28 earlier lessons against their official sources: claims checked against RFCs, the JLS and
      Java SE 17 Javadoc, W3C WebDriver, Maven, JUnit, Selenium, Appium, Playwright, Visa rules, ISTQB and PCI SSC;
      outputs re-run; sources cited in each `environment:`. No ids or answers changed.

## Increment 8 - offline install (done)

- [x] Web app manifest (name, standalone display, theme colour) with 192 and 512 px icons, a maskable icon
      and an Apple touch icon, rendered from the app's mark by `scripts/make-icons.mjs`.
- [x] Service worker generated at build time: precaches every file of the build, including all Mermaid
      chunks, so every lesson and diagram works offline after the first visit; the practice shop stays on the
      network. Unchanged hashed files are reused between versions.
- [x] Updates wait for the learner: a "new version is ready - Reload" banner; a one-time "now works offline"
      message after the first install.
- [x] Tests: unit tests for the precache list, the worker source and the update logic; Playwright tests for
      the manifest and icons, every diagram type offline, and the shop staying uncached. The update flow was
      also checked by hand in Chrome (banner, Reload, old cache removed).

## Increment 9 - Track I (full stack) and Track J (AI engineering) (done)

Goal: two end-to-end courses to the same standard as tracks A-H - every lesson from official sources, cited in
`environment:`, with runnable practice projects that need no paid API key.

- [x] Outline: 32 full stack lessons (stages 8-10) and 36 AI lessons (stages 11-15) as planned lessons, with a
      **Full stack developer (TypeScript)** path and an **AI engineer - LLM apps, RAG and agents** path.
- [x] Track I lessons, in batches of 4-6. Batch 1 done: the web platform module (semantic HTML and forms, CSS layout, responsive design, WCAG 2.2 accessibility, DOM events and the event loop). Batch 2 done: modern JavaScript, TypeScript for applications, the Node.js
      runtime and npm, React components and JSX, React state and effects. Batch 3 done: React forms and validation, routing and data
      fetching (React Router 8), frontend state management, an Express HTTP API, REST API design. Batch 4 done: input validation
      and error handling (zod 4), contract-first OpenAPI, relational modelling and SQL, PostgreSQL indexes and query
      plans, transactions and isolation (two-session runs on real PostgreSQL 18.6). Batch 5 done: migrations
      and data access, sessions/cookies/tokens, passwords + OAuth 2.0 + OIDC, the OWASP Top 10:2025, testing
      strategy. Batch 6 done: docker-and-compose, ci-cd-for-web-apps,
      deployment-and-configuration, web-performance-and-caching, observability-for-web-apps, fullstack-capstone,
      fullstack-system-design-interview - all 32 Track I lessons are published. Stack: HTML/CSS (WHATWG, W3C, WCAG 2.2), TypeScript, React, Node.js +
      Express, PostgreSQL, Docker, GitHub Actions, OWASP. Sources: WHATWG HTML, MDN, ECMA-262, the TypeScript
      handbook, react.dev, nodejs.org, expressjs.com, the PostgreSQL manual, RFCs, OWASP, OpenAPI 3.1, docs.docker.com.
- [x] `practice/fullstack`: TypeScript, React 19 (Testing Library, jsdom), Express 5 (supertest) and PostgreSQL
      (PGlite, no server); exercise tests tagged `@exercise`; `npm run verify` in CI via `practice/verify.sh fullstack`.
      54 exercises.
- [x] Track J lessons - all 36 published (2026-11-14 to 2026-11-18), in six batches: machine learning
      foundations, deep learning (PyTorch CPU), generative AI engineering, AI agents (plain-Python graph and crew
      harnesses; LangGraph and CrewAI quoted from their docs, not installed), the Model Context Protocol (revision
      2026-07-28, implemented by hand in plain Python - no SDK, by the owner's choice; SDK and Inspector quoted
      from the docs), and production AI + capstone + mock interview. Sources: the MCP specification
      (modelcontextprotocol.io), Anthropic and OpenAI API docs, LangGraph and CrewAI docs, scikit-learn, NumPy,
      pandas and PyTorch docs, OpenTelemetry GenAI conventions, OWASP Top 10 for LLM applications 2025 and for
      agentic applications. The courses the owner named shape the outline only; lessons cite primary sources.
- [x] `practice/ai`: Python 3.12 venv (pinned `requirements.txt`: NumPy, pandas, scikit-learn, pytest, PyTorch
      CPU); LLM and agent exercises run against `support/llm_fake.py` (ScriptedLLM) and toy embeddings, offline
      and free; `AI_TARGET=solutions` switches the import path; `scripts/verify.py` via `practice/verify.sh ai`
      in CI. 96 exercises (ml_foundations, deep_learning, genai, agents, mcp, production).
- [x] Interview question bank entries for both tracks: 20 Track I questions (`fullstack.yaml`) and 21 Track J
      questions (`ai-engineering.yaml`), with the `ai-engineering` competency.

## Increment 10 - Track K (performance testing) and Track L (security testing) (in progress)

Asked for on 2026-11-18: a performance testing track for JMeter and Locust, and a security testing track. The
owner chose about 30 lessons each, real JMeter and Locust runs, and a deliberately vulnerable app of our own.

- [x] Outline: Track K (`performance-testing`, 31 lessons, stages 16-18: fundamentals, JMeter, Locust, analysis
      and capstone) and Track L (`security-testing`, 30 lessons, stages 19-21: foundations, web vulnerabilities,
      API security, DevSecOps, mobile/payments/reporting and capstone); paths `performance-tester` and
      `security-tester`.
- [x] `practice/perf`: Python 3.12 venv with Locust 2.47.0 and pytest; Apache JMeter 5.6.3 downloaded by
      `scripts/get-jmeter.sh` into `tools/` (gitignored, SHA-512 checked); `support/sandpay_target.py`, a
      loopback-only practice API with configurable latency, capacity, queueing, errors and rate limits;
      `support/load_tools.py` runs JMeter (non-GUI) and Locust (headless); `PERF_TARGET=solutions`.
- [x] `practice/security`: Python 3.12 venv with pytest and requests; `support/sandpay_vuln.py`, a deliberately
      vulnerable SandPay portal bound to loopback only, with 17 flaws (OWASP Top 10:2021 and API Top 10:2023),
      each closable with `make_app(fixed=...)`; `tests/support` proves every flaw is present and fixable;
      `SEC_TARGET=solutions`.
- [ ] Track K lessons, in batches of about 6 - 18 of 31 published (2026-11-20). Done: the fundamentals
      module (6), JMeter part 1 (architecture, thread groups and timers, HTTP samplers, correlation,
      assertions and listeners, parameterisation), JMeter part 2 (logic controllers, JSR223/Groovy, HTML
      dashboard and CI, distributed testing) and Locust part 1 (fundamentals, HTTP validation and grouping).
      Next: the rest of the Locust module (task sets, events and custom clients, load shapes, distributed and
      CI), then analysis, CI and the capstone (9).
      Sources: the Apache JMeter user manual and component reference, the Locust documentation, Little's law
      (Lazowska et al.), Google SRE books, the USE and RED methods, web.dev.
- [ ] Track L lessons, in batches of about 6 - 12 of 30 published (2026-11-20). Done: foundations (6) and
      web vulnerabilities part 1 (authentication, sessions, access control/IDOR, SQL injection, XSS, CSRF and
      clickjacking). Next: web part 2 (SSRF and open redirects, file handling and path traversal, security
      misconfiguration, cryptography and data exposure), then API security (4), DevSecOps (5), and mobile,
      payments, reporting, capstone and mock interview (5). Sources: OWASP WSTG (v4.2 stable), ASVS 5.0.0, Top 10,
      API Security Top 10:2023, MASVS/MASTG, cheat sheets and ZAP docs; RFCs (JWT, OAuth); FIRST CVSS v4.0;
      PCI DSS v4.0.1. ZAP, Burp, Semgrep and similar tools are quoted from their docs, not installed.
- Lesson forks follow a shared brief (kept outside the repo); the hard-won rules are: quote YAML values with
  `: `, `order` items as `{id, text}`, a `solution` and hints on every exercise, no `null`/`true` ids, quoted
  mermaid labels, no 13-19 digit runs (elide JMeter epoch-ms), Locust totals from `--json-file` not
  `_stats.csv`, rates over the active span, never `import locust` in pytest, probes that find the flaw and stay
  quiet when it is fixed.
- [ ] Interview question bank entries for both tracks.

## Next increments

Each increment ends with `npm run check` green (and `practice/verify.sh` for practice projects).

8. **More interview depth.** Spoken-answer practice with a recording timer, and company profiles for more
   companies as reports are checked.

## Open questions for the owner

- Which real payment provider (if any) should provider-specific notes compare against? Lessons currently stay
  provider-neutral with a fictional SandPay.
