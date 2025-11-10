# app/routes/matchups.py
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional, Tuple
import json, os, time, hashlib, re, logging

from app.bedrock_client import call_claude_json
from app.rag.index import (
  get_champ_doc,
  get_archetype_doc_by_key,
  guess_archetype,
  _norm_key,
)

router = APIRouter(prefix="/api", tags=["matchups"])

# ---------- logging ----------
log = logging.getLogger("matchups")
if not log.handlers:
  h = logging.StreamHandler()
  fmt = logging.Formatter("[MX] %(levelname)s: %(message)s")
  h.setFormatter(fmt)
  log.addHandler(h)
  log.setLevel(logging.INFO)

# ---------- utils ----------
def _ensure_list(x) -> List[Any]:
  if isinstance(x, list):
    return x
  if x in (None, "", False):
    return []
  return [x]

def _merge_unique(a: List[Any], b: List[Any]) -> List[Any]:
  seen, out = set(), []
  for item in (a or []) + (b or []):
    key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
    if key not in seen:
      seen.add(key)
      out.append(item)
  return out

def _truncate(s: Any, limit: int = 4800) -> str:
  if not isinstance(s, str):
    s = json.dumps(s, ensure_ascii=False)
  return s if len(s) <= limit else s[:limit]

# ---------- tiny AI cache ----------
_AI_CACHE: Dict[str, Dict[str, Any]] = {}
def _ai_key(payload: dict) -> str:
  h = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()
  return f"mx:{h}"
def _ai_get(key: str):
  v = _AI_CACHE.get(key)
  return None if not v or v["exp"] < time.time() else v["val"]
def _ai_set(key: str, val: Any, ttl: int = 1800):
  _AI_CACHE[key] = {"val": val, "exp": time.time() + ttl}

# ---------- archetype -> plan ----------
def _plan_from_archetype_doc(vs_doc: dict) -> dict:
  if not isinstance(vs_doc, dict):
    return {}
  base = vs_doc.get("how_to_play") if isinstance(vs_doc.get("how_to_play"), dict) else vs_doc
  strengths  = _ensure_list(base.get("strengths"))
  weaknesses = _ensure_list(base.get("weaknesses"))
  tips       = _ensure_list(base.get("tips_for_this_player"))
  return {
    "summary": base.get("summary") or ("Leverage your strengths and deny theirs; ward deep to track flanks."
                                       if (strengths or weaknesses) else ""),
    "laning": tips,
    "trading": tips[:5],
    "wave": [],
    "wards": ["Deep ward common pathing.", "Track disappear timers."],
    "with_jungle": ["Stack wave before dive.", "Ping ~20s before setup."],
    "win_conditions": strengths,
    "mistakes": weaknesses,
    "skill_tips": [],
    "items": [],
    "runes": [],
    "timers": [],
    "checklist": [
      "Place/replace vision ~2:45 and ~5:00.",
      "Track enemy jungler when you push.",
    ],
  }

