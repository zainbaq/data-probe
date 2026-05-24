export type SourceType = "postgres" | "csv" | "xlsx";

export interface SourceConnection {
  id: string;
  name: string;
  source_type: SourceType;
  has_file: boolean;
  created_at: string;
}

export type JobStatus =
  | "queued"
  | "profiling"
  | "inferring"
  | "analyzing"
  | "validating"
  | "assembling"
  | "completed"
  | "failed";

export interface TokenCost {
  input_tokens: number;
  output_tokens: number;
  estimated_usd: number;
}

export interface Job {
  id: string;
  source_connection_id: string;
  status: JobStatus;
  progress_pct: number;
  progress_message: string | null;
  token_cost: TokenCost | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  report_id: string | null;
}

export type Severity = "critical" | "high" | "medium" | "low";
export type FixRisk = "green" | "yellow" | "red";

export interface Finding {
  code: string;
  table: string;
  column: string | null;
  tables?: string[];
  severity: Severity;
  fix_risk: FixRisk;
  description: string;
  evidence: Record<string, unknown>;
  sql_fix: string | null;
  investigation_query: string | null;
  dry_run_result: {
    passed: boolean;
    estimated_rows_affected: number | null;
    error: string | null;
    disposition: string;
  } | null;
}

export interface Report {
  id: string;
  job_id: string;
  health_score: number;
  executive_summary: string;
  markdown: string;
  findings_json: Finding[];
  has_cleaned_file: boolean;
  created_at: string;
}

export interface ReportListItem {
  id: string;
  job_id: string;
  health_score: number;
  executive_summary: string;
  source_name: string | null;
  source_type: string | null;
  has_cleaned_file: boolean;
  created_at: string;
}
