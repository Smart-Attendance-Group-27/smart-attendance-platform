export type PushRegistrationStatus =
  | 'checking'
  | 'registered'
  | 'permission-denied'
  | 'not-a-physical-device'
  | 'unsupported-platform'
  | 'error';

let status: PushRegistrationStatus = 'checking';
const listeners = new Set<() => void>();

export function getPushRegistrationStatus(): PushRegistrationStatus {
  return status;
}

export function subscribePushRegistrationStatus(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function setPushRegistrationStatus(next: PushRegistrationStatus): void {
  status = next;
  for (const listener of listeners) listener();
}
