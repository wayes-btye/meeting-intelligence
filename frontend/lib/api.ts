// API client — all calls go to FastAPI backend, never to Supabase directly
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// --- Types matching actual API schemas ---

export interface Meeting {
  id: string;
  title: string;
  created_at: string;
  chunk_count: number;
  num_speakers: number | null;
}

export interface SourceChunk {
  content: string;
  speaker: string;
  start_time: number | null;
  end_time: number | null;
  similarity: number | null;
  meeting_id: string | null;
  combined_score: number | null;
  meeting_title?: string | null;
}

export interface QueryResponse {
  answer: string;
  sources: SourceChunk[];
  model: string | null;
  usage: Record<string, unknown> | null;
}

export interface IngestResponse {
  meeting_id: string;
  title: string;
  num_chunks: number;
  chunking_strategy: string;
}

/** Returned by POST /api/ingest when a .zip file is uploaded. */
export interface BatchIngestResponse {
  meetings_ingested: number;
  meeting_ids: string[];
  errors: string[];
}

export interface ExtractedItem {
  item_type: string;
  content: string;
  assignee: string | null;
  due_date: string | null;
  speaker: string | null;
  confidence: number;
}

export interface ExtractResponse {
  meeting_id: string;
  items_extracted: number;
  action_items: ExtractedItem[];
  decisions: ExtractedItem[];
  topics: ExtractedItem[];
}

export interface MeetingDetail {
  id: string;
  title: string;
  created_at: string;
  num_speakers: number | null;
  raw_transcript: string | null;
  summary: string | null;
  chunks: SourceChunk[];
  extracted_items: ExtractedItem[];
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, options);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => apiFetch<{ status: string }>("/health"),

  getMeetings: () => apiFetch<Meeting[]>("/api/meetings"),

  getMeeting: (id: string) => apiFetch<MeetingDetail>(`/api/meetings/${id}`),

  // chunking_strategy: "naive" | "speaker_turn"
  // Returns IngestResponse for single files, BatchIngestResponse for .zip uploads.
  ingest: (file: File, title: string, chunkingStrategy: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    form.append("chunking_strategy", chunkingStrategy);
    return apiFetch<IngestResponse | BatchIngestResponse>("/api/ingest", { method: "POST", body: form });
  },

  extract: (meetingId: string) =>
    apiFetch<ExtractResponse>(`/api/meetings/${meetingId}/extract`, {
      method: "POST",
    }),

  deleteMeeting: async (meetingId: string): Promise<void> => {
    const res = await fetch(`${API_URL}/api/meetings/${meetingId}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(`Delete failed: ${res.status}`)
  },

  // strategy: "semantic" | "hybrid" (single retrieval strategy field)
  query: (
    question: string,
    meetingId: string | null,
    strategy: string,
  ) =>
    apiFetch<QueryResponse>("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        meeting_id: meetingId || null,
        strategy,
      }),
    }),
};
