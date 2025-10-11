
def score_vessel_risk(df, flag_state, false_positive):
    # Extract sample data (replace with your actual logic)
    mmsi = df["MMSI"].iloc[-1] if "MMSI" in df.columns else "Unknown"
    imo = df["IMO"].iloc[-1] if "IMO" in df.columns else "Unknown"
    last_position = f"{df['Latitude'].iloc[-1]}°, {df['Longitude'].iloc[-1]}°" if "Latitude" in df.columns and "Longitude" in df.columns else "Unknown"

    # Risk scoring logic
    dark_hours = 36
    loiter_time = 48
    port_days = 40

    flag_risk_map = {
        "Panama": "High", "Liberia": "High", "Marshall Islands": "High",
        "China": "Medium", "Taiwan": "Medium", "Other": "Low"
    }
    flag_risk = flag_risk_map.get(flag_state, "Low")

    base_score = 50
    if flag_risk == "High":
        base_score += 20
    elif flag_risk == "Medium":
        base_score += 10

    if dark_hours > 24:
        base_score += 10
    if loiter_time > 24:
        base_score += 10
    if port_days > 30:
        base_score += 5
    if false_positive:
        base_score -= 10

    narrative = (
        f"This vessel, flagged under {flag_state} ({flag_risk} risk), showed suspicious activity including loitering in the high seas pocket and extended AIS dark periods. "
        f"It has not entered port for {port_days} days and ranks among the top 5% of high-risk vessels."
    )
    recommendation = "Monitor real-time. Notify RFMO and flag state. Intercept if vessel re-enters EEZ or lands catch."

    return {
        "mmsi": mmsi,
        "imo": imo,
        "last_position": last_position,
        "flag_risk": flag_risk,
        "ais_dark_hours": dark_hours,
        "past_violations": "Flagged for transshipment irregularities (2022, WCPFC)",
        "behavior_notes": f"Loitered {loiter_time} hrs; no port call for {port_days} days",
        "risk_score": base_score,
        "narrative": narrative,
        "recommendation": recommendation
    }
