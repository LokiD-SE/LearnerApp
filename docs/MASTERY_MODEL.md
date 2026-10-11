# Mastery model

One right answer is not mastery. LearnerApp distinguishes **familiarity** (I recognise it) from
**demonstrated ability** (I can apply it, and I still can a day later). The rules are implemented in
`src/domain/grading.ts`, `src/domain/mastery.ts` and `src/domain/srs.ts`, and unit-tested in `tests/unit/`.
Change the code and this document together.

## 1. Evidence

Every answer is an **attempt**, with a raw score from 0 to 1:

| Exercise type                        | Graded by                         | Raw score                                               |
| ------------------------------------ | --------------------------------- | ------------------------------------------------------- |
| Multiple choice / "pick the lines"   | the app                           | (right picks - wrong picks) / right answers, at least 0 |
| Put in order                         | the app                           | share of items in the correct position                  |
| Short answer, test design, interview | **the learner**, against a rubric | share of rubric points the learner ticks                |
| Recall card                          | **the learner**                   | Didn't know it = 0, Partly = 0.6, Knew it = 1           |

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

## 7. Known simplifications (candidates to revisit)

- Box intervals are fixed. An SM-2/FSRS-style per-item ease factor would adapt better, but needs more data.
- Self-assessment trusts the learner. The rubric makes it concrete; honesty still matters.
- "Latest first try" can drop after one bad day. That is intended - mastery should reflect current ability.
