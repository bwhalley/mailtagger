import { Inbox, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { GmailAuthCard } from "./components/GmailAuthCard";
import { LaneSection } from "./components/LaneSection";
import {
  getDashboardSummary,
  getGmailStatus,
  getRecentEmails,
  getSenders,
  revokeGmailOAuth,
  searchEmails,
  startGmailOAuth,
  updateSenderStatus
} from "./api";
import { groupEmailsForInbox } from "./adapters";
import type { ApiSender, DashboardSummary, GmailStatus, SenderStatus, UiEmailGroup } from "./types";

const laneMeta = {
  urgent: {
    title: "Right Now",
    subtitle: "High-priority threads that likely need action."
  },
  ready: {
    title: "When You Are Ready",
    subtitle: "Medium-priority threads worth reviewing soon."
  },
  auto: {
    title: "On Autopilot",
    subtitle: "Lower-priority, routine messages."
  }
} as const;

function App() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [groups, setGroups] = useState<UiEmailGroup[]>([]);
  const [gmailStatus, setGmailStatus] = useState<GmailStatus | null>(null);
  const [newSenders, setNewSenders] = useState<ApiSender[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadDashboard = useCallback(async (query?: string) => {
    const emails = query && query.trim().length >= 2 ? await searchEmails(query) : await getRecentEmails();
    setGroups(groupEmailsForInbox(emails));
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, statusData, newSenderData] = await Promise.all([
        getDashboardSummary(),
        getGmailStatus(),
        getSenders("new", 15)
      ]);
      setSummary(summaryData);
      setGmailStatus(statusData);
      setNewSenders(newSenderData);
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Mailtagger data.");
    } finally {
      setLoading(false);
    }
  }, [loadDashboard]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.has("oauth_success")) {
      setActionMessage("Gmail OAuth completed successfully.");
      window.history.replaceState({}, document.title, window.location.pathname);
      refresh();
    } else if (params.has("oauth_error")) {
      const oauthError = params.get("oauth_error") ?? "unknown_error";
      setActionMessage(`OAuth failed: ${oauthError}`);
      window.history.replaceState({}, document.title, window.location.pathname);
      refresh();
    }
  }, [refresh]);

  const urgent = useMemo(() => groups.filter((group) => group.lane === "urgent"), [groups]);
  const ready = useMemo(() => groups.filter((group) => group.lane === "ready"), [groups]);
  const auto = useMemo(() => groups.filter((group) => group.lane === "auto"), [groups]);
  const laneCount = urgent.length + ready.length + auto.length;

  const classificationSummary = useMemo(() => {
    if (!summary) return [];
    return Object.entries(summary.by_classification)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4);
  }, [summary]);

  const handleSenderStatus = async (senderId: number, status: SenderStatus) => {
    setBusy(true);
    try {
      await updateSenderStatus(senderId, status);
      setActionMessage(`Sender marked as ${status}.`);
      const [newSenderData] = await Promise.all([getSenders("new", 15), loadDashboard(search)]);
      setNewSenders(newSenderData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update sender status.");
    } finally {
      setBusy(false);
    }
  };

  const onSearchSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    try {
      await loadDashboard(search);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setBusy(false);
    }
  };

  const handleAuthorize = async () => {
    setBusy(true);
    setActionMessage("Starting OAuth flow...");
    try {
      const response = await startGmailOAuth();
      window.location.href = response.auth_url;
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Failed to start OAuth flow.");
      setBusy(false);
    }
  };

  const handleRevoke = async () => {
    setBusy(true);
    try {
      const response = await revokeGmailOAuth();
      setActionMessage(response.message);
      const statusData = await getGmailStatus();
      setGmailStatus(statusData);
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Failed to revoke OAuth token.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b border-border bg-background/90 backdrop-blur">
        <div className="container flex items-center justify-between py-3">
          <div className="flex items-center gap-2">
            <Inbox className="h-5 w-5 text-primary" />
            <h1 className="font-display text-lg font-semibold">Mailtagger Inbox</h1>
          </div>
          <button
            type="button"
            onClick={refresh}
            className="rounded-md bg-muted px-2.5 py-1.5 text-xs font-medium text-muted-foreground"
          >
            Refresh
          </button>
        </div>
      </header>

      <main className="container py-6">
        <section className="mb-6 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Indexed emails</p>
            <p className="mt-2 text-2xl font-display font-semibold">{summary?.total ?? "-"}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">High priority</p>
            <p className="mt-2 text-2xl font-display font-semibold">
              {summary?.by_priority?.high ?? "-"}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Medium priority</p>
            <p className="mt-2 text-2xl font-display font-semibold">
              {summary?.by_priority?.medium ?? "-"}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Low priority</p>
            <p className="mt-2 text-2xl font-display font-semibold">
              {summary?.by_priority?.low ?? "-"}
            </p>
          </div>
        </section>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_330px]">
          <section className="space-y-4">
            <form
              onSubmit={onSearchSubmit}
              className="flex items-center gap-2 rounded-lg border border-border bg-card p-3 shadow-sm"
            >
              <Search className="h-4 w-4 text-muted-foreground" />
              <input
                className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                type="text"
                placeholder="Search sender, subject, or snippet"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              <button
                type="submit"
                disabled={busy}
                className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-70"
              >
                Search
              </button>
            </form>

            {error && (
              <div className="rounded-md border border-lane-urgent/30 bg-lane-urgent-soft px-3 py-2 text-sm">
                {error}
              </div>
            )}

            {newSenders.length > 0 && (
              <section className="rounded-xl border border-lane-ready/25 bg-lane-ready-soft p-4">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <h2 className="font-display text-base font-semibold">New to your inbox</h2>
                    <p className="text-sm text-muted-foreground">
                      First-time sender domains. Highlight what matters or keep quiet.
                    </p>
                  </div>
                  <span className="rounded-full bg-background px-2.5 py-1 text-xs font-medium">
                    {newSenders.length}
                  </span>
                </div>
                <ul className="space-y-2">
                  {newSenders.map((sender) => (
                    <li
                      key={sender.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2"
                    >
                      <div>
                        <p className="text-sm font-medium text-foreground">{sender.sender_domain}</p>
                        <p className="text-xs text-muted-foreground">
                          tld: .{sender.tld} · {sender.message_count} message
                          {sender.message_count === 1 ? "" : "s"}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleSenderStatus(sender.id, "highlight")}
                          className="rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-70"
                        >
                          Highlight
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleSenderStatus(sender.id, "quiet")}
                          className="rounded-md bg-muted px-2.5 py-1.5 text-xs font-medium text-muted-foreground disabled:opacity-70"
                        >
                          Keep quiet
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {loading ? (
              <div className="rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground">
                Loading dashboard...
              </div>
            ) : laneCount === 0 ? (
              <div className="rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground">
                No indexed emails found yet.
              </div>
            ) : (
              <div className="space-y-4">
                <LaneSection lane="urgent" {...laneMeta.urgent} groups={urgent} />
                <LaneSection lane="ready" {...laneMeta.ready} groups={ready} />
                <LaneSection lane="auto" {...laneMeta.auto} groups={auto} />
              </div>
            )}
          </section>

          <aside className="space-y-4">
            <GmailAuthCard
              status={gmailStatus}
              actionMessage={actionMessage}
              pending={busy}
              onAuthorize={handleAuthorize}
              onRevoke={handleRevoke}
            />

            <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
              <h2 className="font-display text-base font-semibold">Top Classifications</h2>
              {classificationSummary.length === 0 ? (
                <p className="mt-2 text-sm text-muted-foreground">
                  Classification counts appear after emails are processed.
                </p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {classificationSummary.map(([label, count]) => (
                    <li
                      key={label}
                      className="flex items-center justify-between rounded-md bg-muted px-2.5 py-2 text-sm"
                    >
                      <span className="capitalize text-foreground/90">{label}</span>
                      <span className="font-medium text-foreground">{count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </aside>
        </div>
      </main>
    </div>
  );
}

export default App;
