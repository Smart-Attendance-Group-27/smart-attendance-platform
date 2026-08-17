// Small simulated network latency so the service layer behaves like a real fetch
// (and Stage 5's loading states have something real to show). Remove once a call
// site is backed by an actual fetch to core-backend.
export function mockDelay<T>(value: T, ms = 150): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}
