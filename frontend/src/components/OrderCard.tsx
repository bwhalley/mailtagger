import { ChevronDown, ShoppingBag } from "lucide-react";
import { useState } from "react";
import type { ApiOrder } from "../types";

const statusLabels: Record<ApiOrder["status"], string> = {
  ordered: "Ordered",
  confirmed: "Confirmed",
  cancelled: "Cancelled",
  unknown: "Unknown"
};

const formatRelative = (timestamp?: string | null) => {
  if (!timestamp) return "unknown";
  const then = new Date(timestamp).getTime();
  if (Number.isNaN(then)) return timestamp;
  const diffMs = Date.now() - then;
  const diffMin = Math.max(1, Math.floor(diffMs / 60000));
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h ago`;
  return `${Math.floor(diffH / 24)}d ago`;
};

interface OrderCardProps {
  order: ApiOrder;
}

export function OrderCard({ order }: OrderCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <article className="rounded-lg border border-border bg-card text-card-foreground shadow-sm">
      <button
        className="w-full px-4 py-3 text-left"
        onClick={() => setExpanded((open) => !open)}
        type="button"
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <ShoppingBag className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="truncate text-sm font-semibold">{order.brand_domain}</p>
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                {statusLabels[order.status]}
              </span>
            </div>
            <p className="mt-1 font-mono text-sm text-foreground/85">#{order.order_number}</p>
            <p className="mt-2 text-xs text-muted-foreground">
              Updated {formatRelative(order.last_email_at)}
            </p>
          </div>
          <ChevronDown
            className={`mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        </div>
      </button>

      {expanded && (
        <div className="border-t border-border px-4 py-3">
          {(order.linked_emails ?? []).length > 0 && (
            <ul className="mb-3 space-y-1.5">
              {(order.linked_emails ?? []).map((email, idx) => (
                <li
                  key={`${email.gmail_id ?? idx}`}
                  className="rounded-md bg-muted/50 px-3 py-2 text-xs text-foreground/90"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate font-medium">{email.subject || "(No subject)"}</span>
                    <span className="shrink-0 text-muted-foreground">
                      {formatRelative(email.received_at)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {(order.shipments ?? []).length > 0 && (
            <p className="text-xs text-muted-foreground">
              {order.shipments!.length} linked shipment
              {order.shipments!.length === 1 ? "" : "s"}
            </p>
          )}
        </div>
      )}
    </article>
  );
}
