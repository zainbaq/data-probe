import { auth } from "@clerk/nextjs/server";
import { notFound } from "next/navigation";
import { getReport, buildDownloadUrl } from "@/lib/api";
import { ReportMarkdown } from "@/components/reports/ReportMarkdown";
import { DownloadButton } from "@/components/reports/DownloadButton";

function HealthGauge({ score }: { score: number }) {
  const color =
    score >= 80 ? "#22c55e" : score >= 50 ? "#f59e0b" : "#ef4444";
  const filled = Math.round(score / 10);
  const bar = "█".repeat(filled) + "░".repeat(10 - filled);
  const label = score >= 80 ? "Good" : score >= 50 ? "Fair" : "Poor";

  return (
    <div className="flex items-center gap-4 p-5 bg-white rounded-xl border border-slate-200">
      <div className="text-4xl font-bold" style={{ color }}>
        {score}
      </div>
      <div>
        <div className="text-xs text-slate-500 mb-1">Data Health Score</div>
        <div className="font-mono text-sm" style={{ color }}>
          {bar}
        </div>
        <div className="text-xs text-slate-400 mt-1">{label}</div>
      </div>
    </div>
  );
}

export default async function ReportPage({
  params,
}: {
  params: { id: string };
}) {
  const { getToken } = await auth();
  const token = await getToken();

  if (!token) notFound();

  let report;
  try {
    report = await getReport(token, params.id);
  } catch {
    notFound();
  }

  const downloadUrl = report.has_cleaned_file
    ? buildDownloadUrl(report.id, token)
    : null;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-8 gap-6">
        <div className="flex-1">
          <HealthGauge score={report.health_score} />
        </div>
        {downloadUrl && (
          <div className="shrink-0 pt-1">
            <DownloadButton url={downloadUrl} />
          </div>
        )}
      </div>

      <div className="prose prose-slate max-w-none bg-white rounded-xl border border-slate-200 p-8">
        <ReportMarkdown markdown={report.markdown} />
      </div>
    </div>
  );
}
