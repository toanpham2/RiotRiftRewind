import hashlib, json, time
_CACHE = {}
def ai_cache_get(key):
  v=_CACHE.get(key);
  return None if not v or v["exp"]<time.time() else v["val"]
def ai_cache_set(key, val, ttl=3600):
  _CACHE[key]={"val":val,"exp":time.time()+ttl}

def key_for(payload: dict) -> str:
  h = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()
  return f"mx:{h}"