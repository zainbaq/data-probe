"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ComponentPropsWithoutRef } from "react";

type CodeProps = ComponentPropsWithoutRef<"code"> & { inline?: boolean };

export function ReportMarkdown({ markdown }: { markdown: string }) {
  return (
    <div className="report-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1({ children }) {
            return (
              <h1 className="text-2xl font-bold text-slate-900 mt-8 mb-4 pb-3 border-b border-slate-200 first:mt-0">
                {children}
              </h1>
            );
          },
          h2({ children }) {
            return (
              <h2 className="text-xl font-semibold text-slate-800 mt-8 mb-3 pb-2 border-b border-slate-100 first:mt-0">
                {children}
              </h2>
            );
          },
          h3({ children }) {
            return (
              <h3 className="text-base font-semibold text-slate-800 mt-6 mb-2">
                {children}
              </h3>
            );
          },
          h4({ children }) {
            return (
              <h4 className="text-sm font-semibold text-slate-700 mt-4 mb-1 uppercase tracking-wide">
                {children}
              </h4>
            );
          },
          p({ children }) {
            return (
              <p className="text-slate-700 leading-relaxed mb-4 last:mb-0">
                {children}
              </p>
            );
          },
          ul({ children }) {
            return (
              <ul className="mb-4 space-y-1.5 pl-5 list-disc marker:text-slate-400">
                {children}
              </ul>
            );
          },
          ol({ children }) {
            return (
              <ol className="mb-4 space-y-1.5 pl-5 list-decimal marker:text-slate-400">
                {children}
              </ol>
            );
          },
          li({ children }) {
            return (
              <li className="text-slate-700 leading-relaxed">
                {children}
              </li>
            );
          },
          blockquote({ children }) {
            return (
              <blockquote className="my-4 pl-4 border-l-4 border-amber-400 bg-amber-50 rounded-r-lg py-3 pr-4 text-amber-900 text-sm italic">
                {children}
              </blockquote>
            );
          },
          strong({ children }) {
            return <strong className="font-semibold text-slate-900">{children}</strong>;
          },
          a({ href, children }) {
            return (
              <a
                href={href}
                className="text-indigo-600 underline underline-offset-2 hover:text-indigo-800"
                target="_blank"
                rel="noopener noreferrer"
              >
                {children}
              </a>
            );
          },
          hr() {
            return <hr className="my-6 border-slate-200" />;
          },
          code({ className, children, inline, ...props }: CodeProps) {
            const isBlock = !inline && className?.startsWith("language-");
            if (isBlock) {
              return (
                <pre className="bg-slate-900 text-slate-100 rounded-xl p-4 overflow-x-auto text-xs font-mono my-4 shadow-inner">
                  <code className={className} {...props}>{children}</code>
                </pre>
              );
            }
            const text = String(children);
            return (
              <code
                className="bg-indigo-50 text-indigo-700 border border-indigo-100 px-1.5 py-0.5 rounded text-xs font-mono"
                {...props}
              >
                {text}
              </code>
            );
          },
          table({ children }) {
            return (
              <div className="overflow-x-auto my-4 rounded-lg border border-slate-200">
                <table className="min-w-full divide-y divide-slate-200 text-sm">{children}</table>
              </div>
            );
          },
          thead({ children }) {
            return <thead className="bg-slate-50">{children}</thead>;
          },
          th({ children }) {
            return (
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase tracking-wide">
                {children}
              </th>
            );
          },
          td({ children }) {
            return <td className="px-4 py-3 text-slate-700 border-t border-slate-100">{children}</td>;
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
