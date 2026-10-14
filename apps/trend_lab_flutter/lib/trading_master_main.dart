import 'package:flutter/material.dart';

import 'auth_gate.dart';
import 'trading_master.dart';

void main() => runApp(const TradingMasterApp());

class TradingMasterApp extends StatelessWidget {
  const TradingMasterApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Trading Master · 나의 매매를 이해하다',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      fontFamily: 'DMSans',
      fontFamilyFallback: const ['NotoSansKR'],
      brightness: Brightness.dark,
      scaffoldBackgroundColor: const Color(0xff101623),
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xff86dfb4),
        brightness: Brightness.dark,
        surface: const Color(0xff171f2d),
      ),
      textTheme: ThemeData.dark().textTheme.apply(
        fontFamily: 'DMSans',
        bodyColor: const Color(0xffe7ebf2),
        displayColor: const Color(0xffe7ebf2),
      ),
      cardTheme: const CardThemeData(
        color: Color(0xff171f2d),
        elevation: 0,
        margin: EdgeInsets.zero,
      ),
      dividerColor: const Color(0xff293242),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: const Color(0xff86dfb4),
          foregroundColor: const Color(0xff102720),
          minimumSize: const Size(0, 44),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(7)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: const Color(0xffa7b5ca),
          side: const BorderSide(color: Color(0xff344152)),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
        ),
      ),
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
        filled: true,
        fillColor: Color(0xff111a27),
        isDense: true,
      ),
      useMaterial3: true,
    ),
    home: const bool.fromEnvironment('MASTER_PREVIEW')
        ? const TradingMasterScreen(preview: true)
        : AuthGate(
            child: (api) => TradingMasterScreen(
              key: ValueKey(api?.baseUrl ?? 'local'),
              api: api,
            ),
          ),
  );
}
