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
    cost_fraction: number;
    source_url: string;
  }[];
  total_cost: number;
  guaranteed_profit: number;
  profit_after_fees: number;
  profit_pct: number;
  max_size_usd: number;
  status: string;
  detected_at: string;
  expires_at: string | null;
  description: string;
  match_confidence: number;
}

export interface OpportunityFilters {
  min_profit?: number;
  max_profit?: number;
  platform?: string;
  min_liquidity?: number;
  sort?: string;
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
  manifold: string;
}

export function useOpportunities(status = "active", filters?: OpportunityFilters) {
  const params = new URLSearchParams({ status, limit: "200" });
  if (filters?.min_profit != null) params.set("min_profit", String(filters.min_profit));
  if (filters?.max_profit != null) params.set("max_profit", String(filters.max_profit));
  if (filters?.platform) params.set("platform", filters.platform);
  if (filters?.min_liquidity != null) params.set("min_liquidity", String(filters.min_liquidity));
  if (filters?.sort) params.set("sort", filters.sort);

  return useQuery<{ opportunities: Opportunity[]; total: number }>({
    queryKey: ["opportunities", status, filters],
    queryFn: () => fetchJson(`/opportunities?${params}`),
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
