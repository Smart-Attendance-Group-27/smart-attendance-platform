"use server";

import { revalidatePath } from "next/cache";
import { postManualReviewDecision } from "@/lib/api/lecturer";
import type { ApiManualReviewDecisionRequest } from "@/lib/api/lecturer";

export type ReviewDecisionKind = ApiManualReviewDecisionRequest["decision"];
export type ReviewDecisionInput = ApiManualReviewDecisionRequest;

export type ReviewDecisionResult = {
  ok: true;
  caseId: string;
  decision: ReviewDecisionKind;
};

export async function submitReviewDecision(
  caseId: string,
  input: ReviewDecisionInput,
): Promise<ReviewDecisionResult> {
  if (typeof caseId !== "string" || !caseId.trim()) {
    throw new Error("Select a verification case.");
  }
  if (!input || (input.decision !== "approve" && input.decision !== "reject")) {
    throw new Error("Choose Approve or Reject.");
  }
  const reason = typeof input.reason === "string" ? input.reason.trim() : "";
  if (reason.length < 3 || reason.length > 500) {
    throw new Error("Reason must be between 3 and 500 characters.");
  }

  let body: ApiManualReviewDecisionRequest;
  if (input.decision === "approve") {
    if (input.attendanceStatus !== "present" && input.attendanceStatus !== "late") {
      throw new Error("Choose Present or Late before approving attendance.");
    }
    body = { decision: "approve", attendanceStatus: input.attendanceStatus, reason };
  } else {
    if ("attendanceStatus" in input) {
      throw new Error("Reject must not include an attendance status.");
    }
    body = { decision: "reject", reason };
  }

  await postManualReviewDecision(caseId, body);
  revalidatePath("/lecturer/review");
  revalidatePath("/lecturer/dashboard");
  return { ok: true, caseId, decision: body.decision };
}
