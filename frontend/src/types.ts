export type Priority = "high" | "medium" | "low";
export type Lane = "urgent" | "ready" | "auto";
export type SenderStatus = "new" | "highlight" | "quiet";

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
  sender_status?: SenderStatus | null;
  sender_settings?: Record<string, unknown> | string | null;
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

export interface ApiSender {
  id: number;
  sender_domain: string;
  domain_key?: string;
  latest_sender?: string;
  tld: string;
  status: SenderStatus;
  settings: Record<string, unknown>;
  message_count: number;
  first_seen?: string;
  last_seen?: string;
}

export type ShipmentStatus =
  | "ordered"
  | "confirmed"
  | "shipped"
  | "in_transit"
  | "out_for_delivery"
  | "delivered"
  | "unknown";

export interface ApiShipmentEmail {
  gmail_id?: string;
  subject?: string;
  received_at?: string;
}

export interface ApiShipment {
  id: number;
  merchant: string;
  carrier?: string | null;
  tracking_number?: string | null;
  tracking_url?: string | null;
  order_number?: string | null;
  status: ShipmentStatus;
  estimated_delivery?: string | null;
  item_summary?: string | null;
  amount?: string | null;
  currency?: string | null;
  last_email_at?: string | null;
  thread_id?: string | null;
  linked_emails?: ApiShipmentEmail[];
}

export interface OrdersSummary {
  by_status: Record<string, number>;
  in_transit: number;
  out_for_delivery: number;
  arriving_this_week: number;
  delivered_recent: number;
  total: number;
}
