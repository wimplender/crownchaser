# app.py
import streamlit as st
import time
import requests
import pandas as pd
from streamlit_js_eval import streamlit_js_eval
from geopy.geocoders import Nominatim
from concurrent.futures import ThreadPoolExecutor, as_completed

from auth import get_auth_url, exchange_token
from config import CLIENT_ID, REDIRECT_URI, CACHE_FILE
from cache import load_kom_cache, save_kom_cache, load_explore_cache, save_explore_cache
from strava_api import get_segment_detail
from utils import (
    parse_time_to_seconds, format_time, format_distance, 
    format_speed_mps_to_kmh, estimate_power_for_time, format_checkbox
)

# --- Page config ---
st.set_page_config(page_title="CrownChaser", layout="centered")
st.title("🚴 CrownChaser")
st.markdown("Find Strava segments near you that you *might* be able to crown based on your FTP.")

# --- Auth ---
query_params = st.query_params
code = query_params.get("code", None)
st.sidebar.header("Strava Login")

if code and "access_token" not in st.session_state and "code_exchanged" not in st.session_state:
    response = exchange_token(code)
    st.sidebar.write("Token exchange response:", response.status_code, response.text)
    if response.ok:
        token_info = response.json()
        st.session_state.access_token = token_info["access_token"]
        st.session_state["code_exchanged"] = True
        time.sleep(0.2)
        st.rerun()
    else:
        st.error(f"❌ Token exchange failed: {response.status_code} {response.text}")
        st.stop()
elif "access_token" not in st.session_state:
    st.markdown(f"[🔑 Login with Strava]({get_auth_url()})", unsafe_allow_html=True)
    st.stop()

access_token = st.session_state.get("access_token")
kom_cache = load_kom_cache()
explore_cache = load_explore_cache()
location_cache = {}

# --- Get browser location using JS fallback ---
geo_data = streamlit_js_eval(js_expressions="navigator.geolocation.getCurrentPosition")

if geo_data and "coords" in geo_data:
    coords = geo_data["coords"]
    lat = coords["latitude"]
    lon = coords["longitude"]
    st.sidebar.caption(f"📍 Browser location: {lat:.4f}, {lon:.4f}")

    # Reverse geocode to get city name
    geolocator = Nominatim(user_agent="crownchaser", timeout=5)
    location = geolocator.reverse((lat, lon))
    city_name = location.raw.get("address", {}).get("city", "Unknown")
else:
    st.sidebar.warning("⚠️ Could not get browser location. Please enter city manually.")
    city_name = st.sidebar.text_input("🌍 Enter city or area manually", value="Le Thillot")
    geolocator = Nominatim(user_agent="crownchaser", timeout=5)
    location = geolocator.geocode(city_name)
    if not location:
        st.sidebar.error("City not found.")
        st.stop()
    lat, lon = location.latitude, location.longitude

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("Your Info")
    ftp = st.number_input("⚡ Your FTP (W)", min_value=100, max_value=1000, value=250)

    st.header("Location")
    radius_km = st.slider("🔍 Search radius (km)", 1, 20, 5)

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
        st.success("KOM cache cleared. Reloading...")
        time.sleep(1)
        st.rerun()

# --- Segment Search ---
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
        lat_offsets = [-tile_step, 0, tile_step]
        lon_offsets = [-tile_step, 0, tile_step]
        total_estimate = 9 * 10
        all_segments = []

        for lat_offset in lat_offsets:
            for lon_offset in lon_offsets:
                tile_lat = lat + lat_offset
                tile_lon = lon + lon_offset
                bounds_key = f"{bounds_key_base}_{round(tile_lat,4)}_{round(tile_lon,4)}"

                if bounds_key in explore_cache:
                    segments = explore_cache[bounds_key]
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
                    save_explore_cache(explore_cache)

                for seg in segments:
                    if seg["id"] in collected_ids:
                        continue
                    if not (min_distance <= seg["distance"] <= max_distance):
                        continue
                    if filter_uphill and seg["avg_grade"] < 0:
                        continue
                    collected_ids.add(seg["id"])
                    all_segments.append(seg)

        def enrich_segment(seg):
            detail = get_segment_detail(seg["id"], access_token, kom_cache)
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
        st.markdown(df.to_markdown(index=False), unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Unexpected error: {e}")
else:
    st.info("Login to Strava to begin.")
