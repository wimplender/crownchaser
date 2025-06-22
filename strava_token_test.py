import requests
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
import os

load_dotenv()
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")

REDIRECT_URI = "http://localhost:8501"  # must exactly match your Strava app settings
CODE = "xxx"

response = requests.post(
    "https://www.strava.com/oauth/token",
    data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": CODE,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    },
)

print("Status code:", response.status_code)
print("Response body:", response.json())
