import streamlit as st
import requests
import pandas as pd
import time
import re
import os
import json
import math
import textwrap
from urllib.parse import urlencode
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from concurrent.futures import ThreadPoolExecutor, as_completed

if os.path.exists(".env"):
    load_dotenv()
    CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
    CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
else:
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
        
REDIRECT_URI = "http://127.0.0.1:8501"

st.set_page_config(page_title="CrownChaser", layout="centered")
st.title("🚴 CrownChaser")
st.markdown("Find Strava segments near you that you *might* be able to crown based on your FTP.")

query_params = st.query_params
code = query_params.get("code", None)

st.sidebar.header("Strava Login")

# --- OAuth token exchange ---
if code and "access_token" not in st.session_state and "code_exchanged" not in st.session_state:
    token_url = "https://www.strava.com/oauth/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }
    response = requests.post(token_url, data=data)
    st.sidebar.write("Token exchange response:", response.status_code, response.text)
    if response.ok:
        token_info = response.json()
        st.session_state.access_token = token_info["access_token"]
        st.session_state["code_exchanged"] = True
        st.query_params
        time.sleep(0.2)
        st.rerun()
    else:
        st.error(f"❌ Token exchange failed: {response.status_code} {response.text}")

elif "access_token" not in st.session_state:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "read,activity:read_all",
        "approval_prompt": "auto",
    }
    login_url = f"https://www.strava.com/oauth/authorize?{urlencode(params)}"
    st.markdown(f"[🔑 Login with Strava]({login_url})", unsafe_allow_html=True)
    st.stop()

# --- Cache ---
CACHE_FILE = "kom_cache.json"

location_cache = {}
if os.path.exists("location_cache.json"):
    with open("location_cache.json", "r") as f:
        location_cache = json.load(f)

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache_data):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f)
    except Exception:
        pass

kom_cache = load_cache()

# --- Sidebar inputs ---
with st.sidebar:
    st.header("Your Info")
    access_token = st.session_state.get("access_token")
    ftp = st.number_input("⚡ Your FTP (W)", min_value=100, max_value=1000, value=250)

    st.header("Location")
    city_name = st.text_input("🌍 Enter city or area", value="Le Thillot")
    radius_km = st.slider("🔍 Search radius (km)", 1, 20, 5)

    if city_name in location_cache:
        lat, lon = location_cache[city_name]
        st.write(f"📍 Located (cached): {city_name}")
    else:
        geolocator = Nominatim(user_agent="crownchaser", timeout=5)
        location = geolocator.geocode(city_name)
        if location:
            lat = location.latitude
            lon = location.longitude
            st.write(f"📍 Located: {location.address}")
            location_cache[city_name] = (lat, lon)
            with open("location_cache.json", "w") as f:
                json.dump(location_cache, f)
        else:
            st.warning("City not found. Please check the name.")
            st.stop()

    st.header("Results")
    max_results = st.slider("How many segments to show", 1, 10, 3)

    st.header("Distance filter (meters)")
    min_distance = st.number_input("Min distance", 0, 100000, 0, step=100)
    max_distance = st.number_input("Max distance", 0, 100000, 100000, step=100)

    st.header("Advanced Filters")
    filter_uphill = st.checkbox("Only segments with avg grade ≥ 0%", value=True)
    filter_unpaved = st.checkbox("Exclude known unpaved segments", value=True)

    st.header("🧹 Cache")
    if st.button("❌ Clear KOM cache"):
        kom_cache.clear()
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
        st.success("KOM cache cleared. Reloading...")
        time.sleep(1)
        st.rerun()
        
# --- Helpers ---
rate_limit_usage = {"short": 0, "daily": 0}
short_limit, daily_limit = 200, 2000

def parse_time_to_seconds(time_str):
    if time_str is None:
        return None
    if m := re.match(r"^(\d+)s$", time_str):
        return int(m.group(1))
    if m := re.match(r"^(\d{1,2}):(\d{2})$", time_str):
        return int(m.group(1)) * 60 + int(m.group(2))
    if m := re.match(r"^(\d+):(\d{2}):(\d{2})$", time_str):
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    return None

