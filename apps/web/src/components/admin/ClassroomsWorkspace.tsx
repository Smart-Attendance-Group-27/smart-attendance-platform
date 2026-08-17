"use client";

import { FormEvent, useMemo, useState } from "react";
import { Card } from "@/components/ui/Card";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";
import { classroomStatusDisplay } from "@/lib/status";
import { BuildingOption, Classroom } from "@/types/admin";
import { saveClassroom } from "@/app/actions/classrooms";

type FormState = {
  classroomCode: string;
  buildingId: string;
  floorNumber: string;
  capacity: string;
  latitude: string;
  longitude: string;
  radius: string;
  status: string;
};

function emptyForm(defaultBuildingId: string): FormState {
  return {
    classroomCode: "",
    buildingId: defaultBuildingId,
    floorNumber: "",
    capacity: "",
    latitude: "",
    longitude: "",
    radius: "",
    status: "active",
  };
}

function classroomToForm(classroom: Classroom): FormState {
  return {
    classroomCode: classroom.classroomCode,
    buildingId: classroom.buildingId,
    floorNumber: String(classroom.floorNumber),
    capacity: String(classroom.capacity),
    latitude: String(classroom.latitude),
    longitude: String(classroom.longitude),
    radius: String(classroom.defaultGeofenceRadiusMeters),
    status: classroom.rawStatus,
  };
}

function validate(form: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!form.classroomCode.trim()) errors.classroomCode = "Classroom code is required.";
  if (!form.buildingId) errors.buildingId = "Building is required.";

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

export function ClassroomsWorkspace({
  classrooms,
  buildings,
}: {
  classrooms: Classroom[];
  buildings: BuildingOption[];
}) {
  const defaultBuildingId = buildings[0]?.id ?? "";
  const [dialogMode, setDialogMode] = useState<"none" | "create" | "edit">("none");
  const [editingClassroomId, setEditingClassroomId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm(defaultBuildingId));
  const [touched, setTouched] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const errors = useMemo(() => validate(form), [form]);
  const hasErrors = Object.keys(errors).length > 0;

  function openCreate() {
    setForm(emptyForm(defaultBuildingId));
    setEditingClassroomId(null);
    setTouched(false);
    setSubmitError(null);
    setDialogMode("create");
  }

  function openEdit(classroom: Classroom) {
    setForm(classroomToForm(classroom));
    setEditingClassroomId(classroom.classroomId);
    setTouched(false);
    setSubmitError(null);
    setDialogMode("edit");
  }

  function closeDialog() {
    setDialogMode("none");
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (hasErrors) return;

    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const result = await saveClassroom(editingClassroomId, {
        buildingId: form.buildingId,
        classroomCode: form.classroomCode.trim(),
        floorNumber: form.floorNumber.trim() === "" ? null : Number(form.floorNumber),
        capacity: form.capacity.trim() === "" ? null : Number(form.capacity),
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
        defaultGeofenceRadiusM: Number(form.radius),
        status: form.status,
      });
      if (!result.ok) {
        setSubmitError(result.message);
        return;
      }
      setDialogMode("none");
    } finally {
      setIsSubmitting(false);
    }
  }

  function updateField<K extends keyof FormState>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <>
      <Card
        title="Classrooms and geofences"
        flush
        actions={
          <Button variant="primary" onClick={openCreate} disabled={buildings.length === 0}>
            Add classroom
          </Button>
        }
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
            <FormField label="Building" htmlFor="buildingId">
              <select
                id="buildingId"
                className={fieldInputClassName()}
                value={form.buildingId}
                onChange={(event) => updateField("buildingId", event.target.value)}
              >
                {buildings.map((building) => (
                  <option key={building.id} value={building.id}>
                    {building.buildingName}
                  </option>
                ))}
              </select>
              {touched && errors.buildingId ? <p className="mt-1 text-[10px] text-[var(--danger)]">{errors.buildingId}</p> : null}
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
            <FormField label="Status" htmlFor="status">
              <select
                id="status"
                className={fieldInputClassName()}
                value={form.status}
                onChange={(event) => updateField("status", event.target.value)}
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
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
          {submitError ? <p className="mt-3 text-xs text-[var(--danger)]">{submitError}</p> : null}

          <div className="mt-4 flex justify-end gap-2">
            <Button variant="default" onClick={closeDialog} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={isSubmitting}>
              {isSubmitting ? "Saving..." : "Save classroom"}
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
