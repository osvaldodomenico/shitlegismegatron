import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';

/// Breadcrumb estilo UOL: "Eleições 2026 › Apuração › 1º turno › São Paulo › Governador"
class ElectionHeader extends StatelessWidget {
  final String uf;
  final String cargo;

  const ElectionHeader({super.key, required this.uf, required this.cargo});

  @override
  Widget build(BuildContext context) {
    final ufLabel = _ufLabel(uf);
    final cargoLabel = _cargoLabel(cargo);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Text.rich(
        TextSpan(
          children: [
            const TextSpan(text: 'Eleições 2026 › Apuração › 1º turno › '),
            TextSpan(
              text: ufLabel,
              style: const TextStyle(color: AppColors.muted, fontWeight: FontWeight.w600),
            ),
            const TextSpan(text: ' › '),
            TextSpan(
              text: cargoLabel,
              style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.w600),
            ),
          ],
          style: const TextStyle(color: AppColors.textDim, fontSize: 13),
        ),
      ),
    );
  }

  static String _ufLabel(String uf) {
    const labels = {
      'sp': 'São Paulo', 'rj': 'Rio de Janeiro', 'mg': 'Minas Gerais',
      'rs': 'Rio Grande do Sul', 'ba': 'Bahia', 'pr': 'Paraná',
      'pe': 'Pernambuco', 'ce': 'Ceará', 'pa': 'Pará',
      'sc': 'Santa Catarina', 'br': 'Brasil',
    };
    return labels[uf] ?? uf.toUpperCase();
  }

  static String _cargoLabel(String cargo) {
    const labels = {
      'presidente': 'Presidente', 'governador': 'Governador',
      'senador': 'Senador',
      'dep_federal': 'Deputado Federal', 'dep_estadual': 'Deputado Estadual',
    };
    return labels[cargo] ?? cargo;
  }
}