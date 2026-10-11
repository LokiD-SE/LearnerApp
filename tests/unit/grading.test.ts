import { describe, expect, it } from 'vitest';
import { creditFor, gradeOrder, gradeRubric, gradeSelection } from '../../src/domain/grading';

describe('gradeSelection', () => {
  it('gives full marks for exactly the right set', () => {
    expect(gradeSelection(['a', 'c'], ['c', 'a']).score).toBe(1);
  });
  it('gives partial credit for some right picks and none for nothing right', () => {
    expect(gradeSelection(['a'], ['a', 'b']).score).toBe(0.5);
    expect(gradeSelection(['x'], ['a']).score).toBe(0);
  });
  it('cancels a right pick with a wrong one and never goes below zero', () => {
    const result = gradeSelection(['a', 'x'], ['a', 'b']);
    expect(result.score).toBe(0);
    expect(result).toMatchObject({ hits: ['a'], wrong: ['x'], missed: ['b'] });
    expect(gradeSelection(['x', 'y', 'z'], ['a']).score).toBe(0);
  });
  it('does not reward selecting everything', () => {
    expect(gradeSelection(['a', 'b', 'c', 'd'], ['a', 'b']).score).toBe(0);
  });
});

describe('gradeOrder', () => {
  it('scores the share of items in their correct position', () => {
    expect(gradeOrder(['a', 'b', 'c', 'd'], ['a', 'b', 'c', 'd'])).toBe(1);
    expect(gradeOrder(['a', 'b', 'd', 'c'], ['a', 'b', 'c', 'd'])).toBe(0.5);
    expect(gradeOrder(['b', 'a'], ['a', 'b'])).toBe(0);
  });
  it('rejects a submission of the wrong length', () => {
    expect(gradeOrder(['a'], ['a', 'b'])).toBe(0);
  });
});

describe('gradeRubric', () => {
  it('is the covered share, clamped to 0..1', () => {
    expect(gradeRubric(3, 4)).toBe(0.75);
    expect(gradeRubric(5, 4)).toBe(1);
    expect(gradeRubric(-1, 4)).toBe(0);
    expect(gradeRubric(1, 0)).toBe(0);
  });
});

describe('creditFor', () => {
  it('removes 15% per hint, at most 45%', () => {
    expect(creditFor(1, 0)).toBe(1);
    expect(creditFor(1, 1)).toBe(0.85);
    expect(creditFor(1, 2)).toBe(0.7);
    expect(creditFor(1, 3)).toBe(0.55);
    expect(creditFor(1, 10)).toBe(0.55);
    expect(creditFor(0.5, 1)).toBe(0.425);
  });
  it('clamps out-of-range scores', () => {
    expect(creditFor(2, 0)).toBe(1);
    expect(creditFor(-1, 0)).toBe(0);
  });
});
