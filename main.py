import os
import sqlite3
import requests
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import traceback

# Configurar el logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Puedes ajustar las URLs permitidas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SQLite Configuración
DATABASE = "database.db"  # Nombre de la base de datos SQLite

# RapidAPI (API-FOOTBALL) Configuración
API_KEY = os.getenv("RAPIDAPI_KEY")
API_HOST = os.getenv("RAPIDAPI_HOST", "api-football-v1.p.rapidapi.com")
API_BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
}

# Inicializar base de datos SQLite
def init_db():
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS statistics (
                                fixture_id INTEGER PRIMARY KEY,
                                pressure_home INTEGER,
                                pressure_away INTEGER,
                                free_kicks_home INTEGER,
                                free_kicks_away INTEGER,
                                dangerous_attacks_home INTEGER,
                                dangerous_attacks_away INTEGER,
                                possession_home INTEGER,
                                possession_away INTEGER,
                                corners_home INTEGER,
                                corners_away INTEGER,
                                total_shots_home INTEGER,
                                total_shots_away INTEGER,
                                shots_on_goal_home INTEGER,
                                shots_on_goal_away INTEGER,
                                xg_home REAL,
                                xg_away REAL,
                                api_prediction TEXT,
                                next_goals TEXT
                            )''')
            conn.commit()
            logger.info("Base de datos inicializada correctamente.")
    except Exception as e:
        logger.error(f"Error al inicializar la base de datos: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al inicializar la base de datos")

# Fetch statistics and store in SQLite
def fetch_statistics(fixture_id: int) -> dict:
    logger.info(f"Consultando estadísticas para el partido ID {fixture_id}")
    
    try:
        # Verificar si los datos existen en la base de datos
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM statistics WHERE fixture_id = ?", (fixture_id,))
            data = cursor.fetchone()

        if data:
            logger.info(f"Datos encontrados en la base de datos para el partido ID {fixture_id}")
            return {
                "fixture_id": data[0],
                "pressure": {"home": data[1], "away": data[2]},
                "free_kicks": {"home": data[3], "away": data[4]},
                "dangerous_attacks": {"home": data[5], "away": data[6]},
                "possession": {"home": data[7], "away": data[8]},
                "corners": {"home": data[9], "away": data[10]},
                "total_shots": {"home": data[11], "away": data[12]},
                "shots_on_goal": {"home": data[13], "away": data[14]},
                "xg": {"home": data[15], "away": data[16]},
                "api_prediction": data[17],
                "next_goals": data[18]
            }
        
        # Si no encuentra en la base de datos, lo obtiene de la API
        logger.info(f"No se encontraron datos en la base de datos. Consultando la API para el partido ID {fixture_id}")
        url = f"{API_BASE_URL}/fixtures/statistics?fixture={fixture_id}"
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code != 200:
            logger.error(f"Error al consultar la API para el partido ID {fixture_id}. Código de respuesta: {response.status_code}")
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

        # Guardar datos en la base de datos
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO statistics (
                    fixture_id, pressure_home, pressure_away, free_kicks_home, free_kicks_away,
                    dangerous_attacks_home, dangerous_attacks_away, possession_home, possession_away,
                    corners_home, corners_away, total_shots_home, total_shots_away,
                    shots_on_goal_home, shots_on_goal_away, xg_home, xg_away, api_prediction, next_goals
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fixture_id, parsed["pressure"]["home"], parsed["pressure"]["away"],
                parsed["free_kicks"]["home"], parsed["free_kicks"]["away"],
                parsed["dangerous_attacks"]["home"], parsed["dangerous_attacks"]["away"],
                parsed["possession"]["home"], parsed["possession"]["away"],
                parsed["corners"]["home"], parsed["corners"]["away"],
                parsed["total_shots"]["home"], parsed["total_shots"]["away"],
                parsed["shots_on_goal"]["home"], parsed["shots_on_goal"]["away"],
                parsed["xg"]["home"], parsed["xg"]["away"], parsed["api_prediction"], parsed["next_goals"]
            ))
            conn.commit()
            logger.info(f"Datos del partido ID {fixture_id} guardados correctamente en la base de datos.")

        return parsed
    
    except Exception as e:
        logger.error(f"Error en fetch_statistics para el partido ID {fixture_id}: {str(e)}")
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Error al obtener las estadísticas")

# Ruta para obtener las actualizaciones en vivo
@app.get("/live-updates")
def get_live_updates():
    try:
        url = f"{API_BASE_URL}/fixtures?live=all"
        res = requests.get(url, headers=HEADERS)
        
        if res.status_code != 200:
            logger.error(f"Error al consultar la API de partidos en vivo. Código de respuesta: {res.status_code}")
            raise HTTPException(status_code=500, detail=f"Error RapidAPI: {res.status_code}, {res.text}")
        
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
        
        logger.info("Actualizaciones en vivo obtenidas correctamente.")
        return {"updates": updates}
    
    except Exception as e:
        logger.error(f"Error en la ruta /live-updates: {str(e)}")
        logger.debug(traceback.format_exc())
        return {"error": str(e), "trace": traceback.format_exc()}
