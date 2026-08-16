import { ComponentType } from "react";
import {
  AdminIcon,
  CoursesIcon,
  IconProps,
  OverviewIcon,
  ReportsIcon,
  ReviewIcon,
  SessionsIcon,
} from "@/components/icons";
import { WebRole } from "@/lib/auth/roles";

export type NavItem = {
  href: string;
  label: string;
  icon: ComponentType<IconProps>;
};

export const LECTURER_NAV_ITEMS: NavItem[] = [
  { href: "/lecturer/dashboard", label: "Overview", icon: OverviewIcon },
  { href: "/lecturer/courses", label: "Courses", icon: CoursesIcon },
  { href: "/lecturer/sessions", label: "Sessions", icon: SessionsIcon },
  { href: "/lecturer/review", label: "Verification review", icon: ReviewIcon },
  { href: "/lecturer/reports", label: "Reports", icon: ReportsIcon },
];

export const ADMIN_NAV_ITEMS: NavItem[] = [
  { href: "/admin/dashboard", label: "Administration", icon: AdminIcon },
];

export function navItemsForRole(role: WebRole): NavItem[] {
  return role === "administrator" ? ADMIN_NAV_ITEMS : LECTURER_NAV_ITEMS;
}

export function pageTitleForPath(role: WebRole, pathname: string): string {
  const items = navItemsForRole(role);
  const match = items.find((item) => pathname.startsWith(item.href));
  return match?.label ?? "Overview";
}
