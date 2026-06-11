/**
 * Spinner — animated loading indicator.
 *
 * @param {{ size?: "sm" | "md" | "lg", className?: string }} props
 */
export default function Spinner({ size = "md", className = "" }) {
  const sizes = {
    sm: "h-4 w-4 border-2",
    md: "h-6 w-6 border-2",
    lg: "h-8 w-8 border-[3px]",
  };

  return (
    <span
      className={[
        "inline-block rounded-full animate-spin",
        "border-zinc-800 border-t-cyber",
        sizes[size],
        className,
      ].join(" ")}
      aria-label="Loading"
      role="status"
    />
  );
}

/**
 * SkeletonBlock — placeholder rectangle shown during loading.
 *
 * @param {{ className?: string }} props
 */
export function SkeletonBlock({ className = "" }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-[#111] ${className}`}
      aria-hidden="true"
    />
  );
}
