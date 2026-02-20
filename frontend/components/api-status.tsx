"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

// Polls GET /health every 30s and shows a status indicator
export function ApiStatus() {
  const [status, setStatus] = useState<"checking" | "ok" | "down">("checking");

  useEffect(() => {
    const check = async () => {
      try {
        await api.health();
        setStatus("ok");
      } catch {
        setStatus("down");
      }
    };
    check();
    const interval = setInterval(check, 30_000);
    return () => clearInterval(interval);
  }, []);

  if (status === "checking") {
    return (
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className="h-2 w-2 rounded-full bg-yellow-400 animate-pulse" />
        Connecting…
      </span>
    );
  }

  if (status === "down") {
    return (
      <span className="flex items-center gap-1.5 text-xs text-destructive font-medium">
        <span className="h-2 w-2 rounded-full bg-destructive" />
        ⚠️ API not reachable
      </span>
    );
  }

  return (
    <span className="flex items-center gap-1.5 text-xs text-green-600 font-medium">
      <span className="h-2 w-2 rounded-full bg-green-500" />
      API online
    </span>
  );
}
