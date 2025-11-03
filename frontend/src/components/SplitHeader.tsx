
export default function SplitHeader({ title }: { title: string }) {
  return (
      <div className="rounded-xl border border-lolGold/40 bg-[#2035c5]/80 text-gray-100 shadow-[0_12px_30px_rgba(0,0,0,0.4)]">
        <div className="px-6 py-4 text-center font-semibold tracking-wide">{title}</div>
      </div>
  );
}
