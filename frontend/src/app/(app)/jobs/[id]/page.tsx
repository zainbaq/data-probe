"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useJobStream } from "@/hooks/useJobStream";
import type { JobStatus } from "@/lib/types";

const STAGES: { status: JobStatus; label: string; pct: number }[] = [
  { status: "queued", label: "Queued", pct: 0 },
  { status: "profiling", label: "Profiling columns", pct: 10 },
  { status: "inferring", label: "Inferring relationships", pct: 25 },
  { status: "analyzing", label: "AI analysis", pct: 40 },
  { status: "validating", label: "Validating SQL fixes", pct: 75 },
  { status: "assembling", label: "Assembling report", pct: 90 },
  { status: "completed", label: "Complete", pct: 100 },
];

const STATUS_ORDER = STAGES.map((s) => s.status);

function stageIndex(status: JobStatus): number {
  return STATUS_ORDER.indexOf(status);
}

export default function JobPage({ params }: { params: { id: string } }) {
  const { job, error } = useJobStream(params.id);
  const router = useRouter();

  useEffect(() => {
    if (job?.status === "completed" && job.report_id) {
      const timer = setTimeout(() => {
        router.push(`/reports/${job.report_id}`);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [job?.status, job?.report_id, router]);

  const currentIdx = job ? stageIndex(job.status) : -1;
  const isFailed = job?.status === "failed";

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-900 mb-2">Analysis in Progress</h1>
      <p className="text-slate-500 text-sm mb-8">
        {job?.progress_message ?? "Starting up..."}
      </p>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {isFailed && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          <strong>Analysis failed:</strong> {job?.error_message ?? "Unknown error"}
        </div>
      )}

      {/* Progress bar */}
      <div className="mb-8">
        <div className="flex justify-between text-xs text-slate-500 mb-1">
          <span>{isFailed ? "Failed" : `${job?.progress_pct ?? 0}%`}</span>
          {job?.token_cost && (
            <span>${job.token_cost.estimated_usd.toFixed(4)} LLM cost</span>
          )}
        </div>
        <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isFailed ? "bg-red-400" : "bg-accent-500"
            }`}
            style={{ width: `${job?.progress_pct ?? 0}%` }}
          />
        </div>
      </div>

      {/* Stage stepper */}
      <div className="space-y-3">
        {STAGES.filter((s) => s.status !== "failed").map((stage, i) => {
          const isDone = currentIdx > i;
          const isActive = currentIdx === i;
          const isPending = currentIdx < i;

          return (
            <div key={stage.status} className="flex items-center gap-4">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0
                  ${isDone ? "bg-green-500 text-white" :
                    isActive ? "bg-accent-500 text-white animate-pulse" :
                    "bg-slate-200 text-slate-400"}`}
              >
                {isDone ? "✓" : i + 1}
              </div>
              <div>
                <div
                  className={`text-sm font-medium ${
                    isActive ? "text-slate-900" :
                    isDone ? "text-green-700" : "text-slate-400"
                  }`}
                >
                  {stage.label}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {job?.status === "completed" && (
        <div className="mt-8 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
          ✅ Report ready — redirecting...
        </div>
      )}
    </div>
  );
}
