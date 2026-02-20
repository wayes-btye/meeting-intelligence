"use client";

// Chat Page — POST /api/query with optional meeting filter
// MANUAL VISUAL CHECK REQUIRED:
// 1. Start API: uvicorn src.api.main:app --port 8002 (from repo root)
// 2. Start frontend: cd frontend && npm run dev
// 3. Visit http://localhost:3000/chat
// 4. Select a meeting from the dropdown (or leave as "All meetings")
// 5. Type a question and hit Ask
// 6. Expect: answer text below the input, source cards with speaker/content/similarity/start_time

import { useEffect, useState } from "react";
import { api, type Meeting, type QueryResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

export default function ChatPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [selectedMeetingId, setSelectedMeetingId] = useState<string>("");
  const [question, setQuestion] = useState("");
  // strategy: "semantic" | "hybrid" — the only retrieval param the query endpoint accepts
  const [strategy, setStrategy] = useState("hybrid");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load meetings for the dropdown
  useEffect(() => {
    api.getMeetings().then(setMeetings).catch(console.error);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.query(
        question,
        selectedMeetingId || null,
        strategy,
      );
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Ask a Question</h1>
        <p className="text-muted-foreground mt-1">
          Query your meeting transcripts using semantic or hybrid retrieval.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Meeting selector */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium" htmlFor="meeting-select">
            Meeting
          </label>
          <select
            id="meeting-select"
            value={selectedMeetingId}
            onChange={(e) => setSelectedMeetingId(e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
          >
            <option value="">All meetings</option>
            {meetings.map((m) => (
              <option key={m.id} value={m.id}>
                {m.title}
              </option>
            ))}
          </select>
        </div>

        {/* Question */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium" htmlFor="question">
            Question
          </label>
          <Textarea
            id="question"
            placeholder="e.g. What were the key decisions made about the roadmap?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                void handleSubmit(e as unknown as React.FormEvent);
              }
            }}
          />
          <p className="text-xs text-muted-foreground">
            Tip: Cmd/Ctrl+Enter to submit
          </p>
        </div>

        {/* Retrieval strategy */}
        <fieldset>
          <legend className="text-sm font-medium mb-2">Retrieval Strategy</legend>
          <div className="flex gap-4">
            {["semantic", "hybrid"].map((val) => (
              <label
                key={val}
                className="flex items-center gap-2 cursor-pointer text-sm"
              >
                <input
                  type="radio"
                  name="strategy"
                  value={val}
                  checked={strategy === val}
                  onChange={() => setStrategy(val)}
                  className="accent-primary"
                />
                {val === "semantic" ? "Semantic" : "Hybrid"}
              </label>
            ))}
          </div>
        </fieldset>

        {/* Error */}
        {error && (
          <p className="text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/10 p-3">
            {error}
          </p>
        )}

        <Button
          type="submit"
          disabled={!question.trim() || loading}
          className="w-full"
        >
          {loading ? "Searching…" : "Ask"}
        </Button>
      </form>

      {/* Answer */}
      {result && (
        <div className="space-y-6" data-testid="query-result">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Answer</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {result.answer}
              </p>
            </CardContent>
          </Card>

          {/* Sources */}
          {result.sources.length > 0 && (
            <div className="space-y-3">
              <h2 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">
                Sources ({result.sources.length})
              </h2>
              {result.sources.map((source, i) => (
                <Card key={i} className="text-sm">
                  <CardContent className="pt-4 space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline">{source.speaker}</Badge>
                      {source.start_time !== null && (
                        <Badge variant="secondary">
                          {formatTime(source.start_time)}
                        </Badge>
                      )}
                      {source.similarity !== null && (
                        <Badge
                          variant="secondary"
                          className={similarityColor(source.similarity)}
                        >
                          {(source.similarity * 100).toFixed(0)}% match
                        </Badge>
                      )}
                      {source.combined_score !== null && (
                        <Badge variant="outline" className="text-xs">
                          score: {source.combined_score.toFixed(3)}
                        </Badge>
                      )}
                    </div>
                    <Separator />
                    <p className="text-muted-foreground leading-relaxed">
                      {source.content}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function similarityColor(score: number): string {
  if (score >= 0.85) return "text-green-700";
  if (score >= 0.7) return "text-yellow-700";
  return "text-muted-foreground";
}
