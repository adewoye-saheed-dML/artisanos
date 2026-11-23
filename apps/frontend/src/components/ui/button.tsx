import { ButtonHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger" | "light";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-gradient-to-r from-brand-600 to-brand-700 text-white shadow-brand hover:from-brand-700 hover:to-brand-800 sm:hover:-translate-y-0.5 focus-visible:ring-brand-700",
  secondary:
    "bg-surface text-ink hover:bg-brand-100/70 focus-visible:ring-brand-600",
  outline:
    "border border-line bg-white text-ink hover:border-brand-300 hover:bg-surface-blush focus-visible:ring-brand-700",
  ghost:
    "text-ink-soft hover:bg-surface hover:text-ink focus-visible:ring-brand-600",
  danger:
    "bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500",
  light:
    "bg-white text-plum shadow-md hover:bg-surface-blush sm:hover:-translate-y-0.5 focus-visible:ring-white",
};

const sizeClasses: Record<Size, string> = {
  sm: "min-h-9 px-3.5 py-2 text-xs sm:px-4",
  md: "min-h-10 px-4 py-2.5 text-sm sm:px-5",
  lg: "min-h-12 px-5 py-3 text-sm sm:px-6",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex max-w-full items-center justify-center gap-2 rounded-full text-center font-semibold leading-snug transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&>svg]:shrink-0",
        variantClasses[variant],
        sizeClasses[size],
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";
