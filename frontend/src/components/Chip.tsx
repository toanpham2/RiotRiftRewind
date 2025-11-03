export function Chip({ children }: { children: React.ReactNode }) {
  return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs
                     bg-white/5 border border-white/10 text-gray-200">
      {children}
    </span>
  );
}
