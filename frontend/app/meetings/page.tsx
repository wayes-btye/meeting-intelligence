"use client";

// Meetings Browser — GET /api/meetings, then GET /api/meetings/{id} on click
// MANUAL VISUAL CHECK REQUIRED:
// 1. Start API: uvicorn src.api.main:app --port 8002 (from repo root)
// 2. Start frontend: cd frontend && npm run dev
// 3. Visit http://localhost:3000/meetings
// 4. Expect: paginated table of meetings with title, date, chunk count, speaker count
// 5. Click a row — expect a detail panel below with action items, decisions, topics

import { useEffect, useState } from "react";
import { api, type Meeting, type MeetingDetail } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

const PAGE_SIZE = 10;

export default function MeetingsPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<MeetingDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Load meeting list
  useEffect(() => {
    api
      .getMeetings()
      .then(setMeetings)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Load detail when a meeting is selected
  useEffect(() => {
    if (!selected) return;
    setDetailLoading(true);
    setDetail(null);
    api
      .getMeeting(selected)
      .then(setDetail)
      .catch(console.error)
      .finally(() => setDetailLoading(false));
  }, [selected]);

  const totalPages = Math.ceil(meetings.length / PAGE_SIZE);
  const pageMeetings = meetings.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground">
        Loading meetings…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Meetings</h1>
        <p className="text-muted-foreground mt-1">
          {meetings.length} meeting{meetings.length !== 1 ? "s" : ""} ingested
        </p>
      </div>

      {meetings.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No meetings yet. Upload a transcript to get started.
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Table */}
          <div className="rounded-md border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Title</th>
                  <th className="text-left px-4 py-3 font-medium">Date</th>
                  <th className="text-right px-4 py-3 font-medium">Chunks</th>
                  <th className="text-right px-4 py-3 font-medium">Speakers</th>
                </tr>
              </thead>
              <tbody>
                {pageMeetings.map((m) => (
                  <tr
                    key={m.id}
                    onClick={() =>
                      setSelected(selected === m.id ? null : m.id)
                    }
                    className={`cursor-pointer border-t transition-colors hover:bg-muted/40 ${
                      selected === m.id ? "bg-muted/60" : ""
                    }`}
                  >
                    <td className="px-4 py-3 font-medium">{m.title}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDate(m.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Badge variant="secondary">{m.chunk_count}</Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {m.num_speakers !== null ? (
                        <Badge variant="outline">{m.num_speakers}</Badge>
                      ) : (
                        <span className="text-muted-foreground text-xs">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between text-sm">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <span className="text-muted-foreground">
                Page {page + 1} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page === totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}

      {/* Detail panel */}
      {selected && (
        <div data-testid="meeting-detail">
          {detailLoading ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                Loading details…
              </CardContent>
            </Card>
          ) : detail ? (
            <MeetingDetailPanel detail={detail} />
          ) : null}
        </div>
      )}
    </div>
  );
}

function MeetingDetailPanel({ detail }: { detail: MeetingDetail }) {
  const actionItems = detail.extracted_items.filter(
    (i) => i.item_type === "action_item",
  );
  const decisions = detail.extracted_items.filter(
    (i) => i.item_type === "decision",
  );
  const topics = detail.extracted_items.filter((i) => i.item_type === "topic");

  return (
    <Card>
      <CardHeader>
        <CardTitle>{detail.title}</CardTitle>
        <p className="text-sm text-muted-foreground">
          {formatDate(detail.created_at)} · {detail.chunks.length} chunks
          {detail.num_speakers !== null && ` · ${detail.num_speakers} speakers`}
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        {detail.extracted_items.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No extraction data yet. Upload and let the system extract on ingest.
          </p>
        ) : (
          <>
            {/* Action Items */}
            {actionItems.length > 0 && (
              <div>
                <h3 className="font-semibold text-sm mb-3">
                  ✅ Action Items ({actionItems.length})
                </h3>
                <ul className="space-y-2">
                  {actionItems.map((item, i) => (
                    <li
                      key={i}
                      className="text-sm border-l-2 border-primary pl-3"
                    >
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
              </div>
            )}

            {actionItems.length > 0 && decisions.length > 0 && <Separator />}

            {/* Decisions */}
            {decisions.length > 0 && (
              <div>
                <h3 className="font-semibold text-sm mb-3">
                  🏛️ Decisions ({decisions.length})
                </h3>
                <ul className="space-y-1.5">
                  {decisions.map((d, i) => (
                    <li
                      key={i}
                      className="text-sm border-l-2 border-blue-500 pl-3"
                    >
                      {d.content}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {decisions.length > 0 && topics.length > 0 && <Separator />}

            {/* Topics */}
            {topics.length > 0 && (
              <div>
                <h3 className="font-semibold text-sm mb-3">
                  🏷️ Topics ({topics.length})
                </h3>
                <div className="flex flex-wrap gap-2">
                  {topics.map((t, i) => (
                    <Badge key={i} variant="secondary">
                      {t.content}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}
