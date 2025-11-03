import type { YearSummary } from "../types/year";

/** ---------------- Page 1: title bar, main champ, feel-good, stats + other champs ---------------- */
function YearRecapPageOne({ data }: { data: YearSummary }) {
  const y = data.year || {};
  const overall = y.overall;
  const main = y.bestChamp;
  const topChamps = y.topChamps ?? [];

  return (
      <section className="space-y-8">
        {/* Title bar */}
        <div className="rounded-[18px] bg-[#2237a7] border-2 border-lolGold text-center py-4 shadow-[0_0_18px_rgba(201,168,106,0.35)]">
          <div className="h-[3px] w-full rounded-t-[18px] -mt-4 bg-gradient-to-r from-lolGold/40 via-lolGold to-lolGold/40" />
          <h2 className="text-xl font-semibold text-gray-100 tracking-wide">End of Year Recap</h2>
        </div>

        {/* Centered main champ + title */}
        <div className="flex flex-col items-center gap-3">
          <div className="h-36 w-36 rounded-2xl border-2 border-lolGold bg-[#8a1111]/90 shadow-[0_0_22px_rgba(201,168,106,0.3)]" />
          <div className="text-gray-200 text-lg font-semibold">
            {main?.name ?? "—"} {main?.role ? `• ${main.role}` : ""}
          </div>
        </div>

        {/* Feel-good quote */}
        <div className="mx-auto max-w-2xl rounded-[18px] border-2 border-lolGold bg-[#0f1419] px-4 py-3 text-center shadow-[0_0_14px_rgba(201,168,106,0.2)]">
          <p className="text-gray-200">{y.feelGood ?? "GGs! Keep climbing."}</p>
        </div>

        {/* Two columns */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Overall stats */}
          <div className="rounded-[18px] border-2 border-lolGold bg-[#0f1419] p-5 shadow-[0_0_16px_rgba(201,168,106,0.2)]">
            <div className="h-[3px] w-full rounded-t-[18px] -mt-5 mb-4 bg-gradient-to-r from-lolGold/40 via-lolGold to-lolGold/40" />
            <h3 className="text-lolGold font-semibold mb-3">Overall</h3>
            <dl className="grid grid-cols-2 gap-3 text-gray-200">
              <Stat label="Games" value={y.gamesAnalyzed ?? overall?.games} />
              <Stat label="Primary Queue" value={y.primaryQueue ?? overall?.primaryRole ?? "—"} />
              <Stat label="Winrate" value={overall?.winrate ?? "—"} />
              <Stat label="KDA" value={num(overall?.kda)} />
              <Stat label="CS / min" value={num(overall?.csPerMin, 2)} />
              <Stat label="Vision / min" value={num(overall?.visionPerMin, 2)} />
              <Stat label="Primary Role" value={overall?.primaryRole ?? "—"} />
            </dl>
          </div>

          {/* Other champs */}
          <div className="rounded-[18px] border-2 border-lolGold bg-[#0f1419] p-5 shadow-[0_0_16px_rgba(201,168,106,0.2)]">
            <div className="h-[3px] w-full rounded-t-[18px] -mt-5 mb-4 bg-gradient-to-r from-lolGold/40 via-lolGold to-lolGold/40" />
            <h3 className="text-lolGold font-semibold mb-4">Other Champs</h3>
            {topChamps.length === 0 ? (
                <div className="text-gray-400">No secondary champions recorded.</div>
            ) : (
                <ul className="grid sm:grid-cols-2 gap-4">
                  {topChamps.map((c, i) => (
                      <li
                          key={`${c.name}-${i}`}
                          className="flex items-center gap-3 rounded-lg border border-lolGold/40 bg-[#0b1116] px-3 py-2"
                      >
                        <div className="h-12 w-12 rounded-lg bg-[#1b2e92]/40 border border-lolGold/40 flex-shrink-0" />
                        <div className="min-w-0">
                          <div className="text-gray-100 truncate">
                            <span className="mr-2 text-lolGold font-semibold">#{i + 1}</span>
                            {c.name} {c.role ? `• ${c.role}` : ""}
                          </div>
                          <div className="text-sm text-gray-400">
                            {c.games ?? "—"} games • {c.winrate ?? "—"} WR
                          </div>
                        </div>
                      </li>
                  ))}
                </ul>
            )}
          </div>
        </div>
      </section>
  );
}

