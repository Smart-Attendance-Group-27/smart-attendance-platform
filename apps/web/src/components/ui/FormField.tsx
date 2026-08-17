import { ReactNode } from "react";

type FormFieldProps = {
  label: string;
  htmlFor: string;
  help?: string;
  children: ReactNode;
};

export function FormField({ label, htmlFor, help, children }: FormFieldProps) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-[11px] font-semibold">
        {label}
      </label>
      {children}
      {help ? <p className="mt-1.5 text-[10px] leading-snug text-[var(--muted)]">{help}</p> : null}
    </div>
  );
}

export function fieldInputClassName(): string {
  return "h-[34px] w-full border border-[#c7cfd6] bg-white px-2.5 text-xs";
}
