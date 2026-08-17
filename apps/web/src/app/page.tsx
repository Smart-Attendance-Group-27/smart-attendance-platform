import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/auth/dal";
import { dashboardPathForRole } from "@/lib/auth/roles";

export default async function RootPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  redirect(dashboardPathForRole(user.role));
}
