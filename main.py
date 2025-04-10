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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis Cloud via Upstash
redis_url = os.getenv("REDIS_URL")
parsed_url = urllib.parse.urlparse(redis_url)

redis_client = redis.Redis(
    host=parsed_url.hostname,
    port=parsed_url.port,
    password=parsed_url.password,
    ssl=True,
    decode_responses=True
)

# RapidAPI (API-FOOTBALL)
API_KEY = os.getenv("RAPIDAPI_KEY")
API_HOST = os.getenv("RAPIDAPI_HOST", "api-football-v1.p.rapidapi.com")
API_BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
}

@app.get("/")
def root():
    return {"status": "OK", "message": "API Under Goal usando API-FOOTBALL (RapidAPI)"}

def fetch_statistics(fixture_id: int) -> dict:
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

    redis_client.setex(cache_key, 15, json.dumps(parsed))
    return parsed

def calculate_fatigue(pressure: dict, minute: int) -> dict:
    def level(p): return "Alta" if p > 60 else "Moderada" if p > 40 else "Baja"
    return {
        "home": level(pressure["home"]),
        "away": level(pressure["away"])
    }

def simulate_next_10min(pressure: dict, goals: dict) -> str:
    total_goals = goals.get("home", 0) + goals.get("away", 0)
    if max(pressure["home"], pressure["away"]) > 60 and total_goals >= 1:
        return "⚠️ Posible gol"
    elif total_goals == 0 and max(pressure["home"], pressure["away"]) < 40:
        return "✅ Sin peligro"
    return "🔄 Difícil de predecir"

@app.get("/live-predictions")
def get_live_predictions():
    try:
        url = f"{API_BASE_URL}/fixtures?live=all"
        res = requests.get(url, headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Error RapidAPI: {res.status_code}, {res.text}")

        fixtures = res.json().get("response", [])
        if not fixtures:
            return {"matches": [], "message": "No hay partidos activos en este momento"}

        results = []
        for match in fixtures:
            fixture_id = match["fixture"]["id"]
            stats = fetch_statistics(fixture_id)
            pressure = stats.get("pressure", {})
            fatigue = calculate_fatigue(pressure, match["fixture"]["status"].get("elapsed", 0))
            next_10 = simulate_next_10min(pressure, match.get("goals", {}))

            prediction_url = f"{API_BASE_URL}/predictions?fixture={fixture_id}"
            prediction_res = requests.get(prediction_url, headers=HEADERS)
            prediction_data = prediction_res.json().get('response', [])
            api_prediction = prediction_data[0]['predictions'] if isinstance(prediction_data, list) and prediction_data else 'N/A'

            results.append({
                "fixture_id": fixture_id,
                "minute": match["fixture"]["status"].get("elapsed", 0),
                "second": 0,
                "extra_time": match["fixture"]["status"].get("extra", 0) or 0,
                "league": {
                    "name": match["league"].get("name", ""),
                    "country": match["league"].get("country", ""),
                    "round": match["league"].get("round", "")
                },
                "teams": {
                    "home": {
                        "name": match["teams"]["home"].get("name", ""),
                        "logo": match["teams"]["home"].get("logo", "")
                    },
                    "away": {
                        "name": match["teams"]["away"].get("name", ""),
                        "logo": match["teams"]["away"].get("logo", "")
                    }
                },
                "goals": match.get("goals", {}),
                "statistics": {
                    "pressure": pressure,
                    "free_kicks": stats.get("free_kicks", {}),
                    "dangerous_attacks": stats.get("dangerous_attacks", {}),
                    "possession": stats.get("possession", {}),
                    "corners": stats.get("corners", {}),
                    "total_shots": stats.get("total_shots", {}),
                    "shots_on_goal": stats.get("shots_on_goal", {}),
                    "xg": stats.get("xg", {})
                },
                "prediction": "Riesgo alto" if match["goals"]["home"] + match["goals"]["away"] >= 3 else "Bajo riesgo",
                "fatigue": fatigue,
                "next_10min": next_10,
                "api_prediction": api_prediction
            })

        return {"matches": results}

    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}

# ⏳ Keep-alive (auto ping para Render cada 2 min)
def keep_alive():
    def ping():
        while True:
            try:
                requests.get("https://under-goal-backend.onrender.com/")
            except Exception:
                pass
            time.sleep(120)  # cada 2 minutos

    thread = threading.Thread(target=ping)
    thread.daemon = True
    thread.start()

keep_alive()
