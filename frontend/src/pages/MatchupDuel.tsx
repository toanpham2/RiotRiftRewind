import { useState } from "react";
import { champIconURL, useDdragonVersion } from "../lib/ddragon";

export default function MatchupDuel() {
  const version = useDdragonVersion();

  // matchup inputs
  const [myChamp, setMyChamp] = useState("");
  const [enemyChamp, setEnemyChamp] = useState("");

  // matchup data
  const [myImg, setMyImg] = useState<string | null>(null);
  const [enemyImg, setEnemyImg] = useState<string | null>(null);
  const [generalAdvice, setGeneralAdvice] = useState<string[]>([]);
  const [matchupAdvice, setMatchupAdvice] = useState<string[]>([]);
  const [loadingGuide, setLoadingGuide] = useState(false);

  // comparison inputs
  const [myJson, setMyJson] = useState<any | null>(null);
  const [otherJson, setOtherJson] = useState<any | null>(null);
  const [comparisonResult, setComparisonResult] = useState<string | null>(null);
  const [loadingCompare, setLoadingCompare] = useState(false);

  /* -------------------------- matchup guide fetch -------------------------- */
  async function generateGuide() {
    if (!myChamp || !enemyChamp) return;

    try {
      setLoadingGuide(true);

      const url = `/api/matchup-explainer?myChamp=${encodeURIComponent(
          myChamp
      )}&enemy=${encodeURIComponent(enemyChamp)}&mode=auto`;

      const res = await fetch(url);
      const data = await res.json();

      // icons
      setMyImg(champIconURL(myChamp, version));
      setEnemyImg(champIconURL(enemyChamp, version));

      // advice
      setGeneralAdvice([
        ...(data.summary ? [data.summary] : []),
        ...(data.laningPlan || []),
        ...(data.winConditions || []),
      ]);

      setMatchupAdvice([
        ...(data.trading || []),
        ...(data.wave || []),
        ...(data.wards || []),
        ...(data.commonMistakes || []),
      ]);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingGuide(false);
    }
  }

  /* -------------------------- JSON comparison -------------------------- */
  function loadJsonFile(file: File, setFn: (j: any) => void) {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const json = JSON.parse(e.target?.result as string);
        setFn(json);
      } catch {
        alert("Invalid JSON file");
      }
    };
    reader.readAsText(file);
  }

  async function comparePlayers() {
    if (!myJson || !otherJson) return;
    setLoadingCompare(true);
    setComparisonResult(null);

    try {
      const res = await fetch("/api/compare-profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          playerA: myJson,
          playerB: otherJson,
        }),
      });

      const data = await res.json();
      setComparisonResult(data.verdict || "No verdict returned");
    } catch (err) {
      setComparisonResult("Error generating comparison.");
    } finally {
      setLoadingCompare(false);
    }
  }

  /* -------------------------- RENDER -------------------------- */
  return (
      <div className="min-h-screen bg-lolBg relative overflow-hidden">
        {/* BG layers */}
        <div
            className="absolute inset-0 bg-center bg-cover opacity-25"
            style={{ backgroundImage: `url('/lol-bg.jpg')` }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-black/50 via-black/40 to-black/80" />
        <div className="absolute inset-0 lol-vignette" />

        <main className="relative z-10 max-w-7xl mx-auto p-8 space-y-12">
          {/* ------------------------------- TITLE ------------------------------- */}
          <div className="text-center">
            <h1 className="text-3xl text-lolGold font-bold drop-shadow">
              Rift Rewind — Matchup & Duel Mode
            </h1>
            <p className="text-gray-300 mt-2">
              Get matchup advice + compare profiles head-to-head.
            </p>
          </div>

          {/* ------------------------- MATCHUP INPUT BAR ------------------------- */}
          <section className="rounded-[18px] border-2 border-lolGold bg-[#0f1419]/80 shadow-xl p-6">
            <h2 className="text-lolGold text-lg font-semibold mb-4">
              Matchup Guide
            </h2>

            <div className="flex flex-col md:flex-row items-center gap-4">
              <input
                  className="px-3 py-2 rounded-md bg-black/40 text-gray-100 border border-lolGold/60 w-full"
                  placeholder="Your champion (e.g., Renekton)"
                  value={myChamp}
                  onChange={(e) => setMyChamp(e.target.value)}
              />

              <span className="text-lolGold font-bold">VS</span>

              <input
                  className="px-3 py-2 rounded-md bg-black/40 text-gray-100 border border-lolGold/60 w-full"
                  placeholder="Enemy champion (e.g., Jax)"
                  value={enemyChamp}
                  onChange={(e) => setEnemyChamp(e.target.value)}
              />

              <button
                  onClick={generateGuide}
                  disabled={loadingGuide}
                  className="px-4 py-2 rounded-md bg-[#2237a7] border border-lolGold text-gray-100 hover:bg-[#1a2e8b] transition"
              >
                {loadingGuide ? "Loading…" : "Generate Guide"}
              </button>
            </div>
          </section>

          {/* --------------------------- MATCHUP CARDS --------------------------- */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Left: general advice */}
            <div className="rounded-[18px] border-2 border-lolGold bg-[#0b0f13]/70 p-6 shadow-lg">
              <h3 className="text-lolGold font-semibold mb-3 text-center">
                General Champ Advice
              </h3>

              {myImg && (
                  <img
                      src={myImg}
                      className="w-32 h-32 rounded-xl mx-auto mb-4 border-2 border-lolGold"
                  />
              )}

              <ul className="space-y-2 text-gray-300">
                {generalAdvice.map((line, i) => (
                    <li key={i}>• {line}</li>
                ))}
              </ul>
            </div>

            {/* Right: matchup advice */}
            <div className="rounded-[18px] border-2 border-lolGold bg-[#0b0f13]/70 p-6 shadow-lg">
              <h3 className="text-lolGold font-semibold mb-3 text-center">
                Matchup Advice
              </h3>

              {enemyImg && (
                  <img
                      src={enemyImg}
                      className="w-32 h-32 rounded-xl mx-auto mb-4 border-2 border-lolGold"
                  />
              )}

              <ul className="space-y-2 text-gray-300">
                {matchupAdvice.map((line, i) => (
                    <li key={i}>• {line}</li>
                ))}
              </ul>
            </div>
          </section>

          {/* --------------------------- COMPARISON --------------------------- */}
          <section className="rounded-[18px] border-2 border-lolGold bg-[#0f1419]/80 p-6 shadow-xl space-y-6">
            <h2 className="text-lolGold text-lg font-semibold">
              Compare Player Profiles
            </h2>

            <div className="flex flex-col md:flex-row items-center gap-6">
              {/* Player A JSON */}
              <div className="flex flex-col">
                <span className="text-gray-300 mb-1">Your JSON</span>
                <input
                    type="file"
                    accept="application/json"
                    onChange={(e) =>
                        e.target.files?.[0] &&
                        loadJsonFile(e.target.files[0], setMyJson)
                    }
                />
              </div>

              <span className="text-lolGold font-bold">VS</span>

              {/* Player B JSON */}
              <div className="flex flex-col">
                <span className="text-gray-300 mb-1">Other Player JSON</span>
                <input
                    type="file"
                    accept="application/json"
                    onChange={(e) =>
                        e.target.files?.[0] &&
                        loadJsonFile(e.target.files[0], setOtherJson)
                    }
                />
              </div>

              {/* Compare Button */}
              <button
                  onClick={comparePlayers}
                  disabled={loadingCompare}
                  className="px-4 py-2 rounded-md bg-[#2237a7] border border-lolGold text-gray-100 hover:bg-[#1b2d8b] transition"
              >
                {loadingCompare ? "Comparing…" : "Generate Win %"}
              </button>
            </div>

            {/* Comparison Result */}
            {comparisonResult && (
                <div className="mt-4 text-center text-gray-200 text-lg border border-lolGold/40 p-4 rounded-lg bg-black/40">
                  {comparisonResult}
                </div>
            )}
          </section>

          {/* Back button */}
          <div className="text-center">
            <a
                href="/"
                className="text-gray-300 hover:text-lolGold underline text-sm"
            >
              Look up another profile
            </a>
          </div>
        </main>
      </div>
  );
}
