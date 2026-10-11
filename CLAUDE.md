# LearnerApp - notes for Claude Code

Static Vite + TypeScript + Preact app; content in `content/*.yaml`; progress in localStorage. Read `README.md`,
`docs/ARCHITECTURE.md`, `docs/MASTERY_MODEL.md` and `docs/CONTENT_GUIDE.md` before changing behaviour or content.

- Use Node from `.nvmrc` (`nvm use`); system Node may be too old.
- Before finishing any change run `npm run check` (typecheck, lint, format, unit, build, e2e). Never claim a
  check passed without running it.
- Content changes: follow the accuracy rules in `docs/CONTENT_GUIDE.md` - never invent APIs, commands, status
  codes or provider behaviour; label provider/platform/version-specific facts; fictional SandPay only.
- Progress changes go through pure functions in `src/store/state.ts`; bump `STATE_VERSION` and add a migration
  in `src/store/storage.ts` if the stored shape changes.
- Mastery/grading/SRS rule changes must update `docs/MASTERY_MODEL.md` and the unit tests together.
- Keep the UI content-agnostic: a new lesson must never need UI code.
