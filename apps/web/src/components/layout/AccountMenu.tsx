"use client";

import { useRef } from "react";
import { ChevronDownIcon, LogOutIcon } from "@/components/icons";
import { signOut } from "@/app/actions/auth";

type AccountMenuProps = {
  name: string;
  roleLabel: string;
};

function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.slice(-2).map((part) => part[0]?.toUpperCase() ?? "");
  return letters.join("") || "?";
}

export function AccountMenu({ name, roleLabel }: AccountMenuProps) {
  const detailsRef = useRef<HTMLDetailsElement>(null);

  return (
    <details ref={detailsRef} className="relative">
      <summary
        aria-label="Open profile menu"
        className="flex h-[42px] cursor-pointer list-none items-center gap-2.5 rounded-sm px-2 text-white marker:content-none hover:bg-black/15 [&::-webkit-details-marker]:hidden"
      >
        <span className="grid h-[30px] w-[30px] place-items-center rounded-full border border-white/65 bg-[#f4f6f8] text-[11px] font-bold text-[var(--uom-blue)]">
          {initialsFor(name)}
        </span>
        <span className="hidden text-left sm:block">
          <strong className="block text-xs font-semibold leading-tight">{name}</strong>
          <small className="mt-0.5 block text-[10px] text-[#dceaf4]">{roleLabel}</small>
        </span>
        <ChevronDownIcon aria-hidden="true" />
      </summary>
      <div className="absolute right-0 top-[calc(100%+6px)] w-56 border border-[var(--line)] bg-[var(--surface)] py-1.5 text-[var(--text)] shadow-lg">
        <div className="border-b border-[var(--line-soft)] px-3.5 py-2.5">
          <p className="text-sm font-semibold">{name}</p>
          <p className="text-xs text-[var(--muted)]">{roleLabel}</p>
        </div>
        <form action={signOut}>
          <button
            type="submit"
            className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-sm text-[var(--text)] hover:bg-[var(--page)]"
          >
            <LogOutIcon aria-hidden="true" width={16} height={16} />
            Sign out
          </button>
        </form>
      </div>
    </details>
  );
}
