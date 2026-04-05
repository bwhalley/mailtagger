import type { Lane, UiEmailGroup } from "../types";
import { EmailGroupCard } from "./EmailGroupCard";

interface LaneSectionProps {
  lane: Lane;
  title: string;
  subtitle: string;
  groups: UiEmailGroup[];
}

const softLaneClasses: Record<Lane, string> = {
  urgent: "bg-lane-urgent-soft border-lane-urgent/20",
  ready: "bg-lane-ready-soft border-lane-ready/20",
  auto: "bg-lane-auto-soft border-lane-auto/20"
};

export function LaneSection({ lane, title, subtitle, groups }: LaneSectionProps) {
  if (groups.length === 0) {
    return null;
  }

  return (
    <section className={`rounded-xl border p-4 md:p-5 ${softLaneClasses[lane]}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-display font-semibold">{title}</h2>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
        <span className="rounded-full bg-background px-2.5 py-1 text-xs font-medium text-foreground/80">
          {groups.length} {groups.length === 1 ? "group" : "groups"}
        </span>
      </div>
      <div className="space-y-2">
        {groups.map((group) => (
          <EmailGroupCard key={group.id} group={group} />
        ))}
      </div>
    </section>
  );
}
