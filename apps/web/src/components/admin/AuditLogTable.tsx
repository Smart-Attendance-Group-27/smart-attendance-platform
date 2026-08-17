"use client";

import { useMemo, useState } from "react";
import { Card } from "@/components/ui/Card";
import { FilterBar, SearchInput, FilterSelect } from "@/components/ui/FilterBar";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { auditOutcomeDisplay } from "@/lib/status";
import { AuditLogEntry } from "@/types/admin";

export function AuditLogTable({ entries }: { entries: AuditLogEntry[] }) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return entries;
    return entries.filter(
      (row) =>
        row.actorName.toLowerCase().includes(normalized) ||
        row.action.toLowerCase().includes(normalized) ||
        row.entityLabel.toLowerCase().includes(normalized),
    );
  }, [entries, query]);

  return (
    <Card flush>
      <FilterBar>
        <FilterSelect>
          <option>All actors</option>
        </FilterSelect>
        <FilterSelect>
          <option>All action types</option>
        </FilterSelect>
        <SearchInput
          placeholder="Search actor, action, or resource"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </FilterBar>
      <DataTable<AuditLogEntry>
        emptyTitle="No matching audit records"
        columns={[
          { key: "time", header: "Time", render: (row) => row.occurredAtLabel },
          {
            key: "actor",
            header: "Actor",
            render: (row) => <CellPrimary primary={row.actorName} secondary={row.actorRole} />,
          },
          { key: "action", header: "Action", render: (row) => row.action },
          {
            key: "entity",
            header: "Resource",
            render: (row) => <CellPrimary primary={row.entityLabel} secondary={row.entityType} />,
          },
          {
            key: "outcome",
            header: "Outcome",
            render: (row) => {
              const display = auditOutcomeDisplay(row.outcome);
              return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
            },
          },
        ]}
        rows={filtered}
        getRowKey={(row) => row.id}
      />
    </Card>
  );
}
