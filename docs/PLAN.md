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

## Next increments

Each increment ends with `npm run check` green.

2. **Stage 1-2 core content (payments path).** Write the planned lessons on the "Payments QA - core path":
   HTTP anatomy, methods and idempotency, payment lifecycle, sandbox test data, declines/timeouts/unknown
   outcomes, webhooks, scenario matrix. Add a `scenario` matrix exercise type if test-case writing needs more
   structure than the rubric gives.
3. **Diagnostic placement.** A short diagnostic per stage that marks prerequisites as "known" so learners skip
   what they already know (prompt section 14).
4. **Adaptive practice.** After a wrong answer, recommend the remediation section and a sibling exercise on the
   same concept. Add cumulative quizzes that interleave across lessons.
5. **Java track (E) with runnable code.** A companion Maven project (`practice/java/`) with JUnit exercises the
   learner runs locally: write the code, the tests verify it. The app links each exercise to its test class.
6. **Selenium/Appium and framework tracks (F, G).** A small reference framework against a local mock shop with
   simulated payment outcomes - added component by component, each justified by a test that needed it.
7. **Offline install (PWA).** A service worker and manifest so the app installs on a phone and works offline
   after the first visit.
8. **Interview simulations (stage 7).** Timed mixed-topic sessions with follow-ups and rubric scoring.

## Open questions for the owner

- Should the default first lesson follow the "Payments QA - core path" order, or start at stage 1 foundations?
- Which real payment provider (if any) should provider-specific notes compare against? Lessons currently stay
  provider-neutral with a fictional SandPay.
