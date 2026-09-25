export const TAB_BAR_CONTENT_HEIGHT = 64;

// The tab bar's own height must include the bottom safe-area inset. A fixed
// height alone leaves the labels underneath the gesture or navigation bar.
export function getTabBarHeight(bottomInset: number): number {
  return TAB_BAR_CONTENT_HEIGHT + Math.max(0, bottomInset);
}
