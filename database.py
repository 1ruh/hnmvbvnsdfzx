import os
import string
import random
import time

ADMIN_KEY = "9001"

LOCAL_MODE = os.getenv("LOCAL", "0") == "1"

try:
    import redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    HAS_REDIS = True
except Exception:
    HAS_REDIS = False

local_keys = {}
local_key_expiry = {}

if not HAS_REDIS:
    local_keys["dev"] = "active"
    local_key_expiry["dev"] = float('inf')

def is_valid_key(user_key: str) -> bool:
    if LOCAL_MODE and user_key == "dev":
        return True
    if HAS_REDIS:
        return bool(redis_client.exists(f"vain_key:{user_key}"))
    expiry = local_key_expiry.get(user_key, 0)
    if time.time() > expiry:
        local_keys.pop(user_key, None)
        local_key_expiry.pop(user_key, None)
        return False
    return user_key in local_keys

def generate_key(key_type: str = "weekly") -> str:
    chars = string.ascii_letters + string.digits
    key = ''.join(random.choices(chars, k=16))
    ttl_map = {"weekly": 604800, "monthly": 2592000, "lifetime": None}
    ttl = ttl_map.get(key_type)
    if HAS_REDIS:
        if ttl:
            redis_client.setex(f"vain_key:{key}", ttl, "active")
        else:
            redis_client.set(f"vain_key:{key}", "active")
    else:
        local_keys[key] = "active"
        if ttl:
            local_key_expiry[key] = time.time() + ttl
        else:
            local_key_expiry[key] = float('inf')
    return key

def check_admin(admin_key: str) -> bool:
    return admin_key == ADMIN_KEY
