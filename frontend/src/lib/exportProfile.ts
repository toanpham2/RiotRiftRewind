import type { YearSummary } from "../types/year";

export type PlayerProfileV1 = {
  version: "v1";
  playerId: string;               // "MK1Paris#NA1"
  rank?: { queue?: string; tier?: string; division?: string; lp?: number };
  role?: string;
  overall?: {
    games?: number;
    winrate?: number;
    kda?: number;
    csPerMin?: number;
    visionPerMin?: number;
  };
  bestChamp?: {
    name?: string;
    role?: string;
    games?: number;
    winrate?: number;
    kda?: number;
    csPerMin?: number;
    visionPerMin?: number;
    kp?: number;
    dmgShare?: number;
  };
  topChamps?: Array<{ name: string; role?: string; games?: number; winrate?: number }>;
};

function pctTo01(p?: string) {
  if (!p) return undefined;
  const n = Number(String(p).replace("%","").trim());
  return Number.isFinite(n) ? Math.max(0, Math.min(1, n/100)) : undefined;
}

export function buildPlayerProfile(id: string, y: YearSummary): PlayerProfileV1 {
  const o = y.year?.overall;
  const b = y.year?.bestChamp;

  return {
    version: "v1",
    playerId: id,
    rank: y.currentRank ? {
      queue: y.currentRank.queue, tier: y.currentRank.tier,
      division: y.currentRank.division, lp: y.currentRank.lp
    } : undefined,
    role: o?.primaryRole,
    overall: o ? {
      games: o.games,
      winrate: pctTo01(o.winrate),
      kda: o.kda,
      csPerMin: o.csPerMin,
      visionPerMin: o.visionPerMin
    } : undefined,
    bestChamp: b ? {
      name: b.name,
      role: b.role,
      games: b.games,
      winrate: pctTo01(b.winrate),
      kda: b.kda,
      csPerMin: b.csPerMin,
      visionPerMin: b.visionPerMin,
      kp: pctTo01(b.kp),
      dmgShare: pctTo01(b.dmgShare)
    } : undefined,
    topChamps: (y.year?.topChamps ?? []).map(c => ({
      name: c.name, role: c.role, games: c.games, winrate: pctTo01(c.winrate)
    })),
  };
}
