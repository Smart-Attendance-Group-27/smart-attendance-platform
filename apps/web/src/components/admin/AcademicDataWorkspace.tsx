"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Tabs } from "@/components/ui/Tabs";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { academicRecordStatusDisplay, enrolmentStatusDisplay } from "@/lib/status";
import { AcademicData, AdminCourse, AdminTimetableEntry, CourseOffering, Enrolment } from "@/types/admin";

type TabKey = "courses" | "offerings" | "timetable" | "enrolments";

export function AcademicDataWorkspace({ data }: { data: AcademicData }) {
  const [tab, setTab] = useState<TabKey>("courses");

  return (
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

      {tab === "courses" ? (
        <DataTable<AdminCourse>
          emptyTitle="No courses"
          columns={[
            { key: "code", header: "Code", render: (row) => <span className="font-semibold text-[var(--link)]">{row.courseCode}</span> },
            { key: "name", header: "Course", render: (row) => row.courseName },
            { key: "department", header: "Department", render: (row) => row.department },
            { key: "credits", header: "Credits", render: (row) => row.credits },
            {
              key: "status",
              header: "Status",
              render: (row) => {
                const display = academicRecordStatusDisplay(row.status);
                return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
              },
            },
          ]}
          rows={data.courses}
          getRowKey={(row) => row.courseId}
        />
      ) : null}

      {tab === "offerings" ? (
        <DataTable<CourseOffering>
          emptyTitle="No course offerings"
          columns={[
            {
              key: "course",
              header: "Course",
              render: (row) => <CellPrimary primary={row.courseCode} secondary={row.courseName} />,
            },
            { key: "semester", header: "Semester", render: (row) => row.semesterLabel },
            { key: "batch", header: "Batch year", render: (row) => row.batchYear },
            { key: "type", header: "Type", render: (row) => row.courseType },
            { key: "threshold", header: "Attendance threshold", render: (row) => `${row.attendanceThresholdPercent}%` },
            { key: "enrolled", header: "Enrolled", render: (row) => row.enrolledCount },
            {
              key: "status",
              header: "Status",
              render: (row) => {
                const display = academicRecordStatusDisplay(row.status);
                return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
              },
            },
          ]}
          rows={data.offerings}
          getRowKey={(row) => row.offeringId}
        />
      ) : null}

      {tab === "timetable" ? (
        <DataTable<AdminTimetableEntry>
          emptyTitle="No timetable entries"
          columns={[
            { key: "day", header: "Day", render: (row) => row.day },
            { key: "time", header: "Time", render: (row) => row.timeRange },
            {
              key: "course",
              header: "Course",
              render: (row) => <CellPrimary primary={row.courseCode} secondary={row.courseName} />,
            },
            { key: "room", header: "Room", render: (row) => row.room },
            { key: "lecturer", header: "Lecturer", render: (row) => row.lecturerName },
          ]}
          rows={data.timetable}
          getRowKey={(row) => row.id}
        />
      ) : null}

      {tab === "enrolments" ? (
        <DataTable<Enrolment>
          emptyTitle="No enrolments"
          columns={[
            {
              key: "student",
              header: "Student",
              render: (row) => <CellPrimary primary={row.studentName} secondary={row.registrationNumber} />,
            },
            { key: "course", header: "Course", render: (row) => row.courseCode },
            { key: "semester", header: "Semester", render: (row) => row.semesterLabel },
            {
              key: "status",
              header: "Status",
              render: (row) => {
                const display = enrolmentStatusDisplay(row.enrolmentStatus);
                return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
              },
            },
          ]}
          rows={data.enrolments}
          getRowKey={(row) => row.enrolmentId}
        />
      ) : null}
    </Card>
  );
}
