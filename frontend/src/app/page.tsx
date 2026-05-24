import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

export default async function RootPage() {
  const { userId } = await auth();
  if (userId) {
    redirect("/dashboard");
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-slate-900 to-slate-800 text-white p-8">
      <div className="max-w-2xl w-full text-center space-y-8">
        <div>
          <h1 className="text-5xl font-bold tracking-tight mb-4">
            DataProbe
          </h1>
          <p className="text-xl text-slate-300 leading-relaxed">
            Connect your PostgreSQL database or upload a CSV/Excel file.
            Get a trusted data quality report with actionable SQL fixes in minutes.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-6 text-sm">
          {[
            { icon: "🔍", title: "Deterministic Profiling", desc: "Null rates, cardinality, type mismatches — computed from SQL, not guessed" },
            { icon: "🤖", title: "AI-Powered Analysis", desc: "Claude reasons over statistics, never raw rows, for privacy and precision" },
            { icon: "✅", title: "Validated SQL Fixes", desc: "Every suggested fix is dry-run validated before it reaches your report" },
          ].map((f) => (
            <div key={f.title} className="bg-white/10 rounded-xl p-5 text-left">
              <div className="text-3xl mb-3">{f.icon}</div>
              <div className="font-semibold mb-1">{f.title}</div>
              <div className="text-slate-400 text-xs leading-relaxed">{f.desc}</div>
            </div>
          ))}
        </div>

        <div className="flex gap-4 justify-center">
          <a
            href="/sign-up"
            className="bg-accent-500 hover:bg-accent-600 text-white font-semibold px-8 py-3 rounded-lg transition-colors"
          >
            Get Started Free
          </a>
          <a
            href="/sign-in"
            className="border border-white/20 hover:bg-white/10 text-white font-semibold px-8 py-3 rounded-lg transition-colors"
          >
            Sign In
          </a>
        </div>

        <p className="text-slate-500 text-xs">
          Read-only access only. Your source database is never modified.
        </p>
      </div>
    </main>
  );
}
