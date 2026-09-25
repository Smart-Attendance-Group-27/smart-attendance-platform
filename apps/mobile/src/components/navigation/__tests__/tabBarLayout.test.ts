import { describe, expect, test } from '@jest/globals';

import { getTabBarHeight, TAB_BAR_CONTENT_HEIGHT } from '../tabBarLayout';

describe('getTabBarHeight', () => {
  test('keeps the base height on devices without a bottom inset', () => {
    expect(getTabBarHeight(0)).toBe(TAB_BAR_CONTENT_HEIGHT);
  });

  test('adds the bottom safe-area inset so tab labels clear the system bar', () => {
    expect(getTabBarHeight(24)).toBe(TAB_BAR_CONTENT_HEIGHT + 24);
  });

  test('ignores a negative inset', () => {
    expect(getTabBarHeight(-5)).toBe(TAB_BAR_CONTENT_HEIGHT);
  });
});
