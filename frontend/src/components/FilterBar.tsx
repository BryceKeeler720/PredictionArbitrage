import { useState, useEffect } from "react";
import type { OpportunityFilters } from "../hooks/useApi";

const PLATFORMS = [
  { value: "", label: "All Platforms" },
  { value: "polymarket", label: "Polymarket" },
  { value: "kalshi", label: "Kalshi" },
  { value: "predictit", label: "PredictIt" },
];

const SORT_OPTIONS = [
  { value: "profit_desc", label: "Highest Profit" },
  { value: "profit_asc", label: "Lowest Profit" },
  { value: "size_desc", label: "Largest Size" },
  { value: "cost_asc", label: "Cheapest" },
  { value: "newest", label: "Newest" },
];

interface FilterBarProps {
  filters: OpportunityFilters;
  onChange: (filters: OpportunityFilters) => void;
}

export function FilterBar({ filters, onChange }: FilterBarProps) {
  const [minProfit, setMinProfit] = useState(filters.min_profit?.toString() ?? "");
  const [maxProfit, setMaxProfit] = useState(filters.max_profit?.toString() ?? "");
  const [minLiquidity, setMinLiquidity] = useState(filters.min_liquidity?.toString() ?? "");

  useEffect(() => {
    const timer = setTimeout(() => {
      onChange({
        ...filters,
        min_profit: minProfit ? Number(minProfit) : undefined,
        max_profit: maxProfit ? Number(maxProfit) : undefined,
        min_liquidity: minLiquidity ? Number(minLiquidity) : undefined,
      });
    }, 400);
    return () => clearTimeout(timer);
  }, [minProfit, maxProfit, minLiquidity]);

  const hasFilters = minProfit || maxProfit || minLiquidity || filters.platform;

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Filters</h3>
        {hasFilters && (
          <button
            className="text-xs text-blue-400 hover:text-blue-300"
            onClick={() => {
              setMinProfit("");
              setMaxProfit("");
              setMinLiquidity("");
              onChange({ sort: filters.sort });
            }}
          >
            Clear all
          </button>
        )}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Platform</label>
          <select
            className="w-full rounded-lg bg-gray-800 border border-gray-700 text-sm px-3 py-2 text-gray-200 focus:outline-none focus:border-blue-500"
            value={filters.platform ?? ""}
            onChange={(e) => onChange({ ...filters, platform: e.target.value || undefined })}
          >
            {PLATFORMS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-1">Min Profit %</label>
          <input
            type="number"
            step="0.5"
            min="0"
            placeholder="Any"
            className="w-full rounded-lg bg-gray-800 border border-gray-700 text-sm px-3 py-2 text-gray-200 focus:outline-none focus:border-blue-500"
            value={minProfit}
            onChange={(e) => setMinProfit(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-1">Max Profit %</label>
          <input
            type="number"
            step="1"
            min="0"
            placeholder="Any"
            className="w-full rounded-lg bg-gray-800 border border-gray-700 text-sm px-3 py-2 text-gray-200 focus:outline-none focus:border-blue-500"
            value={maxProfit}
            onChange={(e) => setMaxProfit(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-1">Min Liquidity</label>
          <input
            type="number"
            step="100"
            min="0"
            placeholder="Any"
            className="w-full rounded-lg bg-gray-800 border border-gray-700 text-sm px-3 py-2 text-gray-200 focus:outline-none focus:border-blue-500"
            value={minLiquidity}
            onChange={(e) => setMinLiquidity(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-1">Sort By</label>
          <select
            className="w-full rounded-lg bg-gray-800 border border-gray-700 text-sm px-3 py-2 text-gray-200 focus:outline-none focus:border-blue-500"
            value={filters.sort ?? "profit_desc"}
            onChange={(e) => onChange({ ...filters, sort: e.target.value })}
          >
            {SORT_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
