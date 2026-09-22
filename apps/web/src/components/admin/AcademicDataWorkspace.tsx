"use client";

import { FormEvent, useState } from "react";
import {
  addEnrolment,
  removeEnrolment,
  removeTimetableEntry,
  saveCourse,
  saveOffering,
  saveTimetableEntry,
} from "@/app/actions/academic";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CellPrimary, DataTable } from "@/components/ui/DataTable";
import { ConfirmationDialog, Dialog } from "@/components/ui/Dialog";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Tabs } from "@/components/ui/Tabs";
import { academicRecordStatusDisplay, enrolmentStatusDisplay } from "@/lib/status";
import type {
  AcademicData,
  AcademicReferenceData,
  AdminCourse,
  AdminTimetableEntry,
  CourseOffering,
  Enrolment,
} from "@/types/admin";

type TabKey = "courses" | "offerings" | "timetable" | "enrolments";
type Editor = "none" | "course" | "offering" | "timetable" | "enrolment";

type CourseForm = {
  courseCode: string;
  courseName: string;
  departmentId: string;
  credits: string;
  status: "active" | "inactive";
};

type OfferingForm = {
  courseId: string;
  semesterId: string;
  lecturerId: string;
  batchYear: string;
  courseType: string;
  attendanceThresholdPercent: string;
  status: "active" | "inactive";
};

type TimetableForm = {
  courseOfferingId: string;
  classroomId: string;
  dayOfWeek: string;
  startTime: string;
  endTime: string;
  courseType: string;
  validFrom: string;
  validUntil: string;
  status: "active" | "inactive";
};

type Removal =
  | { kind: "enrolment"; offeringId: string; studentId: string; label: string }
  | { kind: "timetable"; entryId: string; label: string }
  | null;

const today = new Date().toISOString().slice(0, 10);

