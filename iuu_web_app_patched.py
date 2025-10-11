
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="IUU Risk Dashboard", layout="wide")

st.title("Enforcement Edge AI: IUU Risk Scoring Tool")

# Upload CSV
uploaded_file = st.file_uploader("Upload Vessel Data CSV", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # Check for required columns
    required_columns = [
        "Vessel Name", "MMSI", "IMO", "Flag State",
        "Latitude", "Longitude", "Days Since Port",
        "Speed (knots)", "Loitering Hours", "AIS Gap Hours"
    ]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        st.stop()

    # Define high-risk flags
    high_risk_flags = ["Panama", "Honduras", "Cambodia", "Belize", "St. Kitts & Nevis", "Sierra Leone", "Togo"]

    # Scoring function
    def score_vessel(row):
        score = 0
        if row["Flag State"] in high_risk_flags:
            score += 25
        if row["Days Since Port"] > 30:
            score += 15
        if row["Loitering Hours"] > 12:
            score += 20
        if row["AIS Gap Hours"] > 24:
            score += 20
        if row["Speed (knots)"] < 2:
            score += 10
        return score

    # Apply scoring
    df["Risk Score"] = df.apply(score_vessel, axis=1)
    df_sorted = df.sort_values(by="Risk Score", ascending=False)

    # Show top 10
    st.subheader("Top 10 Risk-Ranked Vessels")
    st.dataframe(df_sorted.head(10))

    # Map rendering
    st.subheader("Map of Vessel Locations")
    map_center = [df["Latitude"].mean(), df["Longitude"].mean()]
    m = folium.Map(location=map_center, zoom_start=4)

    # Add user's vessel location (blue dot)
    folium.Marker(
        location=[-10.0, 175.0],
        popup="Your Vessel (Patrol Ship)",
        icon=folium.Icon(color="blue", icon="ship", prefix="fa")
    ).add_to(m)

    # Add vessels to map
    for _, row in df.iterrows():
        folium.CircleMarker(
            location=[row["Latitude"], row["Longitude"]],
            radius=6,
            popup=f'{row["Vessel Name"]}: Score {row["Risk Score"]}',
            color="red" if row["Risk Score"] >= 70 else "orange" if row["Risk Score"] >= 50 else "green",
            fill=True,
            fill_opacity=0.7
        ).add_to(m)

    st_data = st_folium(m, width=900, height=500)

    # Generate narrative
    st.subheader("Narrative Summary for Top 3 Vessels")
    for i, row in df_sorted.head(3).iterrows():
        st.markdown(f"""
        **Vessel Name:** {row['Vessel Name']}  
        **Flag State:** {row['Flag State']}  
        **Risk Score:** {row['Risk Score']}  
        **Reason:**  
        - Days Since Port: {row['Days Since Port']}  
        - Loitering: {row['Loitering Hours']} hrs  
        - AIS Offline: {row['AIS Gap Hours']} hrs  
        - Speed: {row['Speed (knots)']} knots  
        """)
