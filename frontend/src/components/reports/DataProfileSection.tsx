"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { ColumnProfile } from "@/lib/types";

const FLAG_META: Record<string, { label: string; color: string }> = {
  all_null:           { label: "All Null",        color: "bg-red-100 text-red-700 border-red-200" },
  high_null_critical: { label: "High Nulls",      color: "bg-red-100 text-red-700 border-red-200" },
  high_null:          { label: "Some Nulls",      color: "bg-amber-100 text-amber-700 border-amber-200" },
  near_unique:        { label: "Near-Unique",     color: "bg-indigo-100 text-indigo-700 border-indigo-200" },
  possible_enum:      { label: "Possible Enum",   color: "bg-violet-100 text-violet-700 border-violet-200" },
  possible_boolean:   { label: "Possible Bool",   color: "bg-blue-100 text-blue-700 border-blue-200" },
  type_mismatch:      { label: "Type Mismatch",   color: "bg-orange-100 text-orange-700 border-orange-200" },
  mixed_types:        { label: "Mixed Types",     color: "bg-orange-100 text-orange-700 border-orange-200" },
};

const TYPE_COLOR: Record<string, string> = {
  integer:   "bg-sky-100 text-sky-700",
  float:     "bg-sky-100 text-sky-700",
  numeric:   "bg-sky-100 text-sky-700",
  string:    "bg-slate-100 text-slate-600",
  date:      "bg-teal-100 text-teal-700",
  timestamp: "bg-teal-100 text-teal-700",
  boolean:   "bg-purple-100 text-purple-700",
};

function NullBar({ pct }: { pct: number }) {
  const filled = Math.round(pct * 100);
  const color =
    pct >= 0.5 ? "bg-red-400" : pct >= 0.2 ? "bg-amber-400" : "bg-emerald-400";
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${filled}%` }} />
      </div>
      <span className="text-xs tabular-nums text-slate-500 shrink-0 w-10 text-right">
        {(pct * 100).toFixed(1)}%
      </span>
    </div>
  );
}

function TypeBadge({ type }: { type: string }) {
  const base = type.toLowerCase();
  const colorClass = TYPE_COLOR[base] ?? "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-block text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded ${colorClass}`}>
      {type}
    </span>
  );
}

function TableProfile({ table, columns }: { table: string; columns: ColumnProfile[] }) {
  const [open, setOpen] = useState(true);
  const rowCount = columns[0]?.row_count ?? 0;

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-5 py-3.5 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
      >
        {open ? (
          <ChevronDown size={15} className="text-slate-400 shrink-0" />
        ) : (
          <ChevronRight size={15} className="text-slate-400 shrink-0" />
        )}
        <span className="font-semibold text-slate-800 font-mono text-sm">{table}</span>
        <span className="ml-auto text-xs text-slate-400">
          {rowCount.toLocaleString()} rows · {columns.length} columns
        </span>
      </button>

      {open && (
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr className="bg-slate-50 border-t border-slate-200">
                <th className="px-4 py-2 text-left font-semibold text-slate-500 uppercase tracking-wide w-40">Column</th>
                <th className="px-4 py-2 text-left font-semibold text-slate-500 uppercase tracking-wide w-24">Type</th>
                <th className="px-4 py-2 text-left font-semibold text-slate-500 uppercase tracking-wide w-40">Null %</th>
                <th className="px-4 py-2 text-left font-semibold text-slate-500 uppercase tracking-wide w-28">Distinct</th>
                <th className="px-4 py-2 text-left font-semibold text-slate-500 uppercase tracking-wide w-44">Min / Max</th>
                <th className="px-4 py-2 text-left font-semibold text-slate-500 uppercase tracking-wide">Top Values</th>
                <th className="px-4 py-2 text-left font-semibold text-slate-500 uppercase tracking-wide w-48">Flags</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {columns.map((col) => (
                <tr key={col.column} className="hover:bg-slate-50 transition-colors">
                  {/* Column name */}
                  <td className="px-4 py-2.5 font-mono font-medium text-slate-800 whitespace-nowrap">
                    {col.column}
                  </td>
                  {/* Type */}
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <TypeBadge type={col.inferred_type} />
                  </td>
                  {/* Null bar */}
                  <td className="px-4 py-2.5 w-40">
                    <NullBar pct={col.null_pct} />
                  </td>
                  {/* Distinct */}
                  <td className="px-4 py-2.5 whitespace-nowrap tabular-nums text-slate-600">
                    {col.distinct_count.toLocaleString()}
                    <span className="text-slate-400 ml-1">
                      ({(col.cardinality_ratio * 100).toFixed(0)}%)
                    </span>
                  </td>
                  {/* Min / Max */}
                  <td className="px-4 py-2.5 whitespace-nowrap text-slate-600">
                    {col.min_val != null || col.max_val != null ? (
                      <span className="font-mono">
                        {String(col.min_val ?? "—")}
                        <span className="text-slate-300 mx-1">→</span>
                        {String(col.max_val ?? "—")}
                      </span>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                  {/* Top values */}
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {col.top_values.slice(0, 5).map((tv, i) => (
                        <span
                          key={i}
                          className="inline-block font-mono text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded truncate max-w-[120px]"
                          title={`${tv.value} (${tv.count})`}
                        >
                          {tv.value === null ? <em className="text-slate-400">null</em> : String(tv.value)}
                        </span>
                      ))}
                    </div>
                  </td>
                  {/* Pattern flags */}
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {col.pattern_flags.map((flag) => {
                        const meta = FLAG_META[flag];
                        return meta ? (
                          <span
                            key={flag}
                            className={`inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded border ${meta.color}`}
                          >
                            {meta.label}
                          </span>
                        ) : null;
                      })}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function DataProfileSection({
  profileJson,
}: {
  profileJson: Record<string, ColumnProfile[]>;
}) {
  const tables = Object.entries(profileJson);
  if (tables.length === 0) return null;

  return (
    <div className="mt-8">
      <h2 className="text-lg font-semibold text-slate-800 mb-4">Data Profile</h2>
      <div className="space-y-4">
        {tables.map(([table, columns]) => (
          <TableProfile key={table} table={table} columns={columns} />
        ))}
      </div>
    </div>
  );
}
