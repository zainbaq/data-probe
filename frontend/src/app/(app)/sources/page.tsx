import { auth } from "@clerk/nextjs/server";
import Link from "next/link";
import { listSources } from "@/lib/api";
import type { SourceConnection } from "@/lib/types";
import { PlusCircle, Database, FileText } from "lucide-react";

export default async function SourcesPage() {
  const { getToken } = await auth();
  const token = await getToken();
  let sources: SourceConnection[] = [];
  try {
    if (token) sources = await listSources(token);
  } catch {
    // empty
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Sources</h1>
          <p className="text-slate-500 text-sm mt-1">{sources.length} connected source{sources.length !== 1 ? "s" : ""}</p>
        </div>
        <Link
          href="/new"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-4 py-2.5 rounded-lg text-sm transition-colors shadow-sm"
        >
          <PlusCircle size={16} />
          Add Source
        </Link>
      </div>

      {sources.length === 0 ? (
        <div className="text-center py-24 bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="w-14 h-14 rounded-full bg-indigo-50 flex items-center justify-center mx-auto mb-4">
            <Database size={24} className="text-indigo-400" />
          </div>
          <p className="text-slate-600 text-sm font-medium mb-1">No sources yet</p>
          <p className="text-slate-400 text-sm">Add a database connection or upload a file to get started.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {sources.map((s) => (
            <div
              key={s.id}
              className="flex items-center gap-4 p-4 bg-white rounded-xl border border-slate-200 hover:border-slate-300 transition-colors"
            >
              <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center shrink-0">
                {s.source_type === "postgres" ? (
                  <Database size={18} className="text-slate-500" />
                ) : (
                  <FileText size={18} className="text-slate-500" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-slate-900 text-sm">{s.name}</div>
                <div className="text-xs text-slate-400 mt-0.5 uppercase tracking-wide font-medium">
                  {s.source_type}
                </div>
              </div>
              <span className="text-xs text-slate-400 tabular-nums">
                {new Date(s.created_at).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
