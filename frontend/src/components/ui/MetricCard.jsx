/**
 * MetricCard — displays a single numeric metric (e.g. PSNR, SSIM).
 *
 * @param {{
 *   label: string,
 *   value: number | string,
 *   unit?: string,
 *   description?: string,
 *   status?: "good" | "warn" | "bad" | "neutral"
 * }} props
 */
export default function MetricCard({
  label,
  value,
  unit = "",
  description,
  status = "neutral",
}) {
  const statusStyles = {
    good:    "text-cyber",
    warn:    "text-amber-400",
    bad:     "text-red-400",
    neutral: "text-gray-100",
  };

  const badgeStyles = {
    good:    "bg-cyber/10 text-cyber border-cyber/30",
    warn:    "bg-amber-500/10 text-amber-400 border-amber-500/30",
    bad:     "bg-red-500/10 text-red-400 border-red-500/30",
    neutral: "bg-[#111] text-gray-500 border-panel-border",
  };

  const badgeLabels = {
    good:    "Excellent",
    warn:    "Acceptable",
    bad:     "Poor",
    neutral: null,
  };

  return (
    <div className="flex flex-col gap-3 p-5 rounded-xl bg-panel border border-panel-border">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
          {label}
        </span>
        {badgeLabels[status] && (
          <span
            className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border ${badgeStyles[status]}`}
          >
            {badgeLabels[status]}
          </span>
        )}
      </div>

      <div className="flex items-baseline gap-1">
        <span className={`text-3xl font-bold tabular-nums ${statusStyles[status]}`}>
          {typeof value === "number" ? value.toFixed(2) : value}
        </span>
        {unit && <span className="text-sm text-zinc-500 font-medium">{unit}</span>}
      </div>

      {description && (
        <p className="text-xs text-zinc-500 leading-relaxed">{description}</p>
      )}
    </div>
  );
}
