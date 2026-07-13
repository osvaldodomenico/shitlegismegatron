import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/election_socket.dart';
import '../../core/models/candidato.dart';
import '../../core/models/historico_point.dart';
import '../../core/storage/favorites_repository.dart';

/// servico do cliente HTTP (AsyncValue<ApiClient>).
final apiClientProvider = FutureProvider<ApiClient>((ref) async {
  return ApiClient();
});

/// servico do socket de eleicao (singleton).
final electionSocketProvider = FutureProvider<ElectionSocket>((ref) async {
  final socket = ElectionSocket();
  ref.onDispose(socket.dispose);
  return socket;
});

/// servico do repositorio de favoritos.
final favoritesRepositoryProvider = FutureProvider<FavoritesRepository>((ref) async {
  return FavoritesRepository();
});

/// UF atualmente selecionada.
final selectedUfProvider = StateProvider<String>((ref) => 'sp');

/// Cargo atualmente selecionado.
final selectedCargoProvider = StateProvider<String>((ref) => 'governador');

/// Stream de snapshots vindos do WS.
final liveSnapshotProvider = StreamProvider<Snapshot>((ref) {
  final socketAsync = ref.watch(electionSocketProvider);
  return socketAsync.when(
    data: (socket) {
      final uf = ref.watch(selectedUfProvider);
      final cargo = ref.watch(selectedCargoProvider);
      socket.connect(uf, cargo);
      return socket.stream;
    },
    loading: () => Stream.empty(),
    error: (_, __) => Stream.error('socket nao pronto'),
  );
});

/// Indica se o socket esta conectado.
final connectionStatusProvider = StateProvider<bool>((ref) => false);

/// Historico (REST) - atualiza quando muda (uf, cargo).
final historicoProvider = FutureProvider<List<HistoricoPoint>>((ref) async {
  final apiAsync = ref.watch(apiClientProvider);
  return apiAsync.when(
    data: (api) async {
      final uf = ref.watch(selectedUfProvider);
      final cargo = ref.watch(selectedCargoProvider);
      try {
        return await api.getHistorico(uf, cargo, ultimas: 30);
      } catch (_) {
        return <HistoricoPoint>[];
      }
    },
    loading: () async => <HistoricoPoint>[],
    error: (_, __) async => <HistoricoPoint>[],
  );
});

/// Lista de favoritos.
final favoritosProvider = FutureProvider<List<Favorito>>((ref) async {
  final repoAsync = ref.watch(favoritesRepositoryProvider);
  return repoAsync.when(
    data: (repo) async => repo.listar(),
    loading: () async => <Favorito>[],
    error: (_, __) async => <Favorito>[],
  );
});

/// Controller para favoritar/desfavoritar.
class FavoritesController extends StateNotifier<AsyncValue<void>> {
  final Ref _ref;
  FavoritesController(this._ref) : super(const AsyncValue.data(null));

  Future<void> toggle(String uf, String cargo, Snapshot? snap) async {
    state = const AsyncValue.loading();
    try {
      final repoAsync = _ref.read(favoritesRepositoryProvider);
      final repo = repoAsync.value;
      if (repo == null) return;
      final existing = await repo.buscar(uf, cargo);
      if (existing == null) {
        await repo.favoritar(uf, cargo, snap);
      } else {
        await repo.remover(uf, cargo);
      }
      _ref.invalidate(favoritosProvider);
      state = const AsyncValue.data(null);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
}

final favoritesControllerProvider =
    StateNotifierProvider<FavoritesController, AsyncValue<void>>((ref) {
  return FavoritesController(ref);
});
