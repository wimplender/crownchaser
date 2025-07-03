import requests
from utils import parse_time_to_seconds
from cache import save_kom_cache
from config import CACHE_FILE

rate_limit_usage = {"short": 0, "daily": 0}

def get_segment_detail(segment_id, token, kom_cache):
    if str(segment_id) in kom_cache:
        return kom_cache[str(segment_id)]
    url = f"https://www.strava.com/api/v3/segments/{segment_id}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)

    if resp.status_code == 200:
        data = resp.json()
        kom_str = data.get("xoms", {}).get("kom")
        kom_s = parse_time_to_seconds(kom_str)
        surface = data.get("surface_type")
        detail = {"kom_time_s": kom_s, "surface_type": surface}
        kom_cache[str(segment_id)] = detail
        save_kom_cache(kom_cache)
        return detail
    return {"kom_time_s": None, "surface_type": None}
