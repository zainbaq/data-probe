import { auth } from "@clerk/nextjs/server";
import Link from "next/link";
import { listReports } from "@/lib/api";
import type { ReportListItem } from "@/lib/types";

function HealthBadge({ score }: { score: number }) {
  const color =
    score >= 80
      ? "bg-green-100 text-green-800"
      : score >= 50
      ? "bg-yellow-100 text-yellow-800"
      : "bg-red-100 text-red-800";
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {score}/100
    </span>
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
          className="bg-accent-500 hover:bg-accent-600 text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors"
        >
          + New Analysis
        </Link>
      </div>

      {reports.length === 0 ? (
        <div className="text-center py-24 bg-white rounded-xl border border-slate-200">
          <div className="text-5xl mb-4">🔍</div>
          <h2 className="text-lg font-semibold text-slate-700 mb-2">No reports yet</h2>
          <p className="text-slate-500 text-sm mb-6">
            Connect a database or upload a file to generate your first data quality report.
          </p>
          <Link
            href="/new"
            className="bg-accent-500 hover:bg-accent-600 text-white font-semibold px-6 py-2.5 rounded-lg text-sm transition-colors"
          >
            Run Your First Analysis
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map((r) => (
            <Link
              key={r.id}
              href={`/reports/${r.id}`}
              className="flex items-center justify-between p-5 bg-white rounded-xl border border-slate-200 hover:border-accent-300 hover:shadow-sm transition-all"
            >
              <div className="flex items-center gap-4">
                <HealthBadge score={r.health_score} />
                <div>
                  <div className="font-medium text-slate-900">{r.source_name ?? "Unnamed source"}</div>
                  <div className="text-sm text-slate-500 mt-0.5 line-clamp-1">{r.executive_summary}</div>
                </div>
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-400 shrink-0 ml-4">
                <span className="uppercase tracking-wide">{r.source_type}</span>
                <span>{new Date(r.created_at).toLocaleDateString()}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
