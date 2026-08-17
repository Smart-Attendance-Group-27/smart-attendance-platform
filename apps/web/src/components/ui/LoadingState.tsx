import { SpinnerIcon } from "@/components/icons";

type LoadingStateProps = {
  label?: string;
};

export function LoadingState({ label = "Loading..." }: LoadingStateProps) {
  return (
    <div role="status" className="flex flex-col items-center gap-2 py-12 text-center text-[var(--muted)]">
      <SpinnerIcon aria-hidden="true" width={22} height={22} />
      <p className="text-xs">{label}</p>
    </div>
  );
}
