import streamlit as st

def set_theme():
    st.markdown(
        """
        <style>
        html, body, .main {
            background-color: #0d0d0d !important;
            color: #e6e6e6 !important;
        }
        h1, h2, h3, h4, h5 {
            color: #ff1e00 !important;
            font-weight: 700 !important;
        }
        section[data-testid="stSidebar"] {
            background-color: #111111 !important;
            border-right: 1px solid #333333 !important;
        }
        div[data-testid="metric-container"] {
            background-color: #1a1a1a !important;
            border-radius: 10px !important;
            padding: 15px !important;
            border: 1px solid #333333 !important;
        }
        .stButton>button {
            background-color: #ff1e00 !important;
            color: white !important;
            border-radius: 8px !important;
            padding: 0.6rem 1.2rem !important;
            border: none !important;
            font-weight: 600 !important;
        }
        .stButton>button:hover {
            background-color: #cc1900 !important;
        }
        footer {
            visibility: hidden !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )