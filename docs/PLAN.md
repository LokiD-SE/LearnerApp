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

## Increment 5 - Java track with runnable code (first slice done)

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
- [ ] Remaining Track E lessons: strings and StringBuilder, OOP pillars, exceptions, choosing collections,
      streams and lambdas, concurrency basics - each with at least one coding exercise.

## Next increments

Each increment ends with `npm run check` green (and `practice/verify.sh` for practice projects).

6. **Selenium/Appium and framework tracks (F, G).** A small reference framework against a local mock shop with
   simulated payment outcomes - added component by component, each justified by a test that needed it.
7. **Offline install (PWA).** A service worker and manifest so the app installs on a phone and works offline
   after the first visit.
8. **Interview simulations (stage 7).** Timed mixed-topic sessions with follow-ups and rubric scoring.

## Open questions for the owner

- Which real payment provider (if any) should provider-specific notes compare against? Lessons currently stay
  provider-neutral with a fictional SandPay.
