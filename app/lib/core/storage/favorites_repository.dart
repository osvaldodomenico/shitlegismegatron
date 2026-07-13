import 'package:path_provider/path_provider.dart';
import 'package:sqflite_common/sqflite.dart';
import 'package:sqflite_common_ffi_web/sqflite_ffi_web.dart';

import '../models/candidato.dart';

class Favorito {
  final String uf;
  final String cargo;
  final Snapshot? lastSnapshot;
  final DateTime lastSeenAt;

  const Favorito({
    required this.uf,
    required this.cargo,
    required this.lastSnapshot,
    required this.lastSeenAt,
  });
}

/// Repositório de favoritos persistido em IndexedDB (sqflite_common_ffi_web).
class FavoritesRepository {
  static const _dbName = 'megatron_favorites';
  static const _table = 'favorites';

  Database? _db;

  Future<Database> _open() async {
    if (_db != null) return _db!;
    databaseFactory = databaseFactoryFfiWeb;
    final dir = await getApplicationDocumentsDirectory();
    final path = '${dir.path}/$_dbName.db';
    _db = await databaseFactory.openDatabase(
      path,
      options: OpenDatabaseOptions(
        version: 1,
        onCreate: (db, version) async {
          await db.execute('''
            CREATE TABLE $_table (
              uf TEXT NOT NULL,
              cargo TEXT NOT NULL,
              last_snapshot TEXT,
              last_seen_at INTEGER NOT NULL,
              PRIMARY KEY (uf, cargo)
            )
          ''');
        },
      ),
    );
    return _db!;
  }

  Future<List<Favorito>> listar() async {
    final db = await _open();
    final rows = await db.query(_table, orderBy: 'last_seen_at DESC');
    return rows.map(_fromRow).toList();
  }

  Future<void> favoritar(String uf, String cargo, Snapshot? snap) async {
    final db = await _open();
    await db.insert(
      _table,
      {
        'uf': uf,
        'cargo': cargo,
        'last_snapshot': snap != null ? _encodeSnapshot(snap) : null,
        'last_seen_at': DateTime.now().millisecondsSinceEpoch,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<void> atualizarSnapshot(String uf, String cargo, Snapshot snap) async {
    final db = await _open();
    await db.update(
      _table,
      {
        'last_snapshot': _encodeSnapshot(snap),
        'last_seen_at': DateTime.now().millisecondsSinceEpoch,
      },
      where: 'uf = ? AND cargo = ?',
      whereArgs: [uf, cargo],
    );
  }

  Future<void> remover(String uf, String cargo) async {
    final db = await _open();
    await db.delete(_table, where: 'uf = ? AND cargo = ?', whereArgs: [uf, cargo]);
  }

  Future<Favorito?> buscar(String uf, String cargo) async {
    final db = await _open();
    final rows = await db.query(
      _table,
      where: 'uf = ? AND cargo = ?',
      whereArgs: [uf, cargo],
      limit: 1,
    );
    if (rows.isEmpty) return null;
    return _fromRow(rows.first);
  }

  Favorito _fromRow(Map<String, Object?> r) {
    final snapJson = r['last_snapshot'] as String?;
    return Favorito(
      uf: r['uf'] as String,
      cargo: r['cargo'] as String,
      lastSnapshot: snapJson != null ? _decodeSnapshot(snapJson) : null,
      lastSeenAt: DateTime.fromMillisecondsSinceEpoch(r['last_seen_at'] as int),
    );
  }

  String _encodeSnapshot(Snapshot s) {
    // Simplificado: serializa só pst + hor + nomes dos top candidatos.
    final payload = {
      'pst': s.pst,
      'hor': s.hor,
      'cands': s.todosCandidatos
          .take(10)
          .map((c) => {'nm': c.nm, 'sg': c.sg, 'vap': c.vap, 'pvap': c.pvap, 'e': c.e})
          .toList(),
    };
    return payload.toString();
  }

  Snapshot? _decodeSnapshot(String _) => null; // placeholder; re-hidratar via API
}