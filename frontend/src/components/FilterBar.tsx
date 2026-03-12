import { useState, useEffect } from "react";
import type { OpportunityFilters } from "../hooks/useApi";

const PLATFORMS = [
  { value: "", label: "All Platforms" },
  { value: "polymarket", label: "Polymarket" },
  { value: "kalshi", label: "Kalshi" },
  { value: "predictit", label: "PredictIt" },
];

const SORT_OPTIONS = [
  { value: "profit_desc", label: "Profit % (High to Low)" },
  { value: "profit_asc", label: "Profit % (Low to High)" },
  { value: "size_desc", label: "Max Size (Largest)" },
  { value: "cost_asc", label: "Cost (Cheapest)" },
  { value: "newest", label: "Newest First" },
];

interface FilterBarProps {
  filters: OpportunityFilters;
  onChange: (filters: OpportunityFilters) => void;
}

export function FilterBar({ filters, onChange }: FilterBarProps) {
  const [minProfit, setMinProfit] = useState(filters.min_profit?.toString() ?? "");
  const [maxProfit, setMaxProfit] = useState(filters.max_profit?.toString() ?? "");
  const [minLiquidity, setMinLiquidity] = useState(filters.min_liquidity?.toString() ?? "");

  // Debounce numeric inputs
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

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg bg-gray-900/50 border border-gray-800 px-4 py-3">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-400">Platform</label>
        <select
          className="rounded bg-gray-800 border border-gray-700 text-sm px-2 py-1.5 text-gray-200 focus:outline-none focus:border-blue-500"
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

      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-400">Min Profit %</label>
        <input
          type="number"
          step="0.5"
          min="0"
          placeholder="0"
          className="w-20 rounded bg-gray-800 border border-gray-700 text-sm px-2 py-1.5 text-gray-200 focus:outline-none focus:border-blue-500"
          value={minProfit}
          onChange={(e) => setMinProfit(e.target.value)}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-400">Max Profit %</label>
        <input
          type="number"
          step="1"
          min="0"
          placeholder="No max"
          className="w-20 rounded bg-gray-800 border border-gray-700 text-sm px-2 py-1.5 text-gray-200 focus:outline-none focus:border-blue-500"
          value={maxProfit}
          onChange={(e) => setMaxProfit(e.target.value)}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-400">Min Liquidity $</label>
        <input
          type="number"
          step="100"
          min="0"
          placeholder="0"
          className="w-24 rounded bg-gray-800 border border-gray-700 text-sm px-2 py-1.5 text-gray-200 focus:outline-none focus:border-blue-500"
          value={minLiquidity}
          onChange={(e) => setMinLiquidity(e.target.value)}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-400">Sort By</label>
        <select
          className="rounded bg-gray-800 border border-gray-700 text-sm px-2 py-1.5 text-gray-200 focus:outline-none focus:border-blue-500"
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

      {(minProfit || maxProfit || minLiquidity || filters.platform) && (
        <button
          className="text-xs text-gray-400 hover:text-white underline py-1.5"
          onClick={() => {
            setMinProfit("");
            setMaxProfit("");
            setMinLiquidity("");
            onChange({ sort: filters.sort });
          }}
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
