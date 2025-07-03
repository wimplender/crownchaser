# auth.py
from urllib.parse import urlencode
import requests
from config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

def get_auth_url():
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "read,activity:read_all",
        "approval_prompt": "auto",
    }
    return f"https://www.strava.com/oauth/authorize?{urlencode(params)}"

def exchange_token(code):
    token_url = "https://www.strava.com/oauth/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }
    return requests.post(token_url, data=data)
