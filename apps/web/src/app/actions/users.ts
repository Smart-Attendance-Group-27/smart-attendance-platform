"use server";

import { revalidatePath } from "next/cache";
import {
  provisionAccount as provisionAccountRequest,
  updateAccountStatus,
  type ApiAccountProvisionRequest,
  type ApiProvisionedAccount,
} from "@/lib/api/admin";
import { CoreBackendError } from "@/lib/api/coreBackend";

export type SetAccountStatusResult = { ok: true } | { ok: false; message: string };
export type ProvisionAccountResult =
  | { ok: true; account: ApiProvisionedAccount }
  | { ok: false; message: string };

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

export async function provisionAccount(
  payload: ApiAccountProvisionRequest,
): Promise<ProvisionAccountResult> {
  try {
    const account = await provisionAccountRequest(payload);
    revalidatePath("/admin/users");
    revalidatePath("/admin/dashboard");
    return { ok: true, account };
  } catch (error) {
    return {
      ok: false,
      message:
        error instanceof CoreBackendError
          ? error.message
          : "Couldn't provision this account. Please try again.",
    };
  }
}
