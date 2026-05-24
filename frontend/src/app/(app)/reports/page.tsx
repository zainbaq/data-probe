import { auth } from "@clerk/nextjs/server";
import Link from "next/link";
import { listReports } from "@/lib/api";
import type { ReportListItem } from "@/lib/types";

function HealthScore({ score }: { score: number }) {
  const color =
    score >= 80 ? "text-green-600" : score >= 50 ? "text-yellow-600" : "text-red-600";
  return <span className={`font-bold text-lg ${color}`}>{score}</span>;
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
        <h1 className="text-2xl font-bold text-slate-900">Reports</h1>
        <Link
          href="/new"
          className="bg-accent-500 hover:bg-accent-600 text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors"
        >
          + New Analysis
        </Link>
      </div>

      {reports.length === 0 ? (
        <div className="text-center py-24 text-slate-500">No reports yet.</div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
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
            <tbody>
              {reports.map((r) => (
                <tr
                  key={r.id}
                  className="border-b border-slate-100 hover:bg-slate-50 transition-colors"
                >
                  <td className="px-5 py-4">
                    <Link href={`/reports/${r.id}`} className="font-medium text-accent-600 hover:underline">
                      {r.source_name ?? "—"}
                    </Link>
                  </td>
                  <td className="px-5 py-4 uppercase text-slate-500 text-xs">{r.source_type}</td>
                  <td className="px-5 py-4 text-center">
                    <HealthScore score={r.health_score} />
                  </td>
                  <td className="px-5 py-4 text-slate-600 line-clamp-1 max-w-xs">
                    {r.executive_summary}
                  </td>
                  <td className="px-5 py-4 text-right text-slate-400 text-xs">
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
