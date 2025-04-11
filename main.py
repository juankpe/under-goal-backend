import os
import json
import redis
import urllib.parse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import traceback
import threading
import time

app = FastAPI()

# CORS Configuration (Allow requests from any origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can adjust this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis Configuration
redis_url = os.getenv("REDIS_URL")  # Make sure the REDIS_URL is set as an environment variable
parsed_url = urllib.parse.urlparse(redis_url)

redis_client = redis.Redis(
    host=parsed_url.hostname,
    port=parsed_url.port,
    password=parsed_url.password,
    ssl=True,
    decode_responses=True
)

# RapidAPI (API-FOOTBALL) Configuration
API_KEY = os.getenv("RAPIDAPI_KEY")  # Make sure RAPIDAPI_KEY is set in the environment variables
API_HOST = os.getenv("RAPIDAPI_HOST", "api-football-v1.p.rapidapi.com")
API_BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
}

@app.get("/")
def root():
    return {"status": "OK", "message": "API Under Goal using API-FOOTBALL (RapidAPI)"}

def fetch_statistics(fixture_id: int) -> dict:
    """Fetch match statistics from Redis or API"""
    cache_key = f"stats:{fixture_id}"
    cached_data = redis_client.get(cache_key)
    if cached_data:
        return json.loads(cached_data)

    url = f"{API_BASE_URL}/fixtures/statistics?fixture={fixture_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return {}

    stats = response.json().get("response", [])
    parsed = {
        "pressure": {"home": 0, "away": 0},
        "free_kicks": {"home": 0, "away": 0},
        "dangerous_attacks": {"home": 0, "away": 0},
        "possession": {"home": 0, "away": 0},
        "corners": {"home": 0, "away": 0},
        "total_shots": {"home": 0, "away": 0},
        "shots_on_goal": {"home": 0, "away": 0},
        "xg": {"home": 0.0, "away": 0.0},
        "api_prediction": "N/A",
        "next_goals": "N/A"
    }

    for idx, team_stats in enumerate(stats):
        side = "home" if idx == 0 else "away"
        for stat in team_stats.get("statistics", []):
            name = stat.get("type", "").lower()
            value = stat.get("value", 0) or 0
            if "shots on goal" in name:
                parsed["shots_on_goal"][side] = int(value)
                parsed["pressure"][side] += int(value) * 2.5
            elif "total shots" in name:
                parsed["total_shots"][side] = int(value)
                parsed["pressure"][side] += int(value) * 1.5
            elif "dangerous attacks" in name:
                parsed["dangerous_attacks"][side] = int(value)
                parsed["pressure"][side] += int(value) * 2
            elif "possession" in name and isinstance(value, str):
                parsed["possession"][side] = int(value.replace("%", ""))
            elif "free kicks" in name:
                parsed["free_kicks"][side] = int(value)
            elif "corners" in name:
                parsed["corners"][side] = int(value)
            elif "expected goals" in name or "xg" in name:
                try:
                    parsed["xg"][side] = float(value)
                except:
                    parsed["xg"][side] = 0.0

    total = parsed["pressure"]["home"] + parsed["pressure"]["away"] or 1
    parsed["pressure"]["home"] = round(parsed["pressure"]["home"] / total * 100)
    parsed["pressure"]["away"] = round(parsed["pressure"]["away"] / total * 100)

    redis_client.setex(cache_key, 15, json.dumps(parsed))  # Cache expires in 15 seconds
    return parsed

@app.get("/live-updates")
def get_live_updates():
    """Get live match updates with real-time stats"""
    try:
        url = f"{API_BASE_URL}/fixtures?live=all"
        res = requests.get(url, headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Error from RapidAPI: {res.status_code}, {res.text}")

        fixtures = res.json().get("response", [])
        updates = []

        for match in fixtures:
            fixture_id = match["fixture"]["id"]
            stats = fetch_statistics(fixture_id)
            updates.append({
                "fixture_id": fixture_id,
                "minute": match["fixture"]["status"].get("elapsed", 0),
                "extra_time": match["fixture"]["status"].get("extra", 0) or 0,
                "goals": match.get("goals", {}),
                "free_kicks": stats.get("free_kicks", {}),
                "dangerous_attacks": stats.get("dangerous_attacks", {}),
                "corners": stats.get("corners", {}),
                "shots_on_goal": stats.get("shots_on_goal", {}),
                "total_shots": stats.get("total_shots", {}),
                "xg": stats.get("xg", {})
            })

        return {"updates": updates}

    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}

# Keep-alive function to prevent timeouts in Render (ping every 2 minutes)
def keep_alive():
    def ping():
        while True:
            try:
                requests.get("https://under-goal-backend.onrender.com/")  # Replace with your Render app URL
            except Exception:
                pass
            time.sleep(120)  # Sleep for 2 minutes

    thread = threading.Thread(target=ping)
    thread.daemon = True
    thread.start()

# Start the keep-alive thread
keep_alive()
