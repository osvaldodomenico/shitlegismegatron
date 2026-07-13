import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/models/candidato.dart';
import '../../core/theme/app_theme.dart';
import 'live_provider.dart';
import 'widgets/candidato_tile.dart';
import 'widgets/election_header.dart';
import 'widgets/filter_bar.dart';
import 'widgets/historico_chart.dart';
import 'widgets/progress_strip.dart';
import 'widgets/status_badge.dart';

/// Tela principal — espelha o App.jsx do React com layout estilo UOL.
class LiveScreen extends ConsumerWidget {
  const LiveScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final snap = ref.watch(liveSnapshotProvider);
    final historicoAsync = ref.watch(historicoProvider);
    final uf = ref.watch(selectedUfProvider);
    final cargo = ref.watch(selectedCargoProvider);

    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('🗳️ '),
            const Text('MEGATRON',
                style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1.2,
                    color: AppColors.primary)),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.star_border),
            onPressed: () => context.push('/favoritos'),
            tooltip: 'Favoritos',
          ),
        ],
      ),
      body: snap.when(
        loading: () => const _Aguardando(),
        error: (e, _) => _Erro(message: '$e'),
        data: (s) => _buildContent(context, ref, s, uf, cargo, historicoAsync),
      ),
    );
  }

  Widget _buildContent(
    BuildContext context,
    WidgetRef ref,
    Snapshot s,
    String uf,
    String cargo,
    AsyncValue<List<dynamic>> historicoAsync,
  ) {
    final cands = s.todosCandidatos;
    final maxVotos = cands.isEmpty
        ? 1.0
        : cands.map((c) => c.votos.toDouble()).reduce((a, b) => a > b ? a : b);

    return Column(
      children: [
        const FilterBar(),
        const ElectionHeader(uf: '', cargo: ''), // dinâmico abaixo
        _Meta(snapshot: s),
        const SizedBox(height: 4),
        ProgressStrip(pct: s.pstPct),
        const SizedBox(height: 4),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            children: [
              StatusBadge(connected: ref.watch(electionSocketProvider).valueOrNull?.isConnected ?? false, simulando: s.unidades.isNotEmpty && s.unidades.first.nm.contains('SIMULADO')),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.favorite_border, color: AppColors.textDim),
                tooltip: 'Favoritar',
                onPressed: () => ref.read(favoritesControllerProvider.notifier).toggle(uf, cargo, s),
              ),
            ],
          ),
        ),
        const Divider(height: 1, color: AppColors.border),
        Expanded(
          child: cands.isEmpty
              ? const _Aguardando()
              : ListView.builder(
                  itemCount: cands.length,
                  itemBuilder: (_, i) => CandidatoTile(
                    rank: i + 1,
                    candidato: cands[i],
                    maxVotos: maxVotos,
                  ),
                ),
        ),
        historicoAsync.when(
          data: (pts) => Container(
            color: AppColors.surface,
            child: HistoricoChart(pontos: pts.cast()),
          ),
          loading: () => const SizedBox(height: 100, child: Center(child: CircularProgressIndicator())),
          error: (_, __) => const SizedBox.shrink(),
        ),
      ],
    );
  }
}

class _Meta extends ConsumerWidget {
  final Snapshot snapshot;
  const _Meta({required this.snapshot});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final uf = ref.watch(selectedUfProvider);
    final unidade = snapshot.unidades.isNotEmpty ? snapshot.unidades.first : null;
    final nome = unidade?.nm ?? uf.toUpperCase();
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        children: [
          Expanded(
            child: Text(nome,
                style: const TextStyle(color: AppColors.textDim, fontSize: 13)),
          ),
          Text('Atualizado às ${snapshot.hor}',
              style: const TextStyle(color: AppColors.textDim, fontSize: 12)),
        ],
      ),
    );
  }
}

class _Aguardando extends StatelessWidget {
  const _Aguardando();
  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('🗳️', style: TextStyle(fontSize: 56)),
          SizedBox(height: 12),
          Text('Aguardando dados de apuração...',
              style: TextStyle(color: AppColors.textDim)),
        ],
      ),
    );
  }
}

class _Erro extends StatelessWidget {
  final String message;
  const _Erro({required this.message});
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text('Erro: $message',
            style: const TextStyle(color: Color(0xFFFCA5A5)),
            textAlign: TextAlign.center),
      ),
    );
  }
}