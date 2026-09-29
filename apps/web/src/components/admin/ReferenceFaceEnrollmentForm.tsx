"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FormField } from "@/components/ui/FormField";

type Feedback = { error?: string; success?: string };
type EnrollmentSummary = {
  discovered: number;
  enrolled: number;
  alreadyEnrolled: number;
  skipped: number;
  failed: number;
};

const MAX_IMAGES = 500;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_BATCH_BYTES = 250 * 1024 * 1024;
const SUPPORTED_IMAGE_PATTERN = /\.(jpe?g|png)$/i;

export function ReferenceFaceEnrollmentForm({ readOnly = false }: { readOnly?: boolean }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [images, setImages] = useState<File[]>([]);
  const [folderName, setFolderName] = useState("");
  const [feedback, setFeedback] = useState<Feedback>({});
  const [pending, setPending] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFeedback({});
    const validationError = validateImages(images);
    if (validationError) {
      setFeedback({ error: validationError });
      return;
    }

    const body = new FormData();
    images.forEach((image) => body.append("images", image, image.name));
    setPending(true);
    try {
      const response = await fetch("/api/admin/reference-faces/enrolments", {
        method: "POST",
        body,
      });
      const payload = await response.json().catch(() => null) as unknown;
      if (!response.ok) {
        setFeedback({ error: readError(payload) });
        return;
      }
      const summary = readSummary(payload);
      if (!summary) {
        setFeedback({ error: "The server returned an invalid enrolment summary." });
        return;
      }
      setFeedback({
        success:
          `Processed ${summary.discovered} image${summary.discovered === 1 ? "" : "s"}: `
          + `${summary.enrolled} enrolled, ${summary.alreadyEnrolled} unchanged, `
          + `${summary.skipped} skipped, ${summary.failed} failed.`,
      });
      setImages([]);
      setFolderName("");
      if (inputRef.current) inputRef.current.value = "";
      router.refresh();
    } catch {
      setFeedback({ error: "Couldn't upload the images. Please try again." });
    } finally {
      setPending(false);
    }
  }

  const selectionError = images.length > 0 ? validateImages(images) : null;
  const hasValidFolder = images.length > 0 && selectionError === null;

  return (
    <Card
      title="Enrol reference faces"
      className="border-l-4 border-l-[var(--uom-gold)]"
    >
      <form onSubmit={submit}>
        <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
          <FormField
            label="Photo folder"
            htmlFor="reference-face-folder"
            help={!hasValidFolder
              ? "Select a folder containing JPEG or PNG images named with student registration numbers (for example, 230XXXX.jpg)."
              : undefined}
          >
            <div className="flex min-h-[38px] items-center gap-3 border border-[#c7cfd6] bg-white px-2.5 py-1.5">
              <span className="min-w-0 flex-1 truncate text-xs text-[#33434f]">
                {folderName || "No folder selected"}
              </span>
              <label
                htmlFor="reference-face-folder"
                className={buttonClassName("default", "shrink-0 cursor-pointer")}
              >
                Choose folder
              </label>
            </div>
            <input
              ref={inputRef}
              id="reference-face-folder"
              name="images"
              type="file"
              accept="image/jpeg,image/png,.jpg,.jpeg,.png"
              multiple
              required
              disabled={readOnly || pending}
              onChange={(event) => {
                const selectedFiles = Array.from(event.currentTarget.files ?? []);
                const supportedImages = selectedFiles.filter((file) =>
                  SUPPORTED_IMAGE_PATTERN.test(file.name),
                );
                setImages(supportedImages);
                setFolderName(readFolderName(selectedFiles));
                const validationError = validateImages(supportedImages);
                setFeedback(
                  selectedFiles.length > supportedImages.length
                    ? { error: "Non-image files in the folder were ignored." }
                    : validationError
                      ? { error: validationError }
                      : {},
                );
              }}
              className="sr-only"
              {...{ webkitdirectory: "" }}
            />
          </FormField>
          <Button type="submit" variant="primary" disabled={readOnly || pending}>
            {pending ? "Enrolling…" : "Run enrolment"}
          </Button>
        </div>
        {hasValidFolder ? (
          <p className="mt-2 text-xs text-[var(--muted)]">
            {images.length} image{images.length === 1 ? "" : "s"} · {formatFileSize(totalFileSize(images))}
          </p>
        ) : null}
        {feedback.error ? (
          <p role="alert" className="mt-3 text-xs text-[var(--danger)]">{feedback.error}</p>
        ) : null}
        {feedback.success ? (
          <p role="status" className="mt-3 text-xs text-green-700">{feedback.success}</p>
        ) : null}
      </form>
    </Card>
  );
}

function readFolderName(files: File[]): string {
  const relativePath = files[0]?.webkitRelativePath;
  if (relativePath) return relativePath.split("/")[0] ?? "";
  return files.length > 0 ? "Selected folder" : "";
}

function totalFileSize(files: File[]): number {
  return files.reduce((total, file) => total + file.size, 0);
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function validateImages(images: File[]): string | null {
  if (images.length < 1 || images.length > MAX_IMAGES) {
    return `Select a folder containing between 1 and ${MAX_IMAGES} images.`;
  }
  let totalBytes = 0;
  const names = new Set<string>();
  for (const image of images) {
    if (!SUPPORTED_IMAGE_PATTERN.test(image.name)) {
      return `${image.name} is not a JPEG or PNG image.`;
    }
    if (image.size < 1 || image.size > MAX_IMAGE_BYTES) {
      return `${image.name} must be between 1 byte and 5 MB.`;
    }
    const normalizedName = image.name.toLocaleLowerCase();
    if (names.has(normalizedName)) return "Image filenames must be unique.";
    names.add(normalizedName);
    totalBytes += image.size;
  }
  if (totalBytes > MAX_BATCH_BYTES) return "The selected image batch exceeds 250 MB.";
  return null;
}

function readSummary(value: unknown): EnrollmentSummary | null {
  if (!value || typeof value !== "object") return null;
  const payload = value as Record<string, unknown>;
  const keys = ["discovered", "enrolled", "alreadyEnrolled", "skipped", "failed"] as const;
  if (!keys.every((key) => Number.isInteger(payload[key]) && Number(payload[key]) >= 0)) return null;
  return payload as EnrollmentSummary;
}

function readError(value: unknown): string {
  if (!value || typeof value !== "object") return "Reference-face enrolment failed.";
  const detail = (value as Record<string, unknown>).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const message = (detail as Record<string, unknown>).message;
    if (typeof message === "string") return message;
  }
  return "Reference-face enrolment failed.";
}
