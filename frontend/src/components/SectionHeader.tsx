export default function SectionHeader({ children }: {children: React.ReactNode}) {
  return (
      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-lolGold/50 to-transparent" />
        <h3 className="font-display text-lg text-lolGold tracking-wide">{children}</h3>
        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-lolGold/50 to-transparent" />
      </div>
  );
}
