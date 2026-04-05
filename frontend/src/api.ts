import type { ApiEmail, DashboardSummary, GmailStatus } from "./types";

interface ApiEnvelope<T> {
  success: boolean;
  emails?: T;
  summary?: DashboardSummary;
  detail?: string;
}

interface OAuthStartResponse {
  auth_url: string;
  state: string;
}

const getApiBaseUrl = () => {
  const origin = window.location.origin;
  const port = window.location.port;
  if (port === "8080" && origin.startsWith("http")) {
    return origin.replace(":8080", ":8000");
  }
  return origin;
};

export const API_BASE_URL = getApiBaseUrl();

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail?: unknown }).detail)
        : `${response.status} ${response.statusText}`;
    throw new Error(detail);
  }
  return payload as T;
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const response = await requestJson<ApiEnvelope<ApiEmail[]>>("/api/dashboard");
  if (!response.success || !response.summary) {
    throw new Error("Dashboard summary unavailable");
  }
  return response.summary;
}

export async function getRecentEmails(limit = 150): Promise<ApiEmail[]> {
  const response = await requestJson<ApiEnvelope<ApiEmail[]>>(
    `/api/emails?limit=${limit}&offset=0`
  );
  if (!response.success || !response.emails) {
    return [];
  }
  return response.emails;
}

export async function searchEmails(query: string, limit = 80): Promise<ApiEmail[]> {
  const response = await requestJson<ApiEnvelope<ApiEmail[]>>(
    `/api/search?q=${encodeURIComponent(query)}&limit=${limit}`
  );
  if (!response.success || !response.emails) {
    return [];
  }
  return response.emails;
}

export async function getGmailStatus(): Promise<GmailStatus> {
  return requestJson<GmailStatus>("/api/gmail/status");
}

export async function startGmailOAuth(): Promise<OAuthStartResponse> {
  return requestJson<OAuthStartResponse>("/api/oauth/start");
}

export async function revokeGmailOAuth(): Promise<{ success: boolean; message: string }> {
  return requestJson<{ success: boolean; message: string }>("/api/gmail/revoke", {
    method: "POST"
  });
}
