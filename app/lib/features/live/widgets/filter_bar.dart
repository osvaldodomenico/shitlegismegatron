import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants/cargos.dart';
import '../../../core/constants/ufs.dart';
import '../../../core/theme/app_theme.dart';
import '../live_provider.dart';

/// Barra de filtros (UF + Cargo) sticky no topo.
class FilterBar extends ConsumerWidget {
  const FilterBar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final uf = ref.watch(selectedUfProvider);
    final cargo = ref.watch(selectedCargoProvider);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      color: AppColors.bg,
      child: Row(
        children: [
          Expanded(
            child: _Dropdown<String>(
              label: 'UF',
              value: uf,
              items: Ufs.all,
              labelOf: Ufs.label,
              onChanged: (v) => ref.read(selectedUfProvider.notifier).state = v,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: _Dropdown<String>(
              label: 'Cargo',
              value: cargo,
              items: Cargos.all,
              labelOf: Cargos.label,
              onChanged: (v) => ref.read(selectedCargoProvider.notifier).state = v,
            ),
          ),
        ],
      ),
    );
  }
}

class _Dropdown<T> extends StatelessWidget {
  final String label;
  final T value;
  final List<T> items;
  final String Function(T) labelOf;
  final ValueChanged<T> onChanged;

  const _Dropdown({
    required this.label,
    required this.value,
    required this.items,
    required this.labelOf,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<T>(
      initialValue: value,
      isExpanded: true,
      decoration: InputDecoration(
        labelText: label,
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      ),
      dropdownColor: AppColors.surface,
      items: items
          .map((i) => DropdownMenuItem<T>(
                value: i,
                child: Text(labelOf(i), style: const TextStyle(fontSize: 14)),
              ))
          .toList(),
      onChanged: (v) {
        if (v != null) onChanged(v);
      },
    );
  }
}