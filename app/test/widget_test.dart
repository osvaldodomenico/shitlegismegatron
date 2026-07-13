import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:megatron_app/core/constants/cargos.dart';
import 'package:megatron_app/core/constants/ufs.dart';
import 'package:megatron_app/core/models/candidato.dart';
import 'package:megatron_app/core/theme/app_theme.dart';

void main() {
  test('AppTheme.dark usa cores MEGATRON', () {
    final theme = AppTheme.dark;
    expect(theme.scaffoldBackgroundColor, const Color(0xFF0a0a1a));
    expect(theme.colorScheme.primary, const Color(0xFF1565C0));
    expect(theme.brightness, Brightness.dark);
  });

  test('Ufs contem estados principais', () {
    expect(Ufs.all, containsAll(['sp', 'rj', 'mg', 'br']));
    expect(Ufs.label('sp'), 'São Paulo');
    expect(Ufs.label('br'), 'Brasil');
  });

  test('Cargos tem labels em portugues', () {
    expect(Cargos.all, containsAll(['presidente', 'governador', 'dep_federal']));
    expect(Cargos.label('dep_federal'), 'Deputado Federal');
    expect(Cargos.label('presidente'), 'Presidente');
  });

  test('Snapshot.fromJson parseia payload valido', () {
    final json = {
      'pst': '78.42%',
      'hor': '21:34:12',
      'e': [
        {
          'cd': 'sp',
          'nm': 'SÃO PAULO',
          'c': [
            {'sqcand': '1', 'nm': 'JOÃO SILVA', 'sg': 'PT', 'n': '13', 'vap': '12345', 'pvap': '45.32%', 'e': 'Eleito'},
          ],
        },
      ],
    };
    final snap = Snapshot.fromJson(json);
    expect(snap.pst, '78.42%');
    expect(snap.pstPct, 78.42);
    expect(snap.hor, '21:34:12');
    expect(snap.unidades, hasLength(1));
    expect(snap.unidades.first.cd, 'sp');
    expect(snap.todosCandidatos, hasLength(1));
    expect(snap.todosCandidatos.first.nm, 'JOÃO SILVA');
    expect(snap.todosCandidatos.first.votos, 12345);
  });

  test('Candidato.iniciais gera iniciais corretas', () {
    const c = Candidato(sqcand: '1', nm: 'JOÃO DA SILVA', sg: 'PT', n: '13', vap: '0', pvap: '0%', e: '');
    expect(c.iniciais, 'JS');
    const c2 = Candidato(sqcand: '1', nm: 'MARIA', sg: 'PT', n: '13', vap: '0', pvap: '0%', e: '');
    expect(c2.iniciais, 'M');
  });
}
