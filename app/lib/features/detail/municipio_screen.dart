import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_theme.dart';

/// Tela de detalhe por município. Por enquanto, mostra a UF selecionada
/// (o backend ainda não expõe drill-down por município).
class MunicipioScreen extends StatelessWidget {
  final String uf;
  final String cargo;
  final String municipio;

  const MunicipioScreen({
    super.key,
    required this.uf,
    required this.cargo,
    required this.municipio,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('$municipio · ${uf.toUpperCase()}'),
        leading: IconButton(icon: const Icon(Icons.arrow_back), onPressed: () => context.pop()),
      ),
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('🏙️', style: TextStyle(fontSize: 56)),
              SizedBox(height: 12),
              Text(
                'Drill-down por município\n(em breve — depende do backend)',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppColors.textDim),
              ),
            ],
          ),
        ),
      ),
    );
  }
}