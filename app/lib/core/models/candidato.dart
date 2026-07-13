/// Modelo do payload TSE (dados-simplificados).
class Candidato {
  final String sqcand;
  final String nm;
  final String sg;
  final String n;
  final String vap; // votos (string int)
  final String pvap; // percentual "XX.XX%"
  final String e; // "Eleito" | "Não eleito" | "2º turno"

  const Candidato({
    required this.sqcand,
    required this.nm,
    required this.sg,
    required this.n,
    required this.vap,
    required this.pvap,
    required this.e,
  });

  factory Candidato.fromJson(Map<String, dynamic> j) => Candidato(
        sqcand: j['sqcand']?.toString() ?? '',
        nm: j['nm']?.toString() ?? '',
        sg: j['sg']?.toString() ?? '',
        n: j['n']?.toString() ?? '',
        vap: j['vap']?.toString() ?? '0',
        pvap: j['pvap']?.toString() ?? '0%',
        e: j['e']?.toString() ?? '',
      );

  int get votos => int.tryParse(vap) ?? 0;
  double get pct {
    final s = pvap.replaceAll('%', '').replaceAll(',', '.');
    return double.tryParse(s) ?? 0.0;
  }

  String get iniciais {
    final parts = nm.trim().split(' ').where((s) => s.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
    return (parts.first.substring(0, 1) + parts.last.substring(0, 1)).toUpperCase();
  }
}

class UnidadeFederativa {
  final String cd;
  final String nm;
  final List<Candidato> candidatos;
  const UnidadeFederativa({
    required this.cd,
    required this.nm,
    required this.candidatos,
  });

  factory UnidadeFederativa.fromJson(Map<String, dynamic> j) => UnidadeFederativa(
        cd: j['cd']?.toString() ?? '',
        nm: j['nm']?.toString() ?? '',
        candidatos: (j['c'] as List? ?? [])
            .map((e) => Candidato.fromJson(Map<String, dynamic>.from(e)))
            .toList(),
      );
}

/// Snapshot completo de apuração por (uf, cargo).
class Snapshot {
  final String pst; // "78.42%"
  final String hor; // "21:34:12"
  final List<UnidadeFederativa> unidades;

  const Snapshot({
    required this.pst,
    required this.hor,
    required this.unidades,
  });

  factory Snapshot.fromJson(Map<String, dynamic> j) => Snapshot(
        pst: j['pst']?.toString() ?? '0%',
        hor: j['hor']?.toString() ?? '',
        unidades: (j['e'] as List? ?? [])
            .map((e) => UnidadeFederativa.fromJson(Map<String, dynamic>.from(e)))
            .toList(),
      );

  /// % apurada como double (0-100).
  double get pstPct {
    final s = pst.replaceAll('%', '').replaceAll(',', '.');
    return double.tryParse(s) ?? 0.0;
  }

  /// Lista plana de candidatos (achatada se houver várias UFs).
  List<Candidato> get todosCandidatos =>
      unidades.expand((u) => u.candidatos).toList();
}
