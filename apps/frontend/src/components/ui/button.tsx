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
    "bg-gradient-to-r from-brand-600 to-brand-700 text-white shadow-brand hover:from-brand-700 hover:to-brand-800 hover:-translate-y-0.5 focus-visible:ring-brand-700",
  secondary:
    "bg-surface text-ink hover:bg-brand-100/70 focus-visible:ring-brand-600",
  outline:
    "border border-line bg-white text-ink hover:border-brand-300 hover:bg-surface-blush focus-visible:ring-brand-700",
  ghost:
    "text-ink-soft hover:bg-surface hover:text-ink focus-visible:ring-brand-600",
  danger:
    "bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500",
  light:
    "bg-white text-plum shadow-md hover:bg-surface-blush hover:-translate-y-0.5 focus-visible:ring-white",
};

const sizeClasses: Record<Size, string> = {
  sm: "h-9 px-4 text-xs",
  md: "h-10 px-5 text-sm",
  lg: "h-12 px-6 text-sm",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
        variantClasses[variant],
        sizeClasses[size],
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";
