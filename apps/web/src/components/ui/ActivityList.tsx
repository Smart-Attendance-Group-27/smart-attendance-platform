import { ReactNode } from "react";

export type ActivityItem = {
  id: string;
  time: string;
  title: string;
  detail?: string;
  status?: ReactNode;
};

type ActivityListProps = {
  items: ActivityItem[];
};

export function ActivityList({ items }: ActivityListProps) {
  return (
    <ul className="list-none p-0">
      {items.map((item) => (
        <li
          key={item.id}
          className="grid grid-cols-[64px_1fr_auto] items-start gap-3 border-b border-[var(--line-soft)] py-2.5 last:border-b-0"
        >
          <span className="text-[11px] text-[var(--muted)]">{item.time}</span>
          <span className="text-xs leading-snug">
            <strong className="font-semibold">{item.title}</strong>
            {item.detail ? <small className="mt-1 block text-[var(--muted)]">{item.detail}</small> : null}
          </span>
          {item.status ? <span>{item.status}</span> : null}
        </li>
      ))}
    </ul>
  );
}
