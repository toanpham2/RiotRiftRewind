// client.ts
export async function fetchYearSummaryByRiotId(name: string, tag: string) {
  const riotId = encodeURIComponent(`${name.trim()}#${tag.trim().replace(/^#/, "")}`);
  const res = await fetch(`/api/year-summary?riotId=${riotId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
