from typing import Any, Dict, List

FIELDS = ["summary","laningPlan","trading","wave","wards","withJungle",
          "winConditions","commonMistakes","skillTips","itemization",
          "runes","timers","quickChecklist"]

def ensure_list(x):
  if isinstance(x, list): return x
  if x in (None, "", False): return []
  return [x]

def coerce_plan(d: Dict[str, Any]) -> Dict[str, List[Any]]:
  out = {k: [] for k in FIELDS}
  for k, v in (d or {}).items():
    out[k] = ensure_list(v) if k != "summary" else v or ""
  return out