@app.get("/live-predictions")
def get_live_predictions():
    url = f"{API_BASE_URL}/fixtures?live=all"
    response = requests.get(url, headers=HEADERS)
    
    # Log: API call response time
    print(f"API response time: {response.elapsed.total_seconds()} seconds")
    
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

        # Log: Track fixture processing time
        print(f"Processing fixture ID: {fixture_id}")
        
        # Direct call to get statistics without doing complex calculations in the loop
        stats = fetch_statistics(fixture_id)
        
        # Optimize pressure and fatigue calculation
        pressure = calculate_pressure(stats.get("pressure_raw", {}), minute)
        fatigue = calculate_fatigue(pressure, minute)
        
        # Add the ball location and rhythm
        ball_location = determine_ball_location(pressure)
        rhythm = classify_rhythm(pressure, stats.get("pressure_raw", {}))
        
        # Simulate the next 10 minutes (without complex checks)
        next_10 = simulate_next_10min(rhythm, goals)

        # Reduce unnecessary prediction checks, but add a basic risk assessment
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

    # Log the total time spent
    print(f"Total fixtures processed: {len(results)}")
    
    return {"matches": results}
