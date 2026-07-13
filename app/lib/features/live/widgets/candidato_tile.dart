import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/models/candidato.dart';
import '../../../core/theme/app_theme.dart';

/// Tile de candidato (padrão UOL: avatar, nome, partido, votos, %, status).
class CandidatoTile extends StatelessWidget {
  final int rank;
  final Candidato candidato;
  final double maxVotos;
  const CandidatoTile({
    super.key,
    required this.rank,
    required this.candidato,
    required this.maxVotos,
  });

  Color get _statusColor {
    switch (candidato.e) {
      case 'Eleito':
        return const Color(0xFF86EFAC);
      case 'Não eleito':
        return AppColors.textDim;
      case '2º turno':
        return const Color(0xFFFCD34D);
      default:
        return AppColors.textDim;
    }
  }

  @override
  Widget build(BuildContext context) {
    final barWidth = maxVotos > 0 ? (candidato.votos / maxVotos) : 0.0;
    final fmt = NumberFormat.decimalPattern('pt_BR');
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.border, width: 0.5)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          // Avatar (iniciais)
          CircleAvatar(
            radius: 20,
            backgroundColor: AppColors.border,
            child: Text(candidato.iniciais,
                style: const TextStyle(
                    color: AppColors.muted, fontWeight: FontWeight.bold, fontSize: 13)),
          ),
          const SizedBox(width: 12),
          // Rank
          SizedBox(
            width: 22,
            child: Text('$rank',
                style: const TextStyle(
                    color: AppColors.textDim, fontSize: 14, fontWeight: FontWeight.w500)),
          ),
          // Nome + partido
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(candidato.nm,
                    style: const TextStyle(
                        color: AppColors.muted, fontSize: 14, fontWeight: FontWeight.w500),
                    overflow: TextOverflow.ellipsis),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Text(candidato.sg,
                        style: const TextStyle(color: AppColors.textDim, fontSize: 11)),
                    Text(' · nº ${candidato.n}',
                        style: const TextStyle(color: AppColors.textDim, fontSize: 11)),
                  ],
                ),
                const SizedBox(height: 6),
                // Barra de progresso inline
                Stack(
                  children: [
                    Container(
                      height: 4,
                      decoration: BoxDecoration(
                        color: AppColors.border,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                    FractionallySizedBox(
                      widthFactor: barWidth,
                      child: Container(
                        height: 4,
                        decoration: BoxDecoration(
                          color: AppColors.primary,
                          borderRadius: BorderRadius.circular(2),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          // Votos + %
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(fmt.format(candidato.votos),
                  style: const TextStyle(
                      color: AppColors.muted, fontSize: 13, fontWeight: FontWeight.w600)),
              const SizedBox(height: 2),
              Text('${candidato.pct.toStringAsFixed(2)}%',
                  style: const TextStyle(color: AppColors.primary, fontSize: 12)),
            ],
          ),
          const SizedBox(width: 12),
          // Status (badge à direita)
          if (candidato.e.isNotEmpty)
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(color: _statusColor, shape: BoxShape.circle),
            ),
        ],
      ),
    );
  }
}