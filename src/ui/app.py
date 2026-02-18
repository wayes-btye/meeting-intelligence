"""Meeting Intelligence -- Streamlit UI.

Multi-page application for uploading meeting transcripts, asking questions,
and browsing ingested meetings.
"""

from __future__ import annotations

import streamlit as st

from src.pipeline_config import ChunkingStrategy, RetrievalStrategy
from src.ui.api_client import (
    check_health,
    get_meeting_detail,
    get_meetings,
    query_meetings,
    upload_transcript,
)

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Meeting Intelligence", layout="wide")

# ---------------------------------------------------------------------------
# Sidebar -- navigation + strategy selectors + API status
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("Meeting Intelligence")
    st.markdown("---")

    page = st.radio(
        "Navigate",
        ["Upload Meeting", "Ask Questions", "Meetings"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.subheader("Pipeline Strategies")

    sidebar_chunking: str = st.selectbox(
        "Chunking strategy",
        options=[s.value for s in ChunkingStrategy],
        format_func=lambda x: "Speaker-turn" if x == "speaker_turn" else "Naive",
        key="sidebar_chunking",
    )

    sidebar_retrieval: str = st.selectbox(
        "Retrieval strategy",
        options=[s.value for s in RetrievalStrategy],
        format_func=lambda x: x.capitalize(),
        key="sidebar_retrieval",
    )

    st.markdown("---")

    # API connection indicator
    api_healthy = check_health()
    if api_healthy:
        st.markdown(":green_circle: API connected")
    else:
        st.markdown(":red_circle: API unreachable")

# ---------------------------------------------------------------------------
# Page: Upload Meeting
# ---------------------------------------------------------------------------
if page == "Upload Meeting":
    st.header("Upload Meeting")
    st.write("Upload a transcript or audio file to ingest into the system.")

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["vtt", "txt", "json", "mp3", "wav", "m4a"],
    )

    title = st.text_input("Meeting title", placeholder="e.g. Sprint Planning 2026-02-18")

    # Inform users about audio transcription
    if uploaded_file is not None and uploaded_file.name.split(".")[-1] in {
        "mp3",
        "wav",
        "m4a",
    }:
        st.info(
            "Audio files will be transcribed using AssemblyAI with speaker diarization. "
            "This may take a few minutes depending on the file length."
        )

    if st.button("Upload", disabled=uploaded_file is None or not title):
        if not api_healthy:
            st.error("Cannot upload: the API server is not reachable.")
        elif uploaded_file is not None and title:
            with st.spinner("Uploading and processing..."):
                result = upload_transcript(
                    file_content=uploaded_file.getvalue(),
                    filename=uploaded_file.name,
                    title=title,
                    chunking_strategy=sidebar_chunking,
                )
            if result:
                st.success("Meeting uploaded successfully.")
                if "meeting_id" in result:
                    st.write(f"**Meeting ID:** {result['meeting_id']}")
                if "num_chunks" in result:
                    st.write(f"**Chunks created:** {result['num_chunks']}")
            # Error case is already handled inside upload_transcript via st.error

# ---------------------------------------------------------------------------
# Page: Ask Questions
# ---------------------------------------------------------------------------
elif page == "Ask Questions":
    st.header("Ask Questions")
    st.write("Ask a natural-language question about your ingested meetings.")

    # Fetch meetings for the optional filter
    meetings_list = get_meetings() if api_healthy else []

    question = st.text_input(
        "Your question", placeholder="What were the action items from the last standup?"
    )

    meeting_options: dict[str, str | None] = {"All meetings": None}
    for m in meetings_list:
        label = m.get("title", m.get("id", "Unknown"))
        meeting_options[label] = m.get("id")
    selected_meeting_label = st.selectbox(
        "Filter by meeting (optional)", options=list(meeting_options.keys())
    )
    selected_meeting_id = meeting_options[selected_meeting_label]

    if st.button("Ask", disabled=not question):
        if not api_healthy:
            st.error("Cannot query: the API server is not reachable.")
        elif question:
            with st.spinner("Searching and generating answer..."):
                result = query_meetings(
                    question=question,
                    meeting_id=str(selected_meeting_id) if selected_meeting_id else None,
                    strategy=sidebar_retrieval,
                )
            if result:
                # Display the generated answer
                st.subheader("Answer")
                st.markdown(result.get("answer", "No answer returned."))

                # Display source chunks
                sources = result.get("sources", [])
                if sources:
                    st.subheader("Sources")
                    for i, src in enumerate(sources, 1):
                        with st.expander(
                            f"Source {i} -- {src.get('meeting_title', 'Unknown meeting')}"
                        ):
                            if "speaker" in src:
                                st.write(f"**Speaker:** {src['speaker']}")
                            if "timestamp" in src:
                                st.write(f"**Timestamp:** {src['timestamp']}")
                            if "similarity" in src:
                                st.write(f"**Similarity:** {src['similarity']:.4f}")
                            st.markdown("---")
                            st.write(src.get("text", ""))

# ---------------------------------------------------------------------------
# Page: Meetings
# ---------------------------------------------------------------------------
elif page == "Meetings":
    st.header("Meetings")
    st.write("Browse all ingested meetings.")

    if not api_healthy:
        st.warning("The API server is not reachable. Cannot load meetings.")
    else:
        meetings_list = get_meetings()
        if not meetings_list:
            st.info("No meetings found. Upload a transcript to get started.")
        else:
            for meeting in meetings_list:
                meeting_title = meeting.get("title", "Untitled")
                meeting_id = meeting.get("id", "")
                date = meeting.get("date", "N/A")
                num_speakers = meeting.get("num_speakers", "N/A")
                num_chunks = meeting.get("num_chunks", "N/A")

                with st.expander(f"{meeting_title}"):
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Date", date)
                    col_b.metric("Speakers", str(num_speakers))
                    col_c.metric("Chunks", str(num_chunks))

                    # Fetch detail on expand
                    detail = get_meeting_detail(meeting_id)
                    if detail:
                        # Action items
                        action_items = detail.get("action_items", [])
                        if action_items:
                            st.subheader("Action Items")
                            for item in action_items:
                                owner = item.get("owner", "Unassigned")
                                text = item.get("text", "")
                                st.write(f"- **{owner}:** {text}")

                        # Decisions
                        decisions = detail.get("decisions", [])
                        if decisions:
                            st.subheader("Decisions")
                            for dec in decisions:
                                st.write(f"- {dec.get('text', '')}")

                        # Topics
                        topics = detail.get("topics", [])
                        if topics:
                            st.subheader("Topics")
                            st.write(", ".join(topics))

                        if not action_items and not decisions and not topics:
                            st.write("No extracted items available yet.")
