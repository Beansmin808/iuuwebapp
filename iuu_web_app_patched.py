import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import io

st.set_page_config(page_title="IUU Risk Dashboard", layout="wide")

st.title("Enforcement Edge AI: IUU Risk Scoring Tool")

st.markdown(
    "Upload a CSV of vessel positions and behaviors to generate an IUU risk ranking, "
    "visualize vessels on the map, and review narrative summaries for high-risk targets."
)

# -------- SIDEBAR CONFIG --------
st.sidebar.header("Scoring Configuration")

# High-risk flags (could also be editable via text_input)
default_high_risk_flags = [
    "Panama", "Honduras", "Cambodia", "Belize",
    "St. Kitts & Nevis", "Sierra Leone", "Togo"
]
high_risk_flags_input = st.sidebar.text_area(
    "High-risk flag states (comma separated):",
    ", ".join(default_high_risk_flags)
)
high_risk_flags = [f.strip() for f in high_risk_flags_input.split(",") if f.strip()]

# Weights
w_flag = st.sidebar.slider("Weight: High-risk flag", 0, 40, 25)
w_days_port = st.sidebar.slider("Weight: Days since port", 0, 30, 15)
w_loiter = st.sidebar.slider("Weight: Loitering", 0, 40, 20)
w_ais_gap = st.sidebar.slider("Weight: AIS gap", 0, 40, 20)
w_slow_speed = st.sidebar.slider("Weight: Very low speed", 0, 20, 10)

# Thresholds
t_days_port = st.sidebar.number_input("Threshold: Days since port >", 0, 365, 30)
t_loiter = st.sidebar.number_input("Threshold: Loitering hours >", 0, 168, 12)
t_ais_gap = st.sidebar.number_input("Threshold: AIS gap hours >", 0, 168, 24)
t_speed = st.sidebar.number_input("Threshold: Speed (knots) <", 0.0, 10.0, 2.0, 0.5)

# Patrol vessel location
st.sidebar.header("Patrol Asset")
patrol_lat = st.sidebar.number_input("Patrol latitude", -90.0, 90.0, -10.0, 0.1)
patrol_lon = st.sidebar.number_input("Patrol longitude", -180.0, 180.0, 175.0, 0.1)

# -------- FILE UPLOAD --------
uploaded_file = st.file_uploader("Upload Vessel Data CSV", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # Required columns
    required_columns = [
        "Vessel Name", "MMSI", "IMO", "Flag State",
        "Latitude", "Longitude", "Days Since Port",
        "Speed (knots)", "Loitering Hours", "AIS Gap Hours"
    ]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        st.stop()

    # Coerce numeric columns & fill NAs
    numeric_cols = [
        "Latitude", "Longitude", "Days Since Port",
        "Speed (knots)", "Loitering Hours", "AIS Gap Hours"
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df[numeric_cols] = df[numeric_cols].fillna(0)

    # -------- SCORING FUNCTION --------
    def score_vessel(row):
        score = 0

        # Flag state risk
        if row["Flag State"] in high_risk_flags:
            score += w_flag

        # Days since port
        if row["Days Since Port"] > t_days_port:
            score += w_days_port

        # Loitering
        if row["Loitering Hours"] > t_loiter:
            score += w_loiter

        # AIS gap
        if row["AIS Gap Hours"] > t_ais_gap:
            score += w_ais_gap

        # Very low speed
        if row["Speed (knots)"] < t_speed:
            score += w_slow_speed

        return score

    df["Risk Score"] = df.apply(score_vessel, axis=1)

    # Risk level buckets
    def risk_level(score):
        if score >= 80:
            return "Critical"
        elif score >= 60:
            return "High"
        elif score >= 40:
            return "Medium"
        else:
            return "Low"

    df["Risk Level"] = df["Risk Score"].apply(risk_level)

    df_sorted = df.sort_values(by="Risk Score", ascending=False)

    # -------- TOP 10 TABLE --------
    st.subheader("Top 10 Risk-Ranked Vessels")
    st.dataframe(
        df_sorted[
            ["Vessel Name", "MMSI", "Flag State", "Risk Score", "Risk Level",
             "Days Since Port", "Loitering Hours", "AIS Gap Hours", "Speed (knots)"]
        ].head(10),
        use_container_width=True
    )

    # Download button for scored data
    csv_buffer = io.StringIO()
    df_sorted.to_csv(csv_buffer, index=False)
    st.download_button(
        label="Download Full Scored Dataset (CSV)",
        data=csv_buffer.getvalue(),
        file_name="enforcement_edge_scored_vessels.csv",
        mime="text/csv"
    )

    # -------- MAP --------
    st.subheader("Map of Vessel Locations")

    map_center = [df["Latitude"].mean(), df["Longitude"].mean()]
    m = folium.Map(location=map_center, zoom_start=4)

    # Add patrol vessel marker
    folium.Marker(
        location=[patrol_lat, patrol_lon],
        popup="Your Vessel (Patrol Ship)",
        icon=folium.Icon(color="blue", icon="ship", prefix="fa"),
    ).add_to(m)

    # Helper: color by risk level
    def risk_color(score):
        if score >= 80:
            return "darkred"
        elif score >= 60:
            return "red"
        elif score >= 40:
            return "orange"
        else:
            return "green"

    for _, row in df.iterrows():
        folium.CircleMarker(
            location=[row["Latitude"], row["Longitude"]],
            radius=6,
            popup=(
                f"{row['Vessel Name']} ({row['Flag State']})<br>"
                f"Risk: {row['Risk Score']} ({row['Risk Level']})<br>"
                f"Days since port: {row['Days Since Port']}<br>"
                f"AIS gap: {row['AIS Gap Hours']} hrs"
            ),
            color=risk_color(row["Risk Score"]),
            fill=True,
            fill_opacity=0.7,
        ).add_to(m)

    st_folium(m, width=900, height=500)

    # -------- NARRATIVE --------
    st.subheader("Narrative Summary for Top 3 Vessels")

    for _, row in df_sorted.head(3).iterrows():
        reasons = []
        if row["Flag State"] in high_risk_flags:
            reasons.append(f"Flagged to higher-risk state ({row['Flag State']})")
        if row["Days Since Port"] > t_days_port:
            reasons.append(f"Extended time at sea: {row['Days Since Port']} days since last port")
        if row["Loitering Hours"] > t_loiter:
            reasons.append(f"Significant loitering: {row['Loitering Hours']} hours")
        if row["AIS Gap Hours"] > t_ais_gap:
            reasons.append(f"Long AIS silence: {row['AIS Gap Hours']} hours offline")
        if row["Speed (knots)"] < t_speed:
            reasons.append(f"Very low speed: {row['Speed (knots)']} knots")

        if not reasons:
            reasons.append("Routine behavior within configured thresholds.")

        st.markdown(f"""
        **Vessel Name:** {row['Vessel Name']}  
        **MMSI:** {row['MMSI']}  
        **Flag State:** {row['Flag State']}  
        **Risk Score / Level:** {row['Risk Score']} ({row['Risk Level']})  

        **Key Factors:**
        - {'; '.join(reasons)}
        """)

else:
    st.info("Upload a CSV file with vessel data to begin scoring.")

