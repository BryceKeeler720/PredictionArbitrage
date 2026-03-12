import { useState } from "react";
import type { Opportunity } from "../hooks/useApi";
import { PlatformBadge } from "./PlatformBadge";

function ProfitBadge({ pct }: { pct: number }) {
  let color = "text-green-400";
  if (pct >= 5) color = "text-red-400 font-bold";
  else if (pct >= 3) color = "text-yellow-400 font-semibold";
  return <span className={color}>{pct.toFixed(2)}%</span>;
}

function formatTime(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diff = (now.getTime() - d.getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return d.toLocaleDateString();
}

export function OpportunityTable({ opportunities }: { opportunities: Opportunity[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (opportunities.length === 0) {
    return (
      <div className="text-center text-gray-500 py-12">
        No arbitrage opportunities detected yet. The scanner is running — check back soon.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800 text-gray-400 text-left">
            <th className="py-3 px-4">Question</th>
            <th className="py-3 px-4">Platforms</th>
            <th className="py-3 px-4 text-right">Cost</th>
            <th className="py-3 px-4 text-right">Profit</th>
            <th className="py-3 px-4 text-right">Max Size</th>
            <th className="py-3 px-4 text-right">Detected</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((opp) => (
            <>
              <tr
                key={opp.id}
                className="border-b border-gray-800/50 hover:bg-gray-900/50 cursor-pointer transition-colors"
                onClick={() => setExpanded(expanded === opp.id ? null : opp.id)}
              >
                <td className="py-3 px-4 max-w-md truncate">{opp.description}</td>
                <td className="py-3 px-4">
                  <div className="flex gap-1">
                    {opp.legs.map((leg, i) => (
                      <PlatformBadge key={i} platform={leg.platform} />
                    ))}
                  </div>
                </td>
                <td className="py-3 px-4 text-right font-mono">
                  ${opp.total_cost.toFixed(4)}
                </td>
                <td className="py-3 px-4 text-right">
                  <ProfitBadge pct={opp.profit_pct} />
                </td>
                <td className="py-3 px-4 text-right font-mono">
                  {opp.max_size_usd > 0 ? `$${opp.max_size_usd.toLocaleString()}` : "—"}
                </td>
                <td className="py-3 px-4 text-right text-gray-400">
                  {formatTime(opp.detected_at)}
                </td>
              </tr>
              {expanded === opp.id && (
                <tr key={`${opp.id}-detail`} className="bg-gray-900/30">
                  <td colSpan={6} className="px-4 py-4">
                    <div className="grid grid-cols-2 gap-4 max-w-2xl">
                      {opp.legs.map((leg, i) => (
                        <div key={i} className="rounded-lg bg-gray-800/50 p-3">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-medium text-gray-400">Leg {i + 1}</span>
                            <PlatformBadge platform={leg.platform} />
                          </div>
                          <div className="text-lg font-mono">
                            Buy <span className={leg.side === "YES" ? "text-green-400" : "text-red-400"}>{leg.side}</span> @ ${leg.price.toFixed(3)}
                          </div>
                          <div className="text-xs text-gray-400 mt-1">
                            Effective: ${leg.effective_cost.toFixed(4)} &middot; Fee: {(leg.fee_rate * 100).toFixed(1)}%
                            {leg.available_size_usd > 0 && ` · Depth: $${leg.available_size_usd.toLocaleString()}`}
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 text-xs text-gray-500">
                      Raw profit: ${opp.guaranteed_profit.toFixed(4)} &middot; After fees: ${opp.profit_after_fees.toFixed(4)}
                    </div>
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}
