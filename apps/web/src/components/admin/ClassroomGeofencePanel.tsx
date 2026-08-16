"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { classroomStatusDisplay } from "@/lib/status";
import { Classroom } from "@/types/admin";

export function ClassroomGeofencePanel({ classrooms }: { classrooms: Classroom[] }) {
  const [selectedId, setSelectedId] = useState(classrooms[0]?.classroomId ?? null);
  const selected = classrooms.find((room) => room.classroomId === selectedId) ?? null;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      <div className="lg:col-span-7">
        <Card
          title="Classrooms and geofences"
          className="border-l-4 border-l-[var(--uom-gold)]"
          flush
          actions={
            <Button title="Available once classroom management API is integrated" disabled>
              Add classroom
            </Button>
          }
        >
          <DataTable<Classroom>
            emptyTitle="No classrooms configured yet"
            columns={[
              { key: "room", header: "Room", render: (row) => <span className="font-semibold text-[var(--link)]">{row.room}</span> },
              { key: "building", header: "Building", render: (row) => row.building },
              { key: "radius", header: "Radius", render: (row) => `${row.defaultGeofenceRadiusMeters} m` },
              { key: "courses", header: "Assigned courses", render: (row) => row.assignedCoursesCount },
              {
                key: "status",
                header: "Status",
                render: (row) => {
                  const display = classroomStatusDisplay(row.status);
                  return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
                },
              },
            ]}
            rows={classrooms}
            getRowKey={(row) => row.classroomId}
            onRowClick={(row) => setSelectedId(row.classroomId)}
          />
        </Card>
      </div>

      <div className="lg:col-span-5">
        <Card
          title={selected ? `Selected geofence · ${selected.room}` : "Selected geofence"}
          className="border-l-4 border-l-[var(--uom-gold)]"
          actions={
            <Button title="Available once geofence management API is integrated" disabled>
              Edit
            </Button>
          }
        >
          {!selected ? (
            <p className="p-6 text-center text-xs text-[var(--muted)]">Select a classroom to preview its geofence.</p>
          ) : (
            <div
              className="relative h-[310px] overflow-hidden bg-[#edf1f3]"
              style={{
                backgroundImage:
                  "linear-gradient(#d9dfe4 1px, transparent 1px), linear-gradient(90deg, #d9dfe4 1px, transparent 1px)",
                backgroundSize: "28px 28px",
              }}
            >
              <div className="absolute left-1/2 top-1/2 grid h-[190px] w-[190px] -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-2 border-dashed border-[var(--uom-blue)] bg-[var(--uom-blue)]/10">
                <div className="grid h-[100px] w-[100px] place-items-center border-2 border-[var(--uom-blue)] bg-white/50 text-center text-xs font-semibold text-[var(--uom-blue)]">
                  {selected.room}
                  <br />
                  {selected.defaultGeofenceRadiusMeters} m radius
                </div>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
