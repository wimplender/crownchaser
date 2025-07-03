import os
import streamlit as st
from dotenv import load_dotenv

if os.path.exists(".env"):
    load_dotenv()
    CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
    CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
    REDIRECT_URI = "http://127.0.0.1:8501"
else:
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
    REDIRECT_URI = "https://crownchaser.streamlit.app"

CACHE_FILE = "kom_cache.json"
EXPLORE_CACHE_FILE = "explore_cache.json"
