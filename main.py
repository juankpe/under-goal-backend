from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

# Inicializamos la aplicación FastAPI
app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite el acceso desde cualquier dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ruta principal de la API
@app.get("/")
def root():
    return {"status": "OK", "message": "Under Goal API está funcionando"}

# Obtener la clave de API desde las variables de entorno
API_KEY = os.getenv("RAPIDAPI_KEY")
API_HOST = os.getenv("RAPIDAPI_HOST", "api-football-v1.p.rapidapi.com")
API_BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
}

# Función para obtener las estadísticas de un partido
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
