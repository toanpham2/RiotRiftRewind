export function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
      <div className="flex items-center justify-between py-1 border-b border-white/5 last:border-0">
        <span className="text-gray-400 text-sm">{label}</span>
        <span className="text-gray-100 font-medium">{value}</span>
      </div>
  );
}