"use server";

import { revalidatePath } from "next/cache";
import { postManualReviewDecision } from "@/lib/api/lecturer";

export type ReviewDecisionKind = "approve" | "reject" | "retry" | "escalate";

export type ReviewDecisionResult = {
  ok: true;
  caseId: string;
  decision: ReviewDecisionKind;
};

export async function submitReviewDecision(
  caseId: string,
  decision: ReviewDecisionKind,
  reason?: string,
): Promise<ReviewDecisionResult> {
  await postManualReviewDecision(caseId, decision, reason);
  revalidatePath("/lecturer/review");
  revalidatePath("/lecturer/dashboard");
  return { ok: true, caseId, decision };
}
