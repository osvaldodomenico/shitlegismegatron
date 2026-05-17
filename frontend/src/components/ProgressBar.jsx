export function ProgressBar({ pst }) {
  const pct = parseFloat(pst?.replace("%", "") || 0);
  return (
    <div className="mb-6">
      <div className="flex justify-between text-sm text-gray-400 mb-1">
        <span>Seções apuradas</span>
        <span className="text-white font-bold">{pct.toFixed(2)}%</span>
      </div>
      <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden">
        <div
          className="h-3 bg-primary rounded-full transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
