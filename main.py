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

    for team_stats in stats:
        team = team_stats.get("team", {})
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
                val = int(str(value).replace("%", ""))
                if team.get("name") == team_stats["team"]["name"]:
                    if team_stats == stats[0]:
                        possession["home"] = val
                    else:
                        possession["away"] = val

    return {
        "cards": cards,
        "corners": corners,
        "possession": possession
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

        minute = fixture.get("status", {}).get("elapsed", 0)
        total_goals = goals.get("home", 0) + goals.get("away", 0)

        # Obtener estadísticas avanzadas por partido
        fixture_id = fixture.get("id")
        statistics = fetch_statistics(fixture_id)

        # Clasificación de riesgo
        if minute >= 60 and total_goals >= 3:
            prediction = "Riesgo alto"
        elif minute >= 30 and total_goals >= 2:
            prediction = "Riesgo moderado"
        else:
            prediction = "Bajo riesgo"

        # Incluir datos
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
                "corners": statistics.get("corners", {})
            },
            "prediction": prediction
        })

    return {"matches": results}