# ---------- champ doc -> normalized ----------
def _extract_from_champ_doc(doc: dict, enemy_key: str) -> dict:
  if not isinstance(doc, dict):
    return {
      "summary": "", "laningPlan": [], "trading": [], "wave": [], "wards": [],
      "withJungle": [], "winConditions": [], "commonMistakes": [], "skillTips": [],
      "itemization": [], "runes": [], "timers": [], "quickChecklist": []
    }

  out = {
    "summary": "",
    "laningPlan": [], "trading": [], "wave": [], "wards": [],
    "withJungle": [], "winConditions": [], "commonMistakes": [], "skillTips": [],
    "itemization": [], "runes": [], "timers": [], "quickChecklist": [],
  }

  out["summary"] = doc.get("summary") or doc.get("identity_summary", "") or ""

  out["laningPlan"]     = _merge_unique(out["laningPlan"],     _ensure_list(doc.get("laning_plan")))
  out["trading"]        = _merge_unique(out["trading"],        _ensure_list(doc.get("trading")))
  out["runes"]          = _merge_unique(out["runes"],          _ensure_list(doc.get("runes")))
  out["itemization"]    = _merge_unique(out["itemization"],    _ensure_list(doc.get("items")))
  out["quickChecklist"] = _merge_unique(out["quickChecklist"], _ensure_list(doc.get("checklist")))
  out["skillTips"]      = _merge_unique(out["skillTips"],      _ensure_list(doc.get("skill_tips")))
  out["timers"]         = _merge_unique(out["timers"],         _ensure_list(doc.get("power_spikes")))
  out["winConditions"]  = _merge_unique(out["winConditions"],  _ensure_list(doc.get("core_strengths")))
  out["commonMistakes"] = _merge_unique(out["commonMistakes"], _ensure_list(doc.get("core_weaknesses")))

  tp = doc.get("trading_pattern") or {}
  if isinstance(tp, dict):
    for k in ["fundamentals", "key_patterns", "vs_melee", "vs_range", "vs_ranged"]:
      if tp.get(k):
        out["trading"] = _merge_unique(out["trading"], _ensure_list(tp[k]))

  wm = doc.get("wave_management") or {}
  if isinstance(wm, dict):
    for k in ["level_1","level_2_cheese","lvl1","lvl3","lvl4–5","mid_game","late_game","vs_ranged","vs_melees"]:
      if wm.get(k):
        out["wave"] = _merge_unique(out["wave"], _ensure_list(wm[k]))

  jc = doc.get("jungle_coordination") or {}
  if isinstance(jc, dict):
    for k in ["when_you_call_gank","when_enemy_ganks","your_jg_ganks","enemy_jg_ganks"]:
      if jc.get(k):
        out["withJungle"] = _merge_unique(out["withJungle"], _ensure_list(jc[k]))

  ts = doc.get("timing_spikes") or {}
  if isinstance(ts, dict):
    out["timers"] = _merge_unique(out["timers"], [f"{k}: {v}" for k, v in ts.items() if isinstance(v, str)])

  ci = doc.get("core_items") or {}
  if isinstance(ci, dict):
    core = ci.get("core")
    if isinstance(core, dict):
      out["itemization"] = _merge_unique(out["itemization"], _ensure_list(core.get("preferred")))
      out["itemization"] = _merge_unique(out["itemization"], _ensure_list(core.get("alt")))
      if core.get("notes"):
        out["itemization"] = _merge_unique(out["itemization"], _ensure_list(core["notes"]))
    if ci.get("boots"):
      out["itemization"] = _merge_unique(out["itemization"], _ensure_list(ci["boots"]))
    if ci.get("core_legendaries"):
      out["itemization"] = _merge_unique(out["itemization"], _ensure_list(ci["core_legendaries"]))

  si = doc.get("situational_items") or {}
  if isinstance(si, dict):
    for v in si.values():
      out["itemization"] = _merge_unique(out["itemization"], _ensure_list(v))

  orunes = doc.get("optimal_runes") or {}
  if isinstance(orunes, dict):
    for k in ["primary","keystone","primary_runes","secondary_tree","secondary_choices","shards"]:
      if orunes.get(k) is not None:
        out["runes"] = _merge_unique(out["runes"], _ensure_list(orunes[k]))

  mu = doc.get("matchups") or {}
  enemy_block: Optional[dict] = None
  if isinstance(mu, dict):
    for k, v in mu.items():
      if _norm_key(k) == enemy_key:
        enemy_block = v if isinstance(v, dict) else {}
        break

  if enemy_block:
    if isinstance(enemy_block.get("trading"), list):
      out["trading"] = _merge_unique(out["trading"], _ensure_list(enemy_block["trading"]))
    else:
      for tk in ["tips", "instructions"]:
        if enemy_block.get(tk):
          out["trading"] = _merge_unique(out["trading"], _ensure_list(enemy_block[tk]))

    if enemy_block.get("items"):
      out["itemization"] = _merge_unique(out["itemization"], _ensure_list(enemy_block["items"]))

    wv = enemy_block.get("wave")
    if isinstance(wv, dict):
      for v in wv.values():
        out["wave"] = _merge_unique(out["wave"], _ensure_list(v))
    elif isinstance(wv, (str, list)):
      out["wave"] = _merge_unique(out["wave"], _ensure_list(wv))

    if enemy_block.get("you_win_if"):
      out["winConditions"] = _merge_unique(out["winConditions"], _ensure_list(enemy_block["you_win_if"]))
    if enemy_block.get("threats"):
      out["commonMistakes"] = _merge_unique(out["commonMistakes"], _ensure_list(enemy_block["threats"]))

  return out

