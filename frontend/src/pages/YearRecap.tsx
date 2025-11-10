// src/pages/YearRecap.tsx
import { useRef, useState } from "react";
import type { YearSummary } from "../types/year";
import { useDdragonVersion, champIconURL } from "../lib/ddragon";
import ExportPngButton from "../components/ExportPngButton";
import { buildPlayerProfile } from "../lib/exportProfile";

/* ---------------- epithets + helpers ---------------- */

const EPITHETS: Record<string, string> = {
  Renekton: "the Butcher of the Sands",
  "Xin Zhao": "the Seneschal of Demacia",
  Pantheon: "the Unbreakable Spear",
  Mordekaiser: "the Iron Revenant",
  "Lee Sin": "the Blind Monk",
  Rengar: "the Pridestalker",
  Warwick: "the Uncaged Wrath of Zaun",
  Gwen: "the Hallowed Seamstress",
  Darius: "the Hand of Noxus",
  Yasuo: "the Unforgiven",
  Yone: "the Unforgotten",
  "Kai'Sa": "the Daughter of the Void",
  "Kha'Zix": "the Voidreaver",
  "Miss Fortune": "the Bounty Hunter",
  "Jarvan IV": "the Exemplar of Demacia",
  LeBlanc: "the Deceiver",
  Wukong: "the Monkey King",
};

function rankIconSrc(tier?: string) {
  if (!tier) return "/ranks/unranked.png";
  return `/ranks/${tier.toLowerCase()}.png`;
}

function epithetFor(name?: string | null) {
  if (!name) return null;
  const fixed = name.replace(/^XinZhao$/i, "Xin Zhao").replace(/^Leblanc$/i, "LeBlanc");
  return EPITHETS[fixed] ?? null;
}

function extractChampionFrom(text?: string | null) {
  if (!text) return null;
  const m = text.match(/\b(?:on|with)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)/i);
  return m?.[1] ?? null;
}

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

/* ---------------- small ChampIcon (DDragon) ---------------- */

function ChampIcon({ name, size = 144 }: { name?: string; size?: number }) {
  const version = useDdragonVersion();
  if (!name) {
    return <div style={{ width: size, height: size }} className="rounded-2xl bg-white/5 border border-white/10" />;
  }
  return (
      <img
          src={champIconURL(name, version)}
          alt={name}
          width={size}
          height={size}
          className="rounded-2xl border-2 border-lolGold shadow-[0_0_22px_rgba(201,168,106,0.3)] object-cover bg-black/40"
          loading="lazy"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.visibility = "hidden";
          }}
      />
  );
}

/* ---------------- rank helpers ---------------- */

function formatRank(r?: YearSummary["currentRank"]) {
  if (!r?.tier) return "Unranked";
  const div = r.division ? ` ${r.division}` : "";
  return `${r.tier}${div}`;
}
function formatLP(r?: YearSummary["currentRank"]) {
  return typeof r?.lp === "number" ? `${r.lp} LP` : "—";
}

function RankPill({ r }: { r?: YearSummary["currentRank"] }) {
  const txt = r?.queue ? r.queue.replace(/_/g, " ").toLowerCase() : "ranked";
  return (
      <span className="ml-auto inline-flex items-center gap-2 rounded-md border border-lolGold/60 bg-white/5 px-2 py-1 text-xs text-gray-200">
      <span className="uppercase tracking-wide text-gray-400">{txt}</span>
      <img
          src={rankIconSrc(r?.tier)}
          alt={r?.tier}
          className="h-5 w-5 object-contain"
          onError={(e) => (e.currentTarget.style.display = "none")}
      />
      <span className="text-gray-100 font-semibold">{formatRank(r)}</span>
      <span className="text-gray-300">{formatLP(r)}</span>
    </span>
  );
}

/* ---------------- Page 1 ---------------- */

