import os

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Meeting Intelligence", layout="wide")
st.title("Meeting Intelligence")

# Health check
try:
    response = httpx.get(f"{API_URL}/health", timeout=5.0)
    if response.status_code == 200:
        st.success("API connected")
    else:
        st.error(f"API returned {response.status_code}")
except httpx.ConnectError:
    st.warning("API not reachable. Start the API server first.")

st.info("Upload a meeting transcript or ask questions about your meetings.")
