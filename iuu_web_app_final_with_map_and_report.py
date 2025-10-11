
import streamlit as st
import pandas as pd
import pydeck as pdk
import math

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Radius of Earth in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c * 0.539957  # km to nautical miles

def score_vessel(row):
    risk = 0
    if row["FlagState"] in ["Panama", "Vanuatu", "Marshall Islands"]:
        risk += 40
    if row["Speed"] < 1:
        risk += 20
    if "Last Report" in row and row["Last Report"]:
        risk += 10  # placeholder for stale report
    return min(risk, 100)

st.title("Enforcement Edge AI – Proximity Risk Prioritization Tool")

uploaded_file = st.file_uploader("Upload CSV with Vessel Data", type="csv")
if uploaded_file:
    df = pd.read_csv(uploaded_file)

    lat = st.number_input("Enter Your Vessel's Latitude", value=-10.0)
    lon = st.number_input("Enter Your Vessel's Longitude", value=-170.0)
    range_nm = st.slider("Detection Range (Nautical Miles)", min_value=10, max_value=300, value=100)

    df["Distance (NM)"] = df.apply(lambda row: haversine(lat, lon, row["Latitude"], row["Longitude"]), axis=1)
    df_filtered = df[df["Distance (NM)"] <= range_nm].copy()
    df_filtered["Risk Score"] = df_filtered.apply(score_vessel, axis=1)
    df_filtered = df_filtered.sort_values(by="Risk Score", ascending=False)

    st.subheader("📋 Prioritized Vessel List")
    st.write(df_filtered[["Vessel Name", "MMSI", "FlagState", "Distance (NM)", "Risk Score"]])

    # Narrative summary for top 3 vessels
    st.subheader("📝 Boarding Recommendation Report")
    for i, row in df_filtered.head(3).iterrows():
        st.markdown(f"**{row['Vessel Name']}** (MMSI: {row['MMSI']}, Flag: {row['FlagState']})")
        st.markdown(f"- Distance: {row['Distance (NM)']:.2f} NM")
        st.markdown(f"- Risk Score: {row['Risk Score']}")
        st.markdown(f"- Reason: {'High-risk flag' if row['FlagState'] in ['Panama','Vanuatu','Marshall Islands'] else ''} {'Low speed' if row['Speed'] < 1 else ''} {'Stale AIS signal' if 'Last Report' in row and row['Last Report'] else ''}")
        st.markdown("---")

    # Map with vessel locations and your vessel as blue dot
    st.subheader("🗺️ Map of Nearby Vessels and Your Location")
    vessel_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_filtered,
        get_position="[Longitude, Latitude]",
        get_color="[200, 30, 0, 160]",
        get_radius=10000,
    )
    own_vessel_layer = pdk.Layer(
        "ScatterplotLayer",
        data=pd.DataFrame([{"Latitude": lat, "Longitude": lon}]),
        get_position="[Longitude, Latitude]",
        get_color="[0, 0, 255, 200]",  # Blue dot
        get_radius=12000,
    )
    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/dark-v10",
        initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=4),
        layers=[vessel_layer, own_vessel_layer],
    ))
