"use client";

import { FormEvent, useState } from "react";
import { provisionAccount } from "@/app/actions/users";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";
import type {
  ApiAccountProvisionRequest,
  ApiProvisionedAccount,
  ApiProvisionedAccountRole,
} from "@/lib/api/admin";
import type { AcademicOption } from "@/types/admin";

type FormState = {
  role: ApiProvisionedAccountRole;
  email: string;
  firstName: string;
  middleName: string;
  lastName: string;
  departmentId: string;
  registrationNumber: string;
  intakeYear: string;
  currentSemester: string;
  employeeNumber: string;
  designation: string;
  administrativeScope: string;
};

const roles: { value: ApiProvisionedAccountRole; label: string }[] = [
  { value: "student", label: "Student" },
  { value: "lecturer", label: "Lecturer" },
  { value: "administrator", label: "Administrator" },
];

function initialForm(departments: AcademicOption[]): FormState {
  return {
    role: "student",
    email: "",
    firstName: "",
    middleName: "",
    lastName: "",
    departmentId: departments[0]?.id ?? "",
    registrationNumber: "",
    intakeYear: String(new Date().getFullYear()),
    currentSemester: "1",
    employeeNumber: "",
    designation: "",
    administrativeScope: "university",
  };
}

export function ProvisionAccountButton({ departments }: { departments: AcademicOption[] }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FormState>(() => initialForm(departments));
  const [result, setResult] = useState<ApiProvisionedAccount | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function close() {
    setOpen(false);
    setResult(null);
    setError(null);
    setForm(initialForm(departments));
  }

  function setField<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const payload: ApiAccountProvisionRequest = {
      role: form.role,
      email: form.email,
      firstName: form.firstName,
      ...(form.middleName ? { middleName: form.middleName } : {}),
      lastName: form.lastName,
      departmentId: form.departmentId,
      ...(form.role === "student"
        ? {
            registrationNumber: form.registrationNumber,
            intakeYear: Number(form.intakeYear),
            currentSemester: Number(form.currentSemester),
          }
        : {}),
      ...(form.role === "lecturer"
        ? { employeeNumber: form.employeeNumber, designation: form.designation }
        : {}),
      ...(form.role === "administrator"
        ? { administrativeScope: form.administrativeScope }
        : {}),
    };
    try {
      const response = await provisionAccount(payload);
      if (!response.ok) {
        setError(response.message);
        return;
      }
      setResult(response.account);
    } finally {
      setSubmitting(false);
    }
  }

  async function copyPassword() {
    if (result) await navigator.clipboard.writeText(result.temporaryPassword);
  }

  return (
    <>
      <Button variant="primary" onClick={() => setOpen(true)}>
        Provision account
      </Button>
      <Dialog open={open} title={result ? "Account provisioned" : "Provision account"} onClose={close}>
        {result ? (
          <div>
            <div className="mb-4 border-l-4 border-l-[var(--warning)] border border-[#e3c985] bg-[#fff8e8] p-3">
              <p className="mb-1 text-xs font-semibold text-[#6e5016]">Copy this password now</p>
              <p className="text-[11px] leading-relaxed text-[#6e5016]">
                It is temporary and will not be shown again after this dialog closes.
              </p>
            </div>
            <dl className="mb-4 grid gap-3 text-xs">
              <div>
                <dt className="text-[var(--muted)]">Email</dt>
                <dd className="mt-1 font-medium">{result.email}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted)]">Temporary password</dt>
                <dd className="mt-1 break-all border border-[var(--line)] bg-[#f5f7f8] p-2 font-mono text-sm">
                  {result.temporaryPassword}
                </dd>
              </div>
            </dl>
            <div className="flex justify-end gap-2">
              <Button onClick={copyPassword}>Copy password</Button>
              <Button variant="primary" onClick={close}>Done</Button>
            </div>
          </div>
        ) : (
          <form onSubmit={submit}>
            <div className="mb-4 grid grid-cols-3 border border-[var(--line)]" aria-label="Account role">
              {roles.map((role) => (
                <button
                  key={role.value}
                  type="button"
                  aria-pressed={form.role === role.value}
                  onClick={() => setField("role", role.value)}
                  className={`h-9 border-r border-[var(--line)] text-xs font-medium last:border-r-0 ${
                    form.role === role.value ? "bg-[var(--uom-blue)] text-white" : "bg-white text-[var(--text)]"
                  }`}
                >
                  {role.label}
                </button>
              ))}
            </div>
            <div className="grid max-h-[55vh] grid-cols-1 gap-3 overflow-y-auto pr-1 sm:grid-cols-2">
              <TextField label="Email" id="accountEmail" type="email" value={form.email} onChange={(value) => setField("email", value)} />
              <SelectField label="Department" id="accountDepartment" value={form.departmentId} onChange={(value) => setField("departmentId", value)} options={departments} />
              <TextField label="First name" id="accountFirstName" value={form.firstName} onChange={(value) => setField("firstName", value)} />
              <TextField label="Middle name" id="accountMiddleName" value={form.middleName} onChange={(value) => setField("middleName", value)} required={false} />
              <TextField label="Last name" id="accountLastName" value={form.lastName} onChange={(value) => setField("lastName", value)} />
              {form.role === "student" ? (
                <>
                  <TextField label="Registration number" id="registrationNumber" value={form.registrationNumber} onChange={(value) => setField("registrationNumber", value)} />
                  <TextField label="Intake year" id="intakeYear" type="number" value={form.intakeYear} onChange={(value) => setField("intakeYear", value)} />
                  <TextField label="Current semester" id="currentSemester" type="number" value={form.currentSemester} onChange={(value) => setField("currentSemester", value)} />
                </>
              ) : null}
              {form.role === "lecturer" ? (
                <>
                  <TextField label="Employee number" id="employeeNumber" value={form.employeeNumber} onChange={(value) => setField("employeeNumber", value)} />
                  <TextField label="Designation" id="designation" value={form.designation} onChange={(value) => setField("designation", value)} />
                </>
              ) : null}
              {form.role === "administrator" ? (
                <TextField label="Administrative scope" id="administrativeScope" value={form.administrativeScope} onChange={(value) => setField("administrativeScope", value)} />
              ) : null}
            </div>
            {error ? <p role="alert" className="mt-3 text-xs text-[var(--danger)]">{error}</p> : null}
            <div className="mt-4 flex justify-end gap-2">
              <Button onClick={close} disabled={submitting}>Cancel</Button>
              <Button variant="primary" type="submit" disabled={submitting || departments.length === 0}>
                {submitting ? "Provisioning..." : "Provision account"}
              </Button>
            </div>
          </form>
        )}
      </Dialog>
    </>
  );
}

function TextField({ label, id, value, onChange, type = "text", required = true }: { label: string; id: string; value: string; onChange: (value: string) => void; type?: string; required?: boolean }) {
  return <FormField label={label} htmlFor={id}><input id={id} type={type} required={required} className={fieldInputClassName()} value={value} onChange={(event) => onChange(event.target.value)} /></FormField>;
}

function SelectField({ label, id, value, onChange, options }: { label: string; id: string; value: string; onChange: (value: string) => void; options: AcademicOption[] }) {
  return <FormField label={label} htmlFor={id}><select id={id} required className={fieldInputClassName()} value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></FormField>;
}
