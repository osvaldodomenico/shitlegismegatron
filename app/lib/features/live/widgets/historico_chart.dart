import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/models/historico_point.dart';
import '../../../core/theme/app_theme.dart';

/// LineChart da evolução temporal da % apurada.
class HistoricoChart extends StatelessWidget {
  final List<HistoricoPoint> pontos;
  const HistoricoChart({super.key, required this.pontos});

  @override
  Widget build(BuildContext context) {
    if (pontos.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Text('Sem histórico disponível',
            style: TextStyle(color: AppColors.textDim, fontSize: 13)),
      );
    }
    // API retorna DESC; gráfico precisa ASC.
    final ordem = pontos.reversed.toList();
    final spots = <FlSpot>[];
    for (var i = 0; i < ordem.length; i++) {
      spots.add(FlSpot(i.toDouble(), ordem[i].pstPct));
    }
    final fmt = DateFormat('HH:mm');
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('📈 Evolução da apuração',
              style: TextStyle(
                  color: AppColors.muted, fontSize: 14, fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          SizedBox(
            height: 160,
            child: LineChart(
              LineChartData(
                gridData: const FlGridData(show: false),
                titlesData: FlTitlesData(
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 32,
                      getTitlesWidget: (v, _) => Text('${v.toInt()}%',
                          style: const TextStyle(color: AppColors.textDim, fontSize: 10)),
                    ),
                  ),
                  rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 22,
                      interval: (ordem.length / 4).clamp(1, double.infinity).toDouble(),
                      getTitlesWidget: (v, _) {
                        final i = v.toInt();
                        if (i < 0 || i >= ordem.length) return const SizedBox.shrink();
                        return Text(fmt.format(ordem[i].time),
                            style: const TextStyle(color: AppColors.textDim, fontSize: 10));
                      },
                    ),
                  ),
                ),
                borderData: FlBorderData(show: false),
                minY: 0,
                maxY: 100,
                lineBarsData: [
                  LineChartBarData(
                    spots: spots,
                    isCurved: true,
                    color: AppColors.primary,
                    barWidth: 2,
                    dotData: const FlDotData(show: false),
                    belowBarData: BarAreaData(
                      show: true,
                      color: AppColors.primary.withValues(alpha: 0.15),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}