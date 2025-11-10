export async function fetchYearSummaryByRiotId(name: string, tag: string) {
  const riotId = encodeURIComponent(`${name.trim()}#${tag.trim().replace(/^#/, "")}`);
  const res = await fetch(`/api/year-summary?riotId=${riotId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
export async function compareProfilesClaude(you: any, opponent: any) {
  const r = await fetch("/api/compare-claude", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ you, opponent }),
  });
  if (!r.ok) throw new Error(`Compare failed: ${r.status}`);
  return r.json(); // { result: {winPctYou,...}, cached?: boolean, error?:string }
}