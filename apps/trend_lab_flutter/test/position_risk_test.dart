import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trend_lab/api.dart';
import 'package:trend_lab/position_risk.dart';

class RiskTestApi extends TradingApi {
  final Map<String, dynamic> fixture = jsonDecode(
    File('test/fixtures/position-risk.json').readAsStringSync(),
  ) as Map<String, dynamic>;
  final List<String> writes = [];
  RiskTestApi() : super('http://test', '');
  @override
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
  }) async {
    if (method != 'GET') writes.add(path);
    if (path.endsWith('/simulate')) {
      return {
        'before': fixture['cycles'][0],
        'after': {
          ...fixture['cycles'][0],
          'e': 2,
          'cr': 1,
          'protectedR': -1,
          'giveback': 3000000,
          'givebackPercent': 150,
          'warnings': ['계획상 보호 수익 부족'],
        },
        'reduced': null,
      };
    }
    if (path.endsWith('/rules')) {
      fixture['rules'] = body;
      return body;
    }
    if (path.endsWith('/action')) return fixture['cycles'][0];
    return fixture;
  }
}

void main() {
  testWidgets(
    'account selector shows separate capital plans and renders the real account response on a phone',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      final api = RiskTestApi();
      api.fixture.addAll(
        jsonDecode(
          File('test/fixtures/capital-accounts.json').readAsStringSync(),
        ) as Map<String, dynamic>,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: PositionRiskWorkspace(api: api, legacyCount: 216),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('1E 3,250,000원 · 1R 162,500원'), findsOneWidget);
      await tester.tap(find.text('일반'));
      await tester.pumpAndSettle();
      expect(find.text('1E 2,250,000원 · 1R 112,500원'), findsOneWidget);
      await tester.tap(find.text('DC 퇴직연금'));
      await tester.pumpAndSettle();
      expect(find.text('1E 17,500,000원 · 1R 875,000원'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
      api.dispose();
    },
  );
  testWidgets(
    'RCE portfolio fits phone and desktop and shows zero CR giveback separately',
    (tester) async {
      final api = RiskTestApi();
      for (final width in [390.0, 1400.0]) {
        tester.view.physicalSize = Size(width, 1000);
        tester.view.devicePixelRatio = 1;
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: SingleChildScrollView(
                child: PositionRiskWorkspace(
                  key: ValueKey(width),
                  api: api,
                  legacyCount: 213,
                ),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('0.00 CR'), findsWidgets);
        expect(find.text('2.00R'), findsWidgets);
        expect(find.text('고정 1R 기준'), findsOneWidget);
        expect(find.textContaining('CR=0이어도'), findsOneWidget);
        expect(find.textContaining('미분류 과거 거래 213건'), findsOneWidget);
        expect(tester.takeException(), isNull);
        await tester.ensureVisible(find.text('위험 규칙'));
        await tester.tap(find.text('위험 규칙'));
        await tester.pumpAndSettle();
        expect(find.text('최대 E'), findsOneWidget);
        expect(tester.takeException(), isNull);
        await tester.tap(find.text('취소'));
        await tester.pumpAndSettle();
      }
      await tester.pumpWidget(const SizedBox());
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
      api.dispose();
    },
  );
  testWidgets('simulator responds to edits and never commits a real order', (
    tester,
  ) async {
    final api = RiskTestApi();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: PyramidSimulator(
              api: api,
              cycle: Map<String, dynamic>.from(api.fixture['cycles'][0]),
            ),
          ),
        ),
      ),
    );
    final inputs = find.byType(TextField);
    await tester.enterText(inputs.at(0), '120000');
    await tester.enterText(inputs.at(1), '100');
    await tester.enterText(inputs.at(2), '110000');
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();
    expect(find.textContaining('손절 시 최종 -1.00R'), findsOneWidget);
    expect(find.textContaining('E 1.00 → 2.00'), findsOneWidget);
    expect(api.writes, ['/api/positions/ui-test/simulate']);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    api.dispose();
  });
}
