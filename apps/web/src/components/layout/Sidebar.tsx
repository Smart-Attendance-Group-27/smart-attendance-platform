"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { navItemsForRole } from "@/lib/navigation";
import { WebRole } from "@/lib/auth/roles";

type SidebarProps = {
  role: WebRole;
};

export function Sidebar({ role }: SidebarProps) {
  const pathname = usePathname();
  const items = navItemsForRole(role);

  return (
    <aside
      aria-label="Primary navigation"
      className="fixed inset-x-0 bottom-0 z-40 flex h-14 border-t border-[#1c2329] bg-[var(--rail)] lg:inset-x-auto lg:inset-y-0 lg:left-0 lg:top-[var(--topbar)] lg:h-auto lg:w-[var(--rail-w)] lg:flex-col lg:border-t-0 lg:border-r"
    >
      <nav className="flex w-full overflow-x-auto lg:flex-col lg:overflow-visible">
        {items.map((item) => {
          const isActive = pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              className={`group relative flex h-14 min-w-[56px] flex-1 items-center justify-center border-r border-white/5 text-[#cbd2d8] transition-colors last:border-r-0 hover:bg-[var(--rail-hover)] hover:text-white lg:h-[51px] lg:w-full lg:flex-none lg:border-r-0 lg:border-b lg:last:border-b-0 ${
                isActive
                  ? "border-l-4 border-l-[var(--uom-gold)] bg-[var(--uom-blue)] text-white"
                  : ""
              }`}
            >
              <Icon aria-hidden="true" />
              <span className="sr-only">{item.label}</span>
              <span
                role="tooltip"
                className="pointer-events-none absolute left-[62px] top-1/2 z-[80] hidden -translate-y-1/2 whitespace-nowrap bg-[#111b23] px-2.5 py-1.5 text-xs text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 lg:block"
              >
                {item.label}
              </span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
