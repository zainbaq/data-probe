import { auth } from "@clerk/nextjs/server";
import Link from "next/link";
import { listSources } from "@/lib/api";
import type { SourceConnection } from "@/lib/types";

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
        <h1 className="text-2xl font-bold text-slate-900">Sources</h1>
        <Link
          href="/new"
          className="bg-accent-500 hover:bg-accent-600 text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors"
        >
          + Add Source
        </Link>
      </div>

      {sources.length === 0 ? (
        <div className="text-center py-24 text-slate-500">
          No sources yet. Add a database connection or upload a file.
        </div>
      ) : (
        <div className="space-y-3">
          {sources.map((s) => (
            <div
              key={s.id}
              className="flex items-center justify-between p-5 bg-white rounded-xl border border-slate-200"
            >
              <div className="flex items-center gap-4">
                <div className="text-2xl">{s.source_type === "postgres" ? "🐘" : "📊"}</div>
                <div>
                  <div className="font-medium text-slate-900">{s.name}</div>
                  <div className="text-xs text-slate-400 mt-0.5 uppercase tracking-wide">
                    {s.source_type}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-400">
                  {new Date(s.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
