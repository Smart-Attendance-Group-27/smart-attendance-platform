"use client";

import { ReactNode, useEffect, useRef } from "react";
import { Button } from "@/components/ui/Button";

type DialogProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
};

export function Dialog({ open, title, onClose, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (open && !node.open) node.showModal();
    if (!open && node.open) node.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="dialog-title"
      className="w-full max-w-md border border-[var(--line)] p-0 shadow-lg backdrop:bg-black/40"
    >
      <div className="flex items-center justify-between border-b border-[var(--line)] px-4 py-3">
        <h2 id="dialog-title" className="text-sm font-semibold text-[var(--text)]">
          {title}
        </h2>
        <button
          type="button"
          aria-label="Close dialog"
          onClick={onClose}
          className="text-lg leading-none text-[var(--muted)] hover:text-[var(--text)]"
        >
          &times;
        </button>
      </div>
      <div className="p-4 text-sm text-[var(--text)]">{children}</div>
    </dialog>
  );
}

type ConfirmationDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  danger?: boolean;
};

export function ConfirmationDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  onConfirm,
  onCancel,
  danger = false,
}: ConfirmationDialogProps) {
  return (
    <Dialog open={open} title={title} onClose={onCancel}>
      <p className="mb-4 text-xs leading-relaxed text-[var(--muted)]">{description}</p>
      <div className="flex justify-end gap-2">
        <Button variant="default" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant={danger ? "danger" : "primary"} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </Dialog>
  );
}