# ---------- archetype defaults (for AI top-off) ----------
_ARCH_DEFAULTS: Dict[str, Dict[str, List[str]]] = {
  "splitpusher": {
    "runes": [
      "Precision: Conqueror, Triumph, Legend: Alacrity, Last Stand",
      "Resolve: Second Wind vs poke / Bone Plating vs melee",
      "Shards: AS, Adaptive, Armor/MR",
    ],
    "itemization": [
      "Early: Long Sword/Refillable or Doran’s based on lane",
      "Sheen component if champion uses it → core spike",
      "Anti-tank: Black Cleaver or %HP shred; boots by damage type",
    ],
    "wave": [
      "Slow-push 2–3 waves then crash for plates/tempo",
      "Freeze after crash to force over-extends",
      "Swap to long lane post first item for isolations",
    ],
    "withJungle": [
      "Stack wave before dive; ping ~20s before",
      "Deep ward their jungle path before extending",
      "Herald on your pressure side converts to plates",
    ],
  },
  "bruiser": {
    "runes": [
      "Precision: Conqueror, Triumph, Tenacity, Last Stand",
      "Resolve: Second Wind vs poke / Bone Plating vs burst",
      "Shards: Adaptive, Adaptive, Armor/MR",
    ],
    "itemization": [
      "Damage+HP core; boots by damage type",
      "Death’s Dance vs AD burst / Maw vs AP burst",
      "Anti-heal if they sustain",
    ],
    "wave": [
      "Hold near tower to threaten all-in",
      "Crash big wave → ward then roam/recall",
      "Save slow-push for jungler setup",
    ],
  },
  "tank": {
    "runes": [
      "Resolve: Grasp, Demolish, Second Wind/Bone Plating, Overgrowth",
      "Inspiration: Biscuits, Cosmic Insight",
      "Shards: AS, HP, Armor/MR",
    ],
    "itemization": [
      "Armor vs AD, MR vs AP; Thornmail/Bramble vs healing",
      "Randuin’s vs crit; Spirit Visage with enchanters/heals",
    ],
    "wave": [
      "Last-hit early; thin waves to hold near tower",
      "Fast push to reset when low resources",
      "Buy/refresh wards before pushes",
    ],
  },
  "sustain": {
    "runes": [
      "Precision or Resolve start; Doran’s Shield vs poke lanes",
      "Second Wind + sustain shard for attrition",
      "Shards: HP, Adaptive, Armor/MR",
    ],
    "itemization": [
      "Early sustain component, then core spike",
      "Anti-heal if opponent sustains more",
      "Boots by damage type",
    ],
    "wave": [
      "Avoid perma-push; farm safely to spike",
      "Crash on timing then reset for resources",
      "Hold wave near tower vs gank threat",
    ],
  }
}
def _defaults_for_arch(arch: str) -> Dict[str, List[str]]:
  return _ARCH_DEFAULTS.get(arch or "", _ARCH_DEFAULTS["bruiser"])

# ---------- AI helpers ----------
_FIELDS = ["laningPlan","trading","wave","wards","withJungle","winConditions",
           "commonMistakes","skillTips","itemization","runes","timers","quickChecklist"]

def _coerce_json(raw: Any) -> dict:
  """
  Accepts:
    - dict with Anthropic/Bedrock shapes:
      * {"content": [{"type":"text","text":"{...}"}], ...}
      * {"message":{"content":[{"text":"{...}"}]}}
      * {"outputText":"{...}"} or {"completion":"{...}"}
    - plain JSON string, or text that contains a JSON object
  """
  if raw is None:
    return {}

  # 1) If already a dict with our keys — assume parsed
  if isinstance(raw, dict) and any(k in raw for k in ["summary","laningPlan","trading","wave"]):
    return raw

  # 2) Anthropic Messages (common Bedrock/Anthropic)
  def _anthropic_text(d: dict) -> Optional[str]:
    try:
      if "content" in d and isinstance(d["content"], list) and d["content"]:
        first = d["content"][0]
        if isinstance(first, dict):
          return first.get("text") or first.get("partial_json") or first.get("tool_use") or ""
      if "message" in d and isinstance(d["message"], dict):
        c = d["message"].get("content")
        if isinstance(c, list) and c:
          block = c[0]
          if isinstance(block, dict):
            return block.get("text") or ""
    except Exception:
      return None
    return None

  # 3) Other common wrappers
  def _other_text(d: dict) -> Optional[str]:
    for k in ["outputText","completion","output","result","body","data"]:
      v = d.get(k)
      if isinstance(v, str):
        return v
    return None

  # Pull text from dict-like responses
  if isinstance(raw, dict):
    # Log available keys to help debugging
    log.info("Claude dict keys: %s", list(raw.keys()))
    txt = _anthropic_text(raw) or _other_text(raw)
    if isinstance(txt, str) and txt.strip():
      # try direct parse
      try:
        return json.loads(txt)
      except Exception:
        # try to extract { ... } from text
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
          try:
            return json.loads(m.group(0))
          except Exception:
            return {}
    # If dict but no text — nothing to parse
    return {}

  # String?
  if isinstance(raw, str):
    s = raw.strip()
    try:
      return json.loads(s)
    except Exception:
      m = re.search(r"\{.*\}", s, re.S)
      if m:
        try:
          return json.loads(m.group(0))
        except Exception:
          return {}
  return {}

