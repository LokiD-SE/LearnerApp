# Mastery model

One right answer is not mastery. LearnerApp distinguishes **familiarity** (I recognise it) from
**demonstrated ability** (I can apply it, and I still can a day later). The rules are implemented in
`src/domain/grading.ts`, `src/domain/mastery.ts` and `src/domain/srs.ts`, and unit-tested in `tests/unit/`.
Change the code and this document together.

## 1. Evidence

Every answer is an **attempt**, with a raw score from 0 to 1:

| Exercise type                           | Graded by                                                               | Raw score                                               |
| --------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------- |
| Multiple choice / "pick the lines"      | the app                                                                 | (right picks - wrong picks) / right answers, at least 0 |
| Put in order                            | the app                                                                 | share of items in the correct position                  |
| Short answer, test design, interview    | **the learner**, against a rubric                                       | share of rubric points the learner ticks                |
| Coding (runs on the learner's computer) | **the learner**, against a rubric whose first point is "the tests pass" | share of rubric points the learner ticks                |
| Recall card                             | **the learner**                                                         | Didn't know it = 0, Partly = 0.6, Knew it = 1           |

**Hints cost credit.** Each hint taken before the first answer removes 15% of its credit, up to 45%. With
three hints, a perfect answer earns 0.55.

**Giving up** ("Give up and show solution" before answering) is recorded as a zero-credit attempt.

**Only first tries count.** The first submission of an exercise in a sitting (a page visit or a review) is
evidence. A "Try again" straight after feedback is practice: it is recorded and shown in history, but it is not
used for mastery or the review schedule. An answer given after the solution was shown is never a first try.

## 2. Weighting

| Skill       | Weight | Example                                                   |
| ----------- | ------ | --------------------------------------------------------- |
| recognition | 1      | pick the idempotent HTTP methods                          |
| recall      | 2      | explain the retry rule in your own words; order the steps |
| application | 3      | design a test suite; decide which endpoints need keys     |
| analysis    | 3      | find the race condition; diagnose a duplicate charge      |

Self-assessed evidence is multiplied by **0.8**. It counts, but less than auto-graded evidence.

## 3. Concept score and coverage

For each concept (a lesson declares its concepts; every exercise and recall card belongs to one):

- take the **latest first-try credit** for each item - current ability, not historical average;
- **score** = weighted mean of those credits;
- **coverage** = weight of items with any evidence / weight of all the concept's items.

## 4. Levels

| Level          | Rule                                                                                            |
| -------------- | ----------------------------------------------------------------------------------------------- |
| Not started    | no evidence                                                                                     |
| Attempted      | some evidence, score below 0.6                                                                  |
| Practising     | score 0.6 or more, but not yet proficient                                                       |
| **Proficient** | score ≥ 0.8 **and** coverage ≥ 0.75 **and** an application/analysis item scored ≥ 0.8           |
| **Mastered**   | proficient **and** a review answer scoring ≥ 0.8 at least **24 hours** after the first evidence |

The content validator requires every concept of a published lesson to have at least one application or
analysis exercise, so the practical condition can always be met.

**Lessons** are _in progress_ once opened, _completed_ once marked as read with every required exercise
attempted (any score), and _mastered_ when completed and every concept is mastered. Completion means "worked
through"; mastery means "demonstrated and retained".

## 5. Spaced repetition

Leitner-style boxes, per item:

| Box     | 1     | 2      | 3      | 4       | 5       | 6       |
| ------- | ----- | ------ | ------ | ------- | ------- | ------- |
| Next in | 1 day | 3 days | 7 days | 16 days | 35 days | 90 days |

- credit ≥ 0.8 → up one box (max 6);
- 0.5 ≤ credit < 0.8 → stay (at least box 1);
- credit < 0.5 → back to box 1, and a **lapse** is counted.

Recall cards enter the queue when a lesson is marked as read (first due the next day). Exercises enter when
first attempted. Due items are **interleaved**: consecutive items come from different concepts where possible,
so similar ideas have to be told apart.

## 6. Placement (testing out)

A placement test lets a learner skip lessons they can already show they know. It is a different question from
mastery, so it has its own rules (`recordPlacement` in `src/store/state.ts`):

- Placement questions are **auto-graded only** (multiple choice, ordering, spot-the-lines) and separate from a
  lesson's practice exercises. Every concept of a published lesson has at least one.
- There are **no hints and no feedback until the end**, and "I don't know this yet" is offered to discourage
  guessing.
- A lesson is **tested out** only when **every** one of its placement questions is fully correct (score 1).
  Anything less recommends studying the lesson.
- Testing out sets the lesson status to **Tested out** - below Completed and Mastered, which a learner can still
  reach by working through the lesson. Learning paths skip tested-out lessons when suggesting what is next.
- Placement answers are **not mastery evidence**. A short test at one moment shows familiarity, not retained,
  practised ability. Instead, the lesson's recall cards enter the review queue (first due the next day), and
  those reviews _are_ evidence.
- A retake replaces the earlier result; "Study it anyway" on the lesson removes it.

## 7. Adaptive practice

- **After a wrong or partly right answer** a "To fix this" box links to the sections that teach the concept
  most specifically (sections declare `concepts`) and to a similar exercise on the same concept (untried first,
  otherwise the weakest last result). Code: `remediationFor` in `src/store/adaptive.ts`.
- **Practice sessions** (`#/practice`, or one lesson) are built from lessons the learner has engaged with:
  recognition-only or weak concepts first (with practical items first), untried concepts next, proficient ones
  last; mastered concepts and items answered in the last 10 minutes are skipped; items are interleaved across
  concepts. Each item states why it was chosen. Code: `buildPracticeSession`.
- Practice answers are first tries in a new sitting, so they are evidence. A practice or review answer of 0.8 or
  more at least 24 hours after the first evidence counts as **retention** (mode `practice` or `review`).

## 8. Interview practice

Interview practice (`#/interview`) rehearses whole interview rounds. Its scores answer "how would this round
have gone?", which is a different question from mastery, so it has its own rules (`src/store/interviews.ts`,
updates in `src/store/state.ts`):

