import requests
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict

# Inicializamos la aplicación FastAPI
app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Clave de API de RapidAPI
API_KEY = "132239f6a2mshdb90976390caecfp19239ejsneb1c3e217797"  # Tu clave de API de RapidAPI
API_HOST = "api-football-v1.p.rapidapi.com"
API_BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
}

# Ruta principal de la API
@app.get("/")
def root():
    return {"status": "OK", "message": "Under Goal API está funcionando"}

# Función para obtener las estadísticas de un partido
def fetch_statistics(fixture_id: int) -> Dict:
    url = f"{API_BASE_URL}/fixtures/statistics?fixture={fixture_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print("❌ ERROR STATS:", response.status_code, response.text)
        return {}

    stats = response.json().get("response", [])
    pressure_data = {"home": {}, "away": {}}

    for idx, team_stats in enumerate(stats):
        side = "home" if idx == 0 else "away"
        for stat in team_stats.get("statistics", []):
            name = stat.get("type", "").lower()
            value = stat.get("value", 0) or 0

            if "total shots" in name:
                pressure_data[side]["shots"] = int(value)
            elif "shots on goal" in name:
                pressure_data[side]["shots_on"] = int(value)
            elif "dangerous attacks" in name:
                pressure_data[side]["dangerous"] = int(value)

    return pressure_data

# Función para calcular la presión ofensiva
def calculate_pressure(raw: Dict, minute: int) -> Dict:
    def ipo(data):
        return (data.get("dangerous", 0) * 2 + data.get("shots", 0) * 1.5 + data.get("shots_on", 0) * 2.5) / (minute or 1)

    home_val = ipo(raw.get("home", {}))
    away_val = ipo(raw.get("away", {}))
    total = home_val + away_val or 1
    return {
        "home": round(home_val / total * 100),
        "away": round(away_val / total * 100)
    }

# Función para estimar el cansancio de los jugadores
def calculate_fatigue(pressure: Dict, minute: int) -> Dict:
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

# Función para simular los siguientes 10 minutos
def simulate_next_10min(rhythm: str, goals: Dict) -> str:
    if rhythm == "Alto" and (goals["home"] + goals["away"]) >= 1:
        return "⚠️ Posible gol"
    elif rhythm == "Bajo" and (goals["home"] + goals["away"]) == 0:
        return "✅ Sin peligro"
    return "🔄 Difícil de predecir"

# Función para obtener los partidos en vivo y sus predicciones
@app.get("/live-predictions")
def get_live_predictions():
    url = f"{API_BASE_URL}/fixtures?live=all"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code != 200:
        print("❌ ERROR RapidAPI:", response.status_code)
        print("➡️ Texto:", response.text)
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

        # Obtener estadísticas de cada partido
        stats = fetch_statistics(fixture_id)
        pressure = calculate_pressure(stats.get("pressure_raw", {}), minute)
        fatigue = calculate_fatigue(pressure, minute)
        next_10 = simulate_next_10min(pressure, goals)

        # Predicción de goles
        prediction = "Bajo riesgo"
        if minute >= 60 and (goals.get("home", 0) + goals.get("away", 0)) >= 3:
            prediction = "Riesgo alto"
        elif minute >= 30 and (goals.get("home", 0) + goals.get("away", 0)) >= 2:
            prediction = "Riesgo moderado"

        results.append({
            "fixture_id": fixture_id,
            "minute": minute,
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
                "pressure": pressure
            },
            "prediction": prediction,
            "fatigue": fatigue,
            "next_10min": next_10
        })

    return {"matches": results}
