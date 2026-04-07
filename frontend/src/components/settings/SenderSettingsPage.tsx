import { useCallback, useEffect, useMemo, useState } from "react";
import { getSenders, updateSenderStatus } from "../../api";
import type { ApiSender, SenderStatus } from "../../types";

interface SenderSettingsPageProps {
  onNavigate: (path: string) => void;
}

const statusTitle: Record<SenderStatus, string> = {
  new: "New Senders",
  highlight: "Highlighted Senders",
  quiet: "Quiet Senders"
};

const statusDescription: Record<SenderStatus, string> = {
  new: "Unreviewed domains that need a priority decision.",
  highlight: "Domains that should be emphasized in inbox triage.",
  quiet: "Domains that should be deprioritized and kept quiet."
};

export function SenderSettingsPage({ onNavigate }: SenderSettingsPageProps) {
  const [senders, setSenders] = useState<ApiSender[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const rows = await getSenders(undefined, 300);
      setSenders(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sender settings.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const grouped = useMemo(() => {
    return {
      new: senders.filter((s) => s.status === "new"),
      highlight: senders.filter((s) => s.status === "highlight"),
      quiet: senders.filter((s) => s.status === "quiet")
    };
  }, [senders]);

  const setStatus = async (senderId: number, status: SenderStatus) => {
    setBusyId(senderId);
    try {
      await updateSenderStatus(senderId, status);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update sender status.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b border-border bg-background/90 backdrop-blur">
        <div className="container flex items-center justify-between py-3">
          <div>
            <h1 className="font-display text-lg font-semibold">Email Sender Settings</h1>
            <p className="text-xs text-muted-foreground">
              Review sender domains and tune highlight/quiet behavior.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={load}
              className="rounded-md bg-muted px-2.5 py-1.5 text-xs font-medium text-muted-foreground"
            >
              Refresh
            </button>
            <button
              type="button"
              onClick={() => onNavigate("/settings")}
              className="rounded-md bg-muted px-2.5 py-1.5 text-xs font-medium text-muted-foreground"
            >
              Back to Settings
            </button>
          </div>
        </div>
      </header>

      <main className="container py-6">
        {error && (
          <div className="mb-4 rounded-md border border-lane-urgent/30 bg-lane-urgent-soft px-3 py-2 text-sm">
            {error}
          </div>
        )}

        <div className="space-y-4">
          {(["new", "highlight", "quiet"] as SenderStatus[]).map((status) => (
            <section key={status} className="rounded-xl border border-border bg-card p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div>
                  <h2 className="font-display text-base font-semibold">{statusTitle[status]}</h2>
                  <p className="text-xs text-muted-foreground">{statusDescription[status]}</p>
                </div>
                <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                  {grouped[status].length}
                </span>
              </div>

              {grouped[status].length === 0 ? (
                <p className="text-sm text-muted-foreground">No senders in this group.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="px-2 py-2">Sender</th>
                        <th className="px-2 py-2">Domain</th>
                        <th className="px-2 py-2">Messages</th>
                        <th className="px-2 py-2">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {grouped[status].map((sender) => (
                        <tr key={sender.id} className="border-b border-border/60 last:border-none">
                          <td className="px-2 py-2">
                            <p className="font-medium">{sender.latest_sender || sender.sender_domain}</p>
                          </td>
                          <td className="px-2 py-2 text-muted-foreground">
                            {sender.domain_key || sender.sender_domain}
                          </td>
                          <td className="px-2 py-2">{sender.message_count}</td>
                          <td className="px-2 py-2">
                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                disabled={busyId === sender.id}
                                onClick={() => setStatus(sender.id, "highlight")}
                                className="rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground disabled:opacity-60"
                              >
                                Highlight
                              </button>
                              <button
                                type="button"
                                disabled={busyId === sender.id}
                                onClick={() => setStatus(sender.id, "quiet")}
                                className="rounded-md bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground disabled:opacity-60"
                              >
                                Quiet
                              </button>
                              <button
                                type="button"
                                disabled={busyId === sender.id}
                                onClick={() => setStatus(sender.id, "new")}
                                className="rounded-md bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground disabled:opacity-60"
                              >
                                Set New
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ))}
        </div>
      </main>
    </div>
  );
}
