import { cleanup, render, screen } from '@testing-library/preact';
import { afterEach, describe, expect, it } from 'vitest';
import { ProgressProvider } from '../../src/store/ProgressContext';
import { PlacementPage } from '../../src/ui/pages/PlacementPage';
import { memoryStore, realIndex } from './helpers';

afterEach(cleanup);

describe('PlacementPage', () => {
  it('says so when a path has no placement questions yet', () => {
    const real = realIndex();
    // Only planned lessons, so no placement questions - real paths always have some.
    const planned = [...real.refs.values()].filter((ref) => ref.planned).map((ref) => ref.id);
    const index = {
      ...real,
      curriculum: {
        ...real.curriculum,
        paths: [
          ...real.curriculum.paths,
          {
            id: 'planned-only',
            title: 'Planned only',
            level: 'beginner' as const,
            summary: 'S',
            lessons: planned,
          },
        ],
      },
    };
    render(
      <ProgressProvider store={memoryStore()} now={() => new Date('2026-10-01T09:00:00.000Z')}>
        <PlacementPage index={index} kind="path" id="planned-only" />
      </ProgressProvider>,
    );
    expect(screen.getByRole('heading', { level: 1, name: 'Placement test: Planned only' })).toBeTruthy();
    expect(screen.getByText('There are no placement questions for this path yet.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Browse the curriculum' })).toBeTruthy();
  });
});
