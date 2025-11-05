// src/pages/SplitPage.tsx
import type { SplitBlock } from "../types/year";
import SplitHeader from "../components/SplitHeader";
import { Stat } from "../components/Stat";
import BestChampCard from "../components/BestChampCard";
import GoldCard from "../components/GoldCard";
import { useDdragonVersion, champIconURL } from "../lib/ddragon";

export default function SplitPage({ split }: { split: SplitBlock }) {
  const { splitId, patchRange, overall, bestChamp, topChamps } = split;
  const version = useDdragonVersion();

  return (
      <div className="min-h-screen relative overflow-hidden bg-lolBg">
        {/* Background layers (match Login/SplitEmpty) */}
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
          <div className="max-w-6xl mx-auto p-6 space-y-6">
            <SplitHeader title={`Split ${splitId.toUpperCase()} — Patches ${patchRange}`} />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left: Overall performance */}
              <section className="lg:col-span-2">
                <div className="rounded-[18px] border-2 border-lolGold bg-[#0b0f13]/70 backdrop-blur p-6 shadow-[0_0_24px_rgba(201,168,106,0.25)]">
                  {/* top accent bar */}
                  <div className="h-[3px] w-full rounded-t-[18px] bg-gradient-to-r from-lolGold/40 via-lolGold to-lolGold/40 mb-5" />

                  <GoldCard header>
                    <h3 className="text-lolGold font-semibold text-lg mb-4">Overall Performance</h3>

                    {!overall ? (
                        <div className="text-gray-400">No overall data for this split.</div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          <div className="rounded-lg bg-[#10161c] border border-white/10 p-4">
                            <Stat label="Games analyzed" value={overall.games} />
                            <Stat label="Primary queue" value={(split as any).primaryQueue ?? "—"} />
                            <Stat label="Primary role" value={overall.primaryRole ?? "—"} />
                            <Stat label="Winrate" value={overall.winrate ?? "—"} />
                          </div>
                          <div className="rounded-lg bg-[#10161c] border border-white/10 p-4">
                            <Stat label="KDA" value={overall.kda?.toFixed?.(2) ?? overall.kda ?? "—"} />
                            <Stat label="CS / min" value={overall.csPerMin?.toFixed?.(2) ?? overall.csPerMin ?? "—"} />
                            <Stat label="Vision / min" value={overall.visionPerMin?.toFixed?.(2) ?? overall.visionPerMin ?? "—"} />
                          </div>
                        </div>
                    )}
                  </GoldCard>
                </div>
              </section>

              {/* Right: Best champ + top champs */}
              <section className="lg:col-span-1 space-y-6">
                {bestChamp ? (
                    <BestChampCard champ={bestChamp} />
                ) : (
                    <div className="rounded-[18px] border-2 border-lolGold bg-[#0b0f13]/70 backdrop-blur p-4 shadow-[0_0_16px_rgba(201,168,106,0.2)]">
                      <div className="text-gray-300">No best champion identified for this split.</div>
                    </div>
                )}

                <div className="rounded-[18px] border-2 border-lolGold bg-[#0b0f13]/70 backdrop-blur p-4 shadow-[0_0_16px_rgba(201,168,106,0.2)]">
                  {/* top accent bar */}
                  <div className="h-[3px] w-full rounded-t-[18px] bg-gradient-to-r from-lolGold/40 via-lolGold to-lolGold/40 mb-4" />

                  <h4 className="text-lolGold font-semibold mb-3">Top Champs</h4>
                  {topChamps.length === 0 ? (
                      <div className="text-gray-300">No top champs this split.</div>
                  ) : (
                      <ul className="space-y-2">
                        {topChamps.map((c) => (
                            <li
                                key={`${c.name}-${c.games}`}
                                className="grid grid-cols-3 gap-2 items-center rounded bg-white/5 border border-white/10 p-2"
                            >
                              {/* real champ icon */}
                              <img
                                  src={champIconURL(c.name, version)}
                                  alt={c.name}
                                  className="h-8 w-8 rounded border border-white/15 object-cover"
                                  onError={(e) => (e.currentTarget.style.visibility = "hidden")}
                              />
                              <div>
                                <div className="text-gray-100 font-medium leading-tight">{c.name}</div>
                                <div className="text-xs text-gray-400 leading-tight">{c.role}</div>
                              </div>
                              <div className="text-right text-sm">
                                <div className="text-gray-100">{c.winrate}</div>
                                <div className="text-gray-400 text-xs">{c.games} games</div>
                              </div>
                            </li>
                        ))}
                      </ul>
                  )}
                </div>
              </section>
            </div>
          </div>
        </main>
      </div>
  );
}