export function AcademicDataWorkspace({
  data,
  references,
}: {
  data: AcademicData;
  references: AcademicReferenceData;
}) {
  const [tab, setTab] = useState<TabKey>("courses");
  const [editor, setEditor] = useState<Editor>("none");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [removal, setRemoval] = useState<Removal>(null);
  const [courseForm, setCourseForm] = useState<CourseForm>(() => emptyCourse(references));
  const [offeringForm, setOfferingForm] = useState<OfferingForm>(() => emptyOffering(data, references));
  const [timetableForm, setTimetableForm] = useState<TimetableForm>(() => emptyTimetable(data, references));
  const [enrolmentForm, setEnrolmentForm] = useState({
    offeringId: data.offerings[0]?.offeringId ?? "",
    studentId: references.students[0]?.id ?? "",
  });

  function openCreate() {
    setEditingId(null);
    setSubmitError(null);
    if (tab === "courses") {
      setCourseForm(emptyCourse(references));
      setEditor("course");
    } else if (tab === "offerings") {
      setOfferingForm(emptyOffering(data, references));
      setEditor("offering");
    } else if (tab === "timetable") {
      setTimetableForm(emptyTimetable(data, references));
      setEditor("timetable");
    } else {
      setEnrolmentForm({
        offeringId: data.offerings[0]?.offeringId ?? "",
        studentId: references.students[0]?.id ?? "",
      });
      setEditor("enrolment");
    }
  }

  function openCourse(course: AdminCourse) {
    setEditingId(course.courseId);
    setCourseForm({
      courseCode: course.courseCode,
      courseName: course.courseName,
      departmentId: course.departmentId ?? "",
      credits: String(course.credits),
      status: course.status,
    });
    setSubmitError(null);
    setEditor("course");
  }

  function openOffering(offering: CourseOffering) {
    setEditingId(offering.offeringId);
    setOfferingForm({
      courseId: offering.courseId ?? "",
      semesterId: offering.semesterId ?? "",
      lecturerId: offering.lecturerId ?? "",
      batchYear: String(offering.batchYear),
      courseType: offering.courseType,
      attendanceThresholdPercent: String(offering.attendanceThresholdPercent),
      status: offering.status,
    });
    setSubmitError(null);
    setEditor("offering");
  }

  function openTimetable(entry: AdminTimetableEntry) {
    setEditingId(entry.id);
    setTimetableForm({
      courseOfferingId: entry.courseOfferingId ?? "",
      classroomId: entry.classroomId ?? "",
      dayOfWeek: String(entry.dayOfWeek ?? 1),
      startTime: (entry.startTime ?? "09:00").slice(0, 5),
      endTime: (entry.endTime ?? "10:00").slice(0, 5),
      courseType: entry.courseType ?? "lecture",
      validFrom: entry.validFrom ?? today,
      validUntil: entry.validUntil ?? "",
      status: entry.status ?? "active",
    });
    setSubmitError(null);
    setEditor("timetable");
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const result = editor === "course"
        ? await saveCourse(editingId, {
            ...courseForm,
            courseCode: courseForm.courseCode.trim(),
            courseName: courseForm.courseName.trim(),
            credits: Number(courseForm.credits),
          })
        : editor === "offering"
          ? await saveOffering(editingId, {
              ...offeringForm,
              batchYear: Number(offeringForm.batchYear),
              attendanceThresholdPercent: Number(offeringForm.attendanceThresholdPercent),
              courseType: offeringForm.courseType.trim(),
            })
          : editor === "timetable"
            ? await saveTimetableEntry(editingId, {
                ...timetableForm,
                dayOfWeek: Number(timetableForm.dayOfWeek),
                validUntil: timetableForm.validUntil || null,
              })
            : await addEnrolment(enrolmentForm.offeringId, enrolmentForm.studentId);
      if (!result.ok) {
        setSubmitError(result.message);
        return;
      }
      setEditor("none");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function confirmRemoval() {
    if (!removal) return;
    setIsSubmitting(true);
    const result = removal.kind === "enrolment"
      ? await removeEnrolment(removal.offeringId, removal.studentId)
      : await removeTimetableEntry(removal.entryId);
    setIsSubmitting(false);
    if (!result.ok) {
      setSubmitError(result.message);
      return;
    }
    setRemoval(null);
  }

  const addDisabled = tab === "courses"
    ? references.departments.length === 0
    : tab === "offerings"
      ? data.courses.length === 0 || references.semesters.length === 0 || references.lecturers.length === 0
      : tab === "timetable"
        ? data.offerings.length === 0 || references.classrooms.length === 0
        : data.offerings.length === 0 || references.students.length === 0;

  return (
    <>
      <Card flush>
        <Tabs
          activeKey={tab}
          onChange={(key) => setTab(key as TabKey)}
          tabs={[
            { key: "courses", label: "Courses", count: data.courses.length },
            { key: "offerings", label: "Course offerings", count: data.offerings.length },
            { key: "timetable", label: "Timetable", count: data.timetable.length },
            { key: "enrolments", label: "Enrolments", count: data.enrolments.length },
          ]}
        />
        <div className="flex min-h-11 items-center justify-end border-b border-[var(--line)] bg-[#fafbfc] px-3.5">
          <Button variant="primary" onClick={openCreate} disabled={addDisabled}>
            {tab === "courses" ? "Add course" : tab === "offerings" ? "Add offering" : tab === "timetable" ? "Add timetable entry" : "Enrol student"}
          </Button>
        </div>

        {tab === "courses" ? <CourseTable rows={data.courses} onEdit={openCourse} /> : null}
        {tab === "offerings" ? <OfferingTable rows={data.offerings} onEdit={openOffering} /> : null}
        {tab === "timetable" ? (
          <TimetableTable
            rows={data.timetable}
            onEdit={openTimetable}
            onDeactivate={(entry) => setRemoval({
              kind: "timetable",
              entryId: entry.id,
              label: `${entry.courseCode} ${entry.day}`,
            })}
          />
        ) : null}
        {tab === "enrolments" ? (
          <EnrolmentTable
            rows={data.enrolments}
            onDrop={(row) => setRemoval({
              kind: "enrolment",
              offeringId: row.courseOfferingId ?? "",
              studentId: row.studentId ?? "",
              label: `${row.studentName} from ${row.courseCode}`,
            })}
          />
        ) : null}
      </Card>

      <Dialog open={editor !== "none"} title={editorTitle(editor, editingId)} onClose={() => setEditor("none")}>
        <form onSubmit={handleSubmit} className="space-y-3">
          {editor === "course" ? <CourseFields form={courseForm} setForm={setCourseForm} references={references} /> : null}
          {editor === "offering" ? <OfferingFields form={offeringForm} setForm={setOfferingForm} data={data} references={references} /> : null}
          {editor === "timetable" ? <TimetableFields form={timetableForm} setForm={setTimetableForm} data={data} references={references} /> : null}
          {editor === "enrolment" ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <SelectField label="Offering" id="enrolmentOffering" value={enrolmentForm.offeringId} onChange={(offeringId) => setEnrolmentForm((value) => ({ ...value, offeringId }))} options={data.offerings.map((item) => ({ id: item.offeringId, label: `${item.courseCode} · ${item.semesterLabel}` }))} />
              <SelectField label="Student" id="enrolmentStudent" value={enrolmentForm.studentId} onChange={(studentId) => setEnrolmentForm((value) => ({ ...value, studentId }))} options={references.students} />
            </div>
          ) : null}
          {submitError ? <p role="alert" className="text-xs text-[var(--danger)]">{submitError}</p> : null}
          <div className="flex justify-end gap-2 pt-1">
            <Button onClick={() => setEditor("none")} disabled={isSubmitting}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={isSubmitting}>
              {isSubmitting ? "Saving..." : "Save"}
            </Button>
          </div>
        </form>
      </Dialog>

      <ConfirmationDialog
        open={removal !== null}
        title={removal?.kind === "enrolment" ? "Drop enrolment" : "Deactivate timetable entry"}
        description={removal ? `Confirm ${removal.label}. Historical records will be preserved.` : ""}
        confirmLabel={removal?.kind === "enrolment" ? "Drop enrolment" : "Deactivate"}
        onConfirm={() => void confirmRemoval()}
        onCancel={() => setRemoval(null)}
        danger
        busy={isSubmitting}
      />
    </>
  );
}

