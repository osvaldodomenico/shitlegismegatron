import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config.dart';
import '../models/historico_point.dart';

/// Erro de API (404 quando /resultados não tem dado ainda).
class ApiException implements Exception {
  final int statusCode;
  final String message;
  ApiException(this.statusCode, this.message);
  @override
  String toString() => 'ApiException($statusCode): $message';
}

/// Cliente HTTP para os endpoints REST da API MEGATRON.
class ApiClient {
  final http.Client _http;
  final String _base;

  ApiClient({http.Client? client, String? baseUrl})
      : _http = client ?? http.Client(),
        _base = baseUrl ?? AppConfig.apiBaseUrl;

  String get baseUrl => _base;

  /// GET /resultados/{uf}/{cargo} → mapa JSON (último snapshot).
  /// Lança [ApiException] 404 se não há dados ainda.
  Future<Map<String, dynamic>> getResultado(String uf, String cargo) async {
    final r = await _http.get(Uri.parse('$_base/resultados/$uf/$cargo'));
    if (r.statusCode == 404) {
      throw ApiException(404, 'Sem dados ainda');
    }
    if (r.statusCode >= 400) {
      throw ApiException(r.statusCode, r.body);
    }
    return Map<String, dynamic>.from(jsonDecode(r.body) as Map);
  }

  /// GET /historico/{uf}/{cargo}?ultimas=N → lista (vazia se sem DB).
  Future<List<HistoricoPoint>> getHistorico(String uf, String cargo, {int ultimas = 30}) async {
    final r = await _http.get(Uri.parse('$_base/historico/$uf/$cargo?ultimas=$ultimas'));
    if (r.statusCode >= 400) {
      throw ApiException(r.statusCode, r.body);
    }
    final list = jsonDecode(r.body) as List;
    return list
        .map((e) => HistoricoPoint.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  /// GET /health → true se 200.
  Future<bool> health() async {
    try {
      final r = await _http.get(Uri.parse('$_base/health'));
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  void dispose() => _http.close();
}