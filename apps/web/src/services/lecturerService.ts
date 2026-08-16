import "server-only";
import { mockDelay } from "@/lib/mockDelay";
import {
  MOCK_LECTURER_COURSES,
  MOCK_LECTURER_OVERVIEW,
  MOCK_LECTURER_REPORTS,
  MOCK_REVIEW_CASES,
  MOCK_SESSION_DETAILS,
  MOCK_SESSION_LIST,
} from "@/mocks/lecturer";
import {
  LecturerCoursesData,
  LecturerOverview,
  LecturerReportsData,
  ReviewCase,
  SessionDetail,
  TodayLecture,
} from "@/types/lecturer";

// Every export here is backed by mock data (see apps/web/src/mocks/lecturer.ts) — no
// lecturer-facing backend endpoints exist yet. Callers (Server Components, actions)
// depend only on these function signatures, so swapping a function's body for a real
// `fetch` against core-backend won't require touching any page.

export async function getLecturerOverview(): Promise<LecturerOverview> {
  return mockDelay(MOCK_LECTURER_OVERVIEW);
}

export async function getLecturerCourses(): Promise<LecturerCoursesData> {
  return mockDelay(MOCK_LECTURER_COURSES);
}

export async function getSessionList(): Promise<TodayLecture[]> {
  return mockDelay(MOCK_SESSION_LIST);
}

export async function getSessionDetail(sessionId: string): Promise<SessionDetail | null> {
  return mockDelay(MOCK_SESSION_DETAILS[sessionId] ?? null);
}

export async function getReviewCases(): Promise<ReviewCase[]> {
  return mockDelay(MOCK_REVIEW_CASES);
}

export async function getLecturerReports(): Promise<LecturerReportsData> {
  return mockDelay(MOCK_LECTURER_REPORTS);
}
