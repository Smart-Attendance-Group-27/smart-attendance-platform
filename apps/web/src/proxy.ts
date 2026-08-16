import { NextRequest, NextResponse } from "next/server";
import { decryptSession, SESSION_COOKIE_NAME } from "@/lib/auth/session";
import { dashboardPathForRole } from "@/lib/auth/roles";

// Optimistic (cookie-only) checks, per Next.js's recommended two-layer auth model.
// The authoritative check lives in each role's layout.tsx via requireRole() (lib/auth/dal.ts).
export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const session = await decryptSession(request.cookies.get(SESSION_COOKIE_NAME)?.value);

  const isLecturerRoute = pathname.startsWith("/lecturer");
  const isAdminRoute = pathname.startsWith("/admin");

  if ((isLecturerRoute || isAdminRoute) && !session) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (session && isLecturerRoute && session.role !== "lecturer") {
    return NextResponse.redirect(new URL(dashboardPathForRole(session.role), request.url));
  }

  if (session && isAdminRoute && session.role !== "administrator") {
    return NextResponse.redirect(new URL(dashboardPathForRole(session.role), request.url));
  }

  if (session && pathname === "/login") {
    return NextResponse.redirect(new URL(dashboardPathForRole(session.role), request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
