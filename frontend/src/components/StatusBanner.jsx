export function StatusBanner({ connected, mode }) {
  if (mode === "sim") return (
    <span className="px-3 py-1 rounded-full bg-yellow-900 text-yellow-300 text-sm font-medium">
      🟡 Simulando
    </span>
  );
  return connected ? (
    <span className="px-3 py-1 rounded-full bg-green-900 text-green-300 text-sm font-medium">
      🟢 Ao Vivo
    </span>
  ) : (
    <span className="px-3 py-1 rounded-full bg-red-900 text-red-300 text-sm font-medium">
      🔴 Desconectado
    </span>
  );
}
