"""HTTP client wrapper for the Meeting Intelligence FastAPI backend."""

from __future__ import annotations

import os

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")


def check_health() -> bool:
    """Return True if the API server responds to /health."""
    try:
        r = httpx.get(f"{API_URL}/health", timeout=5.0)
        return r.status_code == 200
    except httpx.ConnectError:
        return False


def upload_transcript(
    file_content: bytes,
    filename: str,
    title: str,
    chunking_strategy: str = "speaker_turn",
) -> dict:  # type: ignore[type-arg]
    """Upload a transcript file to the ingestion endpoint."""
    try:
        r = httpx.post(
            f"{API_URL}/api/ingest",
            files={"file": (filename, file_content)},
            data={"title": title, "chunking_strategy": chunking_strategy},
            timeout=120.0,
        )
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]
    except httpx.HTTPError as e:
        st.error(f"Upload failed: {e}")
        return {}


def query_meetings(
    question: str,
    meeting_id: str | None = None,
    strategy: str = "hybrid",
) -> dict:  # type: ignore[type-arg]
    """Send a question to the query endpoint."""
    try:
        payload: dict[str, str] = {"question": question, "strategy": strategy}
        if meeting_id:
            payload["meeting_id"] = meeting_id
        r = httpx.post(f"{API_URL}/api/query", json=payload, timeout=60.0)
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]
    except httpx.HTTPError as e:
        st.error(f"Query failed: {e}")
        return {}


def get_meetings() -> list[dict]:  # type: ignore[type-arg]
    """Fetch the list of all ingested meetings."""
    try:
        r = httpx.get(f"{API_URL}/api/meetings", timeout=10.0)
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]
    except httpx.HTTPError:
        return []


def get_meeting_detail(meeting_id: str) -> dict:  # type: ignore[type-arg]
    """Fetch detailed information for a single meeting."""
    try:
        r = httpx.get(f"{API_URL}/api/meetings/{meeting_id}", timeout=10.0)
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]
    except httpx.HTTPError:
        return {}
