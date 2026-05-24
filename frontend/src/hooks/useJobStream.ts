"use client";
import { useEffect, useRef, useState } from "react";
import { buildJobStreamUrl, getJob } from "@/lib/api";
import type { Job } from "@/lib/types";
import { useClerkToken } from "./useClerkToken";

export function useJobStream(jobId: string) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { getToken } = useClerkToken();
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const token = await getToken();
        if (!token) {
          setError("Not authenticated");
          return;
        }

        // Hydrate current state before subscribing to SSE
        const current = await getJob(token, jobId);
        if (!cancelled) setJob(current);

        // If already terminal, no need to stream
        if (current.status === "completed" || current.status === "failed") {
          return;
        }

        const url = buildJobStreamUrl(jobId, token);
        const es = new EventSource(url);
        esRef.current = es;

        es.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as Partial<Job>;
            setJob((prev) => (prev ? { ...prev, ...data } : (data as Job)));
            if (data.status === "completed" || data.status === "failed") {
              es.close();
            }
          } catch {
            // ignore parse errors
          }
        };

        es.onerror = () => {
          if (!cancelled) {
            setError("Connection lost — job may still be running");
            es.close();
          }
        };
      } catch (err) {
        if (!cancelled) setError(String(err));
      }
    })();

    return () => {
      cancelled = true;
      esRef.current?.close();
    };
  }, [jobId]);

  return { job, error };
}
