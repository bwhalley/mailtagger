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

export type OrderStatus = "ordered" | "confirmed" | "cancelled" | "unknown";

export type ShipmentStatus =
  | "shipped"
  | "in_transit"
  | "out_for_delivery"
  | "delivered"
  | "unknown";

export interface ApiCommerceEmail {
  gmail_id?: string;
  subject?: string;
  received_at?: string;
  snippet?: string | null;
  source_type?: "brand" | "carrier";
}

export interface ApiOrder {
  id: number;
  order_number: string;
  brand_domain: string;
  status: OrderStatus;
  first_email_at?: string | null;
  last_email_at?: string | null;
  linked_emails?: ApiCommerceEmail[];
  shipments?: ApiShipment[];
}

export interface ApiShipment {
  id: number;
  tracking_number: string;
  carrier?: string | null;
  tracking_url?: string | null;
  status: ShipmentStatus;
  source_type?: "brand" | "carrier";
  brand_domain?: string | null;
  order_id?: number | null;
  order_number?: string | null;
  order_brand_domain?: string | null;
  estimated_delivery?: string | null;
  last_notification_at?: string | null;
  notifications?: ApiCommerceEmail[];
}

export interface CommerceSummary {
  orders_total: number;
  orders_open: number;
  shipments_total: number;
  by_shipment_status: Record<string, number>;
  in_transit: number;
  out_for_delivery: number;
  arriving_this_week: number;
  delivered_recent: number;
  // backward compat
  by_status?: Record<string, number>;
  total?: number;
}

/** @deprecated use CommerceSummary */
export type OrdersSummary = CommerceSummary;
