// src/lib/ddragon.ts
import { useEffect, useState } from "react";


const FALLBACK_VERSION = "14.21.1";

/** Fetches the latest DDragon version once per load. */
export function useDdragonVersion() {
  const [ver, setVer] = useState(FALLBACK_VERSION);

  useEffect(() => {
    fetch("https://ddragon.leagueoflegends.com/api/versions.json")
    .then((r) => r.json())
    .then((arr: string[]) => {
      if (Array.isArray(arr) && arr.length) setVer(arr[0]);
    })
    .catch(() => setVer(FALLBACK_VERSION));
  }, []);

  return ver;
}

/** Some champs have file names that don't match their display name. */
const SPECIAL: Record<string, string> = {
  "Wukong": "MonkeyKing",
  "Monkey King": "MonkeyKing",
  "Dr. Mundo": "DrMundo",
  "Miss Fortune": "MissFortune",
  "Master Yi": "MasterYi",
  "Twisted Fate": "TwistedFate",
  "Xin Zhao": "XinZhao",
  "Jarvan IV": "JarvanIV",
  "Aurelion Sol": "AurelionSol",
  "Tahm Kench": "TahmKench",
  "Renata Glasc": "Renata",
  "Vel'Koz": "Velkoz",
  "Kha'Zix": "Khazix",
  "Kai'Sa": "Kaisa",
  "Cho'Gath": "Chogath",
  "Rek'Sai": "RekSai",
  "LeBlanc": "Leblanc",
  "Bel'Veth": "Belveth",
  "K'Sante": "KSante",
  "Nunu & Willump": "Nunu",
};

function normalizeChampionKey(name: string) {
  if (!name) return "Aatrox";
  if (SPECIAL[name]) return SPECIAL[name];


  const cleaned = name
  .replace(/['.&]/g, "")
  .replace(/\s+/g, "");
  return cleaned;
}

/** Returns a CDN URL for a champion square icon. */
export function champIconURL(champName: string, version: string) {
  const key = normalizeChampionKey(champName);
  return `https://ddragon.leagueoflegends.com/cdn/${version}/img/champion/${key}.png`;
}
