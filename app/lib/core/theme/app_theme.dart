import 'package:flutter/material.dart';

/// Cores idênticas ao tailwind.config.js do frontend React.
class AppColors {
  static const bg = Color(0xFF0a0a1a);
  static const surface = Color(0xFF12122a);
  static const primary = Color(0xFF1565C0);
  static const success = Color(0xFF2E7D32);
  static const muted = Color(0xFFE8EAF6);
  static const textDim = Color(0xFF9CA3AF);
  static const border = Color(0xFF1F2937);
  static const warning = Color(0xFFE65100);
}

/// Tema escuro com paleta MEGATRON.
class AppTheme {
  static ThemeData get dark => ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: AppColors.bg,
        colorScheme: const ColorScheme.dark(
          surface: AppColors.surface,
          primary: AppColors.primary,
          secondary: AppColors.success,
          onSurface: AppColors.muted,
          onPrimary: Colors.white,
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: AppColors.bg,
          foregroundColor: AppColors.muted,
          elevation: 0,
          centerTitle: false,
        ),
        cardTheme: const CardThemeData(
          color: AppColors.surface,
          elevation: 0,
        ),
        dividerTheme: const DividerThemeData(color: AppColors.border, thickness: 1),
        textTheme: const TextTheme(
          bodyLarge: TextStyle(color: AppColors.muted),
          bodyMedium: TextStyle(color: AppColors.muted),
          bodySmall: TextStyle(color: AppColors.textDim),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: AppColors.surface,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: const BorderSide(color: AppColors.border),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: const BorderSide(color: AppColors.primary),
          ),
        ),
      );
}
