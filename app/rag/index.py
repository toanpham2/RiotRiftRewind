import os
import time
from typing import Dict, Optional, Tuple, List
import yaml
import logging

log = logging.getLogger("rag.index")
if not log.handlers:
  logging.basicConfig(level=logging.INFO, format="[RAG] %(message)s")

# ---------- Paths ----------
ROOT = os.path.dirname(__file__)
TOP_DIR = os.path.join(ROOT, "matchups", "top")
ARCH_DIR = os.path.join(ROOT, "matchups", "archetypes")
CHAMP_INDEX = os.path.join(ROOT, "champ_index.yaml")

_BASE_ARCH_KEYS = {
  "assassin","bruiser","engage","juggernaut","poke","ranged_bully",
  "scaler","snowballer","splitpusher","sustain","tank","teamfight"
}

# ---------- Small TTL cache ----------
_cache: Dict[str, Tuple[float, dict]] = {}

def _now() -> float: return time.time()

def _get_cache(key: str) -> Optional[dict]:
  hit = _cache.get(key)
  if not hit: return None
  exp, val = hit
  if _now() > exp:
    _cache.pop(key, None)
    return None
  return val

def _put_cache(key: str, val: dict, ttl: int = 900) -> None:
  _cache[key] = (_now() + ttl, val)

# ---------- Utils ----------
def _norm_key(s: str) -> str:
  return (s or "").strip().lower()

def _safe_read_yaml(path: str) -> dict:
  """
  Robust YAML reader:
  - Tries multi-doc; if that fails, tries single-doc.
  - On any error, logs the error and returns {} (so you can see why it was empty).
  """
  try:
    with open(path, "r", encoding="utf-8") as f:
      try:
        docs = list(yaml.safe_load_all(f))
        if not docs:
          return {}
        if len(docs) == 1:
          return docs[0] or {}
        merged: dict = {}
        for d in docs:
          if isinstance(d, dict):
            merged.update(d)
        return merged or {}
      except Exception as e:
        log.warning(f"YAML multi-doc parse failed for {path}: {e}. Retrying single-doc.")
        f.seek(0)
        one = yaml.safe_load(f) or {}
        if not isinstance(one, dict):
          return {}
        return one
  except Exception as e:
    log.error(f"Failed to read YAML {path}: {e}")
    return {}

def _list_yaml_files(dir_path: str) -> List[str]:
  if not os.path.isdir(dir_path): return []
  return [fn for fn in os.listdir(dir_path) if fn.lower().endswith(".yaml")]

# ---------- Champ index ----------
def _first_base_key(val) -> str:
  if isinstance(val, list):
    for v in val:
      k = _norm_key(str(v))
      for base in _BASE_ARCH_KEYS:
        if base == k or base in k:
          return base
    return ""
  k = _norm_key(str(val))
  for base in _BASE_ARCH_KEYS:
    if base == k or base in k:
      return base
  return ""

def load_champ_index() -> dict:
  key = "champ_index"
  hit = _get_cache(key)
  if hit is not None:
    return hit

  mapping: Dict[str, str] = {}
  data = _safe_read_yaml(CHAMP_INDEX) if os.path.isfile(CHAMP_INDEX) else {}

  if isinstance(data, dict):
    # flat mapping
    if all(isinstance(v, (str, list)) for v in data.values()):
      for champ, labels in data.items():
        arch = _first_base_key(labels)
        if arch:
          mapping[_norm_key(str(champ))] = arch
    else:
      # grouped
      for _, group in data.items():
        if isinstance(group, dict):
          for champ, labels in group.items():
            arch = _first_base_key(labels)
            if arch:
              mapping[_norm_key(str(champ))] = arch

  _put_cache(key, mapping, ttl=3600)
  return mapping

def guess_archetype(champion: str) -> Optional[str]:
  idx = load_champ_index()
  return idx.get(_norm_key(champion))

# ---------- Champion docs ----------
def _build_lower_name_map(dir_path: str) -> Dict[str, str]:
  files = _list_yaml_files(dir_path)
  out: Dict[str, str] = {}
  for fn in files:
    name_no_ext = os.path.splitext(fn)[0]
    out[_norm_key(name_no_ext)] = os.path.join(dir_path, fn)
  return out

def get_champ_doc(champion: str) -> dict:
  """
  Loads app/rag/matchups/top/<Champion>.yaml (case-insensitive).
  Returns {} if not found or on error.
  """
  if not champion:
    return {}
  norm = _norm_key(champion)
  cache_key = f"champdoc:{norm}"
  hit = _get_cache(cache_key)
  if hit is not None:
    return hit

  name_map = _build_lower_name_map(TOP_DIR)
  path = name_map.get(norm)
  if not path:
    _put_cache(cache_key, {}, ttl=60)
    log.info(f"Champ doc not found for '{champion}' in {TOP_DIR}. Known: {sorted(name_map.keys())}")
    return {}

  data = _safe_read_yaml(path) or {}
  if not data:
    log.warning(f"Champ doc parsed empty for '{champion}' at {path}")
  _put_cache(cache_key, data, ttl=900)
  return data

# ---------- Archetype docs ----------
def get_archetype_doc_by_key(arch_key: str) -> dict:
  if not arch_key:
    return {}
  key = _norm_key(arch_key)
  cache_key = f"archdoc:{key}"
  hit = _get_cache(cache_key)
  if hit is not None:
    return hit

  fn = f"vs_{key}.yaml"
  path = os.path.join(ARCH_DIR, fn)
  if not os.path.isfile(path):
    _put_cache(cache_key, {}, ttl=60)
    log.info(f"Archetype doc not found for '{arch_key}' at {path}")
    return {}

  data = _safe_read_yaml(path) or {}
  if not data:
    log.warning(f"Archetype doc parsed empty for '{arch_key}' at {path}")
  _put_cache(cache_key, data, ttl=1800)
  return data
