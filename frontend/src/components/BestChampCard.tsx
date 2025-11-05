import type { BestChamp } from "../types/year";
import {champIconURL, useDdragonVersion} from "../lib/ddragon.ts";

/* ---------- local helpers ---------- */


function pctToNumber(s: string | number | undefined | null) {
  if (s == null) return 0;
  if (typeof s === "number") return s;
  const n = Number(String(s).replace("%", "").trim());
  return Number.isFinite(n) ? n : 0;
}

function clamp01(x: number) {
  return Math.max(0, Math.min(100, x));
}

function fmtNum(n: unknown, digits = 2) {
  const v = typeof n === "number" ? n : Number(n);
  return Number.isFinite(v) ? v.toFixed(digits) : "—";
}


function Chip({ children }: { children: React.ReactNode }) {
  return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs bg-white/5 border border-white/10 text-gray-200">
      {children}
    </span>
  );
}

function MiniBar({ pct }: { pct: number }) {
  const w = clamp01(pct);
  return (
      <div className="h-2 rounded bg-white/10 overflow-hidden">
        <div
            className="h-full bg-gradient-to-r from-lolBlue to-lolGold"
            style={{ width: `${w}%` }}
        />
      </div>
  );
}

/* ---------- card ---------- */

export default function BestChampCard({ champ }: { champ: BestChamp }) {
  const version = useDdragonVersion();
  const winPct = pctToNumber(champ?.winrate);
  const kpPct  = pctToNumber(champ?.kp);
  const dmgPct = pctToNumber(champ?.dmgShare);

  return (
      <div className="rounded-xl border-2 border-lolGold bg-[#0b0f13]/70 p-4 shadow-[0_0_16px_rgba(201,168,106,0.25)]">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-sm text-gray-300">Best Champ</div>
            <div className="text-lg font-semibold text-lolGold">{champ?.name ?? "—"}</div>
            <div
                className="text-xs text-gray-400 uppercase tracking-wide">{champ?.role ?? "—"}</div>
          </div>
          {/* Placeholder for champion icon */}

          <img
              src={champIconURL(champ.name, version)}
              alt={champ.name}
              className="h-36 w-36 rounded-2xl border-2 border-lolGold shadow-[0_0_22px_rgba(201,168,106,0.3)] object-cover"
          />
        </div>

        {/* Stat lines with chips + mini bars */}
        <div className="rounded-lg bg-[#10161c] border border-white/10 p-3 mb-4 space-y-3">
          <div>
            <div className="flex items-center justify-between text-xs text-gray-300 mb-1">
              <span>Winrate</span>
              <Chip>{typeof champ?.winrate === "string" ? champ.winrate : `${Math.round(winPct)}%`}</Chip>
            </div>
            <MiniBar pct={winPct} />
          </div>

          <div>
            <div className="flex items-center justify-between text-xs text-gray-300 mb-1">
              <span>Kill Participation</span>
              <Chip>{typeof champ?.kp === "string" ? champ.kp : `${Math.round(kpPct)}%`}</Chip>
            </div>
            <MiniBar pct={kpPct} />
          </div>

          <div>
            <div className="flex items-center justify-between text-xs text-gray-300 mb-1">
              <span>Damage Share</span>
              <Chip>{typeof champ?.dmgShare === "string" ? champ.dmgShare : `${Math.round(dmgPct)}%`}</Chip>
            </div>
            <MiniBar pct={dmgPct} />
          </div>
        </div>

        {/* Compact metrics grid */}
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="rounded bg-white/5 p-2">
            <div className="text-gray-400 text-xs">Games</div>
            <div className="text-gray-100 font-semibold">{champ?.games ?? "—"}</div>
          </div>
          <div className="rounded bg-white/5 p-2">
            <div className="text-gray-400 text-xs">KDA</div>
            <div className="text-gray-100 font-semibold">{fmtNum(champ?.kda)}</div>
          </div>
          <div className="rounded bg-white/5 p-2">
            <div className="text-gray-400 text-xs">CS / min</div>
            <div className="text-gray-100 font-semibold">{fmtNum(champ?.csPerMin)}</div>
          </div>
          <div className="rounded bg-white/5 p-2">
            <div className="text-gray-400 text-xs">Vision / min</div>
            <div className="text-gray-100 font-semibold">{fmtNum(champ?.visionPerMin)}</div>
          </div>
        </div>
      </div>
  );
}
