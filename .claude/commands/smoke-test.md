Run a guided smoke test of all main user flows. Walk through each flow and report pass/fail:

**Flow 1: Health check**
- GET /health — expect 200 OK

**Flow 2: Text transcript ingestion**
- POST /ingest with `tests/fixtures/sample.vtt` as a text file
- Expect: meeting_id returned, chunks created

**Flow 3: Query against ingested meeting**
- POST /query with a question about the sample transcript
- Expect: answer returned with source citations

**Flow 4: Meetings list**
- GET /meetings — expect list with at least the meeting just ingested

**Flow 5: Meeting detail**
- GET /meetings/{id} for the ingested meeting
- Expect: metadata, chunks count, extracted items

**Flow 6: Structured extraction**
- POST /meetings/{id}/extract — expect action_items, decisions, topics arrays

**Flow 7: Strategy toggle**
- POST /query with `chunking_strategy: "naive"` and `retrieval_strategy: "semantic"`
- Compare retrieved chunks to default (speaker-turn + hybrid)

For each flow, report: ✅ Pass / ❌ Fail / ⚠️ Partial — with a one-line description of what happened.
If the API is not running, instruct the user to run `make api` first.
