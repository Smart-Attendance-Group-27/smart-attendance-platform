import Image from "next/image";
import uniLogo from "../../../assests/Uni.jpg";
import { AccountMenu } from "@/components/layout/AccountMenu";
import { WebRole } from "@/lib/auth/roles";

const ROLE_LABELS: Record<WebRole, string> = {
  lecturer: "Lecturer",
  administrator: "Administrator",
};

type TopBarProps = {
  userName: string;
  role: WebRole;
};

export function TopBar({ userName, role }: TopBarProps) {
  return (
    <header className="fixed inset-x-0 top-0 z-40 flex h-[var(--topbar)] items-center border-b-[3px] border-[var(--uom-gold)] bg-[var(--uom-blue)] text-white shadow-[0_1px_4px_rgba(0,0,0,0.22)]">
      <div className="flex min-w-0 items-center gap-2.5 pl-3 sm:min-w-[260px]">
        <Image
          alt="University logo"
          className="h-9 w-9 shrink-0 rounded-full object-cover ring-2 ring-white/70"
          priority
          src={uniLogo}
        />
        <div className="hidden leading-tight sm:block">
          <strong className="block text-base font-semibold">Smart Attendance</strong>
          <span className="mt-0.5 block text-[11px] text-[#dceaf4]">UniAttend Dashboard</span>
        </div>
      </div>

      <div className="ml-auto flex h-full items-center gap-1 pr-3">
        <AccountMenu name={userName} roleLabel={ROLE_LABELS[role]} />
      </div>
    </header>
  );
}
