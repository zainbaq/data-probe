import { auth } from "@clerk/nextjs/server";
import Link from "next/link";
import { listReports } from "@/lib/api";
import type { ReportListItem } from "@/lib/types";
import { PlusCircle, Database, FileText } from "lucide-react";

function HealthScore({ score }: { score: number }) {
  const color =
    score >= 80 ? "text-green-600" : score >= 50 ? "text-yellow-600" : "text-red-600";
  const bg =
    score >= 80 ? "bg-green-50" : score >= 50 ? "bg-yellow-50" : "bg-red-50";
  return (
    <span className={`inline-block tabular-nums font-bold text-sm px-2 py-0.5 rounded ${bg} ${color}`}>
      {score}
    </span>
  );
}

function SourceTypeIcon({ type }: { type: string }) {
  return type === "postgres" ? (
    <span className="inline-flex items-center gap-1.5 text-slate-500 text-xs uppercase tracking-wide font-medium">
      <Database size={13} />
      postgres
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-slate-500 text-xs uppercase tracking-wide font-medium">
      <FileText size={13} />
      file
    </span>
  );
}

export default async function ReportsPage() {
  const { getToken } = await auth();
  const token = await getToken();
  let reports: ReportListItem[] = [];
  try {
    if (token) reports = await listReports(token);
  } catch {
    // empty
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Reports</h1>
          <p className="text-slate-500 text-sm mt-1">{reports.length} report{reports.length !== 1 ? "s" : ""}</p>
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
        <div className="text-center py-24 bg-white rounded-xl border border-slate-200 shadow-sm text-slate-500 text-sm">
          No reports yet. Run your first analysis to get started.
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <th className="text-left px-5 py-3">Source</th>
                <th className="text-left px-5 py-3">Type</th>
                <th className="text-center px-5 py-3">Health</th>
                <th className="text-left px-5 py-3">Summary</th>
                <th className="text-right px-5 py-3">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {reports.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-4">
                    <Link href={`/reports/${r.id}`} className="font-medium text-indigo-600 hover:text-indigo-800 hover:underline">
                      {r.source_name ?? "—"}
                    </Link>
                  </td>
                  <td className="px-5 py-4">
                    <SourceTypeIcon type={r.source_type ?? ""} />
                  </td>
                  <td className="px-5 py-4 text-center">
                    <HealthScore score={r.health_score} />
                  </td>
                  <td className="px-5 py-4 text-slate-500 text-xs max-w-xs truncate">
                    {r.executive_summary}
                  </td>
                  <td className="px-5 py-4 text-right text-slate-400 text-xs tabular-nums">
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