function CourseTable({ rows, onEdit }: { rows: AdminCourse[]; onEdit: (row: AdminCourse) => void }) {
  return <DataTable rows={rows} getRowKey={(row) => row.courseId} emptyTitle="No courses" columns={[
    { key: "code", header: "Code", render: (row) => <span className="font-semibold text-[var(--link)]">{row.courseCode}</span> },
    { key: "name", header: "Course", render: (row) => row.courseName },
    { key: "department", header: "Department", render: (row) => row.department },
    { key: "credits", header: "Credits", render: (row) => row.credits },
    { key: "status", header: "Status", render: (row) => <AcademicStatus status={row.status} /> },
    { key: "action", header: "Action", align: "right", render: (row) => <Button onClick={() => onEdit(row)}>Edit</Button> },
  ]} />;
}

function OfferingTable({ rows, onEdit }: { rows: CourseOffering[]; onEdit: (row: CourseOffering) => void }) {
  return <DataTable rows={rows} getRowKey={(row) => row.offeringId} emptyTitle="No course offerings" columns={[
    { key: "course", header: "Course", render: (row) => <CellPrimary primary={row.courseCode} secondary={row.courseName} /> },
    { key: "semester", header: "Semester", render: (row) => row.semesterLabel },
    { key: "lecturer", header: "Lecturer", render: (row) => row.lecturerName || "—" },
    { key: "batch", header: "Batch", render: (row) => row.batchYear },
    { key: "type", header: "Type", render: (row) => row.courseType },
    { key: "enrolled", header: "Enrolled", render: (row) => row.enrolledCount },
    { key: "status", header: "Status", render: (row) => <AcademicStatus status={row.status} /> },
    { key: "action", header: "Action", align: "right", render: (row) => <Button onClick={() => onEdit(row)}>Edit</Button> },
  ]} />;
}

