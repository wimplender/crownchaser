# app.py
import streamlit as st
import time
import requests
import pandas as pd
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

@st.cache_data(show_spinner=False)
def get_default_location():
    try:
        resp = requests.get("https://ipapi.co/json/", timeout=3)
        st.sidebar.caption(f"🌐 Location status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            city = data.get("city")
            lat = data.get("latitude")
            lon = data.get("longitude")
            st.sidebar.caption(f"📍 IP location: {city} ({lat}, {lon})")
            if city and lat and lon:
                return {
                    "city": city,
                    "lat": lat,
                    "lon": lon
                }
    except Exception as e:
        st.sidebar.caption(f"❌ IP location error: {e}")

    st.sidebar.caption("🔙 Falling back to default location")
    return {
        "city": "Le Thillot",
        "lat": None,
        "lon": None
    }

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("Your Info")
    ftp = st.number_input("⚡ Your FTP (W)", min_value=100, max_value=1000, value=250)

    st.header("Location")
    location_info = get_default_location()
    st.session_state["city_guess"] = location_info["city"]
    st.session_state["lat_guess"] = location_info["lat"]
    st.session_state["lon_guess"] = location_info["lon"]

    city_name = st.text_input("🌍 Enter city or area", value=st.session_state.city_guess)
    radius_km = st.slider("🔍 Search radius (km)", 1, 20, 5)

    if city_name in location_cache:
        lat, lon = location_cache[city_name]
    else:
        geolocator = Nominatim(user_agent="crownchaser", timeout=5)
        if city_name == st.session_state["city_guess"] and st.session_state.get("lat_guess") and st.session_state.get("lon_guess"):
            lat = st.session_state["lat_guess"]
            lon = st.session_state["lon_guess"]
        else:
            location = geolocator.geocode(city_name)
            if location:
                lat, lon = location.latitude, location.longitude
            else:
                st.warning("City not found. Please check the name.")
                st.stop()

        location_cache[city_name] = (lat, lon)

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

# (Remaining code below remains unchanged...)
# --- Segment Search ---
# [... your segment scanning and enrichment code ...]
