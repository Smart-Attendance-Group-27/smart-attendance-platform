import { Button } from "@/components/ui/Button";

type PaginationProps = {
  page: number;
  pageCount: number;
  onPageChange: (page: number) => void;
};

export function Pagination({ page, pageCount, onPageChange }: PaginationProps) {
  if (pageCount <= 1) return null;

  return (
    <div className="flex items-center justify-between border-t border-[var(--line)] px-3.5 py-2.5 text-xs text-[var(--muted)]">
      <span>
        Page {page} of {pageCount}
      </span>
      <div className="flex gap-1.5">
        <Button variant="default" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Previous
        </Button>
        <Button variant="default" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)}>
          Next
        </Button>
      </div>
    </div>
  );
}
