from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = "132239f6a2mshdb90976390caecfp19239ejsneb1c3e217797"
API_HOST = "api-football-v1.p.rapidapi.com"
API_BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
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

        if minute >= 60 and total_goals >= 3:
            prediction = "Riesgo alto"
        elif minute >= 30 and total_goals >= 2:
            prediction = "Riesgo moderado"
        else:
            prediction = "Bajo riesgo"

        results.append({
            "fixture_id": fixture.get("id"),
            "minute": minute,
            "teams": teams,
            "goals": goals,
            "prediction": prediction
        })

    return {"matches": results}