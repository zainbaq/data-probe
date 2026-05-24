import { auth } from "@clerk/nextjs/server";
import Link from "next/link";
import { listReports } from "@/lib/api";
import type { ReportListItem } from "@/lib/types";
import { PlusCircle, Database, FileText, ChevronRight } from "lucide-react";

function HealthBadge({ score }: { score: number }) {
  const style =
    score >= 80
      ? "bg-green-100 text-green-800 ring-1 ring-green-200"
      : score >= 50
      ? "bg-yellow-100 text-yellow-800 ring-1 ring-yellow-200"
      : "bg-red-100 text-red-800 ring-1 ring-red-200";
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold tabular-nums ${style}`}>
      {score}
    </span>
  );
}

function SourceIcon({ type }: { type: string }) {
  return type === "postgres" ? (
    <Database size={16} className="text-slate-400" />
  ) : (
    <FileText size={16} className="text-slate-400" />
  );
}

export default async function DashboardPage() {
  const { getToken } = await auth();
  const token = await getToken();
  let reports: ReportListItem[] = [];
  try {
    if (token) reports = await listReports(token);
  } catch {
    // Show empty state
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-slate-500 text-sm mt-1">Your recent data quality reports</p>
        </div>
        <Link
          href="/new"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-4 py-2.5 rounded-lg text-sm transition-colors shadow-sm"
        >
          <PlusCircle size={16} />
          New Analysis
        </Link>
      </div>

      {reports.length === 0 ? (
        <div className="text-center py-24 bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="w-14 h-14 rounded-full bg-indigo-50 flex items-center justify-center mx-auto mb-4">
            <FileText size={24} className="text-indigo-400" />
          </div>
          <h2 className="text-lg font-semibold text-slate-700 mb-2">No reports yet</h2>
          <p className="text-slate-500 text-sm mb-6 max-w-xs mx-auto">
            Connect a database or upload a file to generate your first data quality report.
          </p>
          <Link
            href="/new"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors"
          >
            <PlusCircle size={16} />
            Run Your First Analysis
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {reports.map((r) => (
            <Link
              key={r.id}
              href={`/reports/${r.id}`}
              className="flex items-center gap-4 p-4 bg-white rounded-xl border border-slate-200 hover:border-indigo-300 hover:shadow-sm transition-all group"
            >
              <HealthBadge score={r.health_score} />
              <SourceIcon type={r.source_type ?? ""} />
              <div className="flex-1 min-w-0">
                <div className="font-medium text-slate-900 text-sm">{r.source_name ?? "Unnamed source"}</div>
                <div className="text-xs text-slate-500 mt-0.5 truncate">{r.executive_summary}</div>
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-400 shrink-0">
                <span className="uppercase tracking-wide font-medium">{r.source_type ?? "—"}</span>
                <span>{new Date(r.created_at).toLocaleDateString()}</span>
                <ChevronRight size={14} className="text-slate-300 group-hover:text-indigo-400 transition-colors" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
