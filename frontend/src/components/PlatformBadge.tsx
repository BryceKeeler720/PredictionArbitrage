const PLATFORM_COLORS: Record<string, string> = {
  polymarket: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  kalshi: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  predictit: "bg-green-500/20 text-green-300 border-green-500/30",
  manifold: "bg-orange-500/20 text-orange-300 border-orange-500/30",
};

export function PlatformBadge({ platform }: { platform: string }) {
  const colors = PLATFORM_COLORS[platform] ?? "bg-gray-500/20 text-gray-300 border-gray-500/30";
  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded border ${colors}`}>
      {platform}
    </span>
  );
}
