from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("RAPIDAPI_KEY")
API_HOST = os.getenv("RAPIDAPI_HOST", "api-football-v1.p.rapidapi.com")
API_BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
}

def fetch_statistics(fixture_id):
    url = f"{API_BASE_URL}/fixtures/statistics?fixture={fixture_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return {}

    stats = response.json().get("response", [])
    cards = {"yellow": 0, "red": 0}
    corners = {"home": 0, "away": 0}
    possession = {"home": 50, "away": 50}
    pressure_data = {"home": {}, "away": {}}
    free_kicks = {"home": 0, "away": 0}

    for idx, team_stats in enumerate(stats):
        side = "home" if idx == 0 else "away"
        for stat in team_stats.get("statistics", []):
            name = stat.get("type", "").lower()
            value = stat.get("value", 0) or 0

            if "yellow cards" in name:
                cards["yellow"] += int(value)
            elif "red cards" in name:
                cards["red"] += int(value)
            elif "corner" in name:
                corners[side] += int(value)
            elif "possession" in name and "%" in str(value):
                possession[side] = int(str(value).replace("%", ""))
            elif "total shots" in name:
                pressure_data[side]["shots"] = int(value)
            elif "shots on goal" in name:
                pressure_data[side]["shots_on"] = int(value)
            elif "attacks" in name and "dangerous" not in name:
                pressure_data[side]["attacks"] = int(value)
            elif "dangerous attacks" in name:
                pressure_data[side]["dangerous"] = int(value)
            elif "free kicks" in name:
                free_kicks[side] += int(value)

    return {
        "cards": cards,
        "corners": corners,
        "possession": possession,
        "pressure_raw": pressure_data,
        "free_kicks": free_kicks
    }

def calculate_pressure(raw, minute):
    def ipo(data):
        return (data.get("dangerous", 0) * 2 + data.get("shots", 0) * 1.5 + data.get("shots_on", 0) * 2.5) / (minute or 1)

    home_val = ipo(raw.get("home", {}))
    away_val = ipo(raw.get("away", {}))
    total = home_val + away_val or 1
    return {
        "home": round(home_val / total * 100),
        "away": round(away_val / total * 100)
    }

def calculate_fatigue(pressure, minute):
    def estimate(p):
        if minute < 30:
            return "Baja"
        elif p > 60:
            return "Alta"
        elif p > 40:
            return "Moderada"
        return "Baja"
    return {
        "home": estimate(pressure["home"]),
        "away": estimate(pressure["away"])
    }

def determine_ball_location(pressure):
    if pressure["home"] > 60:
        return "local"
    elif pressure["away"] > 60:
        return "visitante"
    return "medio"

def classify_rhythm(pressure, dangerous):
    total = pressure["home"] + pressure["away"]
    danger_total = dangerous["home"] + dangerous["away"]
    if total > 120 or danger_total > 40:
        return "Alto"
    elif total > 90 or danger_total > 25:
        return "Moderado"
    return "Bajo"

def simulate_next_10min(rhythm, goals):
    if rhythm == "Alto" and (goals["home"] + goals["away"]) >= 1:
        return "⚠️ Posible gol"
    elif rhythm == "Bajo" and (goals["home"] + goals["away"]) == 0:
        return "✅ Sin peligro"
    return "🔄 Difícil de predecir"

@app.get("/live-predictions")
def get_live_predictions():
    url = f"{API_BASE_URL}/fixtures?live=all"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Error al obtener datos de partidos en vivo")

    data = response.json()
    fixtures = data.get("response", [])
    results = []

    for match in fixtures:
        fixture = match.get("fixture", {})
        teams = match.get("teams", {})
        goals = match.get("goals", {})
        fixture_id = fixture.get("id")
        minute = fixture.get("status", {}).get("elapsed", 0)
        timestamp = fixture.get("timestamp")

        second = datetime.utcnow().second  # Aprox. para visual

        stats = fetch_statistics(fixture_id)
        pressure = calculate_pressure(stats.get("pressure_raw", {}), minute)
        fatigue = calculate_fatigue(pressure, minute)
        ball_location = determine_ball_location(pressure)
        rhythm = classify_rhythm(pressure, stats.get("pressure_raw", {}))
        next_10 = simulate_next_10min(rhythm, goals)

        if minute >= 60 and (goals.get("home", 0) + goals.get("away", 0)) >= 3:
            prediction = "Riesgo alto"
        elif minute >= 30 and (goals.get("home", 0) + goals.get("away", 0)) >= 2:
            prediction = "Riesgo moderado"
        else:
            prediction = "Bajo riesgo"

        results.append({
            "fixture_id": fixture_id,
            "minute": minute,
            "second": second,
            "teams": {
                "home": {
                    "name": teams.get("home", {}).get("name"),
                    "logo": teams.get("home", {}).get("logo")
                },
                "away": {
                    "name": teams.get("away", {}).get("name"),
                    "logo": teams.get("away", {}).get("logo")
                }
            },
            "goals": goals,
            "statistics": {
                "cards": stats.get("cards", {}),
                "corners": stats.get("corners", {}),
                "free_kicks": stats.get("free_kicks", {}),
                "pressure": pressure,
                "pressure_raw": stats.get("pressure_raw", {})
            },
            "prediction": prediction,
            "fatigue": fatigue,
            "ball_location": ball_location,
            "rhythm": rhythm,
            "next_10min": next_10
        })

    return {"matches": results}
