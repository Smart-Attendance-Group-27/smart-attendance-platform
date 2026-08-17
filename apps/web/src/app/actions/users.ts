"use server";

import { revalidatePath } from "next/cache";
import { updateAccountStatus } from "@/lib/api/admin";

export type SetAccountStatusResult = { ok: true } | { ok: false; message: string };

export async function setAccountStatus(
  userId: string,
  accountStatus: "active" | "suspended",
): Promise<SetAccountStatusResult> {
  try {
    await updateAccountStatus(userId, accountStatus);
  } catch {
    return { ok: false, message: "Couldn't update this account. Please try again." };
  }

  revalidatePath("/admin/users");
  revalidatePath("/admin/dashboard");
  return { ok: true };
}
