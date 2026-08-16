import { ButtonHTMLAttributes, forwardRef } from "react";

export type ButtonVariant = "default" | "primary" | "danger" | "link";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

export const BUTTON_VARIANT_CLASSES: Record<ButtonVariant, string> = {
  default:
    "border border-[#bcc5ce] bg-white text-[#2e3c47] shadow-[0_1px_0_rgba(0,0,0,0.03)] hover:bg-[#f4f6f7] hover:border-[#9ba8b3]",
  primary:
    "border border-[var(--uom-blue)] bg-[var(--uom-blue)] text-white hover:bg-[var(--uom-blue-dark)]",
  danger: "border border-[#d9a5a5] bg-white text-[var(--danger)] hover:bg-[var(--danger-bg)]",
  link: "border-none bg-transparent px-1 text-[var(--link)] shadow-none hover:underline",
};

export function buttonClassName(variant: ButtonVariant = "default", className = ""): string {
  return `inline-flex min-h-[34px] items-center gap-1.5 rounded-sm px-3 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50 ${BUTTON_VARIANT_CLASSES[variant]} ${className}`;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "default", className = "", type = "button", ...props },
  ref,
) {
  return (
    <button ref={ref} type={type} className={buttonClassName(variant, className)} {...props} />
  );
});
