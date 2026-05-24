"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function ReportMarkdown({ markdown }: { markdown: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ node, className, children, ...props }) {
          const isBlock = className?.startsWith("language-");
          return isBlock ? (
            <pre className="bg-slate-900 text-slate-100 rounded-lg p-4 overflow-x-auto text-xs font-mono">
              <code {...props}>{children}</code>
            </pre>
          ) : (
            <code
              className="bg-slate-100 text-slate-800 px-1.5 py-0.5 rounded text-xs font-mono"
              {...props}
            >
              {children}
            </code>
          );
        },
        table({ children }) {
          return (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">{children}</table>
            </div>
          );
        },
      }}
    >
      {markdown}
    </ReactMarkdown>
  );
}
