export async function fetchYearSummaryByRiotId(
    name: string,
    tagWithHash: string,
    opts?: { limit?: number }
) {
  const riotId = `${encodeURIComponent(name)}${encodeURIComponent(tagWithHash)}`;
  const params = new URLSearchParams();
  // let backend auto-detect region; keep defaults for advice/feel-good
  if (opts?.limit && opts.limit > 0) params.set("limit", String(opts.limit));
  const res = await fetch(`/api/year-summary?riotId=${riotId}&${params.toString()}`, {
    method: "GET",
  });
  if (!res.ok) throw new Error(await res.text());
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
