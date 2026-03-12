import { useState, useMemo } from "react";
import type { OpportunityFilters } from "../hooks/useApi";
import { useOpportunities, useHealth } from "../hooks/useApi";
import { OpportunityTable } from "../components/OpportunityTable";
import { PlatformStatus } from "../components/PlatformStatus";
import { FilterBar } from "../components/FilterBar";

export function Dashboard() {
  const [filters, setFilters] = useState<OpportunityFilters>({});
  const { data: oppData, isLoading, error } = useOpportunities("active", filters);
  const { data: health } = useHealth();

  const opps = oppData?.opportunities ?? [];

  // Compute summary stats
  const stats = useMemo(() => {
    if (opps.length === 0) return null;

    const profits = opps.map((o) => o.profit_pct);
    const avgProfit = profits.reduce((a, b) => a + b, 0) / profits.length;
    const medianProfit = [...profits].sort((a, b) => a - b)[Math.floor(profits.length / 2)];
    const bestProfit = Math.max(...profits);
    const totalLiquidity = opps.reduce((sum, o) => sum + (o.max_size_usd || 0), 0);

    // Platform pair breakdown
    const pairCounts: Record<string, number> = {};
    for (const o of opps) {
      const platforms = o.legs.map((l) => l.platform).sort().join(" + ");
      pairCounts[platforms] = (pairCounts[platforms] || 0) + 1;
    }

    // Confidence distribution
    const highConfidence = opps.filter((o) => o.match_confidence >= 0.8).length;

    return { avgProfit, medianProfit, bestProfit, totalLiquidity, pairCounts, highConfidence };
  }, [opps]);

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
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <StatCard
          label="Opportunities"
          value={oppData?.total ?? opps.length}
          color="text-green-400"
        />
        <StatCard
          label="Best Profit"
          value={stats ? `${stats.bestProfit.toFixed(1)}%` : "\u2014"}
          color="text-yellow-400"
        />
        <StatCard
          label="Avg Profit"
          value={stats ? `${stats.avgProfit.toFixed(1)}%` : "\u2014"}
          color="text-blue-400"
        />
        <StatCard
          label="Median Profit"
          value={stats ? `${stats.medianProfit.toFixed(1)}%` : "\u2014"}
          color="text-purple-400"
        />
        <StatCard
          label="Total Liquidity"
          value={stats ? formatCompact(stats.totalLiquidity) : "\u2014"}
          color="text-cyan-400"
        />
        <StatCard
          label="High Confidence"
          value={stats ? `${stats.highConfidence} / ${opps.length}` : "\u2014"}
          color="text-emerald-400"
        />
      </div>

      {/* Platform pair breakdown */}
      {stats && Object.keys(stats.pairCounts).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(stats.pairCounts)
            .sort(([, a], [, b]) => b - a)
            .map(([pair, count]) => (
              <span
                key={pair}
                className="rounded-full bg-gray-800 border border-gray-700 px-3 py-1 text-xs text-gray-300"
              >
                {pair}: <span className="text-white font-medium">{count}</span>
              </span>
            ))}
        </div>
      )}

      {/* Filter bar */}
      <FilterBar filters={filters} onChange={setFilters} />

      {/* Opportunities table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50">
        <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
          <h2 className="font-semibold">Active Opportunities</h2>
          <span className="text-xs text-gray-500">
            {opps.length} shown{oppData?.total ? ` of ${oppData.total}` : ""}
          </span>
        </div>
        {isLoading ? (
          <div className="py-12 text-center text-gray-500">Loading...</div>
        ) : error ? (
          <div className="py-12 text-center text-red-400">
            Failed to load opportunities. Is the backend running?
          </div>
        ) : (
          <OpportunityTable opportunities={opps} />
        )}
      </div>
    </div>
  );
}

function formatCompact(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
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
