"use client";

// Upload Page — POST /api/ingest (chunking_strategy), then POST /api/meetings/{id}/extract
// MANUAL VISUAL CHECK REQUIRED:
// 1. Start API: uvicorn src.api.main:app --port 8002 (from repo root)
// 2. Start frontend: cd frontend && npm run dev
// 3. Visit http://localhost:3000
// 4. Drag a .vtt/.txt/.json file onto the drop zone, set a title, click Upload
// 5. Expect: progress bar during upload, then extraction results (action items, decisions, topics)

import { useCallback, useRef, useState } from "react";
import { api, type ExtractResponse, type IngestResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

type Phase = "idle" | "uploading" | "extracting" | "done" | "error";

const ACCEPTED_EXTS = [".vtt", ".txt", ".json"];

interface Result {
  ingest: IngestResponse;
  extraction: ExtractResponse;
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [chunking, setChunking] = useState("speaker_turn");
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (!dropped) return;
    if (!ACCEPTED_EXTS.some((ext) => dropped.name.endsWith(ext))) {
      setError("Unsupported file type. Drop a .vtt, .txt, or .json file.");
      return;
    }
    setFile(dropped);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setError(null);
    setResult(null);
    setPhase("uploading");
    setProgress(20);

    try {
      // Step 1: ingest transcript
      const ingest = await api.ingest(file, title || file.name, chunking);
      setProgress(60);
      setPhase("extracting");

      // Step 2: auto-run extraction immediately after ingest
      const extraction = await api.extract(ingest.meeting_id);
      setProgress(100);
      setPhase("done");
      setResult({ ingest, extraction });
    } catch (err) {
      setPhase("error");
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Upload Transcript</h1>
        <p className="text-muted-foreground mt-1">
          Upload a meeting transcript to ingest, chunk, embed, and extract
          structured insights.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Drop zone */}
        <div
          data-testid="drop-zone"
          onClick={() => fileInputRef.current?.click()}
          onDrop={handleDrop}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 cursor-pointer transition-colors ${
            isDragging
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-primary/50"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".vtt,.txt,.json"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <div className="text-4xl mb-3">📂</div>
          {file ? (
            <div className="text-center">
              <p className="font-medium">{file.name}</p>
              <p className="text-sm text-muted-foreground mt-1">
                {(file.size / 1024).toFixed(1)} KB
              </p>
            </div>
          ) : (
            <div className="text-center">
              <p className="font-medium">Drop transcript here</p>
              <p className="text-sm text-muted-foreground mt-1">
                Accepts .vtt, .txt, .json
              </p>
            </div>
          )}
        </div>

        {/* Title */}
        <div className="space-y-1.5">
          <Label htmlFor="title">Meeting Title</Label>
          <Input
            id="title"
            placeholder="e.g. Q4 Planning Meeting"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        {/* Chunking strategy (ingest only uses chunking, not retrieval) */}
        <fieldset>
          <legend className="text-sm font-medium mb-2">Chunking Strategy</legend>
          <div className="flex gap-4">
            {["naive", "speaker_turn"].map((val) => (
              <label
                key={val}
                className="flex items-center gap-2 cursor-pointer text-sm"
              >
                <input
                  type="radio"
                  name="chunking"
                  value={val}
                  checked={chunking === val}
                  onChange={() => setChunking(val)}
                  className="accent-primary"
                />
                {val === "naive" ? "Naive" : "Speaker Turn"}
              </label>
            ))}
          </div>
        </fieldset>

        {/* Progress */}
        {(phase === "uploading" || phase === "extracting") && (
          <div className="space-y-2">
            <Progress value={progress} className="h-2" />
            <p className="text-sm text-muted-foreground">
              {phase === "uploading"
                ? "Processing transcript…"
                : "Extracting action items, decisions, topics…"}
            </p>
          </div>
        )}

        {/* Error */}
        {error && (
          <p className="text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/10 p-3">
            {error}
          </p>
        )}

        <Button
          type="submit"
          disabled={!file || phase === "uploading" || phase === "extracting"}
          className="w-full"
        >
          {phase === "uploading" || phase === "extracting"
            ? "Processing…"
            : "Upload & Analyse"}
        </Button>
      </form>

      {/* Results */}
      {result && (
        <div className="space-y-6" data-testid="extraction-results">
          {/* Ingest summary */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                ✅ Ingestion Complete
                <Badge variant="secondary">
                  {result.ingest.num_chunks} chunks
                </Badge>
                <Badge variant="outline">
                  {result.ingest.chunking_strategy === "speaker_turn"
                    ? "Speaker Turn"
                    : "Naive"}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Meeting ID:{" "}
                <code className="font-mono text-xs">
                  {result.ingest.meeting_id}
                </code>
              </p>
            </CardContent>
          </Card>

          {/* Action items */}
          {result.extraction.action_items.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  ✅ Action Items ({result.extraction.action_items.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {result.extraction.action_items.map((item, i) => (
                    <li key={i} className="text-sm border-l-2 border-primary pl-3">
                      <p>{item.content}</p>
                      {(item.assignee || item.due_date) && (
                        <p className="text-muted-foreground mt-0.5 text-xs">
                          {item.assignee && `Assignee: ${item.assignee}`}
                          {item.assignee && item.due_date && " · "}
                          {item.due_date && `Due: ${item.due_date}`}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Decisions */}
          {result.extraction.decisions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  🏛️ Decisions ({result.extraction.decisions.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1.5">
                  {result.extraction.decisions.map((d, i) => (
                    <li
                      key={i}
                      className="text-sm border-l-2 border-blue-500 pl-3"
                    >
                      {d.content}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Topics */}
          {result.extraction.topics.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  🏷️ Topics ({result.extraction.topics.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {result.extraction.topics.map((t, i) => (
                    <Badge key={i} variant="secondary">
                      {t.content}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* If nothing extracted */}
          {result.extraction.items_extracted === 0 && (
            <Card>
              <CardContent className="py-4 text-sm text-muted-foreground">
                No structured items extracted from this transcript.
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
