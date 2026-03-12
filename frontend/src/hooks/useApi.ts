import { useQuery } from "@tanstack/react-query";

const API_BASE = "/api/v1";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface Opportunity {
  id: string;
  match_id: string;
  type: string;
  legs: {
    platform: string;
    market_id: string;
    side: string;
    price: number;
    fee_rate: number;
    effective_cost: number;
    available_size_usd: number;
  }[];
  total_cost: number;
  guaranteed_profit: number;
  profit_after_fees: number;
  profit_pct: number;
  max_size_usd: number;
  status: string;
  detected_at: string;
  description: string;
}

export interface Market {
  id: string;
  platform: string;
  platform_id: string;
  title: string;
  slug: string;
  category: string;
  yes_price: number;
  no_price: number;
  yes_ask: number | null;
  yes_bid: number | null;
  no_ask: number | null;
  no_bid: number | null;
  volume_24h: number;
  liquidity: number;
  open_interest: number | null;
  close_time: string | null;
  last_updated: string;
  source_url: string;
  active: boolean;
}

export interface HealthStatus {
  status: string;
  timestamp: string;
  database: string;
  polymarket: string;
  kalshi: string;
}

export function useOpportunities(status = "active") {
  return useQuery<{ opportunities: Opportunity[] }>({
    queryKey: ["opportunities", status],
    queryFn: () => fetchJson(`/opportunities?status=${status}&limit=100`),
    refetchInterval: 30_000,
  });
}

export function useMarkets(platform?: string, limit = 50, offset = 0) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (platform) params.set("platform", platform);
  return useQuery<{ markets: Market[]; total: number }>({
    queryKey: ["markets", platform, limit, offset],
    queryFn: () => fetchJson(`/markets?${params}`),
    refetchInterval: 60_000,
  });
}

export function useHealth() {
  return useQuery<HealthStatus>({
    queryKey: ["health"],
    queryFn: () => fetchJson("/health"),
    refetchInterval: 30_000,
  });
}
