import { auth } from "@clerk/nextjs/server";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getReport, buildDownloadUrl } from "@/lib/api";
import { ReportMarkdown } from "@/components/reports/ReportMarkdown";
import { DownloadButton } from "@/components/reports/DownloadButton";
import { ChevronLeft } from "lucide-react";

function HealthGauge({ score }: { score: number }) {
  const isGood = score >= 80;
  const isFair = score >= 50;
  const color = isGood ? "#22c55e" : isFair ? "#f59e0b" : "#ef4444";
  const bgColor = isGood ? "bg-green-50 border-green-200" : isFair ? "bg-yellow-50 border-yellow-200" : "bg-red-50 border-red-200";
  const label = isGood ? "Good" : isFair ? "Fair" : "Poor";
  const labelColor = isGood ? "text-green-700" : isFair ? "text-yellow-700" : "text-red-700";
  const segments = 10;
  const filled = Math.round(score / 10);

  return (
    <div className={`flex items-center gap-5 p-5 rounded-xl border ${bgColor}`}>
      <div className="text-5xl font-bold tabular-nums leading-none" style={{ color }}>
        {score}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Data Health Score</span>
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${labelColor} ${bgColor}`}>{label}</span>
        </div>
        <div className="flex gap-1">
          {Array.from({ length: segments }, (_, i) => (
            <div
              key={i}
              className="flex-1 h-2.5 rounded-full transition-all"
              style={{ backgroundColor: i < filled ? color : "#e2e8f0" }}
            />
          ))}
        </div>
        <div className="text-xs text-slate-400 mt-1.5">{score} / 100</div>
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
    <div className="p-8 max-w-4xl mx-auto">
      {/* Back breadcrumb */}
      <Link
        href="/reports"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 mb-6 transition-colors"
      >
        <ChevronLeft size={15} />
        Reports
      </Link>

      {/* Summary card */}
      <div className="flex items-start gap-4 mb-8">
        <div className="flex-1">
          <HealthGauge score={report.health_score} />
        </div>
        {downloadUrl && (
          <div className="shrink-0">
            <DownloadButton url={downloadUrl} />
          </div>
        )}
      </div>

      {/* Report content */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8">
        <ReportMarkdown markdown={report.markdown} />
      </div>
    </div>
  );
}