def _ensure_min_bullets(d: dict, arch_defaults: Dict[str, List[str]]) -> dict:
  for k in _FIELDS:
    v = d.get(k) or []
    if not isinstance(v, list):
      v = [] if not v else [v]
    if len(v) < 1 and k in arch_defaults:
      v = arch_defaults[k][:3]
    d[k] = v
  if not d.get("summary"):
    d["summary"] = "Play your role fundamentals; track jungler timers and fight on spikes."
  return d

def _render_with_claude(payload: dict, arch_defaults: Dict[str, List[str]]) -> Tuple[dict, Optional[str], bool]:
  """Return (parsed_json, error, from_cache)."""
  key = _ai_key(payload)
  cached = _ai_get(key)
  if cached is not None:
    log.info("Claude result served from cache")
    return cached, None, True

  my = payload["myChamp"]; enemy = payload["enemyChamp"]
  system = (
    "You are Rift Rewind, a Challenger top-lane coach.\n"
    f"Coach the player ON {my} versus {enemy}.\n"
    "Use ONLY the provided context (merged bullets, archetype docs, defaults).\n"
    "If champion docs are missing (archetypeOnly=true), write a focused plan from first principles "
    "for this role-vs-role matchup: wave (lvl1/3/6), trading patterns, jungle sync, spikes, items, runes.\n"
    "Return STRICT JSON with keys exactly:\n"
    "summary, laningPlan, trading, wave, wards, withJungle, winConditions, commonMistakes, "
    "NEVER mention 'mythic' or removed items"
    "NEVER mention Turbo chemtank, Divine Sunderer, Goredrinker, Galeforce, Everfrost, Luden's tempest"
    "Use items and relevant information to league of legends season 15 "
    "skillTips, itemization, runes, timers, quickChecklist.\n"
    "Keep bullets short and practical. Do not mention patches or external data."
  )
  user = _truncate(json.dumps(payload, ensure_ascii=False), 4800)

  err = None
  parsed = {}
  try:
    raw = call_claude_json(system, user, max_tokens=950, temperature=0.2)
    log.info("Claude raw type=%s", type(raw).__name__)
    parsed = _coerce_json(raw)
    if not parsed:
      err = "Empty/invalid JSON from Claude"
      head = str(raw)
      head = head if len(head) < 400 else head[:400]
      log.warning("Claude returned invalid/empty JSON. raw(head): %s", head)
  except Exception as e:
    err = f"{type(e).__name__}: {e}"
    log.error("Claude call failed: %s", err)

  out = {k: [] for k in _FIELDS}
  out["summary"] = parsed.get("summary") if isinstance(parsed, dict) else ""
  for k in _FIELDS:
    v = parsed.get(k) if isinstance(parsed, dict) else []
    out[k] = v if isinstance(v, list) else ([] if not v else [v])

  out = _ensure_min_bullets(out, arch_defaults)
  _ai_set(key, out)
  return out, err, False

def _merge_ai_into_base(base: dict, ai: dict) -> dict:
  for k in ["summary"] + _FIELDS:
    if k == "summary":
      if (not base.get(k)) and ai.get(k):
        base[k] = ai[k]
    else:
      if not base.get(k):
        base[k] = ai.get(k, [])
      else:
        base[k] = _merge_unique(base[k], ai.get(k, []))
  return base

