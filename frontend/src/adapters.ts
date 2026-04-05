import type { ApiEmail, Lane, Priority, UiEmailGroup, UiMessage } from "./types";

const categoryFromClassification = (value?: string | null) => {
  if (!value) return "uncategorized";
  return value.toLowerCase();
};

const priorityToLane = (priority?: Priority | null, classification?: string | null): Lane => {
  if (priority === "high") return "urgent";
  if (priority === "low") return "auto";
  if (classification && ["ecommerce", "promo", "social", "receipt"].includes(classification)) {
    return "auto";
  }
  return "ready";
};

const toSenderInitials = (sender?: string | null) => {
  if (!sender) return "??";
  const cleaned = sender
    .replace(/<[^>]*>/g, "")
    .replace(/["']/g, "")
    .trim();
  const parts = cleaned.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "??";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
};

const formatRelative = (timestamp?: string | null) => {
  if (!timestamp) return "unknown";
  const then = new Date(timestamp).getTime();
  if (Number.isNaN(then)) return "unknown";
  const diffMs = Date.now() - then;
  const diffMin = Math.max(1, Math.floor(diffMs / 60000));
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  return `${diffD}d ago`;
};

const sortByMostRecent = (a: ApiEmail, b: ApiEmail) =>
  new Date(b.received_at ?? 0).getTime() - new Date(a.received_at ?? 0).getTime();

export function groupEmailsForInbox(emails: ApiEmail[]): UiEmailGroup[] {
  const bySender = new Map<string, ApiEmail[]>();

  emails.forEach((email) => {
    const sender = (email.sender ?? "Unknown sender").trim() || "Unknown sender";
    const existing = bySender.get(sender) ?? [];
    existing.push(email);
    bySender.set(sender, existing);
  });

  const groups: UiEmailGroup[] = [];

  bySender.forEach((senderEmails, sender) => {
    const sorted = [...senderEmails].sort(sortByMostRecent);
    const newest = sorted[0];
    const priority = (newest.priority ?? "medium") as Priority;
    const classification = categoryFromClassification(newest.classification);
    const lane = priorityToLane(priority, classification);

    const messages: UiMessage[] = sorted.slice(0, 8).map((email) => ({
      id: email.gmail_id ?? String(email.id),
      subject: email.subject ?? "(No subject)",
      preview: email.snippet ?? "",
      timeLabel: formatRelative(email.received_at),
      unread: priority === "high"
    }));

    groups.push({
      id: newest.thread_id ?? newest.gmail_id ?? `sender-${sender}`,
      sender,
      senderInitials: toSenderInitials(sender),
      senderDomain: newest.sender_domain ?? undefined,
      lane,
      priority,
      classification,
      summary: newest.summary ?? newest.snippet ?? "No summary available yet.",
      confidence: Number(newest.confidence ?? 0),
      unreadCount: priority === "high" ? messages.length : 0,
      messages
    });
  });

  return groups.sort((a, b) => {
    const laneOrder: Record<Lane, number> = { urgent: 0, ready: 1, auto: 2 };
    if (laneOrder[a.lane] !== laneOrder[b.lane]) {
      return laneOrder[a.lane] - laneOrder[b.lane];
    }
    return b.messages.length - a.messages.length;
  });
}
