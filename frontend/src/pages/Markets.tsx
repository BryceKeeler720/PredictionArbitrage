import { useState } from "react";
import { useMarkets } from "../hooks/useApi";
import { PlatformBadge } from "../components/PlatformBadge";

const PLATFORMS = ["all", "polymarket", "kalshi", "predictit"];

export function Markets() {
  const [platform, setPlatform] = useState("all");
  const [page, setPage] = useState(0);
  const limit = 50;

  const { data, isLoading } = useMarkets(
    platform === "all" ? undefined : platform,
    limit,
    page * limit
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Market Explorer</h1>
        <p className="text-sm text-gray-400 mt-1">
          Browse all tracked prediction markets across platforms
        </p>
      </div>

      {/* Platform filter */}
      <div className="flex gap-2">
        {PLATFORMS.map((p) => (
          <button
            key={p}
            onClick={() => { setPlatform(p); setPage(0); }}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              platform === p
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {p === "all" ? "All Platforms" : p}
          </button>
        ))}
      </div>

      {/* Markets table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50">
        {isLoading ? (
          <div className="py-12 text-center text-gray-500">Loading markets...</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 text-gray-400 text-left">
                    <th className="py-3 px-4">Platform</th>
                    <th className="py-3 px-4">Title</th>
                    <th className="py-3 px-4 text-right">YES</th>
                    <th className="py-3 px-4 text-right">NO</th>
                    <th className="py-3 px-4 text-right">Volume 24h</th>
                    <th className="py-3 px-4 text-right">Close</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.markets.map((m) => (
                    <tr key={m.id} className="border-b border-gray-800/50 hover:bg-gray-900/50">
                      <td className="py-2.5 px-4">
                        <PlatformBadge platform={m.platform} />
                      </td>
                      <td className="py-2.5 px-4 max-w-lg">
                        <a
                          href={m.source_url || "#"}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:text-blue-400 transition-colors"
                        >
                          {m.title.length > 80 ? m.title.slice(0, 80) + "..." : m.title}
                        </a>
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-green-400">
                        {m.yes_price > 0 ? `${(m.yes_price * 100).toFixed(1)}¢` : "—"}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-red-400">
                        {m.no_price > 0 ? `${(m.no_price * 100).toFixed(1)}¢` : "—"}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-gray-400">
                        {m.volume_24h > 0 ? `$${m.volume_24h.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "—"}
                      </td>
                      <td className="py-2.5 px-4 text-right text-gray-400">
                        {m.close_time ? new Date(m.close_time).toLocaleDateString() : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
              <span className="text-xs text-gray-500">
                {data?.total ?? 0} total markets
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(Math.max(0, page - 1))}
                  disabled={page === 0}
                  className="px-3 py-1 rounded bg-gray-800 text-sm disabled:opacity-30"
                >
                  Prev
                </button>
                <span className="text-sm text-gray-400 px-2 py-1">
                  Page {page + 1}
                </span>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={(data?.markets.length ?? 0) < limit}
                  className="px-3 py-1 rounded bg-gray-800 text-sm disabled:opacity-30"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
