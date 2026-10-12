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
- [ ] Parallel runs and thread safety, CI quality gates and the capstone.

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

## Next increments

Each increment ends with `npm run check` green (and `practice/verify.sh` for practice projects).

8. **Offline install (PWA).** A service worker and manifest so the app installs on a phone and works offline
   after the first visit.
9. **More interview depth.** Spoken-answer practice with a recording timer, and company profiles for more
   companies as reports are checked.

## Open questions for the owner

- Which real payment provider (if any) should provider-specific notes compare against? Lessons currently stay
  provider-neutral with a fictional SandPay.
