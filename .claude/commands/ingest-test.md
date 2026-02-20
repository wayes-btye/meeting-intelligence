Run an end-to-end ingestion test using a real transcript. Do the following:

1. Check if `tests/fixtures/` has a transcript beyond `sample.vtt`. If so, use it. If not, use `tests/fixtures/sample.vtt`.
2. Ask the user: which ingestion mode? (a) call the API directly via `curl`/`httpx`, or (b) run the pipeline functions directly in Python.
3. Run the ingestion against the selected transcript. Report: chunks created, embeddings stored, any errors.
4. After ingestion, run a test query against the ingested meeting. Ask: "What were the main topics discussed?" Report the answer and the retrieved chunk count.
5. Summarise: did it work end-to-end? Any issues found?

Mark this as `@pytest.mark.expensive` behaviour — it calls live APIs (OpenAI embeddings, Supabase storage).
