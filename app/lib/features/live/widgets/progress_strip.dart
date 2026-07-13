import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';

/// Barra de progresso fina estilo UOL (% de seções apuradas).
class ProgressStrip extends StatelessWidget {
  final double pct; // 0.0 a 100.0
  const ProgressStrip({super.key, required this.pct});

  @override
  Widget build(BuildContext context) {
    final clamped = pct.clamp(0.0, 100.0);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Seções apuradas',
                  style: TextStyle(color: AppColors.textDim, fontSize: 13)),
              Text('${clamped.toStringAsFixed(2)}%',
                  style: const TextStyle(
                      color: AppColors.muted, fontSize: 13, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: clamped / 100.0,
              minHeight: 6,
              backgroundColor: AppColors.border,
              valueColor: const AlwaysStoppedAnimation<Color>(AppColors.primary),
            ),
          ),
        ],
      ),
    );
  }
}