type RowProps = {
  label: string;
  value?: React.ReactNode;
  hint?: string;    // small chip-like bubble on the right (e.g., “54.6%”)
};
export function StatRow({ label, value, hint }: RowProps) {
  return (
      <div className="grid grid-cols-12 items-center py-1.5">
        <div className="col-span-6 text-gray-300">{label}</div>
        <div className="col-span-4 text-gray-100 font-semibold">{value ?? "—"}</div>
        <div className="col-span-2 justify-self-end">
          {hint && <span className="px-2 py-0.5 text-xs rounded-md bg-white/10 border border-white/10">{hint}</span>}
        </div>
      </div>
  );
}