def format_time(seconds):
    if seconds is None or (isinstance(seconds, float) and math.isnan(seconds)):
        return "-"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"

def format_distance(meters):
    return f"{meters / 1000:.1f} km" if meters >= 1000 else f"{int(meters)} m"

def format_speed_mps_to_kmh(speed_mps):
    return f"{speed_mps * 3.6:.1f} km/h" if speed_mps else "-"

def estimate_power_for_time(distance_m, avg_grade_pct, time_s, mass_kg=70, crr=0.004, cda=0.25, air_density=1.225, drivetrain_eff=0.975):
    if time_s is None or time_s == 0:
        return None
    speed = distance_m / time_s
    grade = avg_grade_pct / 100
    g = 9.81
    f_gravity = mass_kg * g * math.sin(math.atan(grade))
    f_roll = mass_kg * g * math.cos(math.atan(grade)) * crr
    f_air = 0.5 * air_density * cda * speed**2
    total_force = f_gravity + f_roll + f_air
    return round((total_force * speed) / drivetrain_eff)

def get_segment_detail(segment_id, token):
    if str(segment_id) in kom_cache:
        return kom_cache[str(segment_id)]
    url = f"https://www.strava.com/api/v3/segments/{segment_id}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)

    # extract rate limit
    short = resp.headers.get("X-RateLimit-Usage", "").split(",")
    if len(short) == 2:
        rate_limit_usage["short"] = int(short[0])
        rate_limit_usage["daily"] = int(short[1])

    if resp.status_code == 200:
        data = resp.json()
        kom_str = data.get("xoms", {}).get("kom")
        kom_s = parse_time_to_seconds(kom_str)
        surface = data.get("surface_type")
        detail = {"kom_time_s": kom_s, "surface_type": surface}
        kom_cache[str(segment_id)] = detail
        save_cache(kom_cache)
        return detail
    return {"kom_time_s": None, "surface_type": None}

def format_checkbox(val):
    return "✔️" if val else "❌"

# --- Segment explore cache ---
EXPLORE_CACHE_FILE = "explore_cache.json"
explore_cache = {}
if os.path.exists(EXPLORE_CACHE_FILE):
    with open(EXPLORE_CACHE_FILE, "r") as f:
        explore_cache = json.load(f)

def save_explore_cache():
    try:
        with open(EXPLORE_CACHE_FILE, "w") as f:
            json.dump(explore_cache, f)
    except Exception:
        pass

