import streamlit as st
import plotly.express as px
from utils import load_gold

st.title("🏁 Constructor Dominance")

constructors = load_gold("dim_constructors")
results = load_gold("fact_session_results")
races = load_gold("dim_races")

df = (
    results
    .merge(constructors, on="constructor_id")
    .merge(races, on=["season", "round"])
)

constructor = st.selectbox("Select Constructor", sorted(df["constructor_name"].unique()))

filtered = df[df["constructor_name"] == constructor]

fig = px.line(filtered, x="season", y="points", title="Constructor Points Over Time")

fig = px.histogram(filtered, x="final_position", title="Finishing Position Distribution")
st.plotly_chart(fig, use_container_width=True)
