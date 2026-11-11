"""Formula 1 in numbers - Streamlit entry point (`streamlit run app.py`).

The page itself is a self-contained web app in static/ (index.html, styles.css, app.js, assistant.js,
data.js), built from the cleaned dataset by build_web_data.py. Streamlit serves it full screen and starts
the local assistant service (data_management_project/src/assistant/api.py) if it is not running yet;
the same index.html also opens directly in a browser.
"""
import atexit
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
ASSISTANT_PORT = int(os.environ.get("F1_ASSISTANT_PORT", "8000"))

FULL_SCREEN = """
<style>
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"], [data-testid="stStatusWidget"], #MainMenu, footer { display: none !important; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: #16181c !important; }
[data-testid="stMainBlockContainer"], .block-container { padding: 0 !important; max-width: 100% !important; }
iframe { position: fixed !important; inset: 0 !important; width: 100vw !important; height: 100vh !important;
         border: 0 !important; z-index: 999; }
</style>
"""


@st.cache_resource(show_spinner=False)
def bundled_page(version: float) -> str:
    """index.html with its stylesheet and scripts inlined, so it can run inside one frame."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="styles.css">', f"<style>{css}</style>")
    return re.sub(r'<script src="([^"]+)"></script>',
                  lambda m: f"<script>{(STATIC / m.group(1)).read_text(encoding='utf-8')}</script>", html)


@st.cache_resource(show_spinner=False)
def start_assistant() -> str:
    """Start the assistant service once per Streamlit server, unless its port is already in use."""
    with socket.socket() as s:
        s.settimeout(0.3)
        if s.connect_ex(("127.0.0.1", ASSISTANT_PORT)) == 0:
            return "already running"
    # repository layout: ../data_management_project; submission ZIP layout: ../ (src/ next to dashboard/)
    project = next((p for p in (HERE.parent / "data_management_project", HERE.parent)
                    if (p / "src" / "assistant" / "api.py").exists()), None)
    if project is None:
        return "assistant code not found"
    log_dir = project / "outputs" / "assistant"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "api.log", "a", encoding="utf-8")  # noqa: SIM115 - kept open for the child process
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen([sys.executable, "-m", "src.assistant.api"], cwd=project, stdout=log,
                            stderr=subprocess.STDOUT, creationflags=flags)
    atexit.register(proc.terminate)
    return "started"


st.set_page_config(page_title="Formula 1 in Numbers, 1950-2025", page_icon=":material/sports_motorsports:",
                   layout="wide", initial_sidebar_state="collapsed")
st.markdown(FULL_SCREEN, unsafe_allow_html=True)
start_assistant()
latest_change = max(p.stat().st_mtime for p in STATIC.rglob("*") if p.is_file())
page = bundled_page(latest_change)  # our own static files only, never user input
if hasattr(st, "iframe"):  # newer Streamlit, where components.html is deprecated
    st.iframe(page, height=900)
else:
    components.html(page, height=900, scrolling=True)