# --- Main logic ---
if access_token:
    try:
        deg_radius = radius_km / 111.0
        tile_step = deg_radius
        bounds_key_base = f"{round(lat,4)}_{round(lon,4)}_{radius_km}"

        doable_segments = []
        non_doable_segments = []
        collected_ids = set()

        placeholder = st.empty()
        placeholder.info("🔄 Searching for segments near your location...")
        status_text = st.empty()
        progress = st.progress(0)

        tiles_tried = 0
        max_tiles = 9

        lat_offsets = [-tile_step, 0, tile_step]
        lon_offsets = [-tile_step, 0, tile_step]
        total_estimate = max_tiles * 10

        all_segments = []

        for lat_offset in lat_offsets:
            for lon_offset in lon_offsets:
                tile_lat = lat + lat_offset
                tile_lon = lon + lon_offset
                bounds_key = f"{bounds_key_base}_{round(tile_lat,4)}_{round(tile_lon,4)}"

                if bounds_key in explore_cache:
                    segments = explore_cache[bounds_key]
                    tiles_tried += 1  # ✅ telt ook cached tile mee
                else:
                    bounds = f"{tile_lat - deg_radius},{tile_lon - deg_radius},{tile_lat + deg_radius},{tile_lon + deg_radius}"
                    url = f"https://www.strava.com/api/v3/segments/explore?bounds={bounds}&activity_type=riding"
                    headers = {"Authorization": f"Bearer {access_token}"}
                    resp = requests.get(url, headers=headers)
                    if resp.status_code != 200:
                        continue
                    segments_raw = resp.json().get("segments", [])
                    segments = [s for s in segments_raw if "distance" in s and s["distance"] is not None]
                    explore_cache[bounds_key] = segments
                    save_explore_cache()
                    tiles_tried += 1  # ✅ telt opgehaalde tile mee


                for seg in segments:
                    if seg["id"] in collected_ids:
                        continue
                    if "distance" not in seg or seg["distance"] is None:
                        continue
                    if not (min_distance <= seg["distance"] <= max_distance):
                        continue
                    if filter_uphill and seg["avg_grade"] < 0:
                        continue
                    collected_ids.add(seg["id"])
                    all_segments.append(seg)

        def enrich_segment(seg):
            if not isinstance(seg, dict) or "distance" not in seg or seg["distance"] is None:
                return None
            if "distance" not in seg or seg["distance"] is None:
                return None  # Skip segment if distance missing

            detail = get_segment_detail(seg["id"], access_token)
            kom_s = detail.get("kom_time_s")
            surface_type = detail.get("surface_type")
            if filter_unpaved and surface_type == "unpaved":
                return None
            seg["kom_time_s"] = kom_s
            seg["kom_time"] = format_time(kom_s)
            seg["kom_avg_speed_mps"] = seg["distance"] / kom_s if kom_s else None
            seg["kom_avg_speed"] = format_speed_mps_to_kmh(seg["kom_avg_speed_mps"])
            seg["power_to_beat_kom"] = estimate_power_for_time(seg["distance"], seg["avg_grade"], kom_s)
            seg["doable_kom"] = seg["power_to_beat_kom"] <= ftp + 20 if seg["power_to_beat_kom"] is not None else False
            seg["segment_url"] = f"https://www.strava.com/segments/{seg['id']}"
            seg["name_link"] = f"[{seg['name']}]({seg['segment_url']})"
            return seg

        with st.spinner("🔍 Analyzing segments and KOMs in parallel..."):
            enriched = []
            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = {executor.submit(enrich_segment, s): s for s in all_segments}
                for i, future in enumerate(as_completed(futures)):
                    result = future.result()
                    if result:
                        if result["doable_kom"]:
                            doable_segments.append(result)
                        else:
                            non_doable_segments.append(result)
                    progress.progress(min((i + 1) / total_estimate, 1.0))
                    if len(doable_segments) >= max_results:
                        break

        placeholder.empty()
        status_text.empty()
        progress.empty()

        final_segments = doable_segments[:max_results] if doable_segments else non_doable_segments[:max_results]
        df = pd.DataFrame(final_segments)
        df["Distance"] = df["distance"].apply(format_distance)
        df["Doable?"] = df["doable_kom"].apply(format_checkbox)

        df = df[["name_link", "Distance", "avg_grade", "kom_time", "kom_avg_speed", "power_to_beat_kom", "Doable?"]]
        df.columns = ["Segment", "Distance", "Avg Grade (%)", "KOM Time", "KOM Avg Speed", "Power to Beat KOM (W)", "Doable?"]

        st.success(f"✅ Showing {len(df)} {'doable' if doable_segments else 'non-doable'} segments")
        st.info(f"🔍 Explored {tiles_tried} tile(s), checked {len(collected_ids)} segments")
        st.write("Click a segment to view on Strava:")
        st.markdown(df.to_markdown(index=False), unsafe_allow_html=True)

        st.caption(
            f"📊 API usage: {rate_limit_usage['short']}/{short_limit} (15 min), "
            f"{rate_limit_usage['daily']}/{daily_limit} (daily)"
        )

    except Exception as e:
        st.error(f"Unexpected error: {e}")
else:
    st.info("Login to Strava to begin.")
