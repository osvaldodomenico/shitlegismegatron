import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/constants/cargos.dart';
import '../../core/constants/ufs.dart';
import '../../core/theme/app_theme.dart';
import '../live/live_provider.dart';

class FavoritesScreen extends ConsumerWidget {
  const FavoritesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final favsAsync = ref.watch(favoritosProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('⭐ Favoritos'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: favsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Erro: $e')),
        data: (favs) {
          if (favs.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Nenhum favorito ainda.\nToque no ❤️ na tela de apuração para adicionar.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.textDim),
                ),
              ),
            );
          }
          return ListView.separated(
            itemCount: favs.length,
            separatorBuilder: (_, __) => const Divider(color: AppColors.border, height: 1),
            itemBuilder: (_, i) {
              final f = favs[i];
              final lastSnap = f.lastSnapshot;
              final fmt = DateFormat('dd/MM HH:mm', 'pt_BR');
              return ListTile(
                title: Text(
                  '${Ufs.label(f.uf)} · ${Cargos.label(f.cargo)}',
                  style: const TextStyle(color: AppColors.muted, fontWeight: FontWeight.w500),
                ),
                subtitle: Text(
                  lastSnap != null
                      ? 'Apurado: ${lastSnap.pst} · visto ${fmt.format(f.lastSeenAt)}'
                      : 'Visto ${fmt.format(f.lastSeenAt)}',
                  style: const TextStyle(color: AppColors.textDim, fontSize: 12),
                ),
                trailing: IconButton(
                  icon: const Icon(Icons.delete_outline, color: AppColors.textDim),
                  onPressed: () =>
                      ref.read(favoritesControllerProvider.notifier).toggle(f.uf, f.cargo, null),
                ),
                onTap: () {
                  ref.read(selectedUfProvider.notifier).state = f.uf;
                  ref.read(selectedCargoProvider.notifier).state = f.cargo;
                  context.go('/');
                },
              );
            },
          );
        },
      ),
    );
  }
}