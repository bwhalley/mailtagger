import { ChevronDown, ShoppingBag } from "lucide-react";
import { useEffect, useState } from "react";
import { getOrderDetail } from "../api";
import type { ApiOrder } from "../types";
import { CommerceEmailPreview } from "./CommerceEmailPreview";

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
  const [detail, setDetail] = useState<ApiOrder | null>(null);
  const [loadingEmails, setLoadingEmails] = useState(false);

  useEffect(() => {
    if (!expanded || detail) return;
    let cancelled = false;
    setLoadingEmails(true);
    getOrderDetail(order.id)
      .then((loaded) => {
        if (!cancelled) setDetail(loaded);
      })
      .catch(() => {
        if (!cancelled) setDetail(order);
      })
      .finally(() => {
        if (!cancelled) setLoadingEmails(false);
      });
    return () => {
      cancelled = true;
    };
  }, [expanded, detail, order]);

  const linkedEmails = detail?.linked_emails ?? order.linked_emails ?? [];

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
          {loadingEmails ? (
            <p className="mb-3 text-xs text-muted-foreground">Loading emails...</p>
          ) : linkedEmails.length > 0 ? (
            <ul className="mb-3 space-y-1.5">
              {linkedEmails.map((email, idx) => (
                <CommerceEmailPreview key={`${email.gmail_id ?? idx}`} email={email} />
              ))}
            </ul>
          ) : (
            <p className="mb-3 text-xs text-muted-foreground">No linked emails.</p>
          )}
          {(detail?.shipments ?? order.shipments ?? []).length > 0 && (
            <p className="text-xs text-muted-foreground">
              {(detail?.shipments ?? order.shipments)!.length} linked shipment
              {(detail?.shipments ?? order.shipments)!.length === 1 ? "" : "s"}
            </p>
          )}
        </div>
      )}
    </article>
  );
}