/** ---------------- Page 2: best/worst game, advice blocks ---------------- */
function YearRecapPageTwo({ data }: { data: YearSummary }) {
  const y = data.year || {};
  const bestGame = y.bestGame;
  const worst = y.funStat?.kind === "oops" ? y.funStat : null;
  const advice = y.advice;

  return (
      <section className="space-y-8">
        {/* Best game */}
        <Card tone="good" title="Best Game">
          <Row left="Champion" right={bestGame?.champion ?? "—"} />
          <Row left="KDA" right={bestGame?.kda?.toString?.() ?? String(bestGame?.kda ?? "—")} />
          {y.bestGameQuote && <p className="text-gray-200 mt-2">{y.bestGameQuote}</p>}
        </Card>

        {/* Toughest game */}
        <Card tone="bad" title="Toughest Game">
          <p className="text-gray-200">
            {worst?.text ?? "No ‘toughest game’ found. That’s a win in itself!"}
          </p>
        </Card>

        {/* Advice */}
        <Card title="Advice">
          {advice?.summary && <p className="text-gray-200 mb-3">{advice.summary}</p>}
          {!!advice?.insights?.length && (
              <div className="space-y-1">
                {advice!.insights!.map((t: string, i: number) => (
                    <p key={i} className="text-gray-300">
                      • {t}
                    </p>
                ))}
              </div>
          )}
        </Card>

        {/* Focus */}
        <Card title="What to Focus On">
          {!!advice?.focus?.length ? (
              <ul className="list-disc list-inside text-gray-200 space-y-1">
                {advice!.focus!.map((t: string, i: number) => (
                    <li key={i}>{t}</li>
                ))}
              </ul>
          ) : (
              <p className="text-gray-400">No focus items available.</p>
          )}
          {advice?.fun && <p className="text-gray-400 mt-3 italic">{advice.fun}</p>}
        </Card>
      </section>
  );
}

/** ---------------- Main wrapper renders both “pages” with background layers ---------------- */
export default function YearRecap({ data }: { data: YearSummary }) {
  return (
      <div className="min-h-screen relative overflow-hidden bg-lolBg">
        {/* Background layers to match other screens */}
        <div
            className="absolute inset-0 bg-center bg-cover opacity-20"
            style={{ backgroundImage: `url('/lol-bg.jpg')` }}
            aria-hidden
        />
        <div
            className="absolute inset-0 bg-gradient-to-b from-black/40 via-black/30 to-black/70"
            aria-hidden
        />
        <div className="absolute inset-0 lol-vignette" aria-hidden />

        <main className="relative z-10">
          <div className="max-w-6xl mx-auto p-6 space-y-16 print:space-y-0">
            <div className="print:break-after-page">
              <YearRecapPageOne data={data} />
            </div>
            <div>
              <YearRecapPageTwo data={data} />
            </div>
          </div>
        </main>
      </div>
  );
}

/* ---------------- helpers ---------------- */

function num(v: unknown, digits = 2) {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n.toFixed(digits) : "—";
}

function Stat({ label, value }: { label: string; value: string | number | undefined }) {
  return (
      <div className="flex flex-col">
        <dt className="text-sm text-gray-400">{label}</dt>
        <dd className="text-gray-100">{value ?? "—"}</dd>
      </div>
  );
}

function Row({ left, right }: { left: string; right: string }) {
  return (
      <div className="flex items-center justify-between text-gray-200">
        <span className="text-gray-300">{left}</span>
        <span className="font-medium">{right}</span>
      </div>
  );
}

function Card({
                title,
                tone,
                children,
              }: {
  title?: string;
  tone?: "good" | "bad";
  children: React.ReactNode;
}) {
  const toneBg =
      tone === "good"
          ? "bg-emerald-600/25 border-emerald-400/50"
          : tone === "bad"
              ? "bg-red-600/25 border-red-400/50"
              : "bg-[#0f1419] border-lolGold/60";

  return (
      <div className={`rounded-[18px] border-2 ${toneBg} p-5 shadow-[0_0_16px_rgba(201,168,106,0.2)]`}>
        <div className="h-[3px] w-full rounded-t-[18px] -mt-5 mb-4 bg-gradient-to-r from-lolGold/40 via-lolGold to-lolGold/40" />
        {title && <h3 className="text-lolGold font-semibold mb-3">{title}</h3>}
        {children}
      </div>
  );
}
