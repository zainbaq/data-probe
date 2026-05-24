import type { Job, Report, ReportListItem, SourceConnection } from "./types";

// Server-side (Next.js SSR): use the internal Docker DNS name so requests
// stay inside the Docker network instead of bouncing through the host.
// Client-side (browser): always use the public-facing URL.
const API_URL =
  typeof window === "undefined"
    ? (process.env.INTERNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
    : (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");

export const API_BASE = `${API_URL}/api/v1`;

async function fetchWithAuth(
  path: string,
  token: string | null,
  init: RequestInit = {}
): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.message ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// Sources
export async function listSources(token: string): Promise<SourceConnection[]> {
  const res = await fetchWithAuth("/sources", token);
  return handleResponse<SourceConnection[]>(res);
}

export async function createDBSource(
  token: string,
  name: string,
  dsn: string,
  source_type: string = "postgres"
): Promise<SourceConnection> {
  const res = await fetchWithAuth("/sources", token, {
    method: "POST",
    body: JSON.stringify({ name, dsn, source_type }),
  });
  return handleResponse<SourceConnection>(res);
}

export async function uploadFileSource(
  token: string,
  file: File
): Promise<SourceConnection> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/sources/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  return handleResponse<SourceConnection>(res);
}

export async function deleteSource(token: string, id: string): Promise<void> {
  await fetchWithAuth(`/sources/${id}`, token, { method: "DELETE" });
}

// Jobs
export async function createJob(
  token: string,
  source_connection_id: string
): Promise<Job> {
  const res = await fetchWithAuth("/jobs", token, {
    method: "POST",
    body: JSON.stringify({ source_connection_id }),
  });
  return handleResponse<Job>(res);
}

export async function getJob(token: string, id: string): Promise<Job> {
  const res = await fetchWithAuth(`/jobs/${id}`, token);
  return handleResponse<Job>(res);
}

export function buildJobStreamUrl(jobId: string, token: string): string {
  return `${API_BASE}/jobs/${jobId}/stream?token=${encodeURIComponent(token)}`;
}

// Reports
export async function listReports(token: string): Promise<ReportListItem[]> {
  const res = await fetchWithAuth("/reports", token);
  return handleResponse<ReportListItem[]>(res);
}

export async function getReport(token: string, id: string): Promise<Report> {
  const res = await fetchWithAuth(`/reports/${id}`, token);
  return handleResponse<Report>(res);
}

export function buildDownloadUrl(reportId: string, token: string): string {
  return `${API_BASE}/reports/${reportId}/download?token=${encodeURIComponent(token)}`;
}
