import { AlertTriangle, CheckCircle2, Link2, RotateCw, ShieldX } from "lucide-react";
import type { GmailStatus } from "@/types";

interface GmailAuthCardProps {
  status: GmailStatus | null;
  actionMessage: string | null;
  pending: boolean;
  onAuthorize: () => void;
  onRevoke: () => void;
}

export function GmailAuthCard({
  status,
  actionMessage,
  pending,
  onAuthorize,
  onRevoke
}: GmailAuthCardProps) {
  const authorized = Boolean(status?.authorized && status?.token_valid);
  const missingCredentials = status ? !status.credentials_exists : false;

  return (
    <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <Link2 className="h-4 w-4 text-primary" />
        <h2 className="font-display text-base font-semibold">Gmail Connection</h2>
      </div>

      <div className="mt-3">
        {status === null ? (
          <p className="text-sm text-muted-foreground">Loading Gmail status...</p>
        ) : authorized ? (
          <div className="rounded-md bg-lane-auto-soft px-3 py-2 text-sm">
            <p className="flex items-center gap-1 font-medium text-foreground">
              <CheckCircle2 className="h-4 w-4 text-lane-auto" />
              Authorized
            </p>
            <p className="mt-1 text-muted-foreground">
              {status.email ? `Connected as ${status.email}` : status.message}
            </p>
          </div>
        ) : (
          <div className="rounded-md bg-lane-urgent-soft px-3 py-2 text-sm">
            <p className="flex items-center gap-1 font-medium text-foreground">
              <AlertTriangle className="h-4 w-4 text-lane-urgent" />
              Not connected
            </p>
            <p className="mt-1 text-muted-foreground">
              {missingCredentials
                ? "credentials.json is missing in the configured credentials directory."
                : status.message ?? "Authorize Gmail to enable processing."}
            </p>
          </div>
        )}
      </div>

      {actionMessage && (
        <p className="mt-3 rounded-md bg-muted px-2.5 py-2 text-xs text-muted-foreground">
          {actionMessage}
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onAuthorize}
          disabled={pending || missingCredentials || authorized}
          className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-2 text-xs font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RotateCw className="h-3.5 w-3.5" />
          Authorize Gmail
        </button>
        <button
          type="button"
          onClick={onRevoke}
          disabled={pending || !authorized}
          className="inline-flex items-center gap-1 rounded-md bg-muted px-3 py-2 text-xs font-medium text-muted-foreground disabled:cursor-not-allowed disabled:opacity-60"
        >
          <ShieldX className="h-3.5 w-3.5" />
          Revoke token
        </button>
      </div>
    </section>
  );
}
