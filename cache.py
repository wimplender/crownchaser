import os
import json
from config import CACHE_FILE, EXPLORE_CACHE_FILE

def load_json_cache(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json_cache(data, filename):
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

def load_kom_cache():
    return load_json_cache(CACHE_FILE)

def save_kom_cache(data):
    save_json_cache(data, CACHE_FILE)

def load_explore_cache():
    return load_json_cache(EXPLORE_CACHE_FILE)

def save_explore_cache(data):
    save_json_cache(data, EXPLORE_CACHE_FILE)
