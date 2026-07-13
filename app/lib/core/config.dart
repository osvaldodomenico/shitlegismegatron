/// Configuração de endpoints da API MEGATRON.
///
/// Em dev (VPS 74.208.68.101), usamos SSH port-forward:
///   ssh -L 8000:127.0.0.1:8000 root@74.208.68.101
/// e a URL fica localhost.
///
/// Em build de produção, passamos via --dart-define:
///   flutter build web --dart-define=API_BASE_URL=https://megatron.dominio
class AppConfig {
  /// HTTP base. Ex: http://localhost:8000
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  /// WebSocket base derivado da API. Ex: ws://localhost:8000
  static String get wsBaseUrl {
    final base = apiBaseUrl;
    if (base.startsWith('https://')) return 'wss://${base.substring(8)}';
    if (base.startsWith('http://')) return 'ws://${base.substring(7)}';
    return base;
  }
}
