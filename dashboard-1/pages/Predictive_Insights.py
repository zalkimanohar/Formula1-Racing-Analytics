import streamlit as st
import pandas as pd
from utils import load_gold
from sklearn.ensemble import RandomForestRegressor

st.title("🔮 Predictive Insights")

results = load_gold("fact_session_results")
drivers = load_gold("dim_drivers")
races = load_gold("dim_races")

df = (
    results
    .merge(drivers, on="driver_id")
    .merge(races, on=["season", "round"])
)

# FIXED feature columns
features = df[["grid_position", "season"]]
target = df["final_position"]

from sklearn.ensemble import RandomForestRegressor
model = RandomForestRegressor().fit(features, target)

# FIXED UI inputs
grid = st.slider("Starting Grid Position", 1, 20)
season = st.slider("Season", int(df["season"].min()), int(df["season"].max()))

# FIXED prediction
prediction = model.predict([[grid, season]])[0]

st.metric("Predicted Finish Position", round(prediction, 2))