- **Generating.** An interview follows one company profile's reported loop (`content/interviews/interviews.yaml`):
  every stage in order, optional stages included with their reported `chance`, one round type chosen per stage.
  With "any company", the company differs from the last interview for the same course; a new interview for
  the same course and company re-draws (up to 8 times) to avoid repeating the last set of round types.
- **Questions.** Each round asks `questions` items from the question bank (`content/interviews/questions/`)
  and, when the round type names `fromLessons`, from the chosen course's published lessons - about half from
  the course where it has suitable exercises (a one-question round: every other time). Bank questions marked
  with `subjects` are used only for courses _about_ one of those subjects: the subjects at least two of the
  course's lessons belong to. Questions asked in fewer earlier interviews come first, concepts vary within a
  round, and no question repeats within an interview. Generation is seeded, so it is reproducible in tests.
- **Scoring.** Raw scores and the hint penalty are the same as for exercises (section 1). Only the first answer
  to a question in an attempt counts; "Skip and show the answer" scores 0. A round's score is the average
  credit over its questions, with unanswered questions scoring 0 when the round is finished; a finished round
  is frozen. Self-assessed answers are **not** down-weighted here: most interview rounds are spoken answers, so
  a discount would only shift every round down.
- **Bands.** 85% and above **Strong** (a strong hire signal), 70% **Good** (a hire signal), 50% **Borderline**
  (a mixed signal), below that **Needs work** (no hire signal yet). They describe practice performance, not a
  prediction of any company's decision.
- **Feedback.** Answers at 85% or more are listed as strengths. The others are areas to improve, grouped by
  competency (bank questions) or lesson concept (lesson exercises), with how to improve, a link to study it and
  the rubric points the answer missed. The report compares the round with the learner's previous and best
  finished attempts at it.
- **Retakes.** "Retake the interview" or "Retake this round" starts a new attempt with the same rounds and
  questions; every attempt is kept (the last 12 per interview, the last 30 interviews) for the round-by-round
  history.
- **Not mastery evidence.** Interview answers never create attempts, reviews or lesson completion. The
  conditions differ from study (a timer, mixed topics, bank questions that belong to no lesson), and counting
  lesson exercises answered in interviews would let the same answer count twice.

## 9. Known simplifications (candidates to revisit)

- Box intervals are fixed. An SM-2/FSRS-style per-item ease factor would adapt better, but needs more data.
- Self-assessment trusts the learner. The rubric makes it concrete; honesty still matters.
- "Latest first try" can drop after one bad day. That is intended - mastery should reflect current ability.
