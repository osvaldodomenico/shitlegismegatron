import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../config.dart';
import '../models/candidato.dart';

/// Conexão WebSocket com reconexão automática (backoff igual ao React).
class ElectionSocket {
  static const List<int> _backoffDelays = [2000, 4000, 8000, 16000, 30000];

  WebSocketChannel? _channel;
  StreamController<Snapshot>? _controller;
  StreamSubscription? _sub;
  Timer? _reconnectTimer;
  String? _currentRoom;
  bool _disposed = false;
  int _retryAttempt = 0;

  /// Stream de snapshots. Subscribers recebem a cada mensagem WS.
  Stream<Snapshot> get stream => (_controller ??= StreamController<Snapshot>.broadcast()).stream;

  /// Conecta à sala (uf:cargo). Trocar de sala reconecta.
  void connect(String uf, String cargo) {
    if (_disposed) return;
    final room = '$uf:$cargo';
    if (_currentRoom == room && _channel != null) return;

    _currentRoom = room;
    _retryAttempt = 0;
    _open(room);
  }

  void _open(String room) {
    if (_disposed) return;
    _closeChannel();

    final uri = Uri.parse('${AppConfig.wsBaseUrl}/ws/$room');
    try {
      _channel = WebSocketChannel.connect(uri);
      _retryAttempt = 0;
      _sub = _channel!.stream.listen(
        (data) {
          try {
            final map = Map<String, dynamic>.from(jsonDecode(data.toString()) as Map);
            final snap = Snapshot.fromJson(map);
            _controller?.add(snap);
          } catch (_) {
            // ignora payload inválido
          }
        },
        onError: (_) => _scheduleReconnect(),
        onDone: _scheduleReconnect,
        cancelOnError: true,
      );
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_disposed) return;
    _closeChannel();
    final idx = _retryAttempt.clamp(0, _backoffDelays.length - 1);
    final delay = Duration(milliseconds: _backoffDelays[idx]);
    _retryAttempt += 1;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, () {
      final room = _currentRoom;
      if (room != null) _open(room);
    });
  }

  void _closeChannel() {
    _sub?.cancel();
    _sub = null;
    try {
      _channel?.sink.close();
    } catch (_) {}
    _channel = null;
  }

  /// Indica se está conectado (canal aberto).
  bool get isConnected => _channel != null;

  Future<void> dispose() async {
    _disposed = true;
    _reconnectTimer?.cancel();
    _closeChannel();
    await _controller?.close();
    _controller = null;
  }
}