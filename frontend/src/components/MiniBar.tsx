export function MiniBar({ pct, className="" }: { pct: number; className?: string }) {
  const clamped = Math.max(0, Math.min(100, pct));
  return (
      <div className={["h-2 rounded bg-white/10 overflow-hidden", className].join(" ")}>
        <div
            className="h-full bg-gradient-to-r from-lolBlue via-lolBlue to-lolGold"
            style={{ width: `${clamped}%` }}
        />
      </div>
  );
}
