import { AlertIcon } from "@/components/icons";
import { Button } from "@/components/ui/Button";

type ErrorStateProps = {
  title?: string;
  description?: string;
  onRetry?: () => void;
};

export function ErrorState({ title = "Something went wrong", description, onRetry }: ErrorStateProps) {
  return (
    <div role="alert" className="flex flex-col items-center gap-2 py-12 text-center">
      <AlertIcon aria-hidden="true" width={26} height={26} className="text-[var(--danger)]" />
      <p className="text-sm font-semibold text-[var(--text)]">{title}</p>
      {description ? <p className="max-w-sm text-xs text-[var(--muted)]">{description}</p> : null}
      {onRetry ? (
        <Button variant="default" onClick={onRetry} className="mt-1">
          Try again
        </Button>
      ) : null}
    </div>
  );
}
