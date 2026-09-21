import { myAttendanceFixtures } from './myAttendance';
import type { MyAttendance } from '../types/myAttendance';

const states: Record<string, MyAttendance> = { ...myAttendanceFixtures };

export function resetMockAttendanceStore(): void {
  for (const key of Object.keys(states)) delete states[key];
  Object.assign(states, myAttendanceFixtures);
}

export function getMockAttendance(sessionId: string): MyAttendance | undefined {
  return states[sessionId];
}

export function markMockGeofencePassed(sessionId: string): MyAttendance | undefined {
  const state = states[sessionId];
  if (!state) return undefined;
  const next: MyAttendance = {
    ...state,
    verification: { ...state.verification, attemptStatus: 'in_progress', geofenceStatus: 'passed' },
  };
  states[sessionId] = next;
  return next;
}

export function markMockFacePassed(sessionId: string): void {
  const state = states[sessionId];
  if (!state) return;
  states[sessionId] = {
    ...state,
    canStartCheckIn: false,
    verification: { ...state.verification, attemptStatus: 'checked_in', faceStatus: 'passed' },
    initialCheckIn: { status: 'checked_in', checkedInAt: '2026-07-20T10:04:00+05:30' },
  };
}
