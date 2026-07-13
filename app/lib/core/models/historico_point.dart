/// Ponto de série temporal usado pelo histórico (TimescaleDB / fallback vazio).
class HistoricoPoint {
  final DateTime time;
  final double pstPct;
  final Map<String, dynamic> payload;

  const HistoricoPoint({
    required this.time,
    required this.pstPct,
    required this.payload,
  });

  factory HistoricoPoint.fromJson(Map<String, dynamic> j) => HistoricoPoint(
        time: DateTime.tryParse(j['time']?.toString() ?? '') ?? DateTime.now(),
        pstPct: double.tryParse(j['pst_pct']?.toString() ?? '0') ?? 0.0,
        payload: Map<String, dynamic>.from(j['payload'] ?? {}),
      );
}
