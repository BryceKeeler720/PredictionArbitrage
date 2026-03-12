import type { HealthStatus } from "../hooks/useApi";
import { StatusDot } from "./StatusDot";

export function PlatformStatus({ health }: { health: HealthStatus | undefined }) {
  if (!health) return null;

  const checks = [
    { name: "Database", status: health.database },
    { name: "Polymarket", status: health.polymarket },
    { name: "Kalshi", status: health.kalshi },
  ];

  return (
    <div className="flex items-center gap-4 text-xs text-gray-400">
      {checks.map((c) => (
        <div key={c.name} className="flex items-center gap-1.5">
          <StatusDot ok={c.status === "ok"} />
          <span>{c.name}</span>
        </div>
      ))}
      <span className="text-gray-600">
        Updated {new Date(health.timestamp).toLocaleTimeString()}
      </span>
    </div>
  );
}
