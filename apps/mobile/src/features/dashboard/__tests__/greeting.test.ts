import { describe, expect, test } from '@jest/globals';

import { formatGreeting, getGreeting } from '../utils/greeting';

const at = (hour: number, minute = 0) => new Date(2026, 0, 15, hour, minute);

describe('getGreeting', () => {
  test.each([
    [5, 0, 'Good morning'],
    [11, 59, 'Good morning'],
    [12, 0, 'Good afternoon'],
    [16, 59, 'Good afternoon'],
    [17, 0, 'Good evening'],
    [20, 59, 'Good evening'],
    [21, 0, 'Good night'],
    [0, 0, 'Good night'],
    [4, 59, 'Good night'],
  ])('%i:%i -> %s', (hour, minute, expected) => {
    expect(getGreeting(at(hour, minute))).toBe(expected);
  });
});

describe('formatGreeting', () => {
  test('includes the name once it is known', () => {
    expect(formatGreeting('Nimal', at(14))).toBe('Good afternoon, Nimal');
  });

  test('omits the name while it is still loading', () => {
    expect(formatGreeting('', at(14))).toBe('Good afternoon');
    expect(formatGreeting(undefined, at(14))).toBe('Good afternoon');
    expect(formatGreeting('   ', at(14))).toBe('Good afternoon');
  });
});
