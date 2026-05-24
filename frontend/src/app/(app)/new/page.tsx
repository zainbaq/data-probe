"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useClerkToken } from "@/hooks/useClerkToken";
import { createDBSource, uploadFileSource, createJob } from "@/lib/api";
import type { SourceConnection } from "@/lib/types";

type Step = "source-type" | "configure" | "confirm";
type DBSourceType = "postgres" | "mysql" | "mssql";
type SourceType = DBSourceType | "file";

const DB_OPTIONS: {
  type: DBSourceType;
  emoji: string;
  label: string;
  subtitle: string;
  placeholder: string;
}[] = [
  {
    type: "postgres",
    emoji: "🐘",
    label: "PostgreSQL",
    subtitle: "Read-only connection via DSN",
    placeholder: "postgresql://readonly_user:pass@host:5432/mydb",
  },
  {
    type: "mysql",
    emoji: "🐬",
    label: "MySQL",
    subtitle: "Read-only connection via DSN",
    placeholder: "mysql://readonly_user:pass@host:3306/mydb",
  },
  {
    type: "mssql",
    emoji: "🪟",
    label: "SQL Server",
    subtitle: "Read-only connection via DSN",
    placeholder: "mssql://readonly_user:pass@host:1433/mydb",
  },
];

export default function NewAnalysisPage() {
  const router = useRouter();
  const { getToken } = useClerkToken();
  const [step, setStep] = useState<Step>("source-type");
  const [sourceType, setSourceType] = useState<SourceType>("postgres");
  const [source, setSource] = useState<SourceConnection | null>(null);

  // DB form state
  const [dbName, setDbName] = useState("");
  const [dbDsn, setDbDsn] = useState("");

  // File form state
  const [file, setFile] = useState<File | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDbType = (t: SourceType): t is DBSourceType => t !== "file";

  const currentDbOption = DB_OPTIONS.find((o) => o.type === sourceType);

  async function handleConfigure() {
    setError(null);
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");

      let conn: SourceConnection;
      if (isDbType(sourceType)) {
        conn = await createDBSource(token, dbName, dbDsn, sourceType);
      } else {
        if (!file) throw new Error("No file selected");
        conn = await uploadFileSource(token, file);
      }
      setSource(conn);
      setStep("confirm");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleRunAnalysis() {
    if (!source) return;
    setError(null);
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const job = await createJob(token, source.id);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-900 mb-2">New Analysis</h1>
      <p className="text-slate-500 text-sm mb-8">
        Connect a database or upload a CSV / Excel file to analyze.
      </p>

      {/* Step indicator */}
      <div className="flex items-center gap-3 mb-10 text-sm">
        {(["source-type", "configure", "confirm"] as Step[]).map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold
                ${step === s ? "bg-accent-500 text-white" :
                  i < ["source-type", "configure", "confirm"].indexOf(step)
                  ? "bg-green-500 text-white" : "bg-slate-200 text-slate-500"}`}
            >
              {i + 1}
            </div>
            <span className={step === s ? "font-medium text-slate-900" : "text-slate-400"}>
              {s === "source-type" ? "Source" : s === "configure" ? "Configure" : "Confirm"}
            </span>
            {i < 2 && <span className="text-slate-300">→</span>}
          </div>
        ))}
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Step 1: Source type */}
      {step === "source-type" && (
        <div className="space-y-4">
          <h2 className="font-semibold text-slate-800">Choose your data source</h2>
          <div className="grid grid-cols-2 gap-4">
            {DB_OPTIONS.map((opt) => (
              <button
                key={opt.type}
                onClick={() => { setSourceType(opt.type); setStep("configure"); }}
                className="p-6 bg-white border-2 border-slate-200 rounded-xl hover:border-accent-400 hover:bg-accent-50 transition-all text-left"
              >
                <div className="text-3xl mb-3">{opt.emoji}</div>
                <div className="font-semibold text-slate-800">{opt.label}</div>
                <div className="text-sm text-slate-500 mt-1">{opt.subtitle}</div>
              </button>
            ))}
            <button
              onClick={() => { setSourceType("file"); setStep("configure"); }}
              className="p-6 bg-white border-2 border-slate-200 rounded-xl hover:border-accent-400 hover:bg-accent-50 transition-all text-left"
            >
              <div className="text-3xl mb-3">📊</div>
              <div className="font-semibold text-slate-800">CSV / Excel File</div>
              <div className="text-sm text-slate-500 mt-1">Up to 250 MB, single sheet XLSX</div>
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Configure */}
      {step === "configure" && (
        <div className="space-y-6">
          <h2 className="font-semibold text-slate-800">
            {isDbType(sourceType)
              ? `Connect ${currentDbOption?.label}`
              : "Upload your file"}
          </h2>

          {isDbType(sourceType) ? (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Connection name</label>
                <input
                  type="text"
                  value={dbName}
                  onChange={(e) => setDbName(e.target.value)}
                  placeholder="My Production DB"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-400"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Connection DSN</label>
                <input
                  type="text"
                  value={dbDsn}
                  onChange={(e) => setDbDsn(e.target.value)}
                  placeholder={currentDbOption?.placeholder}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent-400"
                />
                <p className="text-xs text-slate-400 mt-1">
                  Use a read-only role.
                </p>
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">File</label>
              <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-accent-400 transition-colors">
                {file ? (
                  <div>
                    <div className="text-2xl mb-2">📄</div>
                    <div className="font-medium text-slate-700">{file.name}</div>
                    <div className="text-sm text-slate-400 mt-1">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </div>
                    <button
                      onClick={() => setFile(null)}
                      className="mt-3 text-xs text-red-500 underline"
                    >
                      Remove
                    </button>
                  </div>
                ) : (
                  <label className="cursor-pointer">
                    <div className="text-3xl mb-2">📂</div>
                    <div className="text-sm font-medium text-slate-600">
                      Drop a file here or <span className="text-accent-500 underline">browse</span>
                    </div>
                    <div className="text-xs text-slate-400 mt-1">CSV, XLSX — up to 250 MB</div>
                    <input
                      type="file"
                      accept=".csv,.xlsx,.xls"
                      className="hidden"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    />
                  </label>
                )}
              </div>
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => setStep("source-type")}
              className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900 transition-colors"
            >
              ← Back
            </button>
            <button
              onClick={handleConfigure}
              disabled={loading || (isDbType(sourceType) ? (!dbName || !dbDsn) : !file)}
              className="flex-1 bg-accent-500 hover:bg-accent-600 disabled:opacity-50 text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors"
            >
              {loading ? "Saving..." : "Continue →"}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Confirm */}
      {step === "confirm" && source && (
        <div className="space-y-6">
          <h2 className="font-semibold text-slate-800">Ready to analyze</h2>
          <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Source</span>
              <span className="font-medium text-slate-800">{source.name}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Type</span>
              <span className="font-medium text-slate-800 uppercase">{source.source_type}</span>
            </div>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
            <strong>What happens next:</strong> DataProbe profiles your data, runs AI analysis
            over statistics (never raw rows), validates every SQL fix, and generates a report.
            This typically takes 1–5 minutes.
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => setStep("configure")}
              className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900 transition-colors"
            >
              ← Back
            </button>
            <button
              onClick={handleRunAnalysis}
              disabled={loading}
              className="flex-1 bg-accent-500 hover:bg-accent-600 disabled:opacity-50 text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors"
            >
              {loading ? "Starting..." : "Run Analysis"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
