"use client";

import { FormEvent, useMemo, useState } from "react";
import { Card } from "@/components/ui/Card";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";
import { classroomStatusDisplay } from "@/lib/status";
import { Classroom } from "@/types/admin";

type FormState = {
  classroomCode: string;
  room: string;
  building: string;
  floorNumber: string;
  capacity: string;
  latitude: string;
  longitude: string;
  radius: string;
};

const EMPTY_FORM: FormState = {
  classroomCode: "",
  room: "",
  building: "",
  floorNumber: "",
  capacity: "",
  latitude: "",
  longitude: "",
  radius: "",
};

function classroomToForm(classroom: Classroom): FormState {
  return {
    classroomCode: classroom.classroomCode,
    room: classroom.room,
    building: classroom.building,
    floorNumber: String(classroom.floorNumber),
    capacity: String(classroom.capacity),
    latitude: String(classroom.latitude),
    longitude: String(classroom.longitude),
    radius: String(classroom.defaultGeofenceRadiusMeters),
  };
}

function validate(form: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!form.classroomCode.trim()) errors.classroomCode = "Classroom code is required.";
  if (!form.room.trim()) errors.room = "Room name is required.";
  if (!form.building.trim()) errors.building = "Building is required.";

  const lat = Number(form.latitude);
  if (form.latitude.trim() === "" || Number.isNaN(lat)) {
    errors.latitude = "Latitude is required.";
  } else if (lat < -90 || lat > 90) {
    errors.latitude = "Latitude must be between -90 and 90.";
  }

  const lng = Number(form.longitude);
  if (form.longitude.trim() === "" || Number.isNaN(lng)) {
    errors.longitude = "Longitude is required.";
  } else if (lng < -180 || lng > 180) {
    errors.longitude = "Longitude must be between -180 and 180.";
  }

  const radius = Number(form.radius);
  if (form.radius.trim() === "" || Number.isNaN(radius)) {
    errors.radius = "Radius is required.";
  } else if (radius <= 0) {
    errors.radius = "Radius must be greater than 0.";
  }

  return errors;
}

export function ClassroomsWorkspace({ classrooms }: { classrooms: Classroom[] }) {
  const [dialogMode, setDialogMode] = useState<"none" | "create" | "edit">("none");
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [touched, setTouched] = useState(false);

  const errors = useMemo(() => validate(form), [form]);
  const hasErrors = Object.keys(errors).length > 0;

  function openCreate() {
    setForm(EMPTY_FORM);
    setTouched(false);
    setDialogMode("create");
  }

  function openEdit(classroom: Classroom) {
    setForm(classroomToForm(classroom));
    setTouched(false);
    setDialogMode("edit");
  }

  function closeDialog() {
    setDialogMode("none");
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    // MOCK: no classroom-administration API exists yet — validation runs for real,
    // but there is nothing to persist to, so the Save action stays disabled below.
  }

  function updateField<K extends keyof FormState>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <>
      <Card
        title="Classrooms and geofences"
        flush
        actions={<Button variant="primary" onClick={openCreate}>Add classroom</Button>}
      >
        <DataTable<Classroom>
          emptyTitle="No classrooms configured yet"
          columns={[
            { key: "code", header: "Code", render: (row) => <span className="font-semibold text-[var(--link)]">{row.classroomCode}</span> },
            {
              key: "room",
              header: "Room",
              render: (row) => <CellPrimary primary={row.room} secondary={row.building} />,
            },
            { key: "capacity", header: "Capacity", render: (row) => row.capacity },
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
            {
              key: "action",
              header: "Action",
              align: "right",
              render: (row) => <Button onClick={() => openEdit(row)}>Edit</Button>,
            },
          ]}
          rows={classrooms}
          getRowKey={(row) => row.classroomId}
        />
      </Card>

      <Dialog
        open={dialogMode !== "none"}
        title={dialogMode === "edit" ? "Edit classroom" : "Add classroom"}
        onClose={closeDialog}
      >
        <form onSubmit={handleSubmit} noValidate>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <FormField label="Classroom code" htmlFor="classroomCode">
              <input
                id="classroomCode"
                className={fieldInputClassName()}
                value={form.classroomCode}
                onChange={(event) => updateField("classroomCode", event.target.value)}
              />
              {touched && errors.classroomCode ? <p className="mt-1 text-[10px] text-[var(--danger)]">{errors.classroomCode}</p> : null}
            </FormField>
            <FormField label="Room name" htmlFor="room">
              <input
                id="room"
                className={fieldInputClassName()}
                value={form.room}
                onChange={(event) => updateField("room", event.target.value)}
              />
              {touched && errors.room ? <p className="mt-1 text-[10px] text-[var(--danger)]">{errors.room}</p> : null}
            </FormField>
            <FormField label="Building" htmlFor="building">
              <input
                id="building"
                className={fieldInputClassName()}
                value={form.building}
                onChange={(event) => updateField("building", event.target.value)}
              />
              {touched && errors.building ? <p className="mt-1 text-[10px] text-[var(--danger)]">{errors.building}</p> : null}
            </FormField>
            <FormField label="Floor" htmlFor="floorNumber">
              <input
                id="floorNumber"
                type="number"
                className={fieldInputClassName()}
                value={form.floorNumber}
                onChange={(event) => updateField("floorNumber", event.target.value)}
              />
            </FormField>
            <FormField label="Capacity" htmlFor="capacity">
              <input
                id="capacity"
                type="number"
                min={1}
                className={fieldInputClassName()}
                value={form.capacity}
                onChange={(event) => updateField("capacity", event.target.value)}
              />
            </FormField>
            <FormField label="Geofence radius (m)" htmlFor="radius" help="Must be greater than 0.">
              <input
                id="radius"
                type="number"
                step="any"
                className={fieldInputClassName()}
                value={form.radius}
                onChange={(event) => updateField("radius", event.target.value)}
              />
              {touched && errors.radius ? <p className="mt-1 text-[10px] text-[var(--danger)]">{errors.radius}</p> : null}
            </FormField>
            <FormField label="Latitude" htmlFor="latitude" help="Between -90 and 90.">
              <input
                id="latitude"
                type="number"
                step="any"
                className={fieldInputClassName()}
                value={form.latitude}
                onChange={(event) => updateField("latitude", event.target.value)}
              />
              {touched && errors.latitude ? <p className="mt-1 text-[10px] text-[var(--danger)]">{errors.latitude}</p> : null}
            </FormField>
            <FormField label="Longitude" htmlFor="longitude" help="Between -180 and 180.">
              <input
                id="longitude"
                type="number"
                step="any"
                className={fieldInputClassName()}
                value={form.longitude}
                onChange={(event) => updateField("longitude", event.target.value)}
              />
              {touched && errors.longitude ? <p className="mt-1 text-[10px] text-[var(--danger)]">{errors.longitude}</p> : null}
            </FormField>
          </div>

          {touched && hasErrors ? (
            <p className="mt-3 text-xs text-[var(--danger)]">Fix the highlighted fields before saving.</p>
          ) : null}

          <div className="mt-4 flex justify-end gap-2">
            <Button variant="default" onClick={closeDialog}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              title="Available once classroom management API is integrated"
              disabled
            >
              Save classroom
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