function TimetableTable({ rows, onEdit, onDeactivate }: { rows: AdminTimetableEntry[]; onEdit: (row: AdminTimetableEntry) => void; onDeactivate: (row: AdminTimetableEntry) => void }) {
  return <DataTable rows={rows} getRowKey={(row) => row.id} emptyTitle="No timetable entries" columns={[
    { key: "day", header: "Day", render: (row) => row.day },
    { key: "time", header: "Time", render: (row) => row.timeRange },
    { key: "course", header: "Course", render: (row) => <CellPrimary primary={row.courseCode} secondary={row.courseName} /> },
    { key: "room", header: "Room", render: (row) => row.room },
    { key: "lecturer", header: "Lecturer", render: (row) => row.lecturerName },
    { key: "action", header: "Action", align: "right", render: (row) => <span className="inline-flex gap-1.5"><Button onClick={() => onEdit(row)}>Edit</Button><Button variant="danger" onClick={() => onDeactivate(row)}>Deactivate</Button></span> },
  ]} />;
}

function EnrolmentTable({ rows, onDrop }: { rows: Enrolment[]; onDrop: (row: Enrolment) => void }) {
  return <DataTable rows={rows} getRowKey={(row) => row.enrolmentId} emptyTitle="No enrolments" columns={[
    { key: "student", header: "Student", render: (row) => <CellPrimary primary={row.studentName} secondary={row.registrationNumber} /> },
    { key: "course", header: "Course", render: (row) => row.courseCode },
    { key: "semester", header: "Semester", render: (row) => row.semesterLabel },
    { key: "status", header: "Status", render: (row) => { const display = enrolmentStatusDisplay(row.enrolmentStatus); return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>; } },
    { key: "action", header: "Action", align: "right", render: (row) => row.enrolmentStatus === "enrolled" ? <Button variant="danger" onClick={() => onDrop(row)}>Drop</Button> : "—" },
  ]} />;
}

function CourseFields({ form, setForm, references }: { form: CourseForm; setForm: React.Dispatch<React.SetStateAction<CourseForm>>; references: AcademicReferenceData }) {
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
    <TextField label="Course code" id="courseCode" value={form.courseCode} onChange={(courseCode) => setForm((value) => ({ ...value, courseCode }))} required />
    <TextField label="Course name" id="courseName" value={form.courseName} onChange={(courseName) => setForm((value) => ({ ...value, courseName }))} required />
    <SelectField label="Department" id="departmentId" value={form.departmentId} onChange={(departmentId) => setForm((value) => ({ ...value, departmentId }))} options={references.departments} />
    <TextField label="Credits" id="credits" type="number" value={form.credits} onChange={(credits) => setForm((value) => ({ ...value, credits }))} required />
    <StatusField value={form.status} onChange={(status) => setForm((value) => ({ ...value, status }))} />
  </div>;
}

function OfferingFields({ form, setForm, data, references }: { form: OfferingForm; setForm: React.Dispatch<React.SetStateAction<OfferingForm>>; data: AcademicData; references: AcademicReferenceData }) {
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
    <SelectField label="Course" id="offeringCourse" value={form.courseId} onChange={(courseId) => setForm((value) => ({ ...value, courseId }))} options={data.courses.map((item) => ({ id: item.courseId, label: `${item.courseCode} · ${item.courseName}` }))} />
    <SelectField label="Semester" id="semesterId" value={form.semesterId} onChange={(semesterId) => setForm((value) => ({ ...value, semesterId }))} options={references.semesters} />
    <SelectField label="Lecturer" id="lecturerId" value={form.lecturerId} onChange={(lecturerId) => setForm((value) => ({ ...value, lecturerId }))} options={references.lecturers} />
    <TextField label="Batch year" id="batchYear" type="number" value={form.batchYear} onChange={(batchYear) => setForm((value) => ({ ...value, batchYear }))} required />
    <TextField label="Course type" id="courseType" value={form.courseType} onChange={(courseType) => setForm((value) => ({ ...value, courseType }))} required />
    <TextField label="Attendance threshold (%)" id="attendanceThreshold" type="number" value={form.attendanceThresholdPercent} onChange={(attendanceThresholdPercent) => setForm((value) => ({ ...value, attendanceThresholdPercent }))} required />
    <StatusField value={form.status} onChange={(status) => setForm((value) => ({ ...value, status }))} />
  </div>;
}

