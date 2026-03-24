/**
 * CircularGauge — SVG-based radial progress indicator.
 *
 * @param {{
 *   value: number,          // raw value to display
 *   progress: number,       // 0–1 fill fraction
 *   label: string,
 *   sublabel?: string,
 *   color?: string,         // Tailwind stroke color class OR hex
 *   size?: number,
 *   invertStatus?: boolean  // if true, low value = good (e.g. BER)
 * }} props
 */
export default function CircularGauge({
  value,
  progress,
  label,
  sublabel,
  size = 140,
  invertStatus = false,
}) {
  const RADIUS = 44;
  const STROKE = 8;
  const circumference = 2 * Math.PI * RADIUS;
  const offset = circumference * (1 - Math.max(0, Math.min(1, progress)));

  // Determine colour based on progress and direction
  const getColor = () => {
    const normalised = invertStatus ? 1 - progress : progress;
    if (normalised >= 0.9) return "#00FF66"; // cyber neon
    if (normalised >= 0.7) return "#fbbf24"; // amber-400
    return "#f87171";                         // red-400
  };

  const color = getColor();

  // Glow filter id must be unique per instance
  const filterId = `glow-${label.replace(/\s+/g, "-").toLowerCase()}`;

  const displayValue =
    value <= 1 && value >= 0 ? `${(value * 100).toFixed(1)}%` : value.toFixed(3);

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox="0 0 100 100"
          className="rotate-[-90deg]"
        >
          <defs>
            <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Track */}
          <circle
            cx="50"
            cy="50"
            r={RADIUS}
            fill="none"
            stroke="#27272a"
            strokeWidth={STROKE}
          />

          {/* Progress arc */}
          <circle
            cx="50"
            cy="50"
            r={RADIUS}
            fill="none"
            stroke={color}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            filter={`url(#${filterId})`}
            style={{ transition: "stroke-dashoffset 0.8s cubic-bezier(0.4,0,0.2,1)" }}
          />
        </svg>

        {/* Centre text — counter-rotate to appear upright */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="text-lg font-bold tabular-nums"
            style={{ color }}
          >
            {displayValue}
          </span>
        </div>
      </div>

      <div className="text-center">
        <p className="text-sm font-semibold text-zinc-200">{label}</p>
        {sublabel && (
          <p className="text-xs text-zinc-500 mt-0.5">{sublabel}</p>
        )}
      </div>
    </div>
  );
}
