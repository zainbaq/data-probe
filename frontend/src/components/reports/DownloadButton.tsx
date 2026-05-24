"use client";

export function DownloadButton({ url }: { url: string }) {
  return (
    <a
      href={url}
      download
      className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors"
    >
      ⬇ Download Cleaned File
    </a>
  );
}
