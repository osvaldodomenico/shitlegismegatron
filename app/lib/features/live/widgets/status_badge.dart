import 'package:flutter/material.dart';

/// Badge de status: 🟢 Ao Vivo / 🟡 Simulando / 🔴 Offline.
class StatusBadge extends StatelessWidget {
  final bool connected;
  final bool simulando;
  const StatusBadge({super.key, required this.connected, this.simulando = false});

  @override
  Widget build(BuildContext context) {
    final Color bg;
    final Color fg;
    final String text;
    final String emoji;
    if (simulando) {
      bg = const Color(0xFF713F12);
      fg = const Color(0xFFFCD34D);
      text = 'Simulando';
      emoji = '🟡';
    } else if (connected) {
      bg = const Color(0xFF14532D);
      fg = const Color(0xFF86EFAC);
      text = 'Ao Vivo';
      emoji = '🟢';
    } else {
      bg = const Color(0xFF7F1D1D);
      fg = const Color(0xFFFCA5A5);
      text = 'Offline';
      emoji = '🔴';
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
      child: Text('$emoji $text',
          style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w500)),
    );
  }
}