# ---------- endpoint ----------
@router.get("/matchup-explainer")
def matchup_explainer(myChamp: str, enemy: str, mode: str = "auto"):
  """
  mode:
    - 'rag'         : deterministic merge from YAML only
    - 'rag+claude'  : return Claude-only synthesized (grounded) JSON
    - 'auto'        : merge YAML, call Claude to backfill/augment, merge (default)
  """
  if not myChamp or not enemy:
    raise HTTPException(400, "Provide ?myChamp= and ?enemy=")

  my_key = _norm_key(myChamp)
  en_key = _norm_key(enemy)

  my_doc = get_champ_doc(my_key) or {}
  enemy_doc = get_champ_doc(en_key) or {}

  my_arch = _norm_key(my_doc.get("archetype") or guess_archetype(my_key) or "")
  enemy_arch = _norm_key(enemy_doc.get("archetype") or guess_archetype(en_key) or "")

  enemy_arch_doc = get_archetype_doc_by_key(enemy_arch) if enemy_arch else {}
  plan = _plan_from_archetype_doc(enemy_arch_doc)

  base = {
    "summary": plan.get("summary") or f"General plan for {myChamp} vs {enemy}.",
    "laningPlan": _ensure_list(plan.get("laning")),
    "trading": _ensure_list(plan.get("trading")),
    "wave": _ensure_list(plan.get("wave")),
    "wards": _ensure_list(plan.get("wards")),
    "withJungle": _ensure_list(plan.get("with_jungle")),
    "winConditions": _ensure_list(plan.get("win_conditions")),
    "commonMistakes": _ensure_list(plan.get("mistakes")),
    "skillTips": _ensure_list(plan.get("skill_tips")),
    "itemization": _ensure_list(plan.get("items")),
    "runes": _ensure_list(plan.get("runes")),
    "timers": _ensure_list(plan.get("timers")),
    "quickChecklist": _ensure_list(plan.get("checklist")),
    "sources": {
      "myChampDoc": bool(my_doc),
      "enemyChampDoc": bool(enemy_doc),
      "myArchetype": my_arch,
      "enemyArchetype": enemy_arch,
      "aiCalled": False,
      "aiCached": False,
      "aiError": None,
      "mode": mode,
    },
  }

  mine = _extract_from_champ_doc(my_doc, en_key)
  for k in ["summary","laningPlan","trading","wave","wards","withJungle",
            "winConditions","commonMistakes","skillTips","itemization","runes",
            "timers","quickChecklist"]:
    if k == "summary":
      base[k] = mine[k] or base[k]
    else:
      base[k] = _merge_unique(base[k], mine[k])

  if isinstance(enemy_doc, dict):
    if enemy_doc.get("power_spikes"):
      base["timers"] = _merge_unique(base["timers"], _ensure_list(enemy_doc["power_spikes"]))
    if enemy_doc.get("ability_tips"):
      base["skillTips"] = _merge_unique(base["skillTips"], _ensure_list(enemy_doc["ability_tips"]))
    if enemy_doc.get("threats"):
      base["commonMistakes"] = _merge_unique(base["commonMistakes"], _ensure_list(enemy_doc["threats"]))
    if enemy_doc.get("itemization_vs"):
      base["itemization"] = _merge_unique(base["itemization"], _ensure_list(enemy_doc["itemization_vs"]))

  if mode.lower() == "rag":
    return base

  my_arch_doc = get_archetype_doc_by_key(my_arch) if my_arch else {}
  arch_defaults = _defaults_for_arch(my_arch or "bruiser")
  archetype_only = (not my_doc) and (not enemy_doc)

  payload = {
    "myChamp": myChamp,
    "enemyChamp": enemy,
    "myArchetype": my_arch,
    "enemyArchetype": enemy_arch,
    "context": {
      "merged": {k: base[k] for k in [
        "summary","laningPlan","trading","wave","wards","withJungle","winConditions",
        "commonMistakes","skillTips","itemization","runes","timers","quickChecklist"
      ]},
      "myArchDoc": my_arch_doc or {},
      "enemyArchDoc": enemy_arch_doc or {},
      "archDefaults": arch_defaults,
      "archetypeOnly": archetype_only,
    },
  }

  # Always call Claude in auto to augment/backfill
  force_ai = (mode.lower() == "rag+claude")
  enable_env = os.getenv("ENABLE_MATCHUP_CLAUDE", "").strip() == "1"
  if force_ai or enable_env or True:
    log.info("Calling Claude (force=%s env=%s) | my=%s enemy=%s | archOnly=%s",
             force_ai, enable_env, my_key, en_key, archetype_only)
    ai, err, cached = _render_with_claude(payload, arch_defaults)
    base["sources"]["aiCalled"] = True
    base["sources"]["aiCached"] = cached
    base["sources"]["aiError"] = err

    if mode.lower() == "rag+claude":
      ai["sources"] = base["sources"]
      return ai

    base = _merge_ai_into_base(base, ai)

  return base
