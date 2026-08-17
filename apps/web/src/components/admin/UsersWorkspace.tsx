"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Tabs } from "@/components/ui/Tabs";
import { FilterBar, SearchInput } from "@/components/ui/FilterBar";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { accountStatusDisplay } from "@/lib/status";
import { AdministratorAccount, LecturerAccount, StudentAccount, UserDirectoryData } from "@/types/admin";

type TabKey = "students" | "lecturers" | "administrators";

const DISABLED_TITLE = "Available once user administration API is integrated";

export function UsersWorkspace({ directory }: { directory: UserDirectoryData }) {
  const [tab, setTab] = useState<TabKey>("students");
  const [query, setQuery] = useState("");

  const normalized = query.trim().toLowerCase();

  const students = directory.students.filter(
    (row) =>
      !normalized ||
      row.fullName.toLowerCase().includes(normalized) ||
      row.registrationNumber.toLowerCase().includes(normalized),
  );
  const lecturers = directory.lecturers.filter(
    (row) =>
      !normalized ||
      row.fullName.toLowerCase().includes(normalized) ||
      row.employeeNumber.toLowerCase().includes(normalized),
  );
  const administrators = directory.administrators.filter(
    (row) => !normalized || row.fullName.toLowerCase().includes(normalized),
  );

  return (
    <Card flush>
      <Tabs
        activeKey={tab}
        onChange={(key) => setTab(key as TabKey)}
        tabs={[
          { key: "students", label: "Students", count: directory.students.length },
          { key: "lecturers", label: "Lecturers", count: directory.lecturers.length },
          { key: "administrators", label: "Administrators", count: directory.administrators.length },
        ]}
      />

      <FilterBar>
        <SearchInput
          placeholder="Search by name, registration, or employee number"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </FilterBar>

      {tab === "students" ? (
        <DataTable<StudentAccount>
          emptyTitle="No matching students"
          columns={[
            {
              key: "student",
              header: "Student",
              render: (row) => <CellPrimary primary={row.fullName} secondary={row.registrationNumber} />,
            },
            { key: "department", header: "Department", render: (row) => row.department },
            { key: "intake", header: "Intake / semester", render: (row) => `${row.intakeYear} · Sem ${row.currentSemester}` },
            {
              key: "status",
              header: "Account status",
              render: (row) => {
                const display = accountStatusDisplay(row.accountStatus);
                return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
              },
            },
            {
              key: "action",
              header: "Action",
              align: "right",
              render: () => (
                <Button title={DISABLED_TITLE} disabled>
                  {"Deactivate"}
                </Button>
              ),
            },
          ]}
          rows={students}
          getRowKey={(row) => row.userId}
        />
      ) : null}

      {tab === "lecturers" ? (
        <DataTable<LecturerAccount>
          emptyTitle="No matching lecturers"
          columns={[
            {
              key: "lecturer",
              header: "Lecturer",
              render: (row) => <CellPrimary primary={row.fullName} secondary={row.employeeNumber} />,
            },
            { key: "department", header: "Department", render: (row) => row.department },
            { key: "designation", header: "Designation", render: (row) => row.designation },
            {
              key: "status",
              header: "Account status",
              render: (row) => {
                const display = accountStatusDisplay(row.accountStatus);
                return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
              },
            },
            {
              key: "action",
              header: "Action",
              align: "right",
              render: () => (
                <Button title={DISABLED_TITLE} disabled>
                  Deactivate
                </Button>
              ),
            },
          ]}
          rows={lecturers}
          getRowKey={(row) => row.userId}
        />
      ) : null}

      {tab === "administrators" ? (
        <DataTable<AdministratorAccount>
          emptyTitle="No matching administrators"
          columns={[
            {
              key: "administrator",
              header: "Administrator",
              render: (row) => <CellPrimary primary={row.fullName} secondary={row.email} />,
            },
            { key: "department", header: "Department", render: (row) => row.department },
            { key: "scope", header: "Administrative scope", render: (row) => row.administrativeScope },
            {
              key: "status",
              header: "Account status",
              render: (row) => {
                const display = accountStatusDisplay(row.accountStatus);
                return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
              },
            },
            {
              key: "action",
              header: "Action",
              align: "right",
              render: () => (
                <Button title={DISABLED_TITLE} disabled>
                  Deactivate
                </Button>
              ),
            },
          ]}
          rows={administrators}
          getRowKey={(row) => row.userId}
        />
      ) : null}
    </Card>
  );
}
