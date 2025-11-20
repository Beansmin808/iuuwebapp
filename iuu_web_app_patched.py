import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import io
import math

st.set_page_config(page_title="IUU Risk Dashboard", layout="wide")

st.title("Enforcement Edge AI: IUU Risk Scoring Tool")

st.markdown(
    "Upload a CSV of vessel positions and behaviors to generate an IUU risk ranking, "
    "visualize vessels on the map, and review narrative summaries for high-risk targets."
)

# -------- SIDEBAR CONFIG --------
st.sidebar.header("Scoring Configuration")

# High-risk flags (editable)
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

# Distance filter
st.sidebar.header("Distance Filter")
max_distance_filter = st.sidebar.slider(
    "Show vessels within this distance of patrol asset (nm)",
    10, 1000, 250, 10
)

# -------- HELPER: DISTANCE FUNCTION --------
def haversine_nm(lat1, lon1, lat2, lon2):
    """
    Great-circle distance between two points on Earth in nautical miles.
    """
    # Convert degrees to radians
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)

    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1

    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    # Earth radius in nautical miles ~ 3440.07
    distance_nm = 3440.07 * c
    return distance_nm

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

    # -------- DISTANCE FROM PATROL --------
    df["Distance from Patrol (nm)"] = df.apply(
        lambda r: haversine_nm(patrol_lat, patrol_lon, r["Latitude"], r["Longitude"]),
        axis=1
    )

    # -------- SCORING FUNCTION --------
    def score_vessel(row):
        score = 0

        if row["Flag State"] in high_risk_flags:
            score += w_flag

        if row["Days Since Port"] > t_days_port:
            score += w_days_port

        if row["Loitering Hours"] > t_loiter:
            score += w_loiter

        if row["AIS Gap Hours"] > t_ais_gap:
            score += w_ais_gap

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

    # Apply distance filter for what we display
    df_view = df[df["Distance from Patrol (nm)"] <= max_distance_filter].copy()
    df_view_sorted = df_view.sort_values(by="Risk Score", ascending=False)

    if df_view.empty:
        st.warning(
            f"No vessels found within {max_distance_filter} nm of the patrol asset. "
            "Try increasing the distance filter."
        )
    else:
        # -------- TOP 10 TABLE --------
        st.subheader(f"Top 10 Risk-Ranked Vessels within {max_distance_filter} nm")
        st.dataframe(
            df_view_sorted[
                [
                    "Vessel Name", "MMSI", "Flag State", "Risk Score", "Risk Level",
                    "Days Since Port", "Loitering Hours", "AIS Gap Hours",
                    "Speed (knots)", "Distance from Patrol (nm)"
                ]
            ].head(10),
            use_container_width=True
        )

    # Download button for scored data (full set, not just filtered)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button(
        label="Download Full Scored Dataset (CSV)",
        data=csv_buffer.getvalue(),
        file_name="enforcement_edge_scored_vessels.csv",
        mime="text/csv"
    )

    # -------- MAP --------
    st.subheader(f"Map of Vessel Locations (within {max_distance_filter} nm)")

    if not df_view.empty:
        map_center = [
            df_view["Latitude"].mean(),
            df_view["Longitude"].mean()
        ]
    else:
        map_center = [patrol_lat, patrol_lon]

    m = folium.Map(location=map_center, zoom_start=4)

    # Add patrol vessel marker
    folium.Marker(
        location=[patrol_lat, patrol_lon],
        popup="Your Vessel (Patrol Ship)",
        icon=folium.Icon(color="blue", icon="ship", prefix="fa"),
    ).add_to(m)

    # Helper: color by risk score
    def risk_color(score):
        if score >= 80:
            return "darkred"
        elif score >= 60:
            return "red"
        elif score >= 40:
            return "orange"
        else:
            return "green"

    for _, row in df_view.iterrows():
        folium.CircleMarker(
            location=[row["Latitude"], row["Longitude"]],
            radius=6,
            popup=(
                f"{row['Vessel Name']} ({row['Flag State']})<br>"
                f"Risk: {row['Risk Score']} ({row['Risk Level']})<br>"
                f"Distance from patrol: {row['Distance from Patrol (nm)']:.1f} nm<br>"
                f"Days since port: {row['Days Since Port']}<br>"
                f"AIS gap: {row['AIS Gap Hours']} hrs"
            ),
            color=risk_color(row["Risk Score"]),
            fill=True,
            fill_opacity=0.7,
        ).add_to(m)

    st_folium(m, width=900, height=500)

    # -------- OPERATIONAL SUMMARY (TEMPLATED) --------
    st.subheader("Operational Summary")

    # 1) Vessels within 100 miles of position
    within_100 = df[df["Distance from Patrol (nm)"] <= 100]
    count_100 = len(within_100)

    if count_100 == 0:
        summary_text = (
            "Summary: There are no vessels within 100 miles of your position."
        )
        st.markdown(summary_text)
    else:
        # Determine majority direction based on bearing
        def cardinal_direction(lat_p, lon_p, lat_v, lon_v):
            dlat = lat_v - lat_p
            dlon = lon_v - lon_p
            angle = math.degrees(math.atan2(dlat, dlon))  # -180 to 180

            if -45 <= angle <= 45:
                return "East"
            elif 45 < angle < 135:
                return "North"
            elif -135 < angle < -45:
                return "South"
            else:
                return "West"

        directions = within_100.apply(
            lambda r: cardinal_direction(
                patrol_lat, patrol_lon, r["Latitude"], r["Longitude"]
            ),
            axis=1
        )

        if directions.empty:
            majority_direction = "unknown"
        else:
            majority_direction = directions.value_counts().idxmax()

        # 2) Priority vessels within 50 miles of asset
        within_50 = df[df["Distance from Patrol (nm)"] <= 50].copy()
        within_50_sorted = within_50.sort_values(by="Risk Score", ascending=False)

        priority_vessels = within_50_sorted.head(3)["Vessel Name"].tolist()

        # Build the summary string
        base_summary = (
            f"Summary: There are {count_100} vessels within 100 miles of your position. "
            f"The majority of vessels are to the {majority_direction}."
        )

        if len(priority_vessels) == 0:
            priority_summary = " There are no priority vessels within 50 miles of your asset."
        elif len(priority_vessels) == 1:
            priority_summary = (
                f" There is one priority vessel within 50 miles of your asset. "
                f"It is {priority_vessels[0]}."
            )
        elif len(priority_vessels) == 2:
            priority_summary = (
                f" There are two priority vessels within 50 miles of your asset. "
                f"They are {priority_vessels[0]} and {priority_vessels[1]}."
            )
        else:
            priority_summary = (
                f" There are three priority vessels within 50 miles of your asset. "
                f"They are {priority_vessels[0]}, {priority_vessels[1]}, and {priority_vessels[2]}."
            )

        st.markdown(base_summary + priority_summary)

    # -------- NARRATIVE FOR TOP 3 (OPTIONAL DETAIL) --------
    st.subheader("Narrative Summary for Top 3 Vessels (Filtered View)")

    if not df_view_sorted.empty:
        for _, row in df_view_sorted.head(3).iterrows():
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
            **Distance from Patrol:** {row['Distance from Patrol (nm)']:.1f} nm  

            **Key Factors:**
            - {'; '.join(reasons)}
            """)

else:
    st.info("Upload a CSV file with vessel data to begin scoring.")

