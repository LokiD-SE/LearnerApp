import { describe, expect, it } from 'vitest';
import {
  PINS_KEY,
  isValidPin,
  resetRequestLink,
  setPin,
  verifyPin,
  verifyRecoveryKey,
} from '../../src/security/pin';
import { memoryStore as helperStore } from './helpers';

const memoryStore = () => {
  const store = helperStore();
  return { data: store.data, store };
};

describe('profile PINs', () => {
  it('uses 2030 by default and 4568 for Loki and Gayu', async () => {
    const { store } = memoryStore();
    for (const id of ['kishore', 'saurabh', 'raji', 'priya']) {
      expect(await verifyPin(store, id, '2030')).toBe(true);
      expect(await verifyPin(store, id, '4568')).toBe(false);
    }
    for (const id of ['loki', 'gayu']) {
      expect(await verifyPin(store, id, '4568')).toBe(true);
      expect(await verifyPin(store, id, '2030')).toBe(false);
    }
  });

  it('accepts only 4 digits', () => {
    expect(isValidPin('2030')).toBe(true);
    for (const bad of ['203', '20301', 'abcd', ' 2030', '']) expect(isValidPin(bad)).toBe(false);
  });

  it('saves a changed PIN as a salted hash, never the PIN itself', async () => {
    const { data, store } = memoryStore();
    expect(await setPin(store, 'raji', '1234')).toBe(true);
    expect(await verifyPin(store, 'raji', '1234')).toBe(true);
    expect(await verifyPin(store, 'raji', '2030')).toBe(false);
    expect(await verifyPin(store, 'kishore', '2030')).toBe(true);
    expect(data[PINS_KEY]).not.toContain('1234');
  });

  it('rejects a wrong recovery key', async () => {
    expect(await verifyRecoveryKey('AAAA-BBBB-CCCC')).toBe(false);
    expect(await verifyRecoveryKey('')).toBe(false);
  });

  it('builds the reset email to the recovery address', () => {
    expect(resetRequestLink('Gayu')).toMatch(
      /^mailto:lokeshdevamuthu@gmail\.com\?subject=LearnerApp%20PIN%20reset%20-%20Gayu/,
    );
  });
});
