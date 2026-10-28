import type { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: string;
  detail?: string;
  icon: ReactNode;
  tone?: "default" | "accent" | "warning";
}

export function StatCard({ label, value, detail, icon, tone = "default" }: StatCardProps) {
  return (
    <article className={`stat-card stat-${tone}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-body">
        <span className="stat-label">{label}</span>
        <strong className={`stat-value${value.length > 12 ? " compact" : ""}`}>{value}</strong>
        {detail && <span className="stat-detail">{detail}</span>}
      </div>
    </article>
  );
}
