"use server";

import { mockDelay } from "@/lib/mockDelay";

export type ReviewDecisionKind = "approve" | "reject" | "retry" | "escalate";

export type ReviewDecisionResult = {
  ok: true;
  caseId: string;
  decision: ReviewDecisionKind;
};

// MOCK: no manual-review endpoint exists on core-backend yet (services/core-backend has
// no `attendance_verification.manual_reviews` route). This still runs a real client -> server
// round trip via the Server Action protocol, so ReviewWorkspace.tsx doesn't need to change
// when a real POST to that endpoint replaces the mockDelay() call below. The mock case list
// isn't mutated server-side, so a page refresh currently resets it — that's the one gap a
// real backend closes.
export async function submitReviewDecision(
  caseId: string,
  decision: ReviewDecisionKind,
  reason?: string,
): Promise<ReviewDecisionResult> {
  void reason;
  return mockDelay({ ok: true, caseId, decision }, 200);
}
