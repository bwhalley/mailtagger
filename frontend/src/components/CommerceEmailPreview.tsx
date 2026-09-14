import type { ApiCommerceEmail } from "../types";

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

interface CommerceEmailPreviewProps {
  email: ApiCommerceEmail;
  meta?: string;
}

export function CommerceEmailPreview({ email, meta }: CommerceEmailPreviewProps) {
  const preview = email.snippet?.trim();

  return (
    <li className="rounded-md bg-muted/50 px-3 py-2 text-xs text-foreground/90">
      <div className="flex items-center justify-between gap-3">
        <span className="truncate font-medium">{email.subject || "(No subject)"}</span>
        <span className="shrink-0 text-muted-foreground">
          {meta ?? formatRelative(email.received_at)}
        </span>
      </div>
      {preview && (
        <p className="mt-1 line-clamp-2 text-[11px] text-muted-foreground">{preview}</p>
      )}
    </li>
  );
}
