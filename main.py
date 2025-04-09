from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import os

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
    if not stats:
        return {}

    cards = {"yellow": 0, "red": 0}
    corners = {"total": 0}
    possession = {"home": 50, "away": 50}
    pressure_data = {"home": {}, "away": {}}

    for team_stats in stats:
        team_side = "home" if stats.index(team_stats) == 0 else "away"
        stats_list = team_stats.get("statistics", [])

        for stat in stats_list:
            name = stat.get("type", "").lower()
            value = stat.get("value", 0) or 0

            if "yellow cards" in name:
                cards["yellow"] += int(value)
            elif "red cards" in name:
                cards["red"] += int(value)
            elif "corner kicks" in name:
                corners["total"] += int(value)
            elif "possession" in name and "%" in str(value):
                possession[team_side] = int(str(value).replace("%", ""))

            elif "total shots" in name:
                pressure_data[team_side]["shots"] = int(value)
            elif "shots on goal" in name:
                pressure_data[team_side]["shots_on"] = int(value)
            elif "attacks" in name:
                pressure_data[team_side]["attacks"] = int(value)
            elif "dangerous attacks" in name:
                pressure_data[team_side]["dangerous"] = int(value)

    return {
        "cards": cards,
        "corners": corners,
        "possession": possession,
        "pressure_raw": pressure_data
    }


def calculate_pressure(pressure_data, minute):
    if not pressure_data or minute == 0:
        return {"home": 50, "away": 50}

    def ipo(team):
        d_att = pressure_data[team].get("dangerous", 0)
        shots = pressure_data[team].get("shots", 0)
        shots_on = pressure_data[team].get("shots_on", 0)
        return (d_att * 2 + shots * 1.5 + shots_on * 2.5) / minute

    ipo_home = ipo("home")
    ipo_away = ipo("away")

    total = ipo_home + ipo_away
    if total == 0:
        return {"home": 50, "away": 50}

    return {
        "home": round(ipo_home / total * 100),
        "away": round(ipo_away / total * 100)
    }


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

        statistics = fetch_statistics(fixture_id)
        pressure = calculate_pressure(statistics.get("pressure_raw", {}), minute)

        total_goals = goals.get("home", 0) + goals.get("away", 0)
        if minute >= 60 and total_goals >= 3:
            prediction = "Riesgo alto"
        elif minute >= 30 and total_goals >= 2:
            prediction = "Riesgo moderado"
        else:
            prediction = "Bajo riesgo"

        results.append({
            "fixture_id": fixture_id,
            "minute": minute,
            "teams": {
                "home": {
                    "name": teams.get("home", {}).get("name"),
                    "logo": teams.get("home", {}).get("logo"),
                    "possession": statistics.get("possession", {}).get("home", 50)
                },
                "away": {
                    "name": teams.get("away", {}).get("name"),
                    "logo": teams.get("away", {}).get("logo"),
                    "possession": statistics.get("possession", {}).get("away", 50)
                }
            },
            "goals": goals,
            "statistics": {
                "cards": statistics.get("cards", {}),
                "corners": statistics.get("corners", {}),
                "pressure": pressure
            },
            "prediction": prediction
        })

    return {"matches": results}
