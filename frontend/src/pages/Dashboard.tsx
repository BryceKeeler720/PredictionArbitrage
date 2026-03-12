import { useOpportunities, useHealth } from "../hooks/useApi";
import { OpportunityTable } from "../components/OpportunityTable";
import { PlatformStatus } from "../components/PlatformStatus";

export function Dashboard() {
  const { data: oppData, isLoading, error } = useOpportunities();
  const { data: health } = useHealth();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Arbitrage Scanner</h1>
          <p className="text-sm text-gray-400 mt-1">
            Cross-platform prediction market arbitrage opportunities
          </p>
        </div>
        <PlatformStatus health={health} />
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="Active Opportunities"
          value={oppData?.opportunities.length ?? 0}
          color="text-green-400"
        />
        <StatCard
          label="Best Profit"
          value={
            oppData?.opportunities.length
              ? `${Math.max(...oppData.opportunities.map((o) => o.profit_pct)).toFixed(2)}%`
              : "—"
          }
          color="text-yellow-400"
        />
        <StatCard
          label="System Status"
          value={health?.status === "ok" ? "Healthy" : health?.status ?? "..."}
          color={health?.status === "ok" ? "text-green-400" : "text-red-400"}
        />
        <StatCard
          label="Last Scan"
          value={health ? new Date(health.timestamp).toLocaleTimeString() : "..."}
          color="text-gray-300"
        />
      </div>

      {/* Opportunities table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50">
        <div className="px-4 py-3 border-b border-gray-800">
          <h2 className="font-semibold">Active Opportunities</h2>
        </div>
        {isLoading ? (
          <div className="py-12 text-center text-gray-500">Loading...</div>
        ) : error ? (
          <div className="py-12 text-center text-red-400">
            Failed to load opportunities. Is the backend running?
          </div>
        ) : (
          <OpportunityTable opportunities={oppData?.opportunities ?? []} />
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`text-xl font-bold ${color}`}>{value}</div>
    </div>
  );
}
