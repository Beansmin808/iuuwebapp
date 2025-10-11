
import streamlit as st
import pandas as pd
import pydeck as pdk
import datetime

st.title("Enforcement Edge AI - IUU Vessel Report Generator")

uploaded_file = st.file_uploader("Upload your vessel tracking CSV", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # Handle both "Vessel Name" and "VesselName"
    vessel_col = "Vessel Name" if "Vessel Name" in df.columns else "VesselName"

    # Allow multiple vessel selection
    vessel_options = df[vessel_col].unique()
    selected_vessels = st.multiselect("Select Vessel(s)", vessel_options)

    for vessel in selected_vessels:
        st.subheader(f"Report: {vessel}")
        vessel_df = df[df[vessel_col] == vessel]

        # Basic metadata
        st.write("Last Known Position:")
        st.write(vessel_df.iloc[-1][["Latitude", "Longitude"]].to_dict())

        # Risk Score (mock)
        st.metric("Risk Score", "85 / 100")

        # Summary
        st.markdown("**Narrative Summary**")
        st.markdown("""
        This vessel exhibited suspicious loitering behavior in a high seas pocket near Tokelau. 
        It was offline for 36+ hours and has not visited port in over 40 days. 
        It is flagged under Panama, a known flag of convenience with prior violations. 
        Based on aggregated indicators, this vessel ranks among the top 5% of risk.
        """)

        # Action
        st.markdown("**Action Recommendation**")
        st.markdown("""
        - Monitor real-time movement via AIS
        - Notify RFMO and initiate flag-state inquiry
        - Intercept if vessel crosses EEZ
        """)

        # Map
        st.pydeck_chart(pdk.Deck(
            map_style='mapbox://styles/mapbox/light-v9',
            initial_view_state=pdk.ViewState(
                latitude=vessel_df["Latitude"].mean(),
                longitude=vessel_df["Longitude"].mean(),
                zoom=4,
                pitch=0,
            ),
            layers=[
                pdk.Layer(
                    'ScatterplotLayer',
                    data=vessel_df,
                    get_position='[Longitude, Latitude]',
                    get_color='[200, 30, 0, 160]',
                    get_radius=30000,
                ),
                pdk.Layer(
                    'LineLayer',
                    data=vessel_df,
                    get_source_position='[Longitude, Latitude]',
                    get_target_position='[Longitude, Latitude]',
                    pickable=True,
                    auto_highlight=True
                )
            ],
        ))
