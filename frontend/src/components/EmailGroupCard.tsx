import { ChevronDown, Mail, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import type { UiEmailGroup } from "../types";

const laneClass: Record<UiEmailGroup["lane"], string> = {
  urgent: "border-lane-urgent/50",
  ready: "border-lane-ready/40",
  auto: "border-lane-auto/40"
};

interface EmailGroupCardProps {
  group: UiEmailGroup;
}

export function EmailGroupCard({ group }: EmailGroupCardProps) {
  const [expanded, setExpanded] = useState(false);
  const messageCountLabel = useMemo(() => {
    const count = group.messages.length;
    return count === 1 ? "1 message" : `${count} messages`;
  }, [group.messages.length]);

  return (
    <article
      className={`rounded-lg border bg-card text-card-foreground shadow-sm transition hover:shadow-md ${laneClass[group.lane]}`}
    >
      <button
        className="w-full px-4 py-3 text-left"
        onClick={() => setExpanded((open) => !open)}
        type="button"
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-foreground/90 text-xs font-semibold text-background">
            {group.senderInitials}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="truncate text-sm font-semibold">{group.sender}</p>
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                {group.classification}
              </span>
            </div>
            <p className="mt-1 line-clamp-2 text-sm text-foreground/85">{group.summary}</p>
            <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
              <span>{messageCountLabel}</span>
              <span>{group.messages[0]?.timeLabel}</span>
              <span>confidence {(group.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
          <ChevronDown
            className={`mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        </div>
      </button>

      {expanded && (
        <div className="border-t border-border px-4 py-2">
          <ul className="space-y-1.5">
            {group.messages.map((message) => (
              <li
                key={message.id}
                className="rounded-md bg-muted/50 px-3 py-2 text-xs text-foreground/90"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="truncate font-medium">{message.subject}</span>
                  <span className="shrink-0 text-muted-foreground">{message.timeLabel}</span>
                </div>
                {message.preview && (
                  <p className="mt-1 line-clamp-2 text-[11px] text-muted-foreground">
                    {message.preview}
                  </p>
                )}
              </li>
            ))}
          </ul>
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2.5 py-1.5 text-xs font-medium text-primary"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Draft reply
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-md bg-muted px-2.5 py-1.5 text-xs font-medium text-muted-foreground"
            >
              <Mail className="h-3.5 w-3.5" />
              Open thread
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
