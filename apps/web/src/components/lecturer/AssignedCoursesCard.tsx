"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CellPrimary, DataTable } from "@/components/ui/DataTable";
import { FilterBar, FilterSelect, SearchInput } from "@/components/ui/FilterBar";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { downloadCsv } from "@/lib/csv";
import {
  CourseFilters,
  EMPTY_COURSE_FILTERS,
  courseStatusOptions,
  coursesToCsv,
  filterCourses,
} from "@/lib/courseFilters";
import { courseStatusDisplay } from "@/lib/status";
import { LecturerCourse } from "@/types/lecturer";

export function AssignedCoursesCard({
  courses,
  semesterLabel,
}: {
  courses: LecturerCourse[];
  semesterLabel: string;
}) {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<CourseFilters>(EMPTY_COURSE_FILTERS);

  const statusOptions = useMemo(() => courseStatusOptions(courses), [courses]);
  const visible = useMemo(() => filterCourses(courses, filters), [courses, filters]);
  const isFiltered = filters.query.trim() !== "" || filters.status !== "all";

  function exportList() {
    const date = new Date().toISOString().slice(0, 10);
    downloadCsv(`assigned-courses-${date}.csv`, coursesToCsv(visible));
  }

  return (
    <Card
      title="Assigned courses"
      subtitle={semesterLabel}
      flush
      actions={
        <>
          <Button
            aria-expanded={filtersOpen}
            aria-controls="assigned-courses-filters"
            onClick={() => setFiltersOpen((open) => !open)}
          >
            Filter{isFiltered ? " (active)" : ""}
          </Button>
          <Button onClick={exportList} disabled={visible.length === 0}>
            Export list
          </Button>
        </>
      }
    >
      {filtersOpen ? (
        <div id="assigned-courses-filters">
          <FilterBar>
            <SearchInput
              aria-label="Search courses by code or name"
              placeholder="Search by code or name"
              value={filters.query}
              onChange={(event) => setFilters({ ...filters, query: event.target.value })}
            />
            <FilterSelect
              aria-label="Filter by status"
              value={filters.status}
              onChange={(event) =>
                setFilters({ ...filters, status: event.target.value as CourseFilters["status"] })
              }
            >
              <option value="all">All statuses</option>
              {statusOptions.map((status) => (
                <option key={status} value={status}>
                  {courseStatusDisplay(status).label}
                </option>
              ))}
            </FilterSelect>
            <Button onClick={() => setFilters(EMPTY_COURSE_FILTERS)} disabled={!isFiltered}>
              Clear filters
            </Button>
          </FilterBar>
        </div>
      ) : null}
      {isFiltered ? (
        <p role="status" className="border-b border-[var(--line)] px-3.5 py-2 text-[11px] text-[var(--muted)]">
          Showing {visible.length} of {courses.length} courses
        </p>
      ) : null}
      <DataTable<LecturerCourse>
        emptyTitle={isFiltered ? "No courses match these filters" : "No assigned courses yet"}
        emptyDescription={
          isFiltered ? undefined : "Courses synchronised from University systems will appear here."
        }
        columns={[
          { key: "code", header: "Code", render: (row) => <span className="font-semibold text-[var(--link)]">{row.courseCode}</span> },
          {
            key: "course",
            header: "Course",
            render: (row) => <CellPrimary primary={row.courseName} secondary={row.scheduleSummary} />,
          },
          { key: "lecturer", header: "Lecturer", render: (row) => row.lecturerName },
          { key: "enrolled", header: "Enrolled", render: (row) => row.enrolledCount },
          { key: "attendance", header: "Attendance", render: (row) => `${row.attendanceRatePercent}%` },
          {
            key: "status",
            header: "Status",
            render: (row) => {
              const display = courseStatusDisplay(row.status);
              return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
            },
          },
        ]}
        rows={visible}
        getRowKey={(row) => row.courseId}
      />
    </Card>
  );
}
