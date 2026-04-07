interface SettingsOverviewPageProps {
  onNavigate: (path: string) => void;
}

export function SettingsOverviewPage({ onNavigate }: SettingsOverviewPageProps) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b border-border bg-background/90 backdrop-blur">
        <div className="container flex items-center justify-between py-3">
          <div>
            <h1 className="font-display text-lg font-semibold">Settings</h1>
            <p className="text-xs text-muted-foreground">Configure Mailtagger behavior and review data models.</p>
          </div>
          <button
            type="button"
            onClick={() => onNavigate("/")}
            className="rounded-md bg-muted px-2.5 py-1.5 text-xs font-medium text-muted-foreground"
          >
            Back to Inbox
          </button>
        </div>
      </header>

      <main className="container py-6">
        <div className="space-y-6">
          <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <h2 className="font-display text-base font-semibold">General</h2>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div className="rounded-lg border border-border bg-background p-3">
                <p className="text-sm font-medium">UI Theme</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Theme toggles and display preferences will be managed here.
                </p>
              </div>
              <div className="rounded-lg border border-border bg-background p-3">
                <p className="text-sm font-medium">Notifications</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Future controls for alerts and digest cadence.
                </p>
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <h2 className="font-display text-base font-semibold">Email Workflow</h2>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div className="rounded-lg border border-border bg-background p-3">
                <p className="text-sm font-medium">Prompt and Classification Rules</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Prompt tuning and category handling controls can be managed here.
                </p>
              </div>
              <div className="rounded-lg border border-border bg-background p-3">
                <p className="text-sm font-medium">Sender Priority Rules</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Review sender domains and mark them as highlight or quiet.
                </p>
                <button
                  type="button"
                  onClick={() => onNavigate("/settings/senders")}
                  className="mt-3 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
                >
                  Open Email Sender Settings
                </button>
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <h2 className="font-display text-base font-semibold">Data and Maintenance</h2>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div className="rounded-lg border border-border bg-background p-3">
                <p className="text-sm font-medium">Backfill and Reindex</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Data maintenance actions and index status will appear here.
                </p>
              </div>
              <div className="rounded-lg border border-border bg-background p-3">
                <p className="text-sm font-medium">Integrations</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Gmail and future integrations management will be grouped here.
                </p>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