function TimetableFields({ form, setForm, data, references }: { form: TimetableForm; setForm: React.Dispatch<React.SetStateAction<TimetableForm>>; data: AcademicData; references: AcademicReferenceData }) {
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
    <SelectField label="Offering" id="timetableOffering" value={form.courseOfferingId} onChange={(courseOfferingId) => setForm((value) => ({ ...value, courseOfferingId }))} options={data.offerings.map((item) => ({ id: item.offeringId, label: `${item.courseCode} · ${item.semesterLabel}` }))} />
    <SelectField label="Classroom" id="timetableClassroom" value={form.classroomId} onChange={(classroomId) => setForm((value) => ({ ...value, classroomId }))} options={references.classrooms} />
    <SelectField label="Day" id="dayOfWeek" value={form.dayOfWeek} onChange={(dayOfWeek) => setForm((value) => ({ ...value, dayOfWeek }))} options={["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((label, index) => ({ id: String(index + 1), label }))} />
    <TextField label="Course type" id="timetableType" value={form.courseType} onChange={(courseType) => setForm((value) => ({ ...value, courseType }))} required />
    <TextField label="Start time" id="startTime" type="time" value={form.startTime} onChange={(startTime) => setForm((value) => ({ ...value, startTime }))} required />
    <TextField label="End time" id="endTime" type="time" value={form.endTime} onChange={(endTime) => setForm((value) => ({ ...value, endTime }))} required />
    <TextField label="Valid from" id="validFrom" type="date" value={form.validFrom} onChange={(validFrom) => setForm((value) => ({ ...value, validFrom }))} required />
    <TextField label="Valid until" id="validUntil" type="date" value={form.validUntil} onChange={(validUntil) => setForm((value) => ({ ...value, validUntil }))} />
    <StatusField value={form.status} onChange={(status) => setForm((value) => ({ ...value, status }))} />
  </div>;
}

function TextField({ label, id, value, onChange, type = "text", required = false }: { label: string; id: string; value: string; onChange: (value: string) => void; type?: string; required?: boolean }) {
  return <FormField label={label} htmlFor={id}><input id={id} type={type} required={required} className={fieldInputClassName()} value={value} onChange={(event) => onChange(event.target.value)} /></FormField>;
}

function SelectField({ label, id, value, onChange, options }: { label: string; id: string; value: string; onChange: (value: string) => void; options: { id: string; label: string }[] }) {
  return <FormField label={label} htmlFor={id}><select id={id} required className={fieldInputClassName()} value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></FormField>;
}

function StatusField({ value, onChange }: { value: "active" | "inactive"; onChange: (value: "active" | "inactive") => void }) {
  return <SelectField label="Status" id="academicStatus" value={value} onChange={(status) => onChange(status as "active" | "inactive")} options={[{ id: "active", label: "Active" }, { id: "inactive", label: "Inactive" }]} />;
}

function AcademicStatus({ status }: { status: "active" | "inactive" }) {
  const display = academicRecordStatusDisplay(status);
  return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
}

function emptyCourse(references: AcademicReferenceData): CourseForm {
  return { courseCode: "", courseName: "", departmentId: references.departments[0]?.id ?? "", credits: "3", status: "active" };
}

function emptyOffering(data: AcademicData, references: AcademicReferenceData): OfferingForm {
  return { courseId: data.courses[0]?.courseId ?? "", semesterId: references.semesters[0]?.id ?? "", lecturerId: references.lecturers[0]?.id ?? "", batchYear: String(new Date().getFullYear()), courseType: "lecture", attendanceThresholdPercent: "80", status: "active" };
}

function emptyTimetable(data: AcademicData, references: AcademicReferenceData): TimetableForm {
  return { courseOfferingId: data.offerings[0]?.offeringId ?? "", classroomId: references.classrooms[0]?.id ?? "", dayOfWeek: "1", startTime: "09:00", endTime: "10:00", courseType: "lecture", validFrom: today, validUntil: "", status: "active" };
}

function editorTitle(editor: Editor, editingId: string | null): string {
  if (editor === "course") return editingId ? "Edit course" : "Add course";
  if (editor === "offering") return editingId ? "Edit course offering" : "Add course offering";
  if (editor === "timetable") return editingId ? "Edit timetable entry" : "Add timetable entry";
  if (editor === "enrolment") return "Enrol student";
  return "Academic record";
}
