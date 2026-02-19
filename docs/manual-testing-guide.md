# Manual Testing Guide

Step-by-step instructions for testing the Meeting Intelligence system locally.

## Prerequisites

1. Python 3.11+ installed
2. `.env` file created with API keys (no quotes around values):
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   OPENAI_API_KEY=sk-...
   ASSEMBLYAI_API_KEY=
   SUPABASE_URL=https://qjmswgbkctaazcyhinew.supabase.co
   SUPABASE_KEY=sb_publishable_...
   ```
3. Dependencies installed: `pip install -e ".[dev]"`
4. Supabase migrations applied (already done via CLI)

---

## Step 1: Run the automated tests

```bash
python -m pytest tests/ -v
```

**What this does:** Runs 108 automated checks against the code. These don't call any real APIs — they use fake stand-ins (mocks). Costs nothing, takes ~13 seconds.

**Expected output:** `108 passed, 1 warning`

---

## Step 2: Start the API server

```bash
uvicorn src.api.main:app --reload --port 8000
```

**What this does:** Starts the FastAPI backend on http://localhost:8000. The `--reload` flag means it restarts automatically when you edit code.

**Test it's running:**
```bash
curl http://localhost:8000/health
```
Or open http://localhost:8000/health in a browser. Should return `{"status": "healthy"}`.

**API docs:** Open http://localhost:8000/docs for the interactive Swagger UI where you can try all endpoints.

---

## Step 3: Start the Streamlit UI

Open a second terminal:
```bash
streamlit run src/ui/app.py --server.port 8501
```

**What this does:** Starts the frontend on http://localhost:8501.

**Check:** Sidebar should show a green "API Connected" indicator. If it shows red, the API server from Step 2 isn't running.

---

## Step 4: Upload a test transcript

**Via the UI:**
1. Click "Upload Meeting" in sidebar
2. Upload `tests/fixtures/sample.vtt` (included in the repo)
3. Set title: "Test Council Meeting"
4. Choose chunking strategy (Speaker-turn is default)
5. Click Upload

**Via curl:**
```bash
curl -X POST http://localhost:8000/api/ingest \
  -F "file=@tests/fixtures/sample.vtt" \
  -F "title=Test Council Meeting" \
  -F "chunking_strategy=speaker_turn"
```

**Expected:** Returns a JSON response with `meeting_id` (UUID) and `num_chunks` (should be > 0).

**Note:** This step calls the OpenAI API to generate embeddings — it will cost a fraction of a cent.

> **Known issue:** Do NOT upload audio files (mp3/wav/m4a). The UI shows these as accepted but the backend will crash. Audio transcription is not yet implemented.

---

## Step 5: Ask a question

**Via the UI:**
1. Click "Ask Questions" in sidebar
2. Type: "What was discussed in this meeting?"
3. Click Ask

**Via curl:**
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What was discussed in this meeting?", "strategy": "hybrid"}'
```

**Expected:** Returns an answer with source citations. This calls both OpenAI (embedding the question) and Claude (generating the answer).

**Try different strategies:** Change `"strategy": "hybrid"` to `"strategy": "semantic"` and compare results.

---

## Step 6: Browse meetings

**Via the UI:**
1. Click "Meetings" in sidebar
2. You should see your uploaded meeting listed

> **Known issue:** Some fields may show "N/A" due to field name mismatches between the UI and API. This is a known bug being tracked.

---

## Step 7: Trigger extraction

```bash
curl -X POST http://localhost:8000/api/meetings/{MEETING_ID}/extract
```

Replace `{MEETING_ID}` with the UUID from Step 4.

**What this does:** Calls Claude to extract action items, decisions, and key topics from the meeting transcript and stores them in Supabase.

---

## Step 8: Test query routing

After extraction, try structured vs open-ended questions:

```bash
# Structured query — should route to DB lookup
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What action items were assigned?"}'

# Open-ended query — should route through RAG
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What was the main disagreement about?"}'
```

---

## Step 9: Load MeetingBank data (optional, costs ~$0.10-0.50)

```bash
# Download 30 meetings from HuggingFace
python scripts/download_meetingbank.py

# Ingest into Supabase (calls OpenAI embeddings API)
python scripts/load_meetingbank.py --max 5    # start small
python scripts/load_meetingbank.py --max 30   # full set
```

---

## Docker alternative

Instead of Steps 2-3, run everything with Docker:

```bash
docker compose up --build
```

API on http://localhost:8000, UI on http://localhost:8501.

---

## Cost estimates

- **Tests (Step 1):** Free (no API calls)
- **Upload one transcript (Step 4):** ~$0.001 (OpenAI embeddings)
- **One question (Step 5):** ~$0.01-0.03 (OpenAI embedding + Claude generation)
- **Extraction (Step 7):** ~$0.02-0.05 (Claude extraction)
- **Load 30 MeetingBank meetings (Step 9):** ~$0.10-0.50 (OpenAI embeddings)
