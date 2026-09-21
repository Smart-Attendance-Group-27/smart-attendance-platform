"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export function SessionLiveRefresh() {
  const router = useRouter();

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") router.refresh();
    }, 15_000);
    return () => window.clearInterval(timer);
  }, [router]);

  return <p className="text-xs text-[var(--muted)]">Live counts refresh every 15 seconds.</p>;
}
