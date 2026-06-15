import * as React from "react";

type Variant = "primary" | "secondary" | "accent" | "ghost" | "danger";
type Size = "sm" | "md";

const variants: Record<Variant, string> = {
  primary: "bg-primary text-primary-fg hover:bg-[#1B3A9E] focus-visible:ring-primary",
  secondary: "bg-secondary text-white hover:bg-[#2F6FE0] focus-visible:ring-secondary",
  accent: "bg-accent text-white hover:bg-[#C06A05] focus-visible:ring-accent",
  ghost: "bg-transparent text-foreground hover:bg-muted focus-visible:ring-secondary",
  danger: "bg-destructive text-white hover:bg-[#B91C1C] focus-visible:ring-destructive",
};

const sizes: Record<Size, string> = {
  sm: "h-9 px-3 text-sm",
  md: "h-11 px-4 text-sm",
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    />
  );
}
