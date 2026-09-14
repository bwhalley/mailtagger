import { ChevronDown, ExternalLink, Package } from "lucide-react";
import { useMemo, useState } from "react";
import type { ApiShipment, ShipmentStatus } from "../types";

const statusLabels: Record<ShipmentStatus, string> = {
  shipped: "Shipped",
  in_transit: "In transit",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  unknown: "Unknown"
};

const statusClasses: Record<ShipmentStatus, string> = {
  shipped: "bg-lane-ready-soft text-lane-ready",
  in_transit: "bg-lane-ready-soft text-lane-ready",
  out_for_delivery: "bg-lane-urgent-soft text-lane-urgent",
  delivered: "bg-muted text-muted-foreground",
  unknown: "bg-muted text-muted-foreground"
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

interface ShipmentCardProps {
  shipment: ApiShipment;
  highlight?: boolean;
}

export function ShipmentCard({ shipment, highlight = false }: ShipmentCardProps) {
  const [expanded, setExpanded] = useState(false);
  const status = (shipment.status ?? "unknown") as ShipmentStatus;
  const displayName = useMemo(
    () => shipment.brand_domain || shipment.carrier || "Package",
    [shipment.brand_domain, shipment.carrier]
  );

  const copyTracking = async () => {
    if (!shipment.tracking_number) return;
    try {
      await navigator.clipboard.writeText(shipment.tracking_number);
    } catch {
      // clipboard may be unavailable
    }
  };

  return (
    <article
      className={`rounded-lg border bg-card text-card-foreground shadow-sm transition hover:shadow-md ${
        highlight ? "border-lane-urgent/40" : "border-border"
      }`}
    >
      <button
        className="w-full px-4 py-3 text-left"
        onClick={() => setExpanded((open) => !open)}
        type="button"
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Package className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="truncate text-sm font-semibold">{displayName}</p>
              {shipment.carrier && (
                <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                  {shipment.carrier}
                </span>
              )}
              {shipment.source_type && (
                <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                  {shipment.source_type}
                </span>
              )}
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${statusClasses[status]}`}
              >
                {statusLabels[status]}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  copyTracking();
                }}
                className="font-mono hover:text-foreground"
                title="Click to copy tracking number"
              >
                {shipment.tracking_number}
              </button>
              {shipment.order_number && (
                <span>Order #{shipment.order_number}</span>
              )}
              {shipment.estimated_delivery && <span>ETA: {shipment.estimated_delivery}</span>}
              {shipment.last_notification_at && (
                <span>Updated {formatRelative(shipment.last_notification_at)}</span>
              )}
            </div>
          </div>
          <ChevronDown
            className={`mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        </div>
      </button>

      {expanded && (
        <div className="border-t border-border px-4 py-3">
          {(shipment.notifications ?? []).length > 0 && (
            <ul className="mb-3 space-y-1.5">
              {(shipment.notifications ?? []).map((note, idx) => (
                <li
                  key={`${note.gmail_id ?? idx}`}
                  className="rounded-md bg-muted/50 px-3 py-2 text-xs text-foreground/90"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate font-medium">{note.subject || "(No subject)"}</span>
                    <span className="shrink-0 text-muted-foreground">
                      {note.source_type ?? "brand"} · {formatRelative(note.received_at)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {shipment.tracking_url && (
            <a
              href={shipment.tracking_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2.5 py-1.5 text-xs font-medium text-primary"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Track package
            </a>
          )}
        </div>
      )}
    </article>
  );
}
