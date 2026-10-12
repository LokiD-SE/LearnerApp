# Content guide

How to write a LearnerApp lesson. The schema is `src/content/schema.ts`; the reference lesson is
`content/lessons/api-testing/idempotency-keys.yaml`. Copy its structure.

## Accuracy rules (non-negotiable)

1. **Never invent** APIs, commands, flags, status codes, provider behaviour, framework features or test results.
   If unsure, leave it out or mark it "check the documentation".
2. **Label scope.** Say whether something is universal, standard (cite it: "RFC 9110 section 9.2.2"),
   provider-specific, platform-specific (Android vs iOS) or version-specific (Java 17+, Selenium 4, Appium 2).
3. **Put versions and assumptions in `environment:`** - language and framework versions, tools, and which parts
   are fictional.
4. **Fictional systems only** for payments: SandPay (`https://api.sandpay.example`) and sandbox-style data. No
   real card numbers, credentials, tokens or personal data, even "test" ones copied from a provider.
5. **Code must be correct** for the stated version. Mark excerpts that are not complete programs as illustrative.

## Lesson file

`content/lessons/<subject-id>/<lesson-id>.yaml`. The file name is the lesson id (kebab-case), and the lesson
must be listed under the right module in `content/curriculum.yaml`.

| Field                                                                                | Notes                                                                                                                                                                      |
| ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`, `title`, `subject`, `module`, `level`, `status`, `estimatedMinutes`, `summary` | `status: draft` relaxes the practical-exercise rule while writing                                                                                                          |
| `environment`                                                                        | versions, sources, assumptions, what is fictional                                                                                                                          |
| `prerequisites`                                                                      | lesson ids (published or planned)                                                                                                                                          |
| `concepts`                                                                           | 1-4 per lesson; ids unique across all content; every exercise and recall card names one                                                                                    |
| `objectives`                                                                         | measurable: "explain", "design", "trace", "write" - not "understand"                                                                                                       |
| `sections`                                                                           | the template below, in teaching order                                                                                                                                      |
| `exercises`                                                                          | see types below; **each concept needs an `application` or `analysis` exercise**                                                                                            |
| `placement`                                                                          | 2-3 auto-graded questions (`mcq`, `order`, `debug`) that decide whether a learner may skip the lesson; **at least one per concept**, different from the practice exercises |
| `recall`                                                                             | 4-8 active-recall cards: a question and a short answer                                                                                                                     |
| `next`, `tags`                                                                       | suggested next lessons; search keywords                                                                                                                                    |

`estimatedMinutes` is the whole lesson: reading, diagrams, every exercise and the recall cards. It is the only
time figure you write. The app shares it between the lesson's parts by their size (prose at 180 words a
minute, code at 12 lines a minute, 1.5 minutes per diagram, a typical time per exercise type, a minute per
recall card) and adds lessons up for chapters, courses, paths and stages - see `src/content/time.ts`. Planned
lessons have no figure; totals show them separately as "about" the typical published lesson.

## The lesson template (section `kind`s)

Use each kind when it helps the concept - not mechanically.

| kind           | Purpose                                                                                   |
| -------------- | ----------------------------------------------------------------------------------------- |
| `intuition`    | plain-language explanation with an analogy                                                |
| `what`         | precise definition and terminology                                                        |
| `why`          | the problem it solves                                                                     |
| `internals`    | how it works underneath                                                                   |
| `when`         | when to use it, when not, what it does not replace                                        |
| `visual`       | a Mermaid diagram (sequence, flowchart, state) with a sentence on what to notice          |
| `steps`        | step-by-step procedure the learner can follow                                             |
| `example`      | a realistic project scenario and what a tester checks                                     |
| `code`         | syntax, configuration, commands, requests and responses (`collapsed: true` for long ones) |
| `line-by-line` | why the important lines are written that way                                              |
| `tests`        | positive and negative test cases with expected results and evidence                       |
| `mistakes`     | common mistakes and a debugging method                                                    |
| `tradeoffs`    | limitations, trade-offs and alternatives                                                  |
| `summary`      | quick-reference bullets                                                                   |

Each section lists the lesson `concepts` it teaches (`concepts: [idempotency-key-contract]`). After a wrong
answer the app points the learner to the sections that teach that concept most specifically, so tag only
what a section really explains. Every concept needs at least one section other than `summary`.

Objectives, practice (exercises), interview questions and "test yourself" (recall) are rendered from their own
fields, so the template is complete without separate sections for them.

### Markdown in bodies

GitHub-flavoured Markdown: tables, lists, fenced code with a language (`java`, `json`, `http`, `bash`, `yaml`,
`xml`, `sql`, `javascript`, `typescript`) and fenced `mermaid` diagrams. Raw HTML is escaped, so don't use it.
Link to another lesson with `[text](#/lesson/<id>)`, and to the practice shop with `[text](shop/index.html)`.

## Exercise types

All exercises have `id`, `type`, `concept`, `skill`, `title`, `prompt`, `hints` (progressive, from a nudge to
nearly the answer), `solution` (worked, with reasoning), an optional `followUp` (a similar problem: transfer
practice), and `required` (default true).

| type         | Extra fields                                                                                            | Graded        |
| ------------ | ------------------------------------------------------------------------------------------------------- | ------------- |
| `mcq`        | `options[]` (`id`, `text`, `feedback` - explain the misconception for wrong ones), `correct[]`          | auto          |
| `order`      | `items[]` in the **correct** order (the app shuffles)                                                   | auto          |
| `debug`      | `language`, `code`, `correctLines[]` (1-based), optional `lineNotes[]` for tempting wrong lines         | auto          |
| `short`      | `modelAnswer`, `rubric[]`                                                                               | self-assessed |
| `testdesign` | `modelAnswer`, `rubric[]` - ask for preconditions, steps, expected result **and evidence**              | self-assessed |
| `interview`  | `modelAnswer`, `rubric[]`, `followUps[]` - the follow-ups an interviewer would ask                      | self-assessed |
| `coding`     | `modelAnswer` (the reference solution), `rubric[]`, `project`, `files[]`, `test`, `command` - see below | self-assessed |

`skill` is `recognition`, `recall`, `application` or `analysis`; see [MASTERY_MODEL.md](MASTERY_MODEL.md).

Good exercises:

- Wrong options are **plausible misconceptions**, and their feedback names the misconception.
- Hints guide reasoning; they don't give the answer away until the last one.
- Scenario questions give **evidence** (logs, ids, timings), and the solution explains how to **confirm** the
  root cause before acting - not only which option is right.

## Coding exercises and practice projects

A `coding` exercise is code the learner writes and runs on their own computer, in a **practice project** in
this repository. Projects are registered under `practice:` in `content/curriculum.yaml` (id, folder, setup
instructions); the app links to their files on GitHub.

- `project` - the practice project's id, for example `java`.
- `files` - what the learner changes, relative to the project folder. By convention exercises live in
  `src/exercises/java` and the reference solution of each file in the same place under `src/solutions/java`.
- `test` - the test class that checks the work. It must be tagged `@Tag("exercise")`.
- `command` - the command that runs that test, from the project folder (`mvn test -Dtest=MoneyTest`).
- `rubric` - the **first** point is "every test in X passes"; the others are what the tests cannot see
  (no `double`, the right fields, an explanation).
- `modelAnswer` - the key part of the reference solution, with the reasoning.

The Playwright project (`practice/playwright`) follows the same idea with its own layout: exercises in
`exercises/`, reference solutions at the same path under `solutions/`, and exercise specs tagged
`{ tag: '@exercise' }`; `command` names the spec (`npx playwright test tests/shop-locators.spec.ts`).

The app can't run the code, so coding exercises are self-assessed. The rest is checked automatically: a
content test fails if a named file, solution or test class is missing, and `practice/verify.sh <project>`
(run in CI) checks that the reference solutions pass every test and that every exercise test class fails
against the unsolved exercise. Write the exercise, its tests and its solution together, and run
`practice/verify.sh` before committing.

## Placement questions

- They test whether the lesson can be **skipped**, so ask about applying the concept, not about wording from the
  lesson.
- Use only auto-graded types, and give every wrong option its own feedback - learners see it in the results.
- A learner tests out only if every question is right, so keep it to 2-3 well-chosen questions per lesson.
- Write the `solution` for someone who got it wrong: it is shown in the results review.

## Interview practice content

Interview practice reads `content/interviews/interviews.yaml` and the question bank in
`content/interviews/questions/*.yaml`; the validator checks both with the lessons.

- **`asOf` and `note`** - when the company profiles were last checked against their sources, and the caveat
  shown to learners. Update `asOf` whenever you re-check a profile.
- **`competencies`** - what feedback is given on (`id`, `name`, `improve` in Markdown, optional `lesson`).
  Every bank question's `concept` is a competency id.
- **`roundTypes`** - `id`, `title`, `minutes` (the real round's usual length), `questions` (how many a practice
  round asks), `summary`, `assesses[]`, `tips[]`, and optional `fromLessons` (`types`, `skills`, `subjects`) to
  also use exercises from the chosen course's lessons.
- **`profiles`** - a company or kind of company: `name`, `category`, `summary`, `notes[]`, `sources[]` (title
  and https URL - **required**) and `stages[]` in loop order. A stage lists one or more round types (one is
  picked per interview) and an optional `chance` (0-1) for stages only some candidates get.
- **Question files** - `questions[]` of `{ rounds, subjects?, exercise }`. `exercise` is any exercise type
  above. `subjects` limits a tool-specific question (Selenium, JavaScript...) to courses about those subjects.

Rules:

- **Profiles describe what is publicly reported**, with sources, and say where reports are thin (for example
  no reports found for one firm). Never present a question as a company's real or leaked question.
- Write questions **in the style of the round** - "Tell me about a time..." for behavioural, a problem with
  examples for coding - with a model answer, a rubric of what interviewers listen for, and follow-ups.
- Every round type a profile uses needs at least `questions` bank questions **without** `subjects`, so any
  course can fill it; the validator enforces this.
- Links to lessons (`#/lesson/<id>`) are checked; link the lesson that teaches what a question tests.
- Coding questions' reference solutions must compile and pass their own examples - run them before committing.

## YAML pitfalls

- A value containing `: ` (colon and space) must be **quoted**, or YAML reads it as a nested key - common
  with headers (`` `Content-Type: application/json` ``) and JSON snippets. Use `"..."`, or `'...'` when the
  text contains double quotes.
- The same applies to list items such as hints and rubric points.
- Ids such as `null`, `true` and `false` are YAML values, not strings - the validator reports "expected
  string". Use descriptive ids (`prints-null`, `same-object`).
- Long Markdown belongs in a block scalar (`body: |`), where colons are safe.
- `npm run validate:content` names the file and field for schema errors, and `npm run dev` / `build` name the
  file for YAML syntax errors.

## Checking your lesson

```bash
npm run validate:content    # schemas + every reference
npm run dev                 # read it on desktop and on a phone-sized window
npm run check               # everything, before committing
```
