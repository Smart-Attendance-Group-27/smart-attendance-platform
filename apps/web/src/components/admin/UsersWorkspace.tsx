"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Tabs } from "@/components/ui/Tabs";
import { FilterBar, SearchInput } from "@/components/ui/FilterBar";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { ConfirmationDialog } from "@/components/ui/Dialog";
import { accountStatusDisplay } from "@/lib/status";
import { AccountStatus, AdministratorAccount, LecturerAccount, StudentAccount, UserDirectoryData } from "@/types/admin";
import { setAccountStatus } from "@/app/actions/users";

type TabKey = "students" | "lecturers" | "administrators";
type PendingTarget = { userId: string; name: string; nextStatus: "active" | "suspended" };

function AccountStatusAction({
  userId,
  name,
  accountStatus,
  onRequestChange,
}: {
  userId: string;
  name: string;
  accountStatus: AccountStatus;
  onRequestChange: (target: PendingTarget) => void;
}) {
  if (accountStatus === "locked") {
    return (
      <Button title="This account is locked from failed sign-in attempts, not by an administrator." disabled>
        Locked
      </Button>
    );
  }

  const nextStatus = accountStatus === "active" ? "suspended" : "active";
  return (
    <Button
      variant={nextStatus === "suspended" ? "danger" : "default"}
      onClick={() => onRequestChange({ userId, name, nextStatus })}
    >
      {nextStatus === "suspended" ? "Deactivate" : "Activate"}
    </Button>
  );
}

export function UsersWorkspace({ directory }: { directory: UserDirectoryData }) {
  const [tab, setTab] = useState<TabKey>("students");
  const [query, setQuery] = useState("");
  const [pendingTarget, setPendingTarget] = useState<PendingTarget | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

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

  async function confirmPendingChange() {
    if (!pendingTarget) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const result = await setAccountStatus(pendingTarget.userId, pendingTarget.nextStatus);
      if (!result.ok) {
        setSubmitError(result.message);
        return;
      }
      setPendingTarget(null);
    } finally {
      setIsSubmitting(false);
    }
  }

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
              render: (row) => (
                <AccountStatusAction
                  userId={row.userId}
                  name={row.fullName}
                  accountStatus={row.accountStatus}
                  onRequestChange={setPendingTarget}
                />
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
              render: (row) => (
                <AccountStatusAction
                  userId={row.userId}
                  name={row.fullName}
                  accountStatus={row.accountStatus}
                  onRequestChange={setPendingTarget}
                />
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
              render: (row) => (
                <AccountStatusAction
                  userId={row.userId}
                  name={row.fullName}
                  accountStatus={row.accountStatus}
                  onRequestChange={setPendingTarget}
                />
              ),
            },
          ]}
          rows={administrators}
          getRowKey={(row) => row.userId}
        />
      ) : null}

      <ConfirmationDialog
        open={pendingTarget !== null}
        title={pendingTarget?.nextStatus === "suspended" ? "Deactivate account" : "Activate account"}
        description={
          pendingTarget
            ? `${pendingTarget.nextStatus === "suspended" ? "Deactivate" : "Activate"} ${pendingTarget.name}'s account? ${
                pendingTarget.nextStatus === "suspended" ? "They will not be able to sign in until reactivated." : ""
              }${submitError ? ` ${submitError}` : ""}`
            : ""
        }
        confirmLabel={isSubmitting ? "Saving..." : pendingTarget?.nextStatus === "suspended" ? "Deactivate" : "Activate"}
        danger={pendingTarget?.nextStatus === "suspended"}
        busy={isSubmitting}
        onConfirm={confirmPendingChange}
        onCancel={() => {
          setPendingTarget(null);
          setSubmitError(null);
        }}
      />
    </Card>
  );
}
