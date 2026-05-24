"use client";
import { Download } from "lucide-react";

export function DownloadButton({ url }: { url: string }) {
  return (
    <a
      href={url}
      download
      className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-4 py-2.5 rounded-lg text-sm transition-colors shadow-sm"
    >
      <Download size={15} />
      Download Cleaned File
    </a>
  );
}
