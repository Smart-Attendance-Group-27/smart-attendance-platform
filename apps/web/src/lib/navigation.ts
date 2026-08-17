import { ComponentType } from "react";
import {
  AdminIcon,
  AuditIcon,
  BuildingIcon,
  CoursesIcon,
  IconProps,
  OverviewIcon,
  ReportsIcon,
  ReviewIcon,
  SessionsIcon,
  UsersIcon,
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
  { href: "/admin/dashboard", label: "Overview", icon: OverviewIcon },
  { href: "/admin/users", label: "Users", icon: UsersIcon },
  { href: "/admin/academic", label: "Academic data", icon: CoursesIcon },
  { href: "/admin/classrooms", label: "Classrooms", icon: BuildingIcon },
  { href: "/admin/policies", label: "Policies", icon: AdminIcon },
  { href: "/admin/reports", label: "Reports", icon: ReportsIcon },
  { href: "/admin/audit", label: "Audit log", icon: AuditIcon },
];

export function navItemsForRole(role: WebRole): NavItem[] {
  return role === "administrator" ? ADMIN_NAV_ITEMS : LECTURER_NAV_ITEMS;
}

export function pageTitleForPath(role: WebRole, pathname: string): string {
  const items = navItemsForRole(role);
  const match = items.find((item) => pathname.startsWith(item.href));
  return match?.label ?? "Overview";
}
