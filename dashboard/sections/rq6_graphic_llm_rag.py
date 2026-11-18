import streamlit as st
import pandas as pd
import os
import requests
import plotly.graph_objects as go
from utils import f1_fig


def _render_star_schema_network():
    """Renders an interactive Plotly Knowledge Graph of the F1 Star Schema & GraphRAG topology."""
    nodes = [
        ("FactSessionResults", 0.0, 0.0, "#ff1e00", 38),
        ("DimDrivers", -1.4, 1.0, "#00d2be", 28),
        ("DimConstructors", 1.4, 1.0, "#0090ff", 28),
        ("DimRaces", -1.4, -1.0, "#ff8700", 28),
        ("SilverCircuits", 0.0, -1.5, "#ffd700", 24),
        ("RefNationalityRegion", -2.5, 1.4, "#a855f7", 22),
        ("SilverSprints", 1.4, -1.0, "#22c55e", 24),
    ]
    edges = [
        ("DimDrivers", "FactSessionResults"),
        ("DimConstructors", "FactSessionResults"),
        ("DimRaces", "FactSessionResults"),
        ("SilverCircuits", "DimRaces"),
        ("RefNationalityRegion", "DimDrivers"),
        ("SilverSprints", "FactSessionResults"),
    ]
    pos = {n[0]: (n[1], n[2]) for n in nodes}

    edge_x, edge_y = [], []
    for u, v in edges:
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    fig = f1_fig("F1 Star Schema & Neo4j Knowledge Graph Topology", height=420)
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(width=2, color="#555555"),
        hoverinfo="none"
    ))
    fig.add_trace(go.Scatter(
        x=[n[1] for n in nodes],
        y=[n[2] for n in nodes],
        mode="markers+text",
        text=[n[0] for n in nodes],
        textposition="bottom center",
        marker=dict(size=[n[4] for n in nodes], color=[n[3] for n in nodes], line=dict(width=2, color="#ffffff")),
        hoverinfo="text"
    ))
    fig.update_xaxes(visible=False, range=[-3.2, 2.2])
    fig.update_yaxes(visible=False, range=[-2.1, 2.0])
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def render():
    st.title("🏁 F1 LLM-RAG + Graph + Multi-Model Engine")
    st.markdown("🚀 *Powered by Local Ollama Llama 3, Hybrid Vector/Graph RAG, and Parallel ML Engines.*")

    API_URL = "http://127.0.0.1:8000"

    st.sidebar.markdown("---")
    st.sidebar.subheader("🧠 AI Engine Controls")
    run_training_flag = st.sidebar.checkbox("Trigger Training / Auto-Compute", value=False, key="rq6_run_training")

    with st.expander("🌐 View Formula 1 Star Schema Knowledge Graph", expanded=True):
        _render_star_schema_network()
        graph_png_path = "f1_knowledge_graph.png"
        if os.path.exists(graph_png_path):
            st.image(graph_png_path, caption="Exported Neo4j Star Schema Mapping", use_container_width=True)

    st.markdown("---")

    def display_response_data(res_data):
        if isinstance(res_data, dict):
            intent = res_data.get("detected_intent", {})
            winning_model = str(res_data.get("winning_model", "N/A")).upper()
            model_score = res_data.get("model_score", "N/A")

            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            with m_col1:
                st.metric("Detected Target", intent.get("target", "N/A"))
            with m_col2:
                st.metric("Task Mode", intent.get("task", "N/A"))
            with m_col3:
                st.metric("Winning Model", winning_model)
            with m_col4:
                st.metric("Model Score", f"{model_score:.4f}" if isinstance(model_score, float) else str(model_score))

            context_summary = res_data.get("retrieved_context", res_data.get("context_summary", ""))
            if context_summary:
                with st.expander("🔍 View Retrieved Hybrid (Vector + Graph) Context", expanded=False):
                    st.code(context_summary, language="markdown")

            st.markdown("---")
            llm_text = res_data.get("llm_response", res_data.get("response", res_data.get("answer", "")))
            if llm_text:
                st.markdown(llm_text)
            else:
                st.json(res_data)
        else:
            st.markdown(str(res_data))

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if isinstance(message["content"], dict):
                display_response_data(message["content"])
            else:
                st.markdown(message["content"])

    if prompt := st.chat_input("Ask an F1 question (e.g., Show all race results for Max Verstappen in 2024)..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Querying Graph Engine & Local LLM..."):
                payload = {"prompt": str(prompt), "run_training": bool(run_training_flag)}
                try:
                    response = requests.post(
                        f"{API_URL}/chat",
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=180
                    )
                    if response.status_code == 200:
                        res_data = response.json()
                        display_response_data(res_data)
                        st.session_state.messages.append({"role": "assistant", "content": res_data})
                    else:
                        error_msg = f"⚠️ Backend API returned status code {response.status_code}. Response: {response.text}"
                        st.markdown(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
                except Exception as e:
                    error_msg = f"⚠️ Could not reach FastAPI backend at `{API_URL}`. Make sure `uvicorn api.app:app` is running on port 8000.\n\n*Error details:* {e}"
                    st.markdown(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})