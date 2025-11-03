// src/types/year.ts

/** In-game role. Keep union + string to be permissive. */
export type Role = "top" | "jungle" | "mid" | "adc" | "support" | string;

/* --------------------------- Split-level types --------------------------- */

export interface SplitOverall {
  games: number;
  winrate: string;        // e.g., "53.54%"
  kda: number;            // e.g., 2.01
  csPerMin: number;
  visionPerMin: number;
  primaryRole: Role;
}

export interface BestChamp {
  name: string;
  role: Role;
  games: number;
  wins: number;
  winrate: string;        // "59.09%"
  kda: number;
  csPerMin: number;
  visionPerMin: number;
  kp: string;             // "42.27%"
  dmgShare: string;       // "22.31%"
  score: number;          // arbitrary model score
}

export interface TopChampLite {
  name: string;
  role: Role;
  games: number;
  winrate: string;
}

export interface SplitBlock {
  splitId: "s1" | "s2" | "s3";
  patchRange: string;     // "15.17 - 15.24"
  gamesAnalyzed: number;
  primaryQueue: string;   // "solo"
  overall: SplitOverall | null;
  bestChamp: BestChamp | null;
  topChamps: TopChampLite[];
}

/* ---------------------------- Year-level types --------------------------- */

export interface AdviceBlock {
  summary?: string;
  insights?: string[];
  focus?: string[];
  fun?: string;           // optional playful line
}

export interface FunStat {
  kind?: string;          // e.g., "oops"
  text?: string;          // human-readable line
}

export interface GameSummary {
  champion?: string;      // e.g., "Renekton"
  kda?: string;           // e.g., "4/1/13"
  winrate?: string;       // optional
}

export interface CurrentRank {
  queue?: string;         // "RANKED_SOLO_5x5"
  tier?: string;          // "MASTER"
  division?: string;      // "I"
  lp?: number;            // 80
  wins?: number;
  losses?: number;
}

export interface YearData {
  /** Aggregated context */
  primaryQueue?: string;          // e.g., "solo"
  gamesAnalyzed?: number;

  /** Aggregations and highlights */
  overall?: SplitOverall;         // reuse split overall shape
  bestChamp?: BestChamp;
  topChamps?: TopChampLite[];

  /** Copy / narrative */
  feelGood?: string;              // motivational line
  bestGame?: GameSummary;
  bestGameQuote?: string;
  funStat?: FunStat;
  advice?: AdviceBlock;
}

/* ---------------------------- Root payload type -------------------------- */

export interface YearSummary {
  splits: {
    s1: SplitBlock;
    s2: SplitBlock;
    s3: SplitBlock;
  };
  year: YearData;                 // <-- added for recap pages
  currentRank?: CurrentRank;      // optional, present in your sample JSON
}