function YearRecapPageOne({ data }: { data: YearSummary }) {
  const y = data.year || {};
  const overall = y.overall;
  const main = y.bestChamp;
  const topChamps = y.topChamps ?? [];
  const rank = data.currentRank;

  return (
      <section className="space-y-8">
        {/* Title bar */}
        <div className="rounded-[18px] bg-[#2237a7] border-2 border-lolGold text-center py-4 shadow-[0_0_18px_rgba(201,168,106,0.35)]">
          <div className="h-[3px] w-full rounded-t-[18px] -mt-4 bg-gradient-to-r from-lolGold/40 via-lolGold to-lolGold/40" />
          <h2 className="text-xl font-semibold text-gray-100 tracking-wide">End of Year Recap</h2>
        </div>

        {/* Main champ + title */}
        <div className="flex flex-col items-center gap-3">
          <ChampIcon name={main?.name} size={144} />
          <div className="text-gray-200 text-lg font-semibold">
            {main?.name ?? "—"} {main?.role ? `• ${main.role}` : ""}
          </div>
        </div>

        {/* Feel-good */}
        <div className="mx-auto max-w-2xl rounded-[18px] border-2 border-lolGold bg-[#0f1419] px-4 py-3 text-center shadow-[0_0_14px_rgba(201,168,106,0.2)]">
          <p className="text-gray-200">{y.feelGood ?? "GGs! Keep climbing."}</p>
        </div>

        {/* Two columns */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Overall */}
          <div className="rounded-[18px] border-2 border-lolGold bg-[#0f1419] p-5 shadow-[0_0_16px_rgba(201,168,106,0.2)]">
            <div className="flex items-center mb-4">
              <div className="h-[3px] flex-1 rounded-t-[18px] -mt-5 bg-gradient-to-r from-lolGold/40 via-lolGold to-lolGold/40" />
              <RankPill r={rank} />
            </div>

            <h3 className="text-lolGold font-semibold mb-3">Overall</h3>
            <dl className="grid grid-cols-2 gap-3 text-gray-200">
              <Stat label="Games" value={y.gamesAnalyzed ?? overall?.games} />
              <Stat label="Primary Queue" value={y.primaryQueue ?? overall?.primaryRole ?? "—"} />
              <Stat label="Winrate" value={overall?.winrate ?? "—"} />
              <Stat label="KDA" value={num(overall?.kda)} />
              <Stat label="CS / min" value={num(overall?.csPerMin, 2)} />
              <Stat label="Vision / min" value={num(overall?.visionPerMin, 2)} />
              <Stat label="Primary Role" value={overall?.primaryRole ?? "—"} />
              <Stat label="Rank" value={formatRank(rank)} />
              <Stat label="LP" value={formatLP(rank)} />
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
                        <ChampIcon name={c.name} size={48} />
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

/* ---------------- Page 2 ---------------- */

function YearRecapPageTwo({ data }: { data: YearSummary }) {
  const y = data.year || {};
  const bestGame = y.bestGame;
  const worst = y.funStat?.kind === "oops" ? y.funStat : null;
  const advice = y.advice;

  const toughChamp = (worst as any)?.champion ?? extractChampionFrom(worst?.text ?? "");
  const toughEpithet = epithetFor(toughChamp);

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
          <p className="text-gray-200">{worst?.text ?? "No ‘toughest game’ found. That’s a win in itself!"}</p>
          {toughEpithet && (
              <p className="text-gray-400 mt-2 italic">Even {toughEpithet} has off days — regroup and come back sharper.</p>
          )}
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
        </Card>
      </section>
  );
}

/* ---------------- Page 3: Matchup & Compare (rendered but EXCLUDED from PNG) ---------------- */

type MatchupGuide = {
  summary?: string;
  laningPlan?: string[];
  trading?: string[];
  wave?: string[];
  wards?: string[];
  withJungle?: string[];
  winConditions?: string[];
  commonMistakes?: string[];
  skillTips?: string[];
  itemization?: string[];
  runes?: string[];
  quickChecklist?: string[];
};

function MatchupAndCompare() {
  const version = useDdragonVersion();
  const [you, setYou] = useState("");
  const [enemy, setEnemy] = useState("");
  const [guide, setGuide] = useState<MatchupGuide | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // JSON compare
  const [jsonA, setJsonA] = useState<any | null>(null);
  const [jsonB, setJsonB] = useState<any | null>(null);
  const [claudePct, setClaudePct] = useState<number | null>(null);
  const [claudeSummary, setClaudeSummary] = useState<string | null>(null);
  const [claudeReasons, setClaudeReasons] = useState<string[]>([]);
  const [cmpLoading, setCmpLoading] = useState(false);

  async function runGuide() {
    setErr(null);
    setGuide(null);
    setLoading(true);
    try {
      const q = new URLSearchParams({ myChamp: you.trim(), enemy: enemy.trim(), mode: "auto" });
      const res = await fetch(`/api/matchup-explainer?${q.toString()}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setGuide(data);
    } catch (e: any) {
      setErr(e?.message ?? "Failed to fetch matchup guide.");
    } finally {
      setLoading(false);
    }
  }

  function readJson(file: File, set: (v: any) => void) {
    const fr = new FileReader();
    fr.onload = () => {
      try {
        set(JSON.parse(String(fr.result)));
      } catch {
        setErr("Invalid JSON file (expected RiftRewind profile JSON).");
      }
    };
    fr.readAsText(file);
  }

  async function runClaudeCompare() {
    if (!jsonA || !jsonB) return;
    setCmpLoading(true);
    setErr(null);
    setClaudePct(null);
    setClaudeSummary(null);
    setClaudeReasons([]);
    try {
      const res = await fetch("/api/compare-claude", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ aProfile: jsonA, bProfile: jsonB }),
      });
      if (res.ok) {
        const j = await res.json();
        if (typeof j?.aWinPct === "number") setClaudePct(Math.round(j.aWinPct));
        if (j?.summary) setClaudeSummary(j.summary);
        if (Array.isArray(j?.reasons)) setClaudeReasons(j.reasons);
      } else {
        const text = await res.text();
        setErr(text || "Comparison service returned an error.");
      }
    } catch (e: any) {
      setErr(e?.message ?? "Failed to compare profiles.");
    } finally {
      setCmpLoading(false);
    }
  }

  const youIcon = you ? champIconURL(you, version) : "";
  const enemyIcon = enemy ? champIconURL(enemy, version) : "";

  return (
      <section className="space-y-6" data-export-ignore="true">
        <div className="rounded-[18px] bg-[#2237a7] border-2 border-lolGold text-center py-3 shadow-[0_0_18px_rgba(201,168,106,0.35)]">
          <h3 className="text-lg font-semibold text-gray-100 tracking-wide">Matchup Guide & Player Comparison</h3>
        </div>

        {/* Matchup inputs */}
        <Card title="How to Play the Matchup">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
            <div>
              <label className="text-sm text-gray-300">You (champ)</label>
              <input
                  value={you}
                  onChange={(e) => setYou(e.target.value)}
                  placeholder="Nasus"
                  className="mt-1 w-full rounded-md bg-[#121821] border border-lolGold/40 px-3 py-2 text-gray-100"
              />
            </div>
            <div className="text-center text-gray-300 font-medium">vs</div>
            <div>
              <label className="text-sm text-gray-300">Enemy (champ)</label>
              <input
                  value={enemy}
                  onChange={(e) => setEnemy(e.target.value)}
                  placeholder="Renekton"
                  className="mt-1 w-full rounded-md bg-[#121821] border border-lolGold/40 px-3 py-2 text-gray-100"
              />
            </div>
          </div>

          <div className="mt-4 flex items-center gap-4">
            <img src={youIcon} alt="" className="h-16 w-16 rounded-lg border border-lolGold/50 object-cover bg-black/40" />
            <button
                onClick={runGuide}
                disabled={loading || !you || !enemy}
                className="px-4 py-2 rounded-md border-2 border-lolGold bg-[#2237a7] text-gray-100 disabled:opacity-60"
            >
              {loading ? "Generating…" : "Generate Guide"}
            </button>
            <img src={enemyIcon} alt="" className="h-16 w-16 rounded-lg border border-lolGold/50 object-cover bg-black/40" />
          </div>

          {err && <p className="mt-3 text-red-300">{err}</p>}

          {guide && (
              <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="rounded-lg border border-lolGold/40 bg-[#0b1116] p-4">
                  <h4 className="text-lolGold font-semibold mb-2">General Champ Advice</h4>
                  <p className="text-gray-200 mb-2">{guide.summary}</p>
                  <ul className="list-disc list-inside text-gray-300 space-y-1">
                    {(guide.skillTips ?? []).slice(0, 8).map((t, i) => (
                        <li key={i}>{t}</li>
                    ))}
                  </ul>
                </div>
                <div className="rounded-lg border border-lolGold/40 bg-[#0b1116] p-4">
                  <h4 className="text-lolGold font-semibold mb-2">Matchup Advice</h4>
                  <ul className="list-disc list-inside text-gray-300 space-y-1">
                    {(guide.trading ?? []).slice(0, 6).map((t, i) => (
                        <li key={i}>{t}</li>
                    ))}
                    {(guide.wave ?? []).slice(0, 4).map((t, i) => (
                        <li key={`w${i}`}>{t}</li>
                    ))}
                    {(guide.withJungle ?? []).slice(0, 3).map((t, i) => (
                        <li key={`j${i}`}>{t}</li>
                    ))}
                  </ul>
                </div>
              </div>
          )}
        </Card>

        {/* Compare JSONs (Claude only) */}
        <Card title="Compare Two Players">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-center">
            <div>
              <label className="text-sm text-gray-300">Your JSON</label>
              <input
                  type="file"
                  accept="application/json"
                  onChange={(e) => e.target.files?.[0] && readJson(e.target.files[0], setJsonA)}
                  className="mt-1 block w-full text-gray-200"
              />
            </div>
            <div className="text-center text-gray-300 font-medium">vs</div>
            <div>
              <label className="text-sm text-gray-300">Opponent JSON</label>
              <input
                  type="file"
                  accept="application/json"
                  onChange={(e) => e.target.files?.[0] && readJson(e.target.files[0], setJsonB)}
                  className="mt-1 block w-full text-gray-200"
              />
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-4">
            <button
                onClick={runClaudeCompare}
                disabled={!jsonA || !jsonB || cmpLoading}
                className="px-4 py-2 rounded-md border-2 border-lolGold bg-[#2237a7] text-gray-100 disabled:opacity-60"
            >
              {cmpLoading ? "Asking Claude…" : "RiftRewind Verdict"}
            </button>

            {claudePct != null && (
                <div className="ml-auto rounded-md border border-lolGold/60 bg-white/5 px-3 py-2 text-gray-100">
                  <span className="text-lolGold font-semibold">Win % (You): </span>
                  <span>{claudePct}%</span>
                </div>
            )}
          </div>

          {(claudeSummary || claudeReasons.length > 0) && (
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-lg border border-lolGold/40 bg-[#0b1116] p-4">
                  <h4 className="text-lolGold font-semibold mb-2">RiftRewind Verdict</h4>
                  <p className="text-gray-200">{claudeSummary ?? "—"}</p>
                </div>
                <div className="rounded-lg border border-lolGold/40 bg-[#0b1116] p-4">
                  <h4 className="text-lolGold font-semibold mb-2">Key Reasons</h4>
                  <ul className="list-disc list-inside text-gray-300 space-y-1">
                    {claudeReasons.map((r, i) => (
                        <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              </div>
          )}
        </Card>
      </section>
  );
}

/* ---------------- main export ---------------- */

export default function YearRecap({ data }: { data: YearSummary }) {
  const exportRef = useRef<HTMLDivElement>(null);

  // Build a filename from Riot ID if present (fallback to best champ / "player")
  const riotId =
      [ (data as any)?.playerName, (data as any)?.playerTag ].filter(Boolean).join("#") ||
      data?.year?.bestChamp?.name ||
      "player";

  const pngName = `RiftRewind-${riotId.replace(/\s+/g, "_")}.png`;

  function exportJson() {
    const id = riotId || "player";
    const profile = buildPlayerProfile(id, data);
    const blob = new Blob([JSON.stringify(profile, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `RiftRewind-${id}-profile.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function goToLogin() {
    window.location.assign("/"); // adjust if your login path differs
  }

  return (
      <div className="min-h-screen relative overflow-hidden bg-lolBg">
        {/* BG layers */}
        <div
            className="absolute inset-0 bg-center bg-cover opacity-20"
            style={{ backgroundImage: `url('/lol-bg.jpg')` }}
            aria-hidden
        />
        <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-black/30 to-black/70" aria-hidden />
        <div className="absolute inset-0 lol-vignette" aria-hidden />

        <main className="relative z-10">
          {/* Toolbar (ignored in export) */}
          <div
              className="max-w-6xl mx-auto px-6 pt-6 pb-2 flex flex-wrap gap-3 justify-end"
              data-export-ignore="true"
          >
            <button
                onClick={goToLogin}
                className="rounded-md border-2 border-lolGold bg-white/5 px-3 py-2 text-sm text-gray-100 hover:bg-white/10"
                title="Look up another profile"
            >
              Look up another profile
            </button>

            <button
                onClick={exportJson}
                className="rounded-md border-2 border-lolGold bg-white/5 px-3 py-2 text-sm text-gray-100 hover:bg-white/10"
                title="Export comparable JSON"
            >
              Export JSON
            </button>

            <ExportPngButton
                target={exportRef as React.RefObject<Element | null>}
                filename={pngName}
            />
          </div>


          <div ref={exportRef} className="max-w-6xl mx-auto p-6 space-y-16 print:space-y-0">
            <div className="print:break-after-page">
              <YearRecapPageOne data={data} />
            </div>
            <div>
              <YearRecapPageTwo data={data} />
            </div>
          </div>


          <div className="max-w-6xl mx-auto p-6" data-export-ignore="true">
            <MatchupAndCompare />
          </div>
        </main>
      </div>
  );
}
