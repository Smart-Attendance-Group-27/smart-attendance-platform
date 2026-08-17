import Link, { LinkProps } from "next/link";
import { ReactNode } from "react";
import { ButtonVariant, buttonClassName } from "@/components/ui/Button";

type LinkButtonProps = LinkProps & {
  variant?: ButtonVariant;
  className?: string;
  children: ReactNode;
};

export function LinkButton({ variant = "default", className = "", children, ...props }: LinkButtonProps) {
  return (
    <Link className={buttonClassName(variant, className)} {...props}>
      {children}
    </Link>
  );
}
