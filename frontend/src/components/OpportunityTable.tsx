import { useState } from "react";
import type { Opportunity } from "../hooks/useApi";
import { PlatformBadge } from "./PlatformBadge";

function ProfitBadge({ pct }: { pct: number }) {
  let color = "text-green-400";
  if (pct >= 20) color = "text-orange-400 font-bold";
  else if (pct >= 10) color = "text-yellow-400 font-semibold";
  else if (pct >= 5) color = "text-green-300 font-semibold";
  return <span className={color}>{pct.toFixed(2)}%</span>;
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = (confidence * 100).toFixed(0);
  let color = "text-gray-500";
  if (confidence >= 0.9) color = "text-green-400";
  else if (confidence >= 0.7) color = "text-yellow-400";
  else if (confidence >= 0.5) color = "text-orange-400";
  else color = "text-red-400";
  return <span className={`text-xs font-medium ${color}`}>{pct}%</span>;
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

function formatExpiry(iso: string | null): { text: string; urgent: boolean } {
  if (!iso) return { text: "\u2014", urgent: false };
  const d = new Date(iso);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  if (diffMs <= 0) return { text: "Expired", urgent: true };
  const days = Math.floor(diffMs / 86_400_000);
  const hours = Math.floor((diffMs % 86_400_000) / 3_600_000);
  if (days > 30) return { text: `${Math.floor(days / 30)}mo`, urgent: false };
  if (days > 0) return { text: `${days}d ${hours}h`, urgent: days <= 3 };
  if (hours > 0) return { text: `${hours}h`, urgent: true };
  const mins = Math.floor(diffMs / 60_000);
  return { text: `${mins}m`, urgent: true };
}

function formatUSD(amount: number): string {
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(1)}K`;
  if (amount >= 100) return `$${amount.toFixed(0)}`;
  return `$${amount.toFixed(2)}`;
}

interface SortConfig {
  key: string;
  dir: "asc" | "desc";
}

const QUICK_AMOUNTS = [50, 100, 500, 1000, 5000];

export function OpportunityTable({ opportunities }: { opportunities: Opportunity[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [sortConfig, setSortConfig] = useState<SortConfig>({ key: "profit_pct", dir: "desc" });
  const [investAmount, setInvestAmount] = useState<number>(100);

  const sorted = [...opportunities].sort((a, b) => {
    const dir = sortConfig.dir === "asc" ? 1 : -1;
    switch (sortConfig.key) {
      case "profit_pct": return (a.profit_pct - b.profit_pct) * dir;
      case "total_cost": return (a.total_cost - b.total_cost) * dir;
      case "max_size_usd": return (a.max_size_usd - b.max_size_usd) * dir;
      case "match_confidence": return ((a.match_confidence ?? 0) - (b.match_confidence ?? 0)) * dir;
      case "expires_at": {
        const ea = a.expires_at ? new Date(a.expires_at).getTime() : Infinity;
        const eb = b.expires_at ? new Date(b.expires_at).getTime() : Infinity;
        return (ea - eb) * dir;
      }
      case "detected_at": return (new Date(a.detected_at).getTime() - new Date(b.detected_at).getTime()) * dir;
      default: return 0;
    }
  });

  function handleSort(key: string) {
    setSortConfig((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "desc" }
    );
  }

  function SortHeader({ label, sortKey, align }: { label: string; sortKey: string; align?: string }) {
    const active = sortConfig.key === sortKey;
    const arrow = active ? (sortConfig.dir === "asc" ? " \u25B2" : " \u25BC") : "";
    return (
      <th
        className={`py-3 px-4 cursor-pointer hover:text-gray-200 select-none whitespace-nowrap ${align ?? "text-left"}`}
        onClick={() => handleSort(sortKey)}
      >
        {label}{active && <span className="text-blue-400">{arrow}</span>}
      </th>
    );
  }

  if (opportunities.length === 0) {
    return (
      <div className="text-center text-gray-500 py-12">
        No arbitrage opportunities match your filters.
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
            <SortHeader label="Cost" sortKey="total_cost" align="text-right" />
            <SortHeader label="Profit" sortKey="profit_pct" align="text-right" />
            <SortHeader label="Max Size" sortKey="max_size_usd" align="text-right" />
            <SortHeader label="Match" sortKey="match_confidence" align="text-right" />
            <SortHeader label="Expires" sortKey="expires_at" align="text-right" />
            <SortHeader label="Detected" sortKey="detected_at" align="text-right" />
          </tr>
        </thead>
        <tbody>
          {sorted.map((opp) => {
            const isExpanded = expanded === opp.id;
            return (
              <>
                <tr
                  key={opp.id}
                  className={`border-b border-gray-800/50 hover:bg-gray-900/50 cursor-pointer transition-colors ${isExpanded ? "bg-gray-900/50" : ""}`}
                  onClick={() => setExpanded(isExpanded ? null : opp.id)}
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
                    {opp.max_size_usd > 0 ? formatUSD(opp.max_size_usd) : "\u2014"}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <ConfidenceBadge confidence={opp.match_confidence ?? 0} />
                  </td>
                  <td className="py-3 px-4 text-right">
                    {(() => {
                      const exp = formatExpiry(opp.expires_at);
                      return <span className={exp.urgent ? "text-red-400" : "text-gray-400"}>{exp.text}</span>;
                    })()}
                  </td>
                  <td className="py-3 px-4 text-right text-gray-400">
                    {formatTime(opp.detected_at)}
                  </td>
                </tr>
                {isExpanded && (
                  <tr key={`${opp.id}-detail`} className="bg-gray-900/40">
                    <td colSpan={8} className="px-4 py-5">
                      <ExpandedDetail opp={opp} investAmount={investAmount} setInvestAmount={setInvestAmount} />
                    </td>
                  </tr>
                )}
              </>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ExpandedDetail({
  opp,
  investAmount,
  setInvestAmount,
}: {
  opp: Opportunity;
  investAmount: number;
  setInvestAmount: (n: number) => void;
}) {
  const contractsPerDollar = 1 / opp.total_cost;
  const numContracts = investAmount * contractsPerDollar;
  const totalPayout = numContracts;
  const totalProfit = totalPayout - investAmount;
  const exceedsLiquidity = opp.max_size_usd > 0 && investAmount > opp.max_size_usd;

  return (
    <div className="space-y-4 max-w-4xl">
      {/* Per-$1 contract breakdown */}
      <div>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Per $1 Contract
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {opp.legs.map((leg, i) => (
            <div key={i} className="rounded-lg bg-gray-800/60 border border-gray-700/50 p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-gray-500">Leg {i + 1}</span>
                  <PlatformBadge platform={leg.platform} />
                </div>
                {leg.source_url && (
                  <a
                    href={leg.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-400 hover:text-blue-300 underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    View on {leg.platform}
                  </a>
                )}
              </div>
              <div className="text-lg font-mono">
                Buy{" "}
                <span className={leg.side === "YES" ? "text-green-400 font-bold" : "text-red-400 font-bold"}>
                  {leg.side}
                </span>{" "}
                @ <span className="text-white">${leg.price.toFixed(3)}</span>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <span className="text-gray-500">Effective cost:</span>
                <span className="text-gray-300 font-mono">${leg.effective_cost.toFixed(4)}</span>
                <span className="text-gray-500">Platform fee:</span>
                <span className="text-gray-300 font-mono">{(leg.fee_rate * 100).toFixed(1)}%</span>
                <span className="text-gray-500">Share of cost:</span>
                <span className="text-gray-300 font-mono">
                  {((leg.cost_fraction || 1 / opp.legs.length) * 100).toFixed(0)}%
                </span>
                {leg.available_size_usd > 0 && (
                  <>
                    <span className="text-gray-500">Depth:</span>
                    <span className="text-gray-300 font-mono">{formatUSD(leg.available_size_usd)}</span>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-500">
          <span>
            Total cost per contract: <span className="text-white font-mono">${opp.total_cost.toFixed(4)}</span>
          </span>
          <span>
            Guaranteed payout: <span className="text-white font-mono">$1.00</span>
          </span>
          <span>
            Profit per contract: <span className="text-green-400 font-mono">${opp.profit_after_fees.toFixed(4)}</span>
          </span>
          <span>
            Match quality: <ConfidenceBadge confidence={opp.match_confidence ?? 0} />
          </span>
        </div>
      </div>

      {/* Investment calculator */}
      <div className="rounded-lg bg-gradient-to-r from-blue-900/20 to-purple-900/20 border border-blue-800/30 p-4">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Investment Calculator
        </h3>

        <div className="flex flex-wrap items-center gap-3 mb-4" onClick={(e) => e.stopPropagation()}>
          <label className="text-sm text-gray-400">Invest:</label>
          <div className="flex items-center">
            <span className="text-gray-400 mr-1">$</span>
            <input
              type="number"
              min="1"
              step="10"
              className="w-28 rounded bg-gray-800 border border-gray-600 text-sm px-3 py-1.5 text-white font-mono focus:outline-none focus:border-blue-500"
              value={investAmount}
              onChange={(e) => setInvestAmount(Math.max(1, Number(e.target.value)))}
            />
          </div>
          <div className="flex gap-1.5">
            {QUICK_AMOUNTS.map((amt) => (
              <button
                key={amt}
                className={`px-2.5 py-1 rounded text-xs border transition-colors ${
                  investAmount === amt
                    ? "bg-blue-600 border-blue-500 text-white"
                    : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500"
                }`}
                onClick={() => setInvestAmount(amt)}
              >
                ${amt >= 1000 ? `${amt / 1000}K` : amt}
              </button>
            ))}
          </div>
        </div>

        {/* Results grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {opp.legs.map((leg, i) => {
            const legDollars = investAmount * (leg.cost_fraction || 1 / opp.legs.length);
            const legContracts = legDollars / leg.effective_cost;
            return (
              <div key={i} className="rounded bg-gray-800/50 p-3">
                <div className="text-xs text-gray-500 mb-1">
                  Leg {i + 1} &middot; {leg.platform}
                </div>
                <div className="text-lg font-mono text-blue-300">
                  {formatUSD(legDollars)}
                </div>
                <div className="text-xs text-gray-500">
                  Buy {leg.side} &middot; ~{legContracts.toFixed(0)} contracts
                </div>
              </div>
            );
          })}

          <div className="rounded bg-gray-800/50 p-3">
            <div className="text-xs text-gray-500 mb-1">Guaranteed Payout</div>
            <div className="text-lg font-mono text-white">
              {formatUSD(totalPayout)}
            </div>
            <div className="text-xs text-gray-500">
              {numContracts.toFixed(0)} contracts @ $1
            </div>
          </div>

          <div className="rounded bg-green-900/30 border border-green-800/30 p-3">
            <div className="text-xs text-gray-500 mb-1">Net Profit</div>
            <div className="text-lg font-mono text-green-400">
              +{formatUSD(totalProfit)}
            </div>
            <div className="text-xs text-green-600">
              {opp.profit_pct.toFixed(1)}% return
            </div>
          </div>
        </div>

        {exceedsLiquidity && (
          <div className="mt-2 text-xs text-red-400">
            Warning: Investment exceeds available liquidity ({formatUSD(opp.max_size_usd)})
          </div>
        )}
      </div>
    </div>
  );
}
