import 'package:go_router/go_router.dart';

import '../features/detail/municipio_screen.dart';
import '../features/favorites/favorites_screen.dart';
import '../features/live/live_screen.dart';

GoRouter buildRouter() => GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(path: '/', builder: (_, __) => const LiveScreen()),
        GoRoute(path: '/favoritos', builder: (_, __) => const FavoritesScreen()),
        GoRoute(
          path: '/municipio/:uf/:cargo/:mun',
          builder: (_, s) => MunicipioScreen(
            uf: s.pathParameters['uf']!,
            cargo: s.pathParameters['cargo']!,
            municipio: s.pathParameters['mun']!,
          ),
        ),
      ],
    );