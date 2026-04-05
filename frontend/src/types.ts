export type Priority = "high" | "medium" | "low";
export type Lane = "urgent" | "ready" | "auto";

export interface ApiEmail {
  id: number;
  gmail_id?: string | null;
  thread_id?: string | null;
  sender?: string | null;
  sender_domain?: string | null;
  subject?: string | null;
  snippet?: string | null;
  body_text?: string | null;
  received_at?: string | null;
  labels?: string[] | null;
  priority?: Priority | null;
  classification?: string | null;
  confidence?: number | null;
  reason?: string | null;
  summary?: string | null;
}

export interface DashboardSummary {
  total: number;
  by_priority: Record<Priority, number>;
  by_classification: Record<string, number>;
}

export interface GmailStatus {
  credentials_exists: boolean;
  token_exists: boolean;
  authorized: boolean;
  email: string | null;
  token_valid: boolean;
  message?: string;
}

export interface UiMessage {
  id: string;
  subject: string;
  preview: string;
  timeLabel: string;
  unread: boolean;
}

export interface UiEmailGroup {
  id: string;
  sender: string;
  senderInitials: string;
  senderDomain?: string;
  lane: Lane;
  priority: Priority;
  classification: string;
  summary: string;
  confidence: number;
  unreadCount: number;
  messages: UiMessage[];
}
