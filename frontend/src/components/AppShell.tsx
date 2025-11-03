export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
      <div className="min-h-screen bg-lolBg relative">
        {/* top bar */}
        <header className="sticky top-0 z-40 backdrop-blur border-b border-lolGold/40 bg-[#0b0f13]/70">
          <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-6 w-6 rounded-full bg-lolGold shadow-[0_0_16px_rgba(201,168,106,0.5)]" />
              <span className="font-semibold text-lolGold tracking-wide">Rift Rewind</span>
            </div>
            <div className="text-sm text-gray-400">Beta</div>
          </div>
        </header>

        {/* page */}
        <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
      </div>
  );
